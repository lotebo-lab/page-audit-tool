# SEO Audit and Accessibility Crawler: Alt Text, Meta Tags, Headings

Run it on Apify Store: https://apify.com/lotebo-lab/page-audit-tool

You need to know which pages of a site are missing alt text, a title, a meta description or a canonical link, and checking them one by one in a browser extension is not an option when the site has hundreds of pages.

Give this Actor a domain. It crawls the site page by page, with no sitemap and no URL list needed, and returns one row per page with twelve technical SEO and HTML accessibility checks scored, plus a short list of plain sentences saying what to fix on that page.

**It measures the technical rules of WCAG and SEO that a program can check in the HTML source. An automated audit does not attest conformity with WCAG, with Directive (EU) 2019/882 (the European Accessibility Act) or with any search engine guideline.** See "Automated checks are not a statement of legal conformity" below.

## Who runs it, and when

- **Agencies and freelancers** taking over a site, who need the defect list of the whole site before quoting the work or before the first invoice;
- **in-house marketing and content teams** doing a periodic technical SEO pass, where missing titles and meta descriptions across a section matter more than one perfect page;
- **developers preparing an accessibility review**, who want the machine-checkable defects (images with no alt text, form fields with no accessible name, headings out of order) listed by page, so the human review starts where the problems are;
- **anyone after a migration or a redesign**, when templates changed and nobody knows which pages lost their canonical link.

## What comes out, field by field

One dataset row per page that answered with an HTML body. These are all the columns, and there are no others; the same names are declared in `.actor/dataset_schema.json` and checked by `tests/test_schemas.py`.

| field | type | what it holds |
|---|---|---|
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

### The run summary

Every run also writes a `SUMMARY` record in the key-value store with: `startUrl`, `pagesAudited`, `pagesWithIssues`, one total per defect type (`titleMissing`, `metaDescriptionMissing`, `pagesWithoutH1`, `pagesWithMultipleH1`, `pagesWithBrokenHeadingOrder`, `imagesWithoutAlt`, `formFieldsWithoutLabel`, `canonicalMissing`), `totalIssues`, `worstPages` (up to ten pages with their issue list) and the charging counters `chargedEvents`, `chargeLimitReached` and `chargeFailures`.

### Real output rows

Copied from `logs/corrida-local-2026-09-20-canonico.log` in this repository: an end-to-end run of `src/main.py` against a five page test site whose defects were planted on purpose, served from disk at `127.0.0.1:8099` because the build sandbox has no route to the public internet. The run audited 5 pages and found 9 issues. The values are the ones in the log; the keys are reordered here to follow the table above.

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

## Input

The example below is the input this Actor is prefilled with, so you can press Start and read a real result before pointing it at your own site.

```json
{
  "startUrl": "https://www.python.org",
  "maxPages": 25,
  "maxDepth": 3
}
```

| field | type | default | range |
|---|---|---|---|
| `startUrl` (required) | string | — | a bare domain (`example.com`, `https://` is assumed) or a full URL |
| `maxPages` | integer | 25 | 1 to 5000; each page opened is one charged event |
| `maxDepth` | integer | 3 | 0 to 20 clicks from the start page; 0 audits only the start page |
| `requestDelaySeconds` | integer | 1 | 0 to 60 seconds between two requests to the same host |
| `requestTimeoutSeconds` | integer | 15 | 3 to 120 seconds before a page is reported as a timeout |

Start with ten pages whose problems you already know, and compare the rows with what you would find by hand.

## What this Actor does not do

- **It does not run JavaScript.** It reads the HTML the server returns, so content drawn by a script is not seen and a page built entirely in the browser looks empty to it.
- **It does not measure colour contrast.** There is no contrast checker in the code.
- **It does not check focus order, keyboard navigation or ARIA roles**, beyond looking for `aria-label` and `aria-labelledby` when deciding whether a form field has a name.
- **It does not read alt text for meaning.** It counts images without an `alt`; it cannot tell you whether an existing alt text describes the image.
- **It does not compare pages with each other**, so duplicate titles and duplicate meta descriptions across pages are not reported.
- **It does not report redirect chains.** Redirects are followed and only the final URL is kept.
- **It does not check whether links work.** Link targets are never requested; that is a different tool.
- **It does not audit PDFs, images or any other non-HTML file**, and it does not follow links to them.
- **It does not crawl past the caps.** It stops at `maxPages` or `maxDepth`, whichever comes first, and pages nobody links to from the start URL are never found. It does not follow subdomains.
- **It does not log in, fill forms, solve captchas or get past a paywall.**
- **It does not predict rankings, traffic or revenue, and it makes no claim about any of them.**
- **It does not collect personal data.** The output holds page URLs, statuses, tag text, counts and the canonical URL. Page bodies are parsed in memory and discarded; `mailto:` and `tel:` links are skipped.

## Automated checks are not a statement of legal conformity

This Actor measures technical rules that can be checked automatically in HTML source, and nothing else.

**It does not certify, attest or declare conformity with Directive (EU) 2019/882 (the European Accessibility Act), with the Web Content Accessibility Guidelines (WCAG), or with any other accessibility standard, law or search engine guideline.** A row with no issues means the twelve checks above found nothing on that page, not that the page is accessible, not that it is compliant, and not that it will rank.

Accessibility conformity depends on judgement a program cannot make: whether alt text describes the image, whether a label makes sense to the person reading it, whether the page works with a keyboard and a screen reader. Use this Actor to find the machine-checkable defects across a whole site, then have a person review what it found.

## Manners, `robots.txt` and your responsibility

- **`robots.txt` is fetched before the crawl and always respected.** There is no option to turn it off. A page disallowed for our user agent is not opened and not audited, and `robots.txt` requests are never charged.
- **The Actor identifies itself** on every request as `LoteboPageAuditTool/0.2 (+https://apify.com/store; Apify Actor; contact via Apify Store page)`. You can write a rule for that string in your `robots.txt`.
- **One request at a time, with a pause between them**, set by `requestDelaySeconds`. If the site's `robots.txt` asks for a longer `Crawl-delay`, the longer value wins.
- **Only the first 3 MB of a page body is read**, and only when the response looks like HTML.
- **You are responsible for having the right to access the URLs you give it.** Check the terms of the site and its `robots.txt` before you run it, and check whether your own agreement with that site allows automated access.

## Price

Pay per event, two events, exactly as declared in `.actor/actor.json`:

| event | price | when it is charged |
|---|---|---|
| `page-audited` | US$ 0.05 | once per page fetched and checked. The same page in two URL spellings (`/` and `/index.html`) is charged once |
| `site-report` | US$ 0.25 | once per run, and only when at least one page was audited |

A default run of 25 pages is 25 `page-audited` events plus 1 `site-report`: US$ 1.50. Apify charges its own Actor start event and the platform usage of the run on top of this; those are not set by this Actor.

A page that is requested but never answers with an HTML body (timeout, DNS error, a non-HTML response) still cost one request, so it is charged as one `page-audited` event and appears in the run log without a dataset row. If a run reaches your pay-per-event limit, the crawl stops, keeps everything audited so far, and the `site-report` is not charged.

## About this Actor

The code, the tests and the run log quoted here are in this repository. Every check in the table has a test in `tests/test_page_checks.py`, and the crawl was run end to end against the pages in `tests/site/`. The Actor is written in Python and was built with the help of AI.

## Example tasks

Each page below is a published example task of this Actor. It shows the input used and the fields the run returns. The same page is served as Markdown by adding `.md` to the URL.

- [Is my site compliant with the European Accessibility Act?](https://apify.com/lotebo-lab/page-audit-tool/examples/european-accessibility-act-website-check): crawls a site page by page and lists the automated WCAG checks the European Accessibility Act covers, with the failing element on each row.
- [Generate a white label SEO audit report for a client](https://apify.com/lotebo-lab/page-audit-tool/examples/white-label-seo-audit-report-for-clients): crawls a client site and exports one row per page with the technical SEO fields an agency pastes straight into the report it sells.
- [Find every image with missing alt text on a website](https://apify.com/lotebo-lab/page-audit-tool/examples/find-images-missing-alt-text): crawls a whole site and lists every image with no alt text or an empty one, together with the page it sits on.
- [Which pages on my site have no title or meta description?](https://apify.com/lotebo-lab/page-audit-tool/examples/find-pages-missing-title-and-meta-description): crawls a domain and returns one row per page with its title, meta description, canonical tag and heading order, so you see what is missing or duplicated before a client does.
- [How do I list every image missing alt text on my site?](https://apify.com/lotebo-lab/page-audit-tool/examples/list-images-without-alt-text-on-a-site): crawls a domain and returns one row per page with the images that have no alt text and the form fields with no label, the two checks an accessibility review asks for first.
- [Which pages on my site have no meta description?](https://apify.com/lotebo-lab/page-audit-tool/examples/find-pages-missing-meta-description): crawls the whole site from one starting URL and returns every page with no meta description, next to its title length and canonical link.
- [Find pages with no H1 or a broken heading order](https://apify.com/lotebo-lab/page-audit-tool/examples/find-pages-with-no-h1-or-broken-heading-order): lists pages with no h1, with more than one h1 or with a heading level skipped, next to images without alt text and fields without a label.
- [Check a site for SEO defects before it goes live](https://apify.com/lotebo-lab/page-audit-tool/examples/check-a-site-for-seo-defects-before-launch): ends with a single summary row: pages crawled, pages with defects, total defects and what robots.txt blocked.
