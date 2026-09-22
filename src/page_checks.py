"""Per-page technical SEO and accessibility checks.

Pure functions only: no network, no Apify SDK, no global state. `check_page`
takes the URL, the HTTP status and the HTML string of one page and returns a
flat dictionary that goes straight into the Apify dataset.

Scope of this slice: everything that can be measured from the HTML source
alone. Colour contrast, rendered layout and anything that needs a browser are
deliberately out; a wrong answer there is worse than no answer.

No personal data is ever kept: only counts, tag text and the page URL.
"""

from __future__ import annotations

from typing import Iterable

from bs4 import BeautifulSoup

# Form controls that carry no user-visible label by design.
UNLABELLED_INPUT_TYPES = frozenset(
    {"hidden", "submit", "button", "reset", "image"}
)

# Google shows roughly 50-60 characters of a title; longer titles get cut.
TITLE_MIN_LENGTH = 15
TITLE_MAX_LENGTH = 60
META_DESCRIPTION_MAX_LENGTH = 160


def _text(node) -> str:
    return " ".join(node.get_text(" ", strip=True).split())


def _attr(node, name: str) -> str:
    value = node.get(name)
    if isinstance(value, (list, tuple)):
        value = " ".join(str(part) for part in value)
    return (value or "").strip() if isinstance(value, str) else ""


def _has_accessible_name(field, labelled_ids: set[str]) -> bool:
    """True when the control has some name a screen reader can announce."""
    if _attr(field, "aria-label") or _attr(field, "aria-labelledby"):
        return True
    if _attr(field, "title"):
        return True
    field_id = _attr(field, "id")
    if field_id and field_id in labelled_ids:
        return True
    # A control wrapped in its own <label> is labelled too.
    return field.find_parent("label") is not None


def _heading_order_broken(levels: list[int]) -> bool:
    """True when the document skips a heading level or does not start at h1."""
    if not levels:
        return False
    if levels[0] != 1:
        return True
    previous = levels[0]
    for level in levels[1:]:
        if level > previous + 1:
            return True
        previous = level
    return False


def check_page(url: str, status: int | None, html: str | None) -> dict:
    """Audit one page. Returns the dataset row for it.

    `status` may be None when the request failed; `html` may be None or empty
    when the response had no HTML body. In both cases the row is still
    returned, with an issue explaining why nothing could be checked.
    """
    row: dict = {
        "url": url,
        "status": status,
        "title": None,
        "titleLength": 0,
        "titleMissing": True,
        "metaDescription": None,
        "metaDescriptionMissing": True,
        "h1Count": 0,
        "headingOrderBroken": False,
        "imagesWithoutAlt": 0,
        "formFieldsWithoutLabel": 0,
        "canonical": None,
        "canonicalMissing": True,
        "issues": [],
    }
    issues: list[str] = []

    if status is not None and status >= 400:
        issues.append(f"page returned HTTP {status}")

    if not html or not html.strip():
        issues.append("no HTML body to check")
        row["issues"] = issues
        row["issueCount"] = len(issues)
        return row

    soup = BeautifulSoup(html, "html.parser")

    # ------------------------------------------------------------------ title
    title_tag = soup.find("title")
    title = _text(title_tag) if title_tag is not None else ""
    row["title"] = title or None
    row["titleLength"] = len(title)
    row["titleMissing"] = not title
    if not title:
        issues.append("missing <title>")
    elif len(title) > TITLE_MAX_LENGTH:
        issues.append(f"title is {len(title)} characters, over {TITLE_MAX_LENGTH}")
    elif len(title) < TITLE_MIN_LENGTH:
        issues.append(f"title is only {len(title)} characters")

    # ------------------------------------------------------- meta description
    meta = None
    for candidate in soup.find_all("meta"):
        if _attr(candidate, "name").lower() == "description":
            meta = candidate
            break
    description = " ".join(_attr(meta, "content").split()) if meta is not None else ""
    row["metaDescription"] = description or None
    row["metaDescriptionMissing"] = not description
    if not description:
        issues.append("missing meta description")
    elif len(description) > META_DESCRIPTION_MAX_LENGTH:
        issues.append(
            f"meta description is {len(description)} characters, over "
            f"{META_DESCRIPTION_MAX_LENGTH}"
        )

    # --------------------------------------------------------------- headings
    headings = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
    levels = [int(tag.name[1]) for tag in headings]
    h1_count = levels.count(1)
    row["h1Count"] = h1_count
    if h1_count == 0:
        issues.append("no h1 on the page")
    elif h1_count > 1:
        issues.append(f"{h1_count} h1 headings, expected 1")
    order_broken = _heading_order_broken(levels)
    row["headingOrderBroken"] = order_broken
    if order_broken:
        issues.append("heading levels are out of order")

    # ----------------------------------------------------------------- images
    # An explicit alt="" marks a decorative image and is correct, so only a
    # missing alt attribute (or one with nothing but spaces in it) counts.
    images_without_alt = 0
    for image in soup.find_all("img"):
        alt = image.get("alt")
        if alt is None or (isinstance(alt, str) and alt != "" and not alt.strip()):
            images_without_alt += 1
    row["imagesWithoutAlt"] = images_without_alt
    if images_without_alt:
        issues.append(f"{images_without_alt} image(s) without alt text")

    # ------------------------------------------------------------ form fields
    labelled_ids = {
        _attr(label, "for") for label in soup.find_all("label") if _attr(label, "for")
    }
    fields_without_label = 0
    for field in soup.find_all(["input", "select", "textarea"]):
        if field.name == "input" and _attr(field, "type").lower() in UNLABELLED_INPUT_TYPES:
            continue
        if not _has_accessible_name(field, labelled_ids):
            fields_without_label += 1
    row["formFieldsWithoutLabel"] = fields_without_label
    if fields_without_label:
        issues.append(f"{fields_without_label} form field(s) without a label")

    # -------------------------------------------------------------- canonical
    canonical = ""
    for link in soup.find_all("link"):
        rel = link.get("rel") or []
        rel_values = [str(part).lower() for part in rel] if isinstance(rel, (list, tuple)) \
            else [str(rel).lower()]
        if "canonical" in rel_values:
            canonical = _attr(link, "href")
            break
    row["canonical"] = canonical or None
    row["canonicalMissing"] = not canonical
    if not canonical:
        issues.append("missing canonical link")

    row["issues"] = issues
    row["issueCount"] = len(issues)
    return row


def summarize(rows: Iterable[dict]) -> dict:
    """Totals for a whole run, built from the rows `check_page` returned."""
    rows = list(rows)
    pages = len(rows)
    counted = {
        "pagesAudited": pages,
        "pagesWithIssues": sum(1 for row in rows if row["issues"]),
        "titleMissing": sum(1 for row in rows if row["titleMissing"]),
        "metaDescriptionMissing": sum(
            1 for row in rows if row["metaDescriptionMissing"]
        ),
        "pagesWithoutH1": sum(1 for row in rows if row["h1Count"] == 0),
        "pagesWithMultipleH1": sum(1 for row in rows if row["h1Count"] > 1),
        "pagesWithBrokenHeadingOrder": sum(
            1 for row in rows if row["headingOrderBroken"]
        ),
        "imagesWithoutAlt": sum(row["imagesWithoutAlt"] for row in rows),
        "formFieldsWithoutLabel": sum(row["formFieldsWithoutLabel"] for row in rows),
        "canonicalMissing": sum(1 for row in rows if row["canonicalMissing"]),
        "totalIssues": sum(len(row["issues"]) for row in rows),
    }
    worst = sorted(rows, key=lambda row: -len(row["issues"]))[:10]
    counted["worstPages"] = [
        {"url": row["url"], "issueCount": len(row["issues"]), "issues": row["issues"]}
        for row in worst
        if row["issues"]
    ]
    return counted


__all__ = ("check_page", "summarize")
