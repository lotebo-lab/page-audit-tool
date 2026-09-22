"""Core crawl-and-check logic for the Broken Link Auditor.

This module is deliberately free of any Apify SDK import so it can be run and
tested locally with a plain Python interpreter. `src/main.py` is the Actor
entry point and only wires input/output around `audit_site`.

Data policy (enforced here, not just documented):
  * The only things kept from a page are: the page URL, the HTTP status, the
    absolute target URL of each link and the link's anchor text. Page bodies
    are parsed in memory and discarded.
  * `mailto:` and `tel:` links are skipped entirely, so e-mail addresses and
    phone numbers are never collected.
  * robots.txt is always honoured. There is no option to turn it off.
  * Requests are sequential and spaced by a configurable delay, never below
    the target host's own Crawl-delay directive.

Billing hook (used by the Actor, ignored when running locally):
  * `Auditor(charge=...)` takes a callable that is invoked **after** the
    response arrives, and only for a response this Actor can turn into a
    dataset row, as `_is_billable` decides. The Page Audit Tool does not use
    this hook: `PageAuditCrawler` (src/main.py) builds this class with
    `charge=None` and charges `page-audited` itself, once per dataset row, in
    `_write_row`. Either way an HTTP error, a body that is not HTML and a request that never
    reached the server cost the buyer nothing, because none of them produces
    a line of audit. `robots.txt` fetches are never charged either.
  * Charging after the response, and not before it, is the fix for the defect
    where a page that answered 404 or `application/json` was billed as
    `page-audited` and then skipped with `continue`, leaving the buyer with an
    invoice item and no row. The sibling Actor `actor-vigia-paginas` already
    works this way ("Only a URL we actually read is a URL we charge for",
    `src/main.py:406`), and this is the same rule.
  * The charge is keyed by the canonical **final** URL (after redirects), the
    same key the dataset row is keyed by, so one row always means one charge
    and one charge always means one row.
  * The callable returns True when the event was accepted and False when the
    run's charge limit has been reached. On the first False the auditor drops
    the response it is holding (the buyer did not pay for it, so it is not
    reported), stops issuing requests and finishes cleanly, keeping everything
    it had already found.
"""

from __future__ import annotations

import time
import urllib.robotparser
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Iterable
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

try:  # running inside the Actor image (python src/main.py)
    from url_canonical import canonicalize_url
except ImportError:  # running as a package (python -m src.main, tests)
    from .url_canonical import canonicalize_url

USER_AGENT = (
    "LoteboPageAuditTool/0.2 (+https://apify.com/store; "
    "Apify Actor; contact via Apify Store page)"
)

# Marker used when a request was not made because the run hit its charge limit.
# Rows with this error are never reported as broken links.
CHARGE_LIMIT_ERROR = "not_checked_charge_limit_reached"

# Schemes we never follow or check.
SKIPPED_SCHEMES = frozenset(
    {"mailto", "tel", "javascript", "data", "about", "sms", "callto", "ftp", "file"}
)

# Extensions that are certainly not HTML, so we check the status but never parse.
NON_HTML_SUFFIXES = (
    ".pdf", ".zip", ".gz", ".tar", ".rar", ".7z", ".png", ".jpg", ".jpeg",
    ".gif", ".webp", ".svg", ".ico", ".mp3", ".mp4", ".avi", ".mov", ".wav",
    ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".csv", ".json", ".xml",
    ".rss", ".woff", ".woff2", ".ttf", ".eot", ".dmg", ".exe", ".apk", ".iso",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_start_url(raw: str) -> str:
    """Accept `example.com`, `http://example.com` or a full URL; return a URL."""
    raw = (raw or "").strip()
    if not raw:
        raise ValueError("startUrl is empty")
    if "://" not in raw:
        raw = "https://" + raw
    parsed = urlparse(raw)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"unsupported scheme: {parsed.scheme}")
    if not parsed.netloc:
        raise ValueError(f"could not read a host from: {raw}")
    return urlunparse(parsed._replace(path=parsed.path or "/", fragment=""))


def canonical_url(url: str) -> str:
    """One spelling per page, for de-duplication and for billing.

    Kept as a name because the rest of this module (and the tests) call it;
    the rules themselves live in `url_canonical.canonicalize_url`, with the
    reason for every case written next to it. Before 20/09/2026 this function
    only dropped the fragment, which let `/` and `/index.html` be queued,
    audited and charged as two pages.
    """
    return canonicalize_url(url)


def _registrable(host: str) -> str:
    host = (host or "").lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def same_site(url: str, root_host: str, include_subdomains: bool) -> bool:
    host = (urlparse(url).hostname or "").lower()
    if not host:
        return False
    root = _registrable(root_host)
    if _registrable(host) == root:
        return True
    return include_subdomains and host.endswith("." + root)


def looks_like_html(url: str) -> bool:
    path = urlparse(url).path.lower()
    return not path.endswith(NON_HTML_SUFFIXES)


@dataclass
class RobotsCache:
    """One robots.txt per host, fetched once, plus its Crawl-delay."""

    session: requests.Session | None = None
    timeout: float = 15.0
    _parsers: dict[str, urllib.robotparser.RobotFileParser | None] = field(
        default_factory=dict
    )

    def _parser(self, url: str) -> urllib.robotparser.RobotFileParser | None:
        parsed = urlparse(url)
        key = f"{parsed.scheme}://{parsed.netloc}"
        if key in self._parsers:
            return self._parsers[key]
        parser: urllib.robotparser.RobotFileParser | None = None
        getter = self.session.get if self.session is not None else requests.get
        try:
            response = getter(
                key + "/robots.txt",
                headers={"User-Agent": USER_AGENT},
                timeout=self.timeout,
                allow_redirects=True,
            )
            if response.status_code == 200:
                parser = urllib.robotparser.RobotFileParser()
                parser.parse(response.text.splitlines())
            # 4xx/5xx robots.txt: standard reading is "no restrictions stated".
        except requests.RequestException:
            parser = None
        self._parsers[key] = parser
        return parser

    def allowed(self, url: str) -> bool:
        parser = self._parser(url)
        if parser is None:
            return True
        try:
            return parser.can_fetch(USER_AGENT, url)
        except Exception:
            return True

    def crawl_delay(self, url: str) -> float:
        parser = self._parser(url)
        if parser is None:
            return 0.0
        try:
            value = parser.crawl_delay(USER_AGENT)
            return float(value) if value else 0.0
        except Exception:
            return 0.0


@dataclass
class LinkRef:
    """Where a target URL was found. No page content, only these fields."""

    source_url: str
    anchor_text: str


@dataclass
class AuditResult:
    broken_links: list[dict]
    summary: dict
    pages_visited: list[dict] = field(default_factory=list)


class Auditor:
    def __init__(
        self,
        start_url: str,
        max_pages: int = 50,
        max_depth: int = 3,
        delay_seconds: float = 1.0,
        timeout_seconds: float = 15.0,
        check_external_links: bool = True,
        include_subdomains: bool = False,
        log: Callable[[str], None] = print,
        charge: Callable[[], bool] | None = None,
    ) -> None:
        self.start_url = normalize_start_url(start_url)
        self.root_host = urlparse(self.start_url).hostname or ""
        self.max_pages = max(1, int(max_pages))
        self.max_depth = max(0, int(max_depth))
        self.delay_seconds = max(0.0, float(delay_seconds))
        self.timeout_seconds = float(timeout_seconds)
        self.check_external_links = bool(check_external_links)
        self.include_subdomains = bool(include_subdomains)
        self.log = log
        # Called once per billable response (see `_is_billable`), never before
        # the request. Returns False when the run is out of budget; the crawl
        # then stops cleanly.
        self.charge = charge
        self.charge_limit_reached = False
        self.requests_made = 0

        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            }
        )
        self.robots = RobotsCache(session=self.session, timeout=self.timeout_seconds)

        self._last_request_at: dict[str, float] = {}
        # url -> {"status": int|None, "error": str|None, "final_url": str}
        self._checked: dict[str, dict] = {}
        self.pages_visited: list[dict] = []
        self.skipped_by_robots: set[str] = set()
        self.links_seen = 0
        # Canonical URLs the buyer has already been charged for in this run.
        # The queue already de-duplicates, so this set is the second lock on
        # the same door: one page, one charge, whatever spelling arrives here.
        self._charged_urls: set[str] = set()

    # ------------------------------------------------------------------ net

    def _wait(self, url: str) -> None:
        host = urlparse(url).netloc
        delay = max(self.delay_seconds, self.robots.crawl_delay(url))
        last = self._last_request_at.get(host)
        if last is not None:
            elapsed = time.monotonic() - last
            if elapsed < delay:
                time.sleep(delay - elapsed)
        self._last_request_at[host] = time.monotonic()

    def _is_billable(self, method: str, result: dict) -> bool:
        """True when this response is something the buyer gets paid work for.

        Base rule: a response that reached the server and came back. The Actor
        subclass narrows it (see `src/main.py`), because what this Actor sells
        is one audited page, and a response it cannot audit is not a sale.
        """
        return result.get("error") is None

    def _charge_for_result(self, url: str, method: str, result: dict) -> bool:
        """Pay for one billable response. False means the budget is spent.

        The key is the canonical final URL: `/` and `/index.html` are one page,
        so they cost one `page-audited` event and not two, and a URL that
        redirects to a page already paid for is not paid for twice.
        """
        if self.charge is None:
            return True
        if not self._is_billable(method, result):
            return True
        if self.charge_limit_reached:
            return False
        canonical = canonicalize_url(result.get("final_url") or url)
        if canonical in self._charged_urls:
            self.log(f"[budget] already paid for this page, not charging again: {canonical}")
            return True
        allowed = bool(self.charge())
        if allowed:
            self._charged_urls.add(canonical)
        else:
            self.charge_limit_reached = True
        return allowed

    def _request(self, url: str, method: str) -> dict:
        """Return {'status', 'error', 'final_url', 'html'}; html only on GET.

        The charge, when there is one, happens at the end of this method, once
        the response is known. Nothing the buyer cannot use is billed.
        """
        if self.charge is not None and self.charge_limit_reached:
            self.log(f"[budget] charge limit reached, not requesting {url}")
            return {"status": None, "error": CHARGE_LIMIT_ERROR, "final_url": url,
                    "html": None}
        self.requests_made += 1
        self._wait(url)
        try:
            response = self.session.request(
                method,
                url,
                timeout=self.timeout_seconds,
                allow_redirects=True,
                stream=(method == "GET"),
            )
        except requests.exceptions.SSLError as exc:
            return {"status": None, "error": f"ssl_error: {exc.__class__.__name__}",
                    "final_url": url, "html": None}
        except requests.exceptions.ConnectTimeout:
            return {"status": None, "error": "connect_timeout", "final_url": url,
                    "html": None}
        except requests.exceptions.ReadTimeout:
            return {"status": None, "error": "read_timeout", "final_url": url,
                    "html": None}
        except requests.exceptions.TooManyRedirects:
            return {"status": None, "error": "too_many_redirects", "final_url": url,
                    "html": None}
        except requests.exceptions.ConnectionError as exc:
            reason = "dns_or_connection_error"
            text = str(exc).lower()
            if "name or service not known" in text or "nodename nor servname" in text \
                    or "failed to resolve" in text or "getaddrinfo" in text:
                reason = "dns_error"
            return {"status": None, "error": reason, "final_url": url, "html": None}
        except requests.RequestException as exc:
            return {"status": None, "error": f"request_error: {exc.__class__.__name__}",
                    "final_url": url, "html": None}

        html = None
        try:
            if method == "GET":
                content_type = response.headers.get("Content-Type", "").lower()
                if "html" in content_type or not content_type:
                    # Cap the body we read: we only need the <a> tags, and we
                    # never store the body anywhere.
                    chunks, size = [], 0
                    for chunk in response.iter_content(65536, decode_unicode=False):
                        chunks.append(chunk)
                        size += len(chunk)
                        if size > 3_000_000:
                            break
                    encoding = response.encoding or "utf-8"
                    html = b"".join(chunks).decode(encoding, errors="replace")
        finally:
            response.close()

        result = {
            "status": response.status_code,
            "error": None,
            "final_url": response.url,
            "html": html,
        }
        if not self._charge_for_result(url, method, result):
            # The budget ran out on this very response. It was not paid for, so
            # it is not reported: the crawl loop sees the marker and stops.
            self.log(f"[budget] charge limit reached, dropping the response for {url}")
            return {"status": None, "error": CHARGE_LIMIT_ERROR,
                    "final_url": result["final_url"], "html": None}
        return result

    def _check_url(self, url: str) -> dict:
        """HEAD first, fall back to GET when HEAD is not usable."""
        if url in self._checked:
            return self._checked[url]
        if not self.robots.allowed(url):
            self.skipped_by_robots.add(url)
            result = {"status": None, "error": "skipped_disallowed_by_robots",
                      "final_url": url}
            self._checked[url] = result
            return result

        head = self._request(url, "HEAD")
        if head["error"] == CHARGE_LIMIT_ERROR:
            # Not checked and not paid for: keep it out of the results.
            return head
        status = head["status"]
        # Many servers answer HEAD with 403/405/501 or a 5xx even though a real
        # GET works, so those get one confirmation request. A 404 from HEAD is
        # taken at face value: retrying it would double the traffic on exactly
        # the most common case.
        if (status is None or status in (403, 405, 429, 501) or status >= 500) \
                and not self.charge_limit_reached:
            get = self._request(url, "GET")
            if get["error"] == CHARGE_LIMIT_ERROR:
                return get
            if get["status"] is not None or status is None:
                head = {"status": get["status"], "error": get["error"],
                        "final_url": get["final_url"]}
        result = {"status": head["status"], "error": head["error"],
                  "final_url": head["final_url"]}
        self._checked[url] = result
        return result

    # ----------------------------------------------------------------- parse

    @staticmethod
    def _extract_links(html: str, base_url: str) -> list[tuple[str, str]]:
        """Return (absolute_url, anchor_text) pairs. Nothing else is kept."""
        soup = BeautifulSoup(html, "html.parser")
        base_tag = soup.find("base", href=True)
        if base_tag:
            base_url = urljoin(base_url, base_tag["href"].strip())
        out: list[tuple[str, str]] = []
        for anchor in soup.find_all("a", href=True):
            href = anchor["href"].strip()
            if not href or href.startswith("#"):
                continue
            scheme = href.split(":", 1)[0].lower() if ":" in href else ""
            if scheme in SKIPPED_SCHEMES:
                continue
            absolute = canonical_url(urljoin(base_url, href))
            if urlparse(absolute).scheme not in ("http", "https"):
                continue
            text = " ".join(anchor.get_text(" ", strip=True).split())[:200]
            if not text:
                text = (anchor.get("title") or "").strip()[:200]
                if not text:
                    image = anchor.find("img")
                    if image is not None:
                        text = f"[image alt: {(image.get('alt') or '').strip()[:150]}]"
            out.append((absolute, text or "[no anchor text]"))
        return out

    # ------------------------------------------------------------------- run

    def run(self) -> AuditResult:
        started = time.time()
        start = canonical_url(self.start_url)
        queue: list[tuple[str, int]] = [(start, 0)]
        queued: set[str] = {start}
        # target url -> list of LinkRef
        references: dict[str, list[LinkRef]] = {}

        self.log(f"Start: {start}")
        self.log(
            f"Limits: maxPages={self.max_pages} maxDepth={self.max_depth} "
            f"delay={self.delay_seconds}s"
        )

        while queue and len(self.pages_visited) < self.max_pages:
            url, depth = queue.pop(0)
            # Everything that reaches the queue was canonicalised on the way
            # in; doing it again here means no caller can slip a second
            # spelling of a page past the visited set.
            url = canonical_url(url)
            if url in self._checked:
                continue
            if not self.robots.allowed(url):
                self.skipped_by_robots.add(url)
                self.log(f"[robots] skipped {url}")
                continue

            result = self._request(url, "GET")
            if result["error"] == CHARGE_LIMIT_ERROR:
                # Out of budget: stop the crawl and keep what was found.
                break
            self._checked[url] = {
                "status": result["status"],
                "error": result["error"],
                "final_url": result["final_url"],
            }
            self.pages_visited.append(
                {
                    "url": url,
                    "depth": depth,
                    "status": result["status"],
                    "error": result["error"],
                }
            )
            self.log(
                f"[{len(self.pages_visited)}/{self.max_pages}] d{depth} "
                f"{result['status'] or result['error']} {url}"
            )

            if not result["html"]:
                continue

            for target, text in self._extract_links(result["html"], result["final_url"]):
                self.links_seen += 1
                references.setdefault(target, []).append(LinkRef(url, text))
                if (
                    depth < self.max_depth
                    and target not in queued
                    and same_site(target, self.root_host, self.include_subdomains)
                    and looks_like_html(target)
                    and len(queued) < self.max_pages * 4
                ):
                    queued.add(target)
                    queue.append((target, depth + 1))

        # Check every referenced URL that the crawl itself did not already fetch.
        targets = [t for t in references if t not in self._checked]
        internal_targets = [
            t for t in targets if same_site(t, self.root_host, self.include_subdomains)
        ]
        external_targets = [t for t in targets if t not in set(internal_targets)]
        to_check = internal_targets + (external_targets if self.check_external_links else [])
        self.log(
            f"Checking {len(to_check)} link targets not visited by the crawl "
            f"({len(internal_targets)} internal, "
            f"{len(external_targets) if self.check_external_links else 0} external)"
        )
        for target in to_check:
            if self.charge_limit_reached:
                self.log(
                    f"[budget] charge limit reached, {len(to_check) - to_check.index(target)} "
                    "link targets left unchecked"
                )
                break
            self._check_url(target)

        broken = self._collect_broken(references)
        duration = round(time.time() - started, 1)
        summary = {
            "startUrl": self.start_url,
            "pagesVisited": len(self.pages_visited),
            "linksFound": self.links_seen,
            "uniqueTargets": len(references),
            "urlsChecked": sum(
                1 for info in self._checked.values()
                if info["error"] != CHARGE_LIMIT_ERROR
            ),
            "requestsCharged": self.requests_made,
            "chargeLimitReached": self.charge_limit_reached,
            "brokenLinks": len(broken),
            "uniqueBrokenTargets": len({row["brokenUrl"] for row in broken}),
            "skippedByRobots": len(self.skipped_by_robots),
            "maxPages": self.max_pages,
            "maxDepth": self.max_depth,
            "delaySeconds": self.delay_seconds,
            "durationSeconds": duration,
            "finishedAt": _now(),
        }
        self.log(
            f"Done in {duration}s: {summary['pagesVisited']} pages, "
            f"{summary['urlsChecked']} URLs checked, "
            f"{summary['brokenLinks']} broken link rows"
        )
        return AuditResult(
            broken_links=broken, summary=summary, pages_visited=list(self.pages_visited)
        )

    def _collect_broken(self, references: dict[str, list[LinkRef]]) -> list[dict]:
        rows: list[dict] = []
        checked_at = _now()
        for target, refs in references.items():
            info = self._checked.get(target)
            if info is None:
                continue  # external link, checking disabled
            status, error = info["status"], info["error"]
            if error == "skipped_disallowed_by_robots":
                continue
            if error == CHARGE_LIMIT_ERROR:
                # Never report an unchecked URL as broken: we did not look at it.
                continue
            is_broken = (status is not None and status >= 400) or (
                status is None and error is not None
            )
            if not is_broken:
                continue
            internal = same_site(target, self.root_host, self.include_subdomains)
            for ref in refs:
                rows.append(
                    {
                        "brokenUrl": target,
                        "statusCode": status,
                        "error": error,
                        "sourceUrl": ref.source_url,
                        "anchorText": ref.anchor_text,
                        "linkType": "internal" if internal else "external",
                        "checkedAt": checked_at,
                    }
                )
        rows.sort(key=lambda r: (r["linkType"], str(r["statusCode"]), r["brokenUrl"]))
        return rows


def audit_site(
    start_url: str,
    max_pages: int = 50,
    max_depth: int = 3,
    delay_seconds: float = 1.0,
    timeout_seconds: float = 15.0,
    check_external_links: bool = True,
    include_subdomains: bool = False,
    log: Callable[[str], None] = print,
    charge: Callable[[], bool] | None = None,
) -> AuditResult:
    return Auditor(
        start_url=start_url,
        max_pages=max_pages,
        max_depth=max_depth,
        delay_seconds=delay_seconds,
        timeout_seconds=timeout_seconds,
        check_external_links=check_external_links,
        include_subdomains=include_subdomains,
        log=log,
        charge=charge,
    ).run()


__all__: Iterable[str] = ("audit_site", "Auditor", "AuditResult", "USER_AGENT")
