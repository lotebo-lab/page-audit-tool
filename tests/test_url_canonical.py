"""Offline tests for `canonicalize_url`. No network, no Apify, no pytest.

pytest is not installed in the lab sandbox and `pip install` has no network
there, so this file carries its own runner and prints `N/N passed`:

    .venv/bin/python negocios/actor-auditoria-paginas/tests/test_url_canonical.py

The defect these tests lock down: in the local run of 20/09/2026,
`http://127.0.0.1:8099/` and `http://127.0.0.1:8099/index.html` were audited as
two pages, which is two dataset rows and two `page-audited` charges for one
page.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.url_canonical import canonicalize_url, same_page  # noqa: E402

BASE = "http://127.0.0.1:8099"


# --------------------------------------------------------------- same page

SAME_PAGE_CASES = [
    # (first, second, why)
    (f"{BASE}/", f"{BASE}/index.html", "directory and its index file"),
    (f"{BASE}/", f"{BASE}/index.htm", "directory and index.htm"),
    (f"{BASE}/", f"{BASE}/index.php", "directory and index.php"),
    (f"{BASE}/", f"{BASE}/default.html", "directory and default.html"),
    (f"{BASE}/docs/", f"{BASE}/docs/default.html", "sub-directory and default.html"),
    (f"{BASE}/", f"{BASE}/?utm=x", "a campaign tag selects no document"),
    (f"{BASE}/", f"{BASE}/?utm_source=x&utm_medium=email", "the whole utm family"),
    (f"{BASE}/a?b=1", f"{BASE}/a?b=1&utm_campaign=x", "utm next to a real parameter"),
    (f"{BASE}/docs/", f"{BASE}/docs/index.html", "sub-directory and its index"),
    (f"{BASE}/docs", f"{BASE}/docs/", "trailing slash"),
    (f"{BASE}/a?b=2&a=1", f"{BASE}/a?a=1&b=2", "query parameter order"),
    (f"{BASE}/a", f"{BASE}/a#secao", "fragment is never sent to the server"),
    (f"{BASE}/index.html#secao", f"{BASE}/", "index file plus fragment"),
    (f"{BASE}/a", f"{BASE}/a?", "empty query string"),
    (f"{BASE}/a/b", f"{BASE}/a/./b", "a dot segment"),
    (f"{BASE}/a/b", f"{BASE}/a/c/../b", "a dot-dot segment"),
    ("HTTP://127.0.0.1:8099/a", f"{BASE}/a", "scheme and host are case-insensitive"),
    ("http://127.0.0.1:80/a", "http://127.0.0.1/a", "default port for http"),
    ("https://127.0.0.1:443/a", "https://127.0.0.1/a", "default port for https"),
    (f"{BASE}/%7Euser", f"{BASE}/~user", "the same byte, two encodings"),
    (f"{BASE}/a?b=2&a=1#topo", f"{BASE}/a?a=1&b=2", "order and fragment together"),
]


# ----------------------------------------------------------- different page

DIFFERENT_PAGE_CASES = [
    (f"{BASE}/a", f"{BASE}/b", "different paths"),
    (f"{BASE}/pagina", f"{BASE}/pagina/sub", "a page and a page under it"),
    (f"{BASE}/a?a=1", f"{BASE}/a?a=2", "same key, different value"),
    (f"{BASE}/a?a=1", f"{BASE}/a?a=1&b=2", "an extra parameter"),
    (f"{BASE}/Pagina", f"{BASE}/pagina", "paths are case-sensitive"),
    ("http://127.0.0.1/a", "https://127.0.0.1/a", "http is not https"),
    ("http://exemplo.com/a", "http://www.exemplo.com/a", "www is another host"),
    (f"{BASE}/a", f"{BASE}/a?page=2", "a parameter that is not utm is kept"),
    (f"{BASE}/a", f"{BASE}/a?ref=x", "ref is not a utm tag and is kept"),
    (f"{BASE}/index.html", f"{BASE}/docs/index.html", "two different directories"),
    (f"{BASE}/default.aspx", f"{BASE}/", "only the four index files collapse"),
    (f"{BASE}/default.htm", f"{BASE}/", "default.htm was not asked for"),
    ("http://127.0.0.1:8099/a", "http://127.0.0.1:9000/a", "different ports"),
]


def test_root_and_index_html_are_one_page():
    assert canonicalize_url(f"{BASE}/index.html") == f"{BASE}/"
    assert canonicalize_url(f"{BASE}/") == f"{BASE}/"
    assert same_page(f"{BASE}/", f"{BASE}/index.html")


def test_query_order_does_not_make_a_second_page():
    assert canonicalize_url(f"{BASE}/a?b=2&a=1") == canonicalize_url(f"{BASE}/a?a=1&b=2")
    assert canonicalize_url(f"{BASE}/a?b=2&a=1") == f"{BASE}/a?a=1&b=2"


def test_fragment_is_ignored():
    assert canonicalize_url(f"{BASE}/a#secao") == f"{BASE}/a"
    assert canonicalize_url(f"{BASE}/#secao") == f"{BASE}/"


def test_same_page_cases():
    failures = []
    for first, second, why in SAME_PAGE_CASES:
        if canonicalize_url(first) != canonicalize_url(second):
            failures.append(
                f"{why}: {first} -> {canonicalize_url(first)} != "
                f"{second} -> {canonicalize_url(second)}"
            )
    assert not failures, "; ".join(failures)


def test_different_page_cases():
    failures = []
    for first, second, why in DIFFERENT_PAGE_CASES:
        if canonicalize_url(first) == canonicalize_url(second):
            failures.append(
                f"{why}: {first} and {second} both became {canonicalize_url(first)}"
            )
    assert not failures, "; ".join(failures)


def test_repeated_key_keeps_every_value():
    # Dropping one value could change what the server returns, so all of them
    # survive; only the order is normalised.
    assert canonicalize_url(f"{BASE}/a?x=2&x=1") == f"{BASE}/a?x=1&x=2"
    assert canonicalize_url(f"{BASE}/a?x=1&x=2") == f"{BASE}/a?x=1&x=2"
    assert canonicalize_url(f"{BASE}/a?x=1") != canonicalize_url(f"{BASE}/a?x=1&x=2")


def test_blank_value_parameter_survives():
    assert canonicalize_url(f"{BASE}/a?debug=") == f"{BASE}/a?debug="
    assert canonicalize_url(f"{BASE}/a?debug=") != canonicalize_url(f"{BASE}/a")


def test_root_keeps_its_slash():
    assert canonicalize_url("http://127.0.0.1:8099") == f"{BASE}/"
    assert canonicalize_url(f"{BASE}/index.html") == f"{BASE}/"


def test_idempotent():
    for first, second, _ in SAME_PAGE_CASES + DIFFERENT_PAGE_CASES:
        for url in (first, second):
            once = canonicalize_url(url)
            assert canonicalize_url(once) == once, url


def test_the_five_pages_of_the_local_test_site():
    """The crawl of the local site must end with five distinct pages."""
    crawled = [
        f"{BASE}/",
        f"{BASE}/index.html",  # the duplicate that produced the sixth row
        f"{BASE}/sem-title.html",
        f"{BASE}/duas-h1.html",
        f"{BASE}/imagem-sem-alt.html",
        f"{BASE}/headings-fora-de-ordem.html",
    ]
    assert len(crawled) == 6
    assert len({canonicalize_url(url) for url in crawled}) == 5


def test_the_crawler_uses_this_function():
    # `link_auditor.canonical_url` is what the queue and the charge go through.
    from src.link_auditor import canonical_url  # noqa: PLC0415

    assert canonical_url(f"{BASE}/index.html") == canonicalize_url(f"{BASE}/index.html")
    assert canonical_url(f"{BASE}/index.html") == f"{BASE}/"


def _charge(auditor, url):
    """Put one successful response for `url` through the crawler's billing guard."""
    return auditor._charge_for_result(url, "GET", {"error": None, "final_url": url})


def test_charge_is_not_repeated_for_two_spellings_of_one_page():
    """The billing guard in the crawler, exercised without any network."""
    from src.link_auditor import Auditor  # noqa: PLC0415

    charges = []
    auditor = Auditor(
        start_url=f"{BASE}/",
        delay_seconds=0,
        charge=lambda: (charges.append(1), True)[1],
    )
    assert _charge(auditor, f"{BASE}/") is True
    assert _charge(auditor, f"{BASE}/index.html") is True
    assert _charge(auditor, f"{BASE}/index.html#secao") is True
    assert len(charges) == 1, f"one page must cost one charge, got {len(charges)}"
    assert _charge(auditor, f"{BASE}/outra.html") is True
    assert len(charges) == 2


def test_four_spellings_of_the_home_page_are_one_entry():
    """The defect, stated as the buyer sees it: one page, one entry.

    These are the four spellings the crawler meets on a real site: the bare
    root, the directory index file, a campaign link with a fragment, and the
    root with a trailing slash. A queue, a dataset and a charge are all keyed
    by the canonical URL, so one entry here means one row and one
    `page-audited` event.
    """
    spellings = [
        f"{BASE}/",
        f"{BASE}/index.html",
        f"{BASE}/?utm=x#secao",
        f"{BASE}/index.html/",
        f"{BASE}",
        f"{BASE}/default.html#topo",
    ]
    queue_keys = {canonicalize_url(url) for url in spellings}
    assert queue_keys == {f"{BASE}/"}, queue_keys


def test_other_pages_are_not_swallowed_by_the_home_page():
    """The other half of the defect: a real page must never disappear."""
    pages = [
        f"{BASE}/",
        f"{BASE}/sem-title.html",
        f"{BASE}/duas-h1.html",
        f"{BASE}/docs/",
        f"{BASE}/docs/index.html",  # same page as /docs/
        f"{BASE}/docs/guia.html",
        f"{BASE}/lista?page=2",
        f"{BASE}/lista?page=3",
    ]
    keys = {canonicalize_url(url) for url in pages}
    assert len(keys) == 7, sorted(keys)
    assert f"{BASE}/docs/guia.html" in keys
    assert canonicalize_url(f"{BASE}/lista?page=2") != canonicalize_url(
        f"{BASE}/lista?page=3"
    )


def test_campaign_tag_and_fragment_do_not_buy_a_second_audit():
    """The four spellings, put through the crawler's own billing guard."""
    from src.link_auditor import Auditor  # noqa: PLC0415

    charges = []
    auditor = Auditor(
        start_url=f"{BASE}/",
        delay_seconds=0,
        charge=lambda: (charges.append(1), True)[1],
    )
    for spelling in (
        f"{BASE}/",
        f"{BASE}/index.html",
        f"{BASE}/?utm=x#secao",
        f"{BASE}/index.html/",
        f"{BASE}/default.html",
    ):
        assert _charge(auditor, spelling) is True, spelling
    assert len(charges) == 1, f"one page must cost one charge, got {len(charges)}"

    # A different page still costs its own charge: the guard de-duplicates, it
    # does not stop billing.
    assert _charge(auditor, f"{BASE}/sem-title.html") is True
    assert _charge(auditor, f"{BASE}/lista?page=2") is True
    assert _charge(auditor, f"{BASE}/lista?page=3") is True
    assert len(charges) == 4, len(charges)


def test_only_utm_keys_are_dropped():
    assert canonicalize_url(f"{BASE}/a?utm_source=x") == f"{BASE}/a"
    assert canonicalize_url(f"{BASE}/a?UTM_Source=x") == f"{BASE}/a"
    assert canonicalize_url(f"{BASE}/a?b=1&utm_source=x") == f"{BASE}/a?b=1"
    assert canonicalize_url(f"{BASE}/a?utmx=1") == f"{BASE}/a?utmx=1"
    assert canonicalize_url(f"{BASE}/a?gclid=1") == f"{BASE}/a?gclid=1"


def test_default_html_is_the_directory_index():
    assert canonicalize_url(f"{BASE}/default.html") == f"{BASE}/"
    assert canonicalize_url(f"{BASE}/docs/default.html") == f"{BASE}/docs"
    assert canonicalize_url(f"{BASE}/default.aspx") == f"{BASE}/default.aspx"


def _run_all() -> int:
    """Standalone runner used when pytest is not installed."""
    failures: list[str] = []
    ran = 0
    for name, func in sorted(globals().items()):
        if not name.startswith("test_") or not callable(func):
            continue
        ran += 1
        try:
            func()
        except AssertionError as exc:
            failures.append(name)
            print(f"  FAIL  {name}: {exc}")
        except Exception as exc:  # noqa: BLE001 - report, do not crash
            failures.append(name)
            print(f"  ERROR {name}: {exc.__class__.__name__}: {exc}")
        else:
            print(f"  PASS  {name}")
    print(f"\n{ran - len(failures)}/{ran} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(_run_all())
