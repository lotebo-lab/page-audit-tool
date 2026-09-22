"""Apify Actor entry point: Page Audit Tool.

Input is a domain. The Actor crawls the site by following internal links and
pushes one dataset item per page with the technical SEO and accessibility
problems found in that page's HTML.

The crawler is the one from the Broken Link Auditor (`link_auditor.py`, no
Apify dependency, robots.txt always honoured, requests spaced by a delay). The
only change here is a hook that hands each page's HTML to `page_checks.check_page`
before the HTML is discarded. Link checking is switched off: this Actor never
requests a URL it is not going to audit.
"""

from __future__ import annotations

import asyncio

from apify import Actor

try:  # running inside the Actor image (python src/main.py)
    from link_auditor import CHARGE_LIMIT_ERROR, Auditor
    from page_checks import check_page, summarize
    from summary_row import SUMMARY_ROW_TYPE, build_dataset_rows
    from url_canonical import canonicalize_url
except ImportError:  # running as a package (python -m src.main)
    from .link_auditor import CHARGE_LIMIT_ERROR, Auditor
    from .page_checks import check_page, summarize
    from .summary_row import SUMMARY_ROW_TYPE, build_dataset_rows
    from .url_canonical import canonicalize_url

# Pay-per-event. One `page-audited` event per page row in the dataset, and
# nothing else: the event is charged in `PageAuditCrawler._write_row`, at the
# moment the row is added, so an HTTP error, a body that is not HTML, a URL
# blocked by robots.txt or a connection failure costs the buyer zero. Plus one event for the run summary,
# charged only when there is at least one page row. `actor-start` is charged by
# Apify itself, never in code.
PAGE_EVENT = "page-audited"
REPORT_EVENT = "site-report"

# Hard ceiling for one charge round trip. Every charge is an HTTP call to the
# Apify API, so it can hang. It must never hold a run hostage: run
# dDAxrKSafjiCYssUa finished its work in 4.2 s and then sat for exactly 60.1 s
# waiting on the `site-report` charge before giving up. Short ceiling, warning
# in the log, run keeps going.
CHARGE_TIMEOUT_SECONDS = 5.0

DEFAULTS = {
    "startUrl": None,
    "maxPages": 25,
    "maxDepth": 3,
    "requestDelaySeconds": 1.0,
    "requestTimeoutSeconds": 15,
}


def apply_charge_result(state: dict, charge_result, log=print) -> bool:
    """Read one `Actor.charge` answer. True means: the row may be written.

    `event_charge_limit_reached` can come back True on the very call that
    charged the event (`charged_count=1`): it says no *further* event fits the
    run's budget, not that this one was refused. The SDK does exactly that in
    a local pay-per-event run. Treating that answer as a refusal dropped a row
    the buyer had just paid for, so the charged count decides here, and the
    limit flag only stops the next page.
    """
    if charge_result is None:
        state["failures"] += 1
        return True
    charged = int(charge_result.charged_count or 0)
    if charge_result.event_charge_limit_reached and not state["limit_reached"]:
        state["limit_reached"] = True
        log(
            "Charge limit reached, stopping the crawl and keeping "
            "everything audited so far."
        )
    if charged >= 1:
        state["charged"] += charged
        return True
    if charge_result.event_charge_limit_reached:
        return False
    state["failures"] += 1
    return True


class PageAuditCrawler(Auditor):
    """The link crawler, with link checking off and one row per audited page.

    Billing lives here, in `_write_row`, and nowhere else. The base crawler is
    built with `charge=None`, so it never bills a request; this class charges
    one `page-audited` event at the exact moment a page row is added to
    `self.rows`, which is the list main() pushes to the dataset. One row, one
    charge; no row, no charge.
    """

    def __init__(self, charge_page=None, **kwargs) -> None:
        # `charge=None` on purpose: the request layer must not bill anything.
        kwargs.pop("charge", None)
        super().__init__(check_external_links=False, charge=None, **kwargs)
        # Callable returning True when the event was accepted and False when
        # the run's charge limit has been reached. None means "do not bill"
        # (local runs, runs that are not pay per event).
        self._charge_page = charge_page
        self.rows: list[dict] = []
        self._audited: set[str] = set()
        self.pages_charged = 0

    def _check_url(self, url: str) -> dict:
        # This Actor audits pages, it does not check link targets: never spend
        # a request (or a charge) on a URL that produces no dataset row.
        return {"status": None, "error": "not_checked_page_audit", "final_url": url}

    def _is_billable(self, method: str, result: dict) -> bool:
        """True only for a response that becomes a page row in the dataset.

        That is a GET that reached the server, answered 2xx and carried an
        HTML body. Everything else produces no row and so costs nothing:
        HTTP errors (404, 500, ...), a 200 whose body is not HTML
        (`application/pdf`, `application/json`, ...), a 3xx left without
        content, connection errors, timeouts and SSL failures. URLs blocked
        by robots.txt are never requested at all.
        """
        status = result.get("status")
        return (
            method == "GET"
            and result.get("error") is None
            and bool(result.get("html"))
            and status is not None
            and 200 <= int(status) < 300
        )

    def _request(self, url: str, method: str) -> dict:
        result = super()._request(url, method)
        if not self._is_billable(method, result):
            return result
        # The row is keyed by the canonical final URL, so the same page under
        # two spellings, or a redirect to a page already audited, is one row
        # and one charge.
        page_url = canonicalize_url(result.get("final_url") or url)
        if not self._write_row(page_url, result.get("status"), result["html"]):
            # The budget ran out on this very page: it was not paid for, so it
            # is not reported, and the crawl loop sees the marker and stops.
            self.charge_limit_reached = True
            self.log(f"[budget] charge limit reached, dropping the page {page_url}")
            return {"status": None, "error": CHARGE_LIMIT_ERROR,
                    "final_url": result.get("final_url") or url, "html": None}
        return result

    def _write_row(self, url: str, status: int | None, html: str) -> bool:
        """Audit one page, charge `page-audited` once and add its row.

        Returns False only when the charge limit refused the event; the row
        is then not added. A page already audited adds nothing and costs
        nothing.
        """
        if url in self._audited:
            self.log(f"[skip] already audited this page: {url}")
            return True
        row = check_page(url, status, html)
        if self._charge_page is not None:
            if self.charge_limit_reached or not self._charge_page():
                return False
            self.pages_charged += 1
        self._audited.add(url)
        self.rows.append(row)
        self.log(f"[{len(self.rows)}] {row['issueCount']} issue(s) {url}")
        return True


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}
        options = {**DEFAULTS, **{k: v for k, v in actor_input.items() if v is not None}}

        start_url = options["startUrl"]
        if not start_url:
            raise ValueError("Input field 'startUrl' is required (a domain or a URL).")

        Actor.log.info(f"Auditing pages of {start_url}")

        loop = asyncio.get_running_loop()
        charge_state = {"limit_reached": False, "charged": 0, "failures": 0}

        pricing = Actor.get_charging_manager().get_pricing_info()
        is_pay_per_event = pricing.is_pay_per_event
        if not is_pay_per_event:
            Actor.log.info(
                "This run is not billed per event (pricing model: "
                f"{pricing.pricing_model}). Auditing without charging."
            )

        def _apply(event_name: str, charge_result) -> bool:
            return apply_charge_result(charge_state, charge_result, Actor.log.info)

        async def charge_async(event_name: str) -> bool:
            """Charge one event from inside the Actor event loop."""
            if not is_pay_per_event or charge_state["limit_reached"]:
                return not charge_state["limit_reached"]
            try:
                result = await asyncio.wait_for(
                    Actor.charge(event_name=event_name),
                    timeout=CHARGE_TIMEOUT_SECONDS,
                )
            except asyncio.TimeoutError:
                Actor.log.warning(
                    f"Charging {event_name} timed out after "
                    f"{CHARGE_TIMEOUT_SECONDS:.0f}s; continuing the run."
                )
                result = None
            except Exception as exc:  # noqa: BLE001 - never kill a paid run
                Actor.log.warning(f"Could not charge {event_name}: {exc}")
                result = None
            return _apply(event_name, result)

        def charge(event_name: str) -> bool:
            """Charge one event from the crawl worker thread.

            Never call this from the event loop thread: `run_coroutine_threadsafe`
            schedules the coroutine on `loop` and then blocks the calling thread
            until it answers. Called from the loop's own thread that is a
            deadlock, and the only way out is the timeout below. That is exactly
            how run dDAxrKSafjiCYssUa lost its `site-report` charge and 60 s of
            wall clock. The report charge now goes through `charge_async`.
            """
            if not is_pay_per_event:
                return True
            if charge_state["limit_reached"]:
                return False
            future = asyncio.run_coroutine_threadsafe(
                charge_async(event_name), loop
            )
            try:
                return future.result(timeout=CHARGE_TIMEOUT_SECONDS + 2)
            except Exception as exc:  # noqa: BLE001 - never kill a paid run
                future.cancel()
                charge_state["failures"] += 1
                Actor.log.warning(f"Could not charge {event_name}: {exc}")
                return True

        rows: list[dict] = []

        # Filled by the crawl thread with the crawler's own totals (pages
        # visited, URLs skipped by robots.txt, duration). The summary row needs
        # them, and until now the result of the crawl was thrown away.
        crawl_summary: dict = {}

        def run_crawl() -> None:
            crawler = PageAuditCrawler(
                charge_page=(lambda: charge(PAGE_EVENT)) if is_pay_per_event else None,
                start_url=start_url,
                max_pages=int(options["maxPages"]),
                max_depth=int(options["maxDepth"]),
                delay_seconds=float(options["requestDelaySeconds"]),
                timeout_seconds=float(options["requestTimeoutSeconds"]),
                log=Actor.log.info,
            )
            result = crawler.run()
            # Every row here was charged exactly once in `_write_row` (when
            # the run is pay per event), and nothing else was.
            rows.extend(crawler.rows)
            crawl_summary.update(result.summary)

        # The crawl is synchronous and paced by a delay, so it runs in a worker
        # thread to keep the Actor event loop responsive.
        await asyncio.to_thread(run_crawl)

        # The report is only charged when there is a page report to charge for,
        # and it is charged here, before the dataset is written, so the number
        # the summary row states is the number the buyer was billed. Adding the
        # summary row itself charges nothing: every charge in this Actor is
        # decided above this line.
        if rows and is_pay_per_event and not charge_state["limit_reached"]:
            # Awaited, not handed back to the loop we are already running on.
            await charge_async(REPORT_EVENT)

        summary = {
            "startUrl": start_url,
            **summarize(rows),
            "pagesCrawled": crawl_summary.get("pagesVisited", len(rows)),
            "pagesSkippedByRobots": crawl_summary.get("skippedByRobots", 0),
            "durationSeconds": crawl_summary.get("durationSeconds", 0),
            "finishedAt": crawl_summary.get("finishedAt"),
            "chargedEvents": charge_state["charged"],
            "chargeLimitReached": charge_state["limit_reached"],
            "chargeFailures": charge_state["failures"],
        }

        # A successful run always writes at least the summary row. A site whose
        # pages are clean used to hand back an empty dataset, which reads
        # exactly like an Actor that never ran. The summary row says, in the
        # dataset itself, what was crawled and that nothing was wrong. A run
        # with no page row charges nothing at all: no `page-audited`, because
        # no page was auditable, and no `site-report`, because of the gate
        # above.
        dataset_rows = build_dataset_rows(rows, summary)
        await Actor.push_data(dataset_rows)
        Actor.log.info(
            f"Wrote {len(dataset_rows)} row(s) to dataset "
            f"{Actor.configuration.default_dataset_id} "
            f"({len(rows)} page row(s) plus 1 '{SUMMARY_ROW_TYPE}' row)"
        )

        await Actor.set_value("SUMMARY", summary)
        Actor.log.info(
            f"Finished: {summary['pagesAudited']} pages audited, "
            f"{summary['pagesWithIssues']} with at least one issue, "
            f"{summary['totalIssues']} issues in total."
        )


if __name__ == "__main__":
    asyncio.run(main())
