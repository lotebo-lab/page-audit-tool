"""Page Audit Tool Actor package.

`page_checks` holds the per-page checks (pure, testable offline).
`link_auditor` is the crawler shared with the Broken Link Auditor.
`main` is the Apify entry point, exposed as a module so the Apify CLI can run
the Actor with `python -m src`.
"""
