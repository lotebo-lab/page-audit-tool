# Estado das paginas de task publicadas (lotebo-lab)

Data da medicao: 22/09/2026. Medicao pura: nenhuma publicacao, nenhuma escrita na Apify, nenhum build tocado.

Metodo: lista das paginas lida em duas fontes independentes (HTML publico de cada Actor em apify.com/lotebo-lab/<actor>, secao de exemplos; e as URLs registradas nos arquivos do workspace). As duas fontes bateram: 39 paginas, conjuntos identicos, zero diferenca.

Divergencia com o enunciado da tarefa: a tarefa falava em 30 paginas publicadas em 20/09; as duas fontes medidas hoje mostram 39.

Controle de falso positivo: URL inventada (/examples/nao-existe-teste-404) devolve 307 na pagina e 404 no .md, entao 200 aqui e sinal real de pagina viva.

Comando usado por URL: curl -s -o /dev/null -w '%{http_code}' <url> e o mesmo com .md no fim.

Resultado: 39 de 39 paginas com 200 na pagina e 200 no .md. Nenhuma fora do ar.


## broken-link-auditor (8 paginas)

| Actor | task | URL | HTTP pagina | HTTP .md |
|---|---|---|---|---|
| broken-link-auditor | check-a-whole-website-for-404-links | https://apify.com/lotebo-lab/broken-link-auditor/examples/check-a-whole-website-for-404-links | 200 | 200 |
| broken-link-auditor | check-broken-links-after-site-migration | https://apify.com/lotebo-lab/broken-link-auditor/examples/check-broken-links-after-site-migration | 200 | 200 |
| broken-link-auditor | check-the-links-on-a-single-page | https://apify.com/lotebo-lab/broken-link-auditor/examples/check-the-links-on-a-single-page | 200 | 200 |
| broken-link-auditor | crawl-entire-website-for-404-errors | https://apify.com/lotebo-lab/broken-link-auditor/examples/crawl-entire-website-for-404-errors | 200 | 200 |
| broken-link-auditor | crawl-my-site-slowly-without-overloading-it | https://apify.com/lotebo-lab/broken-link-auditor/examples/crawl-my-site-slowly-without-overloading-it | 200 | 200 |
| broken-link-auditor | find-dead-outbound-links-in-blog-posts | https://apify.com/lotebo-lab/broken-link-auditor/examples/find-dead-outbound-links-in-blog-posts | 200 | 200 |
| broken-link-auditor | find-dead-outbound-links-on-blog | https://apify.com/lotebo-lab/broken-link-auditor/examples/find-dead-outbound-links-on-blog | 200 | 200 |
| broken-link-auditor | tell-a-dead-link-from-a-slow-one | https://apify.com/lotebo-lab/broken-link-auditor/examples/tell-a-dead-link-from-a-slow-one | 200 | 200 |

## cnpj-sanction-check (8 paginas)

| Actor | task | URL | HTTP pagina | HTTP .md |
|---|---|---|---|---|
| cnpj-sanction-check | checar-fornecedor-em-licitacao-antes-do-contrato | https://apify.com/lotebo-lab/cnpj-sanction-check/examples/checar-fornecedor-em-licitacao-antes-do-contrato | 200 | 200 |
| cnpj-sanction-check | checar-lista-de-fornecedores-por-cnpj | https://apify.com/lotebo-lab/cnpj-sanction-check/examples/checar-lista-de-fornecedores-por-cnpj | 200 | 200 |
| cnpj-sanction-check | checar-se-uma-empresa-tem-acordo-de-leniencia | https://apify.com/lotebo-lab/cnpj-sanction-check/examples/checar-se-uma-empresa-tem-acordo-de-leniencia | 200 | 200 |
| cnpj-sanction-check | check-if-a-brazilian-supplier-is-debarred | https://apify.com/lotebo-lab/cnpj-sanction-check/examples/check-if-a-brazilian-supplier-is-debarred | 200 | 200 |
| cnpj-sanction-check | consultar-cnpj-de-fornecedor-em-lista-de-sancao | https://apify.com/lotebo-lab/cnpj-sanction-check/examples/consultar-cnpj-de-fornecedor-em-lista-de-sancao | 200 | 200 |
| cnpj-sanction-check | consultar-cnpj-no-ceis-e-no-cnep | https://apify.com/lotebo-lab/cnpj-sanction-check/examples/consultar-cnpj-no-ceis-e-no-cnep | 200 | 200 |
| cnpj-sanction-check | due-diligence-em-lote-de-cnpj | https://apify.com/lotebo-lab/cnpj-sanction-check/examples/due-diligence-em-lote-de-cnpj | 200 | 200 |
| cnpj-sanction-check | verificar-se-uma-ong-esta-impedida-no-cepim | https://apify.com/lotebo-lab/cnpj-sanction-check/examples/verificar-se-uma-ong-esta-impedida-no-cepim | 200 | 200 |

## feed-change-watcher (8 paginas)

| Actor | task | URL | HTTP pagina | HTTP .md |
|---|---|---|---|---|
| feed-change-watcher | check-which-of-my-feeds-stopped-working | https://apify.com/lotebo-lab/feed-change-watcher/examples/check-which-of-my-feeds-stopped-working | 200 | 200 |
| feed-change-watcher | get-only-new-items-from-an-rss-feed | https://apify.com/lotebo-lab/feed-change-watcher/examples/get-only-new-items-from-an-rss-feed | 200 | 200 |
| feed-change-watcher | monitor-regulator-news-feeds-without-rereading-old-items | https://apify.com/lotebo-lab/feed-change-watcher/examples/monitor-regulator-news-feeds-without-rereading-old-items | 200 | 200 |
| feed-change-watcher | read-many-tender-feeds-and-see-only-new-notices | https://apify.com/lotebo-lab/feed-change-watcher/examples/read-many-tender-feeds-and-see-only-new-notices | 200 | 200 |
| feed-change-watcher | send-only-new-feed-items-to-n8n-or-make | https://apify.com/lotebo-lab/feed-change-watcher/examples/send-only-new-feed-items-to-n8n-or-make | 200 | 200 |
| feed-change-watcher | watch-release-feeds-for-new-versions | https://apify.com/lotebo-lab/feed-change-watcher/examples/watch-release-feeds-for-new-versions | 200 | 200 |
| feed-change-watcher | watch-several-release-feeds-in-one-run | https://apify.com/lotebo-lab/feed-change-watcher/examples/watch-several-release-feeds-in-one-run | 200 | 200 |
| feed-change-watcher | watch-vendor-security-advisory-feeds-for-new-entries | https://apify.com/lotebo-lab/feed-change-watcher/examples/watch-vendor-security-advisory-feeds-for-new-entries | 200 | 200 |

## page-audit-tool (8 paginas)

| Actor | task | URL | HTTP pagina | HTTP .md |
|---|---|---|---|---|
| page-audit-tool | check-a-site-for-seo-defects-before-launch | https://apify.com/lotebo-lab/page-audit-tool/examples/check-a-site-for-seo-defects-before-launch | 200 | 200 |
| page-audit-tool | european-accessibility-act-website-check | https://apify.com/lotebo-lab/page-audit-tool/examples/european-accessibility-act-website-check | 200 | 200 |
| page-audit-tool | find-images-missing-alt-text | https://apify.com/lotebo-lab/page-audit-tool/examples/find-images-missing-alt-text | 200 | 200 |
| page-audit-tool | find-pages-missing-meta-description | https://apify.com/lotebo-lab/page-audit-tool/examples/find-pages-missing-meta-description | 200 | 200 |
| page-audit-tool | find-pages-missing-title-and-meta-description | https://apify.com/lotebo-lab/page-audit-tool/examples/find-pages-missing-title-and-meta-description | 200 | 200 |
| page-audit-tool | find-pages-with-no-h1-or-broken-heading-order | https://apify.com/lotebo-lab/page-audit-tool/examples/find-pages-with-no-h1-or-broken-heading-order | 200 | 200 |
| page-audit-tool | list-images-without-alt-text-on-a-site | https://apify.com/lotebo-lab/page-audit-tool/examples/list-images-without-alt-text-on-a-site | 200 | 200 |
| page-audit-tool | white-label-seo-audit-report-for-clients | https://apify.com/lotebo-lab/page-audit-tool/examples/white-label-seo-audit-report-for-clients | 200 | 200 |

## page-change-monitor (7 paginas)

| Actor | task | URL | HTTP pagina | HTTP .md |
|---|---|---|---|---|
| page-change-monitor | check-if-a-supplier-terms-page-changed-since-last-run | https://apify.com/lotebo-lab/page-change-monitor/examples/check-if-a-supplier-terms-page-changed-since-last-run | 200 | 200 |
| page-change-monitor | check-many-pages-in-one-run-and-see-which-changed | https://apify.com/lotebo-lab/page-change-monitor/examples/check-many-pages-in-one-run-and-see-which-changed | 200 | 200 |
| page-change-monitor | know-when-a-vendor-publishes-new-release-notes | https://apify.com/lotebo-lab/page-change-monitor/examples/know-when-a-vendor-publishes-new-release-notes | 200 | 200 |
| page-change-monitor | see-exactly-what-changed-on-a-competitor-pricing-page | https://apify.com/lotebo-lab/page-change-monitor/examples/see-exactly-what-changed-on-a-competitor-pricing-page | 200 | 200 |
| page-change-monitor | watch-one-section-of-a-page-for-changes | https://apify.com/lotebo-lab/page-change-monitor/examples/watch-one-section-of-a-page-for-changes | 200 | 200 |
| page-change-monitor | watch-only-one-section-of-a-page-not-the-whole-page | https://apify.com/lotebo-lab/page-change-monitor/examples/watch-only-one-section-of-a-page-not-the-whole-page | 200 | 200 |
| page-change-monitor | which-supplier-product-pages-failed-the-last-check | https://apify.com/lotebo-lab/page-change-monitor/examples/which-supplier-product-pages-failed-the-last-check | 200 | 200 |
