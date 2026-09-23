# SEO Audit and Accessibility Crawler: Alt Text, Meta Tags, Headings

**Run it on the Apify Store: https://apify.com/lotebo-lab/page-audit-tool**

You need to know which pages of a site are missing alt text, a title, a meta description or a canonical link. A browser extension checks one page at a time, and that does not work once the site has hundreds of pages.

Give this Actor a domain. It crawls the site page by page, with no sitemap and no URL list needed, and returns one row per page with twelve technical SEO and HTML accessibility checks, plus a short list of plain sentences saying what to fix on that page.

**It measures the technical rules a program can check in HTML source. An automated audit does not attest conformity with WCAG, with Directive (EU) 2019/882 (the European Accessibility Act) or with any search engine guideline.** See "Automated checks are not a statement of legal conformity" below.

This repository holds the source code. The Actor runs on the Apify platform, so there is nothing to install and nothing to host.

## Use cases

Each page below is a ready-made run of this Actor: it shows the input used, the fields that come back, and a Run button. The same page is served as Markdown by adding `.md` to the URL.

| question | page |
|---|---|
| Which pages on my site have no title or meta description? | https://apify.com/lotebo-lab/page-audit-tool/examples/find-pages-missing-title-and-meta-description |
| Which pages on my site have no meta description? | https://apify.com/lotebo-lab/page-audit-tool/examples/find-pages-missing-meta-description |
| How do I find every image with missing alt text on a website? | https://apify.com/lotebo-lab/page-audit-tool/examples/find-images-missing-alt-text |
| How do I list every image missing alt text on my site? | https://apify.com/lotebo-lab/page-audit-tool/examples/list-images-without-alt-text-on-a-site |
| Which pages have no H1 or a broken heading order? | https://apify.com/lotebo-lab/page-audit-tool/examples/find-pages-with-no-h1-or-broken-heading-order |
| Which accessibility defects can I find automatically? | https://apify.com/lotebo-lab/page-audit-tool/examples/european-accessibility-act-website-check |
| What data goes into an SEO audit report for a client? | https://apify.com/lotebo-lab/page-audit-tool/examples/white-label-seo-audit-report-for-clients |
| How do I check a site for SEO defects before it goes live? | https://apify.com/lotebo-lab/page-audit-tool/examples/check-a-site-for-seo-defects-before-launch |

Who runs it: agencies and freelancers taking over a site, who need the defect list of the whole site before quoting the work; in-house marketing and content teams doing a periodic technical pass, where missing titles across a section matter more than one perfect page; developers preparing an accessibility review, who want the machine-checkable defects listed by page so the human review starts where the problems are; and anyone after a migration, when templates changed and nobody knows which pages lost their canonical link.

## What goes in

These are the fields of [`.actor/input_schema.json`](.actor/input_schema.json), with the defaults and the ranges the schema declares.

| field | type | default | range |
|---|---|---|---|
| `startUrl` (required) | string | — | a bare domain (`example.com`, `https://` is assumed) or a full URL |
| `maxPages` | integer | 25 | 1 to 5000; each page opened is one charged event |
| `maxDepth` | integer | 3 | 0 to 20 clicks from the start page; 0 audits only the start page |
| `requestDelaySeconds` | integer | 1 | 0 to 60 seconds between two requests to the same host |
| `requestTimeoutSeconds` | integer | 15 | 3 to 120 seconds before a page is reported as a timeout |

An example input, using the value the schema prefills for `startUrl`:

```json
{
  "startUrl": "https://www.python.org",
  "maxPages": 25,
  "maxDepth": 3
}
```

Start with ten pages whose problems you already know, and compare the rows with what you would find by hand.

## What comes out

One dataset row per page that answered with an HTML body, plus one run summary row. These are the fields declared in [`.actor/dataset_schema.json`](.actor/dataset_schema.json), which is the schema the Apify Console renders as the output table, and they are checked against what the code writes by `tests/test_schemas.py`.

| field | type | what it holds |
|---|---|---|
| `rowType` | string | tells a page row from the run summary row |
| `url` | string | the page URL after redirects, in one normalised spelling |
| `status` | integer or null | the HTTP status of the page; `null` when there was no response |
| `title` | string or null | the text of `<title>`, `null` when the page has none |
| `titleLength` | integer | characters in the title, 0 when it is missing |
| `titleMissing` | boolean | `true` when there is no title text |
| `metaDescription` | string or null | the content of `<meta name="description">` |
| `metaDescriptionMissing` | boolean | `true` when the page has none |
| `h1Count` | integer | how many `<h1>` headings the page has |
| `headingOrderBroken` | boolean | `true` when the headings do not start at `h1` or a level is skipped (`h2` straight to `h4`) |
| `imagesWithoutAlt` | integer | `<img>` tags with no `alt`, or an `alt` containing only spaces. An explicit `alt=""` marks a decorative image and is not counted |
| `formFieldsWithoutLabel` | integer | `input`, `select` and `textarea` controls with no `<label for=...>`, no wrapping `<label>`, no `aria-label`, no `aria-labelledby` and no `title`. Hidden, submit, button, reset and image inputs are skipped |
| `canonical` | string or null | the `href` of `<link rel="canonical">` |
| `canonicalMissing` | boolean | `true` when there is no canonical link |
| `issues` | array of strings | one short sentence per problem found on this page; empty when the page passed every check |
| `issueCount` | integer | how many entries `issues` has |

The run summary row carries `startUrl`, `pagesCrawled`, `pagesAudited`, `pagesSkippedByRobots`, `pagesWithIssues`, `totalIssues`, `pagesWithoutH1`, `pagesWithMultipleH1`, `pagesWithBrokenHeadingOrder`, `durationSeconds`, `chargedEvents`, `chargeLimitReached`, `chargeFailures`, `finishedAt` and a one-sentence `message`.

The dataset ships four ready-made views, declared in the same schema: **Page audit** (the row above, trimmed), **SEO fields**, **Accessibility fields** and **Run summary**. Every run also writes a `SUMMARY` record in the key-value store with the same totals plus `worstPages`, up to ten pages with their issue list.

### The twelve checks behind those fields

This is the complete list, and there is nothing else in the code. Each one has a test in `tests/test_page_checks.py`.

| # | check | reported when | field |
|---|---|---|---|
| 1 | HTTP status | the page answered 400 or above: `page returned HTTP 404` | `status` |
| 2 | Title present | no `<title>` text: `missing <title>` | `titleMissing` |
| 3 | Title too long | over 60 characters: `title is 74 characters, over 60` | `titleLength` |
| 4 | Title too short | under 15 characters: `title is only 5 characters` | `titleLength` |
| 5 | Meta description present | no meta description with content: `missing meta description` | `metaDescriptionMissing` |
| 6 | Meta description too long | over 160 characters | `metaDescription` |
| 7 | H1 present | no `<h1>`: `no h1 on the page` | `h1Count` |
| 8 | One H1 only | more than one `<h1>`: `2 h1 headings, expected 1` | `h1Count` |
| 9 | Heading order | levels skipped or not starting at `h1` | `headingOrderBroken` |
| 10 | Image alt text | `3 image(s) without alt text` | `imagesWithoutAlt` |
| 11 | Form field labels | `2 form field(s) without a label` | `formFieldsWithoutLabel` |
| 12 | Canonical link | `missing canonical link` | `canonicalMissing` |

### Real output rows

Copied from `logs/corrida-local-2026-09-20-canonico.log`: an end-to-end run of `src/main.py` against a five page test site whose defects were planted on purpose, served from disk at `127.0.0.1:8099` because the build sandbox has no route to the public internet. The run audited 5 pages and found 9 issues.

A clean page, so you can see what "nothing wrong" looks like:

```json
{"url": "http://127.0.0.1:8099/", "status": 200, "title": "Clean page for the local audit test", "titleLength": 35, "titleMissing": false, "metaDescription": "A page with a title, a meta description, one h1, headings in order, an image with alt text and a labelled form field.", "metaDescriptionMissing": false, "h1Count": 1, "headingOrderBroken": false, "imagesWithoutAlt": 0, "formFieldsWithoutLabel": 0, "canonical": "http://127.0.0.1:8099/index.html", "canonicalMissing": false, "issues": [], "issueCount": 0}
```

The worst page of the same run, five issues in one row:

```json
{"url": "http://127.0.0.1:8099/headings-fora-de-ordem.html", "status": 200, "title": "Short", "titleLength": 5, "titleMissing": false, "metaDescription": null, "metaDescriptionMissing": true, "h1Count": 0, "headingOrderBroken": true, "imagesWithoutAlt": 0, "formFieldsWithoutLabel": 0, "canonical": null, "canonicalMissing": true, "issues": ["title is only 5 characters", "missing meta description", "no h1 on the page", "heading levels are out of order", "missing canonical link"], "issueCount": 5}
```

A page with images and a form field:

```json
{"url": "http://127.0.0.1:8099/imagem-sem-alt.html", "status": 200, "title": "Page with images that have no alt text", "titleLength": 38, "titleMissing": false, "metaDescription": "Two images without an alt attribute and one form field with no label of any kind.", "metaDescriptionMissing": false, "h1Count": 1, "headingOrderBroken": false, "imagesWithoutAlt": 2, "formFieldsWithoutLabel": 1, "canonical": "http://127.0.0.1:8099/imagem-sem-alt.html", "canonicalMissing": false, "issues": ["2 image(s) without alt text", "1 form field(s) without a label"], "issueCount": 2}
```

## Price

Pay per event, two events. These are the prices in force on the platform, so they are what a run of yours is charged:

| event | price | when it is charged |
|---|---|---|
| `page-audited` | US$ 0.05 | once per audit row written to your dataset: an HTML page that answered 2xx and was checked. The same page in two URL spellings (`/` and `/index.html`) is charged once. HTTP errors, non-HTML files, redirects without content and pages blocked by `robots.txt` are not charged |
| `site-report` | US$ 0.25 | once per run, and only when at least one page was audited |

A run of 25 pages is 25 `page-audited` events plus 1 `site-report`: US$ 1.50. Apify charges its own Actor start event and the platform usage of the run on top of this; that part is set by the platform, not by this Actor. If a run reaches the pay-per-event limit you set, the crawl stops, keeps everything audited so far, and the `site-report` is not charged.

## What this Actor does not do

- **It does not run JavaScript.** It reads the HTML the server returns, so content drawn by a script is not seen and a page built entirely in the browser looks empty to it.
- **It does not measure colour contrast.** There is no contrast checker in the code.
- **It does not check focus order, keyboard navigation or ARIA roles**, beyond looking for `aria-label` and `aria-labelledby` when deciding whether a form field has a name.
- **It does not read alt text for meaning.** It counts images without an `alt`; it cannot tell you whether an existing alt text describes the image.
- **It does not compare pages with each other**, so duplicate titles and duplicate meta descriptions across pages are not reported.
- **It does not report redirect chains.** Redirects are followed and only the final URL is kept.
- **It does not check whether links work.** Link targets are never requested; that is a different tool.
- **It does not audit PDFs, images or any other non-HTML file**, and it does not follow links to them.
- **It does not crawl past the caps.** It stops at `maxPages` or `maxDepth`, whichever comes first, pages nobody links to from the start URL are never found, and it does not follow subdomains.
- **It does not log in, fill forms, solve captchas or get past a paywall.**
- **It does not predict rankings, traffic or revenue, and it makes no claim about any of them.**
- **It does not collect personal data.** The output holds page URLs, statuses, tag text, counts and the canonical URL. Page bodies are parsed in memory and discarded; `mailto:` and `tel:` links are skipped.

## Automated checks are not a statement of legal conformity

This Actor measures technical rules that can be checked automatically in HTML source, and nothing else.

**It does not certify, attest or declare conformity with Directive (EU) 2019/882 (the European Accessibility Act), with the Web Content Accessibility Guidelines (WCAG), or with any other accessibility standard, law or search engine guideline.** A row with no issues means the twelve checks above found nothing on that page, not that the page is accessible and not that it is compliant.

Accessibility conformity depends on judgement a program cannot make: whether alt text describes the image, whether a label makes sense to the person reading it, whether the page works with a keyboard and a screen reader. Use this Actor to find the machine-checkable defects across a whole site, then have a person review what it found.

## Manners, `robots.txt` and your responsibility

- **`robots.txt` is fetched before the crawl and always respected.** There is no option to turn it off. A page disallowed for our user agent is not opened and not audited, and `robots.txt` requests are never charged.
- **The Actor identifies itself** on every request as `LoteboPageAuditTool/0.2 (+https://apify.com/store; Apify Actor; contact via Apify Store page)`. You can write a rule for that string in your `robots.txt`.
- **One request at a time, with a pause between them**, set by `requestDelaySeconds`. If the site's `robots.txt` asks for a longer `Crawl-delay`, the longer value wins.
- **Only the first 3 MB of a page body is read**, and only when the response looks like HTML.
- **You are responsible for having the right to access the URLs you give it.** Check the terms of the site and its `robots.txt` before you run it, and check whether your own agreement with that site allows automated access.

## How this was checked

Every check in the twelve-row table has a test in `tests/test_page_checks.py`, and the crawl was run end to end against the pages in `tests/site/`, which is where the three rows quoted above come from. `tests/test_schemas.py` compares the four files in `.actor/` against what the code actually writes, field by field. The suite runs with the plain interpreter and no network.

**What has never been tested, stated plainly:** no paid bill has ever come out of this Actor. Charging has been exercised on the platform, and a charge that fails or times out is a warning in the log rather than the end of the run, but no invoice has ever been produced by it. No site behind a login, a paywall or a bot filter was audited, and no site of tens of thousands of pages.

## For developers

```
.actor/              actor.json, input, output and dataset schemas
src/                 the run: crawl, the twelve page checks, charging, summary
tests/               the offline suite plus tests/site/, the planted-defect fixture
```

The Actor is written in Python and was built with the help of AI.

---

**Actor page on the Apify Store: https://apify.com/lotebo-lab/page-audit-tool**
