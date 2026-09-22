"""Offline tests for the `page-audited` charge. No network, no Apify platform.

The defect these tests lock down: the crawler charged `page-audited` before
the request, so a page that answered 404, 500 or `application/pdf` was billed
and then skipped with `continue`, leaving the buyer with an invoice item and
no dataset row. The rule now is one charge per page row, charged in
`PageAuditCrawler._write_row` at the moment the row is added.

The HTTP layer is replaced by a fake session (`FakeSession`), so every
response is written here, literally. pytest is not installed in the lab
sandbox, so the file carries its own runner and prints `N/N passed`:

    ../../.venv/bin/python tests/test_billing.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.link_auditor import CHARGE_LIMIT_ERROR  # noqa: E402
from src.main import PageAuditCrawler, apply_charge_result  # noqa: E402

BASE = "https://site.test"

HTML_PAGE = """<!doctype html><html lang="en"><head><title>A page</title></head>
<body><h1>Hello</h1>{links}</body></html>"""


class FakeResponse:
    def __init__(self, url: str, status: int, content_type: str, body: bytes) -> None:
        self.url = url
        self.status_code = status
        self.headers = {"Content-Type": content_type} if content_type else {}
        self.encoding = "utf-8"
        self._body = body
        self.text = body.decode("utf-8", errors="replace")

    def iter_content(self, chunk_size: int, decode_unicode: bool = False):
        for start in range(0, len(self._body), chunk_size):
            yield self._body[start:start + chunk_size]

    def close(self) -> None:
        pass


class FakeSession:
    """Answers from a dict: url -> (status, content_type, body[, final_url])."""

    def __init__(self, routes: dict, robots: str = "") -> None:
        self.routes = routes
        self.robots = robots
        self.requested: list[tuple[str, str]] = []

    def get(self, url, **_kwargs):  # used by RobotsCache
        if url.endswith("/robots.txt"):
            return FakeResponse(url, 200 if self.robots else 404, "text/plain",
                                self.robots.encode())
        return self.request("GET", url)

    def request(self, method, url, **_kwargs):
        self.requested.append((method, url))
        route = self.routes.get(url)
        if route is None:
            return FakeResponse(url, 404, "text/html", b"<html>not found</html>")
        status, content_type, body = route[:3]
        final_url = route[3] if len(route) > 3 else url
        if isinstance(body, str):
            body = body.encode()
        return FakeResponse(final_url, status, content_type, body)


def _crawler(routes: dict, robots: str = "", budget: int | None = None,
             start: str = f"{BASE}/"):
    charges: list[int] = []

    def charge_page() -> bool:
        if budget is not None and len(charges) >= budget:
            return False
        charges.append(1)
        return True

    crawler = PageAuditCrawler(
        charge_page=charge_page,
        start_url=start,
        max_pages=20,
        max_depth=3,
        delay_seconds=0,
        log=lambda _msg: None,
    )
    session = FakeSession(routes, robots)
    crawler.session = session
    crawler.robots.session = session
    return crawler, charges, session


def _home(*paths: str) -> str:
    return HTML_PAGE.format(
        links="".join(f'<a href="{path}">{path}</a>' for path in paths)
    )


# ------------------------------------------------------------ (a) HTTP errors

def test_404_page_is_not_charged():
    crawler, charges, _ = _crawler({
        f"{BASE}/": (404, "text/html", "<html><title>Not found</title></html>"),
    })
    crawler.run()
    assert charges == [], f"404 must cost nothing, got {len(charges)} charge(s)"
    assert crawler.rows == []


def test_500_page_is_not_charged():
    crawler, charges, _ = _crawler({
        f"{BASE}/": (500, "text/html", "<html><title>Server error</title></html>"),
    })
    crawler.run()
    assert charges == [], f"500 must cost nothing, got {len(charges)} charge(s)"
    assert crawler.rows == []


def test_error_pages_linked_from_a_good_page_are_not_charged():
    crawler, charges, session = _crawler({
        f"{BASE}/": (200, "text/html; charset=utf-8", _home("/missing", "/broken")),
        f"{BASE}/missing": (404, "text/html", "<html>gone</html>"),
        f"{BASE}/broken": (500, "text/html", "<html>oops</html>"),
    })
    crawler.run()
    assert ("GET", f"{BASE}/missing") in session.requested
    assert ("GET", f"{BASE}/broken") in session.requested
    assert len(charges) == 1, f"only the home page is a row, got {len(charges)}"
    assert [row["url"] for row in crawler.rows] == [f"{BASE}/"]


# -------------------------------------------------------- (b) bodies not HTML

def test_pdf_page_is_not_charged():
    crawler, charges, _ = _crawler({
        f"{BASE}/": (200, "application/pdf", b"%PDF-1.7 fake"),
    })
    crawler.run()
    assert charges == [], f"a PDF must cost nothing, got {len(charges)} charge(s)"
    assert crawler.rows == []


def test_json_page_is_not_charged():
    crawler, charges, _ = _crawler({
        f"{BASE}/": (200, "application/json", '{"ok": true}'),
    })
    crawler.run()
    assert charges == [], f"JSON must cost nothing, got {len(charges)} charge(s)"
    assert crawler.rows == []


def test_redirect_without_content_is_not_charged():
    crawler, charges, _ = _crawler({
        f"{BASE}/": (301, "text/html", b""),
    })
    crawler.run()
    assert charges == [] and crawler.rows == []


def test_3xx_with_a_body_is_not_charged():
    crawler, charges, _ = _crawler({
        f"{BASE}/": (302, "text/html", "<html>moved</html>"),
    })
    crawler.run()
    assert charges == [] and crawler.rows == []


def test_robots_blocked_page_is_not_requested_nor_charged():
    crawler, charges, session = _crawler(
        {
            f"{BASE}/": (200, "text/html", _home("/private/x")),
            f"{BASE}/private/x": (200, "text/html", _home()),
        },
        robots="User-agent: *\nDisallow: /private/\n",
    )
    crawler.run()
    assert ("GET", f"{BASE}/private/x") not in session.requested
    assert len(charges) == 1
    assert [row["url"] for row in crawler.rows] == [f"{BASE}/"]


# ----------------------------------------------------------- (c) HTML 200 page

def test_html_200_page_is_charged_exactly_once():
    crawler, charges, _ = _crawler({
        f"{BASE}/": (200, "text/html; charset=utf-8", _home()),
    })
    crawler.run()
    assert len(charges) == 1, f"one HTML page, one charge; got {len(charges)}"
    assert len(crawler.rows) == 1
    assert crawler.rows[0]["url"] == f"{BASE}/"
    assert crawler.pages_charged == 1


def test_charges_equal_rows_on_a_mixed_site():
    crawler, charges, _ = _crawler({
        f"{BASE}/": (200, "text/html", _home("/a", "/b.pdf", "/api", "/gone",
                                             "/index.html", "/a#top")),
        f"{BASE}/a": (200, "application/xhtml+xml", _home("/")),
        f"{BASE}/api": (200, "application/json", "[]"),
        f"{BASE}/gone": (410, "text/html", "<html>gone</html>"),
    })
    crawler.run()
    urls = [row["url"] for row in crawler.rows]
    assert urls == [f"{BASE}/", f"{BASE}/a"], urls
    assert len(charges) == len(crawler.rows) == 2


def test_redirect_to_a_page_already_audited_is_not_charged_again():
    crawler, charges, _ = _crawler({
        f"{BASE}/": (200, "text/html", _home("/old")),
        f"{BASE}/old": (200, "text/html", _home(), f"{BASE}/"),
    })
    crawler.run()
    assert len(charges) == 1 and len(crawler.rows) == 1


def test_charge_limit_stops_the_crawl_without_an_unpaid_row():
    crawler, charges, session = _crawler(
        {
            f"{BASE}/": (200, "text/html", _home("/a", "/b")),
            f"{BASE}/a": (200, "text/html", _home()),
            f"{BASE}/b": (200, "text/html", _home()),
        },
        budget=1,
    )
    result = crawler.run()
    assert len(charges) == 1 and len(crawler.rows) == 1
    assert crawler.charge_limit_reached
    assert result.summary["chargeLimitReached"] is True
    assert ("GET", f"{BASE}/b") not in session.requested
    assert CHARGE_LIMIT_ERROR  # the marker the crawl loop stops on


def test_no_billing_callable_means_no_charge_but_rows():
    crawler = PageAuditCrawler(
        charge_page=None, start_url=f"{BASE}/", delay_seconds=0,
        log=lambda _msg: None,
    )
    session = FakeSession({f"{BASE}/": (200, "text/html", _home())})
    crawler.session = session
    crawler.robots.session = session
    crawler.run()
    assert len(crawler.rows) == 1 and crawler.pages_charged == 0


# ------------------------------------------- reading the answer of Actor.charge

class _Answer:
    def __init__(self, charged_count: int, limit: bool) -> None:
        self.charged_count = charged_count
        self.event_charge_limit_reached = limit


def _state() -> dict:
    return {"limit_reached": False, "charged": 0, "failures": 0}


def test_charged_event_at_the_limit_still_writes_its_row():
    # Seen in the local SDK on 21/09/2026: the call that hits the limit comes
    # back with charged_count=1 and event_charge_limit_reached=True.
    state = _state()
    assert apply_charge_result(state, _Answer(1, True), log=lambda _m: None) is True
    assert state == {"limit_reached": True, "charged": 1, "failures": 0}


def test_refused_event_writes_no_row():
    state = _state()
    assert apply_charge_result(state, _Answer(0, True), log=lambda _m: None) is False
    assert state["charged"] == 0 and state["limit_reached"] is True


def test_normal_charge_and_failed_charge():
    state = _state()
    assert apply_charge_result(state, _Answer(1, False)) is True
    assert apply_charge_result(state, None) is True
    assert state == {"limit_reached": False, "charged": 1, "failures": 1}


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
