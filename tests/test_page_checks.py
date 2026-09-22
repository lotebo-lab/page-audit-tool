"""Offline tests for `check_page`. Literal HTML only, no network, no Apify.

Written as plain pytest functions. pytest is not installed in the lab sandbox
and `pip install` has no network there, so the file also runs on its own:

    .venv/bin/python negocios/actor-auditoria-paginas/tests/test_page_checks.py

The stub below only covers `pytest.mark.parametrize`; when the real pytest is
available it is imported instead and nothing here changes.
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    import pytest
except ModuleNotFoundError:  # pytest missing: run the same tests standalone

    class _Mark:
        @staticmethod
        def parametrize(argnames, argvalues):
            names = [name.strip() for name in argnames.split(",")]

            def decorate(func):
                func._params = (names, argvalues)
                return func

            return decorate

    class _PytestStub:
        mark = _Mark()

    pytest = _PytestStub()  # type: ignore[assignment]

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.page_checks import check_page, summarize  # noqa: E402
from src.summary_row import (  # noqa: E402
    PAGE_ROW_TYPE,
    ROW_TYPE_FIELD,
    SUMMARY_ROW_TYPE,
    build_dataset_rows,
    build_summary_row,
)

URL = "https://example.com/page"

CLEAN_PAGE = """
<!doctype html>
<html lang="en">
  <head>
    <title>How to audit a website for broken links</title>
    <meta name="description" content="A short, honest description of what this
      page is about, written for a person reading a search result page.">
    <link rel="canonical" href="https://example.com/page">
  </head>
  <body>
    <h1>Audit a website</h1>
    <h2>Why</h2>
    <p>Text.</p>
    <h3>Details</h3>
    <img src="/a.png" alt="A screenshot of the report">
    <img src="/spacer.gif" alt="">
    <form>
      <label for="email">E-mail</label>
      <input type="email" id="email" name="email">
      <label>Name <input type="text" name="name"></label>
      <input type="search" name="q" aria-label="Search">
      <input type="hidden" name="csrf" value="x">
      <input type="submit" value="Send">
    </form>
  </body>
</html>
"""


def test_clean_page_has_no_issues():
    row = check_page(URL, 200, CLEAN_PAGE)
    assert row["issues"] == []
    assert row["issueCount"] == 0
    assert row["titleMissing"] is False
    assert row["titleLength"] == len("How to audit a website for broken links")
    assert row["metaDescriptionMissing"] is False
    assert row["h1Count"] == 1
    assert row["headingOrderBroken"] is False
    assert row["imagesWithoutAlt"] == 0
    assert row["formFieldsWithoutLabel"] == 0
    assert row["canonical"] == "https://example.com/page"
    assert row["canonicalMissing"] is False


def test_page_without_title():
    html = """
    <html><head>
      <meta name="description" content="A description long enough to be useful
        to a reader scanning a page of search results for an answer.">
      <link rel="canonical" href="https://example.com/page">
    </head><body><h1>Only a heading</h1></body></html>
    """
    row = check_page(URL, 200, html)
    assert row["titleMissing"] is True
    assert row["title"] is None
    assert row["titleLength"] == 0
    assert "missing <title>" in row["issues"]


def test_page_without_meta_description():
    html = """
    <html><head>
      <title>A page title that is long enough</title>
      <link rel="canonical" href="https://example.com/page">
    </head><body><h1>Heading</h1></body></html>
    """
    row = check_page(URL, 200, html)
    assert row["metaDescriptionMissing"] is True
    assert row["metaDescription"] is None
    assert "missing meta description" in row["issues"]
    assert row["titleMissing"] is False


def test_page_without_h1():
    html = """
    <html><head>
      <title>A page title that is long enough</title>
      <meta name="description" content="A description long enough to be useful
        to a reader scanning a page of search results for an answer.">
      <link rel="canonical" href="https://example.com/page">
    </head><body><h2>Only a subheading</h2><p>Text.</p></body></html>
    """
    row = check_page(URL, 200, html)
    assert row["h1Count"] == 0
    assert "no h1 on the page" in row["issues"]


def test_title_over_sixty_characters():
    title = "A page title written long enough on purpose to pass sixty characters"
    assert len(title) > 60
    html = f"""
    <html><head>
      <title>{title}</title>
      <meta name="description" content="A description long enough to be useful
        to a reader scanning a page of search results for an answer.">
      <link rel="canonical" href="https://example.com/page">
    </head><body><h1>Heading</h1></body></html>
    """
    row = check_page(URL, 200, html)
    assert row["titleMissing"] is False
    assert row["titleLength"] == len(title)
    assert f"title is {len(title)} characters, over 60" in row["issues"]


def test_title_under_fifteen_characters():
    html = """
    <html><head>
      <title>Short</title>
      <meta name="description" content="A description long enough to be useful
        to a reader scanning a page of search results for an answer.">
      <link rel="canonical" href="https://example.com/page">
    </head><body><h1>Heading</h1></body></html>
    """
    row = check_page(URL, 200, html)
    assert row["titleLength"] == 5
    assert "title is only 5 characters" in row["issues"]


def test_meta_description_over_one_hundred_and_sixty_characters():
    description = (
        "A meta description written on purpose to run past the one hundred and "
        "sixty character mark that search engines cut it at, so that the length "
        "rule has something real to report here."
    )
    assert len(description) > 160
    html = f"""
    <html><head>
      <title>A page title that is long enough</title>
      <meta name="description" content="{description}">
      <link rel="canonical" href="https://example.com/page">
    </head><body><h1>Heading</h1></body></html>
    """
    row = check_page(URL, 200, html)
    assert row["metaDescriptionMissing"] is False
    assert (
        f"meta description is {len(description)} characters, over 160"
        in row["issues"]
    )


def test_two_h1_headings():
    html = """
    <html><head>
      <title>A page title that is long enough</title>
      <meta name="description" content="A description long enough to be useful
        to a reader scanning a page of search results for an answer.">
      <link rel="canonical" href="https://example.com/page">
    </head><body><h1>First</h1><h2>Sub</h2><h1>Second</h1></body></html>
    """
    row = check_page(URL, 200, html)
    assert row["h1Count"] == 2
    assert "2 h1 headings, expected 1" in row["issues"]


def test_heading_order_broken_when_level_is_skipped():
    html = """
    <html><head>
      <title>A page title that is long enough</title>
      <meta name="description" content="A description long enough to be useful
        to a reader scanning a page of search results for an answer.">
      <link rel="canonical" href="https://example.com/page">
    </head><body><h1>First</h1><h3>Skipped h2</h3></body></html>
    """
    row = check_page(URL, 200, html)
    assert row["headingOrderBroken"] is True
    assert "heading levels are out of order" in row["issues"]


def test_image_without_alt():
    html = """
    <html><head>
      <title>A page title that is long enough</title>
      <meta name="description" content="A description long enough to be useful
        to a reader scanning a page of search results for an answer.">
      <link rel="canonical" href="https://example.com/page">
    </head><body>
      <h1>Heading</h1>
      <img src="/no-alt.png">
      <img src="/decorative.gif" alt="">
      <img src="/ok.png" alt="A chart">
    </body></html>
    """
    row = check_page(URL, 200, html)
    assert row["imagesWithoutAlt"] == 1
    assert "1 image(s) without alt text" in row["issues"]


def test_input_without_label():
    html = """
    <html><head>
      <title>A page title that is long enough</title>
      <meta name="description" content="A description long enough to be useful
        to a reader scanning a page of search results for an answer.">
      <link rel="canonical" href="https://example.com/page">
    </head><body>
      <h1>Heading</h1>
      <form>
        <input type="text" name="orphan">
        <textarea name="message"></textarea>
        <label for="ok">Fine</label><input type="text" id="ok" name="ok">
        <input type="submit" value="Send">
      </form>
    </body></html>
    """
    row = check_page(URL, 200, html)
    assert row["formFieldsWithoutLabel"] == 2
    assert "2 form field(s) without a label" in row["issues"]


def test_missing_canonical():
    html = """
    <html><head>
      <title>A page title that is long enough</title>
      <meta name="description" content="A description long enough to be useful
        to a reader scanning a page of search results for an answer.">
    </head><body><h1>Heading</h1></body></html>
    """
    row = check_page(URL, 200, html)
    assert row["canonicalMissing"] is True
    assert row["canonical"] is None
    assert "missing canonical link" in row["issues"]


def test_empty_page_still_returns_a_row():
    row = check_page(URL, None, None)
    assert row["url"] == URL
    assert row["status"] is None
    assert "no HTML body to check" in row["issues"]


def test_error_status_is_reported():
    row = check_page(URL, 404, "<html><body>Not found</body></html>")
    assert "page returned HTTP 404" in row["issues"]


@pytest.mark.parametrize(
    "html,expected",
    [
        ("<html><body><h2>Starts at h2</h2></body></html>", True),
        ("<html><body><h1>A</h1><h2>B</h2><h3>C</h3></body></html>", False),
        ("<html><body><p>No headings at all</p></body></html>", False),
    ],
)
def test_heading_order_cases(html, expected):
    assert check_page(URL, 200, html)["headingOrderBroken"] is expected


def test_summarize_counts_the_run():
    rows = [
        check_page(URL, 200, CLEAN_PAGE),
        check_page(URL + "/2", 200, "<html><body><img src='x.png'></body></html>"),
    ]
    summary = summarize(rows)
    assert summary["pagesAudited"] == 2
    assert summary["pagesWithIssues"] == 1
    assert summary["imagesWithoutAlt"] == 1
    assert summary["titleMissing"] == 1
    assert summary["worstPages"][0]["url"] == URL + "/2"


def _run_all() -> int:
    """Standalone runner used when pytest is not installed."""
    failures: list[str] = []
    ran = 0
    for name, func in sorted(globals().items()):
        if not name.startswith("test_") or not callable(func):
            continue
        params = getattr(func, "_params", None)
        if params is None:
            cases: list[tuple] = [()]
        else:
            cases = [
                value if isinstance(value, tuple) else (value,)
                for value in params[1]
            ]
        for case in cases:
            ran += 1
            label = name + (str(case) if params else "")
            try:
                func(*case)
            except AssertionError as exc:
                failures.append(label)
                print(f"  FAIL  {label}: {exc}")
            except Exception as exc:  # noqa: BLE001 - report, do not crash
                failures.append(label)
                print(f"  ERROR {label}: {exc.__class__.__name__}: {exc}")
            else:
                print(f"  PASS  {label}")
    print(f"\n{ran - len(failures)}/{ran} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(_run_all())
