"""One spelling per page: URL canonicalisation for the Page Audit Tool.

Why this module exists
----------------------
The local run of 20/09/2026 (`logs/corrida-local-2026-09-20.log`) audited
`http://127.0.0.1:8099/` and `http://127.0.0.1:8099/index.html` as two pages.
They are the same document: two dataset rows, and two `page-audited` charges,
for one page. Charging a buyer for work that was not done is a reason to be
taken off the Apify Store, so the crawler now reduces every URL to one
canonical spelling **before it is queued** and **before it is charged**.

The rule of the module: only collapse two URLs when the server is bound to
answer both with the same document. When there is any chance the two URLs are
two different pages, keep them apart. A duplicated row is a bug; a page that
never gets audited is a worse bug.

Each decision below is written out with the reason it is (or is not) the same
page. `canonicalize_url` is pure and has no network and no Apify dependency.
"""

from __future__ import annotations

from urllib.parse import (
    parse_qsl,
    quote,
    unquote,
    urlencode,
    urlsplit,
    urlunsplit,
)

# Filenames a web server serves when the request is for the directory itself.
# Apache calls it DirectoryIndex, nginx calls it index, IIS calls it the default
# document; in all of them, a request for `/docs/` and a request for
# `/docs/index.html` are answered by the same file.
# Only these four are collapsed: they are the defaults shipped by the servers.
# `default.aspx`, `default.asp`, `home.html` and friends are NOT in the list,
# because serving them at the directory URL is a per-site configuration we
# cannot see from the outside, and guessing would merge two pages that may well
# be different.
DIRECTORY_INDEX_FILES = ("index.html", "index.htm", "index.php", "default.html")

# Query keys that only tag where a visit came from. They are read by analytics
# code in the browser, after the server already answered, so two URLs that
# differ only in these keys are one page and must cost one `page-audited`
# event. The list is deliberately short: `utm` and `utm_*`, which is what the
# defect report named. `gclid` and `fbclid` are NOT dropped, because nobody
# asked for them and each extra key in this list is one more chance of merging
# two pages that are really two.
def _is_tracking_key(key: str) -> bool:
    lowered = key.lower()
    return lowered == "utm" or lowered.startswith("utm_")

# Port that is already implied by the scheme. `http://host:80/x` and
# `http://host/x` are byte-for-byte the same request on the wire.
DEFAULT_PORTS = {"http": "80", "https": "443"}


def _clean_path_segments(path: str) -> list[str]:
    """Resolve `.` and `..` inside the path.

    `/a/./b` and `/a/c/../b` are resolved by every server (and by every browser
    before the request is even sent) to `/a/b`: same page. Relative links in
    real HTML produce these all the time, so resolving them here keeps one
    document from being queued two or three times.
    """
    segments: list[str] = []
    for segment in path.split("/"):
        if segment == ".":
            continue
        if segment == "..":
            if segments:
                segments.pop()
            continue
        segments.append(segment)
    return segments


def _normalize_percent_encoding(value: str, safe: str) -> str:
    """Re-encode a path or a query value in a single, stable form.

    `%7Euser` and `~user` are the same byte sequence for the server: the
    percent-encoded form is decoded before routing. Unquoting and re-quoting
    with a fixed `safe` set means the two spellings produce one string. Bytes
    that really need encoding (space, accents, `?`, `#`) stay encoded, so no
    URL is broken by this step.
    """
    return quote(unquote(value), safe=safe)


def canonicalize_url(url: str) -> str:
    """Return the one spelling used to queue, to audit and to charge a page.

    Same page (collapsed):
      * `HTTP://Example.COM/a` and `http://example.com/a`
        The scheme and the host are case-insensitive by definition (RFC 3986),
        so the server cannot tell the two apart.
      * `http://host:80/a` and `http://host/a`
        The default port is implied; the request on the wire is identical.
      * `/` and `/index.html`, `/docs/` and `/docs/index.php`
        The directory index file is what the server returns for the directory
        URL. This is the defect this module was written for.
      * `/pagina/` and `/pagina`
        Servers answer one of the two with a redirect to the other, so the
        buyer ends up on a single document either way. Auditing both would
        charge twice for one page. The site root keeps its `/`, because an
        empty path is not a valid request target.
      * `/a/./b` and `/a/c/../b`
        Dot segments are resolved before the request leaves the client.
      * `?b=2&a=1` and `?a=1&b=2`
        Every server framework we target parses the query into a map, so the
        order of the keys is not part of the identity of the page. The pairs
        are sorted by key and then by value; a repeated key keeps all of its
        values, because dropping one could change the response.
      * `/a#secao` and `/a`
        The fragment is never sent to the server. It selects a position inside
        a document that was already fetched, so it can never be a second page.
      * `/a?` and `/a`
        An empty query string is the same request as no query string.
      * `/?utm=x` and `/`, `/a?utm_source=x&b=1` and `/a?b=1`
        A campaign tag is read by analytics code in the browser, after the
        server has already answered: it selects no document, so it can never be
        a second page. Only `utm` and `utm_*` are dropped.

    NOT the same page (kept apart):
      * `/a` and `/b`, `/pagina` and `/pagina/sub`
        Different paths are different documents. The trailing-slash rule above
        only removes a slash at the very end; it never removes a segment.
      * `?a=1` and `?a=2`
        Same key, different value: the value is what the server reads.
      * `?a=1` and `?a=1&b=2`
        An extra parameter can change the response (a page number, a filter).
      * `/Pagina` and `/pagina`
        Path comparison is case-sensitive in RFC 3986 and on every case-
        sensitive filesystem. Lowercasing would merge two real pages on Linux
        hosting, so only the host is lowercased.
      * `http://host/a` and `https://host/a`
        Different scheme, and an audit of the http version is a real finding
        (mixed content, missing redirect). Merging them would hide it.
      * `host/a` and `www.host/a`
        The `www` host may serve something else entirely. Whether they belong
        to the same crawl is decided by `same_site` in `link_auditor.py`, not
        here; this function never rewrites the host name.
      * `?page=2`, `?ref=x`, `?lang=pt` and no query at all
        Any parameter that is not a `utm` tag can change the response (a page
        number, a filter, a language). We are auditing the customer's own site,
        and silently skipping one of their URLs is worse than one extra row, so
        every other parameter is only reordered, never dropped.
    """
    if url is None:
        raise ValueError("canonicalize_url got None")
    parts = urlsplit(str(url).strip())

    scheme = parts.scheme.lower()

    # Host is case-insensitive; userinfo and port are kept as given, minus the
    # default port. A blank host (relative URL) is left blank: this function
    # canonicalises, it does not resolve relative links.
    host = (parts.hostname or "").lower()
    netloc = ""
    if host:
        if parts.username:
            credentials = parts.username
            if parts.password:
                credentials += ":" + parts.password
            netloc += credentials + "@"
        netloc += host
        port = None
        try:
            port = parts.port
        except ValueError:
            # Malformed port: keep the netloc as the server sent it rather
            # than invent one.
            netloc = parts.netloc
            port = None
        if port is not None and str(port) != DEFAULT_PORTS.get(scheme):
            netloc += f":{port}"

    path = parts.path
    if not path:
        # No path at all means the site root.
        path = "/"

    segments = _clean_path_segments(path)

    # Trailing slash first: a trailing slash is an empty last segment, and
    # dropping it here means `/docs/`, `/docs`, `/docs/index.html` and
    # `/index.html/` all reach the index rule in the same shape.
    while len(segments) > 1 and segments[-1] == "":
        segments.pop()

    # Directory index: the last segment is dropped, leaving the directory it
    # lives in. `/index.html` -> `/`, `/docs/index.php` -> `/docs`.
    if segments and segments[-1].lower() in DIRECTORY_INDEX_FILES:
        segments.pop()

    # `safe` is the set of characters RFC 3986 allows inside a path segment
    # unencoded, minus `/`, which is the separator we just split on.
    path = "/".join(
        _normalize_percent_encoding(s, safe="!$&'()*+,;=:@") for s in segments
    )
    if not path.startswith("/"):
        path = "/" + path

    # Query: drop the campaign tags, keep every other pair, sort them, and
    # re-encode them the same way. `keep_blank_values=True` so that `?debug=`
    # survives: a blank value is still a parameter the server can read.
    if parts.query:
        pairs = [
            pair
            for pair in parse_qsl(parts.query, keep_blank_values=True)
            if not _is_tracking_key(pair[0])
        ]
        pairs.sort(key=lambda pair: (pair[0], pair[1]))
        query = urlencode(pairs, doseq=False)
    else:
        query = ""

    # Fragment always dropped: it never reaches the server.
    return urlunsplit((scheme, netloc, path, query, ""))


def same_page(first: str, second: str) -> bool:
    """True when two URLs are one page for billing and for the dataset."""
    return canonicalize_url(first) == canonicalize_url(second)


__all__ = ("canonicalize_url", "same_page", "DIRECTORY_INDEX_FILES")
