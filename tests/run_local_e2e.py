"""End-to-end run of the Actor against a local test site.

Why this script exists
----------------------
The lab sandbox denies every socket bind (TCP and Unix: `PermissionError:
[Errno 1] Operation not permitted`), so `python -m http.server` cannot listen
and the Actor cannot be pointed at `http://127.0.0.1:<port>/` over a real
socket. Everything else in the run is the real thing: the real `src/main.py`
entry point, the real Apify Actor lifecycle (input, dataset, key-value store),
the real crawler in `src/link_auditor.py` and the real checks in
`src/page_checks.py`.

The only substitution is the transport underneath `requests`: a
`requests` adapter answers the crawler's HTTP requests from files on disk,
with real status codes, real headers and a real body. Every request it serves
is printed in the log, in the same shape `http.server` would print it, so the
log shows which URLs the crawler actually asked for.

Usage:
    python tests/run_local_e2e.py <site-dir> <run-dir> [port]
"""

from __future__ import annotations

import asyncio
import io
import json
import mimetypes
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests
from requests.adapters import BaseAdapter
from requests.structures import CaseInsensitiveDict

HERE = Path(__file__).resolve().parent
ACTOR_DIR = HERE.parent
sys.path.insert(0, str(ACTOR_DIR / "src"))


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%d/%b/%Y %H:%M:%S")


class LocalSiteAdapter(BaseAdapter):
    """Serves one directory over the `requests` API, without a socket."""

    def __init__(self, root: Path) -> None:
        super().__init__()
        self.root = root.resolve()
        self.served = 0

    def _resolve(self, path: str) -> Path | None:
        relative = unquote(path).lstrip("/")
        if not relative:
            relative = "index.html"
        candidate = (self.root / relative).resolve()
        if not str(candidate).startswith(str(self.root)):
            return None
        if candidate.is_dir():
            candidate = candidate / "index.html"
        return candidate if candidate.is_file() else None

    def send(self, request, stream=False, timeout=None, verify=True, cert=None,
             proxies=None):  # noqa: D102 - requests adapter interface
        path = urlparse(request.url).path
        target = self._resolve(path)
        if target is None:
            status, reason = 404, "File not found"
            body = b"<html><head><title>404</title></head><body>404</body></html>"
            content_type = "text/html"
        else:
            status, reason = 200, "OK"
            body = target.read_bytes()
            content_type = mimetypes.guess_type(target.name)[0] or "text/html"
            if content_type.startswith("text/"):
                content_type += "; charset=utf-8"

        response = requests.Response()
        response.status_code = status
        response.reason = reason
        response.url = request.url
        response.request = request
        response.encoding = "utf-8"
        response.headers = CaseInsensitiveDict(
            {
                "Server": "local-file-adapter/1.0 (no socket: sandbox denies bind)",
                "Content-Type": content_type,
                "Content-Length": str(len(body)),
            }
        )
        response.raw = io.BytesIO(b"" if request.method == "HEAD" else body)
        self.served += 1
        print(
            f'[local-site] 127.0.0.1 - - [{stamp()}] "{request.method} {path} '
            f'HTTP/1.1" {status} {len(body)}',
            flush=True,
        )
        return response

    def close(self) -> None:
        return None


def install_adapter(base_url: str, root: Path) -> LocalSiteAdapter:
    adapter = LocalSiteAdapter(root)
    prefix = base_url.rstrip("/")
    original_get_adapter = requests.Session.get_adapter

    def get_adapter(self, url):  # noqa: ANN001 - patching requests
        if url.startswith(prefix):
            return adapter
        return original_get_adapter(self, url)

    requests.Session.get_adapter = get_adapter
    return adapter


def main() -> int:
    site_dir = Path(sys.argv[1]).resolve()
    run_dir = Path(sys.argv[2]).resolve()
    port = sys.argv[3] if len(sys.argv) > 3 else "8099"
    base_url = f"http://127.0.0.1:{port}/"

    actor_input = {
        "startUrl": base_url,
        "maxPages": 10,
        "maxDepth": 2,
        "requestDelaySeconds": 0,
        "requestTimeoutSeconds": 15,
    }

    input_dir = run_dir / "storage" / "key_value_stores" / "default"
    input_dir.mkdir(parents=True, exist_ok=True)
    (input_dir / "INPUT.json").write_text(json.dumps(actor_input, indent=2))
    os.chdir(run_dir)

    print(f"Actor dir: {ACTOR_DIR}")
    print(f"Site dir:  {site_dir}")
    print(f"Run dir:   {run_dir}")
    print(f"Serving {base_url} from disk (sandbox denies socket bind, so the "
          "HTTP transport under `requests` is a local file adapter).")
    print("Files on the test site: "
          + ", ".join(sorted(p.name for p in site_dir.glob('*.html'))))
    print(f"Actor input: {json.dumps(actor_input)}")
    print("-" * 72, flush=True)

    adapter = install_adapter(base_url, site_dir)

    import main as actor_main  # noqa: PLC0415 - after sys.path setup

    # `Actor.exit()` ends the process with its own exit code; catching it here
    # lets the script print what the run wrote to the storages.
    actor_exit_code = 0
    try:
        asyncio.run(actor_main.main())
    except SystemExit as exc:
        actor_exit_code = 0 if exc.code is None else int(exc.code)

    print("-" * 72, flush=True)
    print(f"Actor lifecycle exit code: {actor_exit_code}")
    print(f"HTTP requests served by the local site: {adapter.served}")

    dataset_dir = run_dir / "storage" / "datasets" / "default"
    rows = []
    for item in sorted(dataset_dir.glob("[0-9]*.json")):
        rows.append(json.loads(item.read_text()))
    print(f"Dataset rows written: {len(rows)}")
    for row in sorted(rows, key=lambda r: str(r.get("url") or "")):
        print(json.dumps(row, ensure_ascii=False, sort_keys=True))

    kvs_dir = run_dir / "storage" / "key_value_stores" / "default"
    summary_file = kvs_dir / "SUMMARY"
    if not summary_file.is_file():
        summary_file = kvs_dir / "SUMMARY.json"
    if summary_file.is_file():
        print("SUMMARY record:")
        print(json.dumps(json.loads(summary_file.read_text()), indent=2,
                         ensure_ascii=False))
    else:
        print(f"SUMMARY record not found at {summary_file}")
    return actor_exit_code


if __name__ == "__main__":
    sys.exit(main())
