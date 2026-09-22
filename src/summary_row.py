"""The one dataset row every successful run writes, defects or none.

Why this file exists
--------------------
This Actor audits pages. A site whose pages are clean is not the exception, it
is the outcome the buyer is paying to reach, and until now such a run wrote
nothing at all: `src/main.py` pushed the page rows inside an `if rows:` gate, so
a run that found no page to audit finished SUCCEEDED with an empty dataset. An
empty dataset is indistinguishable from an Actor that crashed, and the buyer was
charged per page all the same. The summary row says, inside the dataset itself,
how many pages were crawled, how many were skipped by robots.txt and how many
defects were found in each category, including when that number is zero.

Nothing here charges anything. The module has no Apify import on purpose: it is
pure data, it is called after the work is done, and the two events this Actor
charges (`page-audited` per page fetched, `site-report` once per run with page
rows) are decided in `src/main.py` and were not touched. The same design is
already running in `actor-links-quebrados` (`build_summary_row`/`dataset_rows`)
and in `actor-vigia-feeds` (`summary_row.py`).
"""

from __future__ import annotations

from datetime import datetime, timezone

# Every row carries this field, so a reader can tell a page row from the run
# summary with one comparison and drop the summary if it only wants pages.
ROW_TYPE_FIELD = "rowType"
PAGE_ROW_TYPE = "page"
SUMMARY_ROW_TYPE = "summary"

# Fields that exist only on the summary row. Declared here so the schema test
# can check the dataset schema against the code instead of against a list typed
# by hand twice.
SUMMARY_ONLY_FIELDS = (
    "startUrl",
    "finishedAt",
    "pagesCrawled",
    "pagesAudited",
    "pagesSkippedByRobots",
    "pagesWithIssues",
    "totalIssues",
    "durationSeconds",
    "chargedEvents",
    "chargeLimitReached",
    "chargeFailures",
    "message",
)

# The defect categories the summary counts, in the order the message lists
# them: the key in the report, and the English words that follow the number.
DEFECT_CATEGORIES = (
    ("titleMissing", "page(s) with no <title>"),
    ("metaDescriptionMissing", "page(s) with no meta description"),
    ("pagesWithoutH1", "page(s) with no h1"),
    ("pagesWithMultipleH1", "page(s) with more than one h1"),
    ("pagesWithBrokenHeadingOrder", "page(s) with headings out of order"),
    ("imagesWithoutAlt", "image(s) without alt text"),
    ("formFieldsWithoutLabel", "form field(s) without a label"),
    ("canonicalMissing", "page(s) with no canonical link"),
)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def tag_pages(rows: list[dict]) -> list[dict]:
    """Stamp `rowType` on the page rows, without touching their content.

    A copy is returned: `check_page` builds the row with exactly the fields the
    dataset schema declares, so the row type is added here, at the door of the
    dataset, and never inside the checker.
    """
    return [{ROW_TYPE_FIELD: PAGE_ROW_TYPE, **row} for row in rows]


def defect_breakdown(report: dict) -> list[str]:
    """One "<count> <what>" phrase per category that has at least one defect."""
    return [
        f"{report.get(key, 0)} {words}"
        for key, words in DEFECT_CATEGORIES
        if report.get(key, 0)
    ]


def summary_message(report: dict) -> str:
    """One plain sentence with the counts. No promise, no advice, no guess."""
    crawled = report.get("pagesCrawled", 0)
    audited = report.get("pagesAudited", 0)
    by_robots = report.get("pagesSkippedByRobots", 0)
    total = report.get("totalIssues", 0)
    with_issues = report.get("pagesWithIssues", 0)

    if audited == 0:
        if by_robots and not crawled:
            text = (
                f"No page could be audited: all {by_robots} URL(s) found are "
                "disallowed by the site's robots.txt for this Actor's user "
                "agent, so this run says nothing about their HTML."
            )
        else:
            text = (
                f"No page could be audited: {crawled} page(s) were crawled and "
                "none of them answered with an HTML body, so no check was run."
            )
    elif total == 0:
        text = (
            f"No defects found: {audited} page(s) were crawled and checked, and "
            "every one of them passed all eight checks (title, meta "
            "description, h1, heading order, image alt text, form labels and "
            "canonical link)."
        )
    else:
        text = (
            f"{total} defect(s) found on {with_issues} of {audited} page(s) "
            "audited: " + ", ".join(defect_breakdown(report)) + "."
        )

    # Always stated, zero included: "skipped by robots.txt" is the one number
    # that explains a page the buyer expected to see and did not.
    if by_robots:
        text += (
            f" {by_robots} URL(s) were skipped because the site's robots.txt "
            "disallows them for this Actor's user agent."
        )
    else:
        text += " 0 page(s) were skipped by the site's robots.txt."

    if report.get("chargeLimitReached"):
        text += (
            " The run stopped early because it reached its pay-per-event charge "
            "limit, so part of the site was not audited."
        )
    return text


def build_summary_row(report: dict) -> dict:
    """The summary row, built from the same numbers the SUMMARY record holds."""
    row = {
        ROW_TYPE_FIELD: SUMMARY_ROW_TYPE,
        "startUrl": report.get("startUrl"),
        "finishedAt": report.get("finishedAt") or _now(),
        "pagesCrawled": report.get("pagesCrawled", 0),
        "pagesAudited": report.get("pagesAudited", 0),
        "pagesSkippedByRobots": report.get("pagesSkippedByRobots", 0),
        "pagesWithIssues": report.get("pagesWithIssues", 0),
        "totalIssues": report.get("totalIssues", 0),
        "durationSeconds": report.get("durationSeconds", 0),
        "chargedEvents": report.get("chargedEvents", 0),
        "chargeLimitReached": bool(report.get("chargeLimitReached", False)),
        "chargeFailures": report.get("chargeFailures", 0),
        "message": summary_message(report),
    }
    # The per-category counts share their names with the page-row fields they
    # add up (titleMissing, imagesWithoutAlt, ...), so they are declared once,
    # in DEFECT_CATEGORIES, and copied here as plain integers.
    for key, _words in DEFECT_CATEGORIES:
        row[key] = report.get(key, 0)
    return row


def build_dataset_rows(page_rows: list[dict], report: dict) -> list[dict]:
    """Everything a run writes to the dataset: pages first, summary last.

    Summary last, on purpose: a reader that takes the first N items still gets
    page rows, and the row order of an existing integration does not change.
    The only run where the summary is item number one is the run with no page
    rows, which is exactly the run that used to return an empty dataset.
    """
    return [*tag_pages(page_rows), build_summary_row(report)]


__all__ = (
    "ROW_TYPE_FIELD",
    "PAGE_ROW_TYPE",
    "SUMMARY_ROW_TYPE",
    "SUMMARY_ONLY_FIELDS",
    "DEFECT_CATEGORIES",
    "build_dataset_rows",
    "build_summary_row",
    "defect_breakdown",
    "summary_message",
    "tag_pages",
)
