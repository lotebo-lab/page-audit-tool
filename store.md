# Página da Apify Store, pronta para colar no Console

Tudo aqui sai do README.md e do código em `src/`. Nenhuma frase promete o que o
Actor não faz. Em especial: nada aqui diz que o Actor deixa um site em
conformidade legal com qualquer lei ou norma de acessibilidade. Ele mede regras
técnicas automatizáveis no HTML, e auditoria automática não atesta conformidade
legal.

## Título

```
Page Audit Tool
```

## Nome técnico (URL do Actor)

```
page-audit-tool
```

## Descrição curta (aparece na busca da Store)

```
Give it a domain and get one row per page with the technical SEO and accessibility defects in its HTML: title, meta description, headings, images without alt, unlabelled form fields, canonical.
```

## Categorias

1. SEO
2. Developer tools

Motivo: o comprador procura auditoria de site dentro de SEO, e a entrega é um
dataset consumido por quem mantém o site. Conferir no seletor do Console se os
rótulos exatos diferem; a lista de categorias só aparece com a conta aberta.

## Descrição longa

Usar o `README.md` do repositório, que o Console renderiza na página do Actor.
Ele traz, nesta ordem: o que o Actor faz e o que ele não é, a tabela de entrada
com nome, tipo e valor padrão iguais aos do formulário, a tabela de saída com
cada campo que o código grava no dataset, as regras checadas uma a uma, o que
ele não faz, limites e boas maneiras, dado coletado e preço.

Frase de enquadramento que precisa aparecer na página, e que já está no README:
o Actor mede regras técnicas que dá para checar automaticamente no HTML, e uma
auditoria automática não certifica conformidade legal com nenhuma norma de
acessibilidade ou de busca.

## Diferença que a página precisa deixar clara

Não é um checador de links: é um raio-x por página. Você dá o domínio, ele
descobre as páginas sozinho seguindo os links internos e devolve, para cada
página, o que está faltando no HTML e uma lista de frases curtas dizendo o que
consertar. Cada linha do dataset é uma página e uma lista de correções.

## Limites que a página declara, porque estão no código

- Respeita `robots.txt` sempre, sem opção de desligar; página proibida não é
  aberta nem auditada.
- Se o `robots.txt` pedir `Crawl-delay` maior que o seu, vale o maior.
- Teto de páginas abertas por execução: `maxPages`, padrão 25, máximo 5000.
- Profundidade: `maxDepth`, padrão 3, máximo 20.
- Intervalo entre requisições ao mesmo host: `requestDelaySeconds`, padrão 1.
- Não executa JavaScript, não faz login, não checa contraste de cor, ordem de
  foco, navegação por teclado nem nada que precise de página renderizada.
- Nunca requisita uma URL que não vai auditar: não há requisição para alvo de
  link.
- Nenhum dado pessoal é coletado: a saída tem URL, status HTTP, título, meta
  description, contagens de tags e a URL canônica.

## Preço

Pay per event, dois eventos, como em `.actor/actor.json`:

| evento | preço | quando é cobrado |
|---|---|---|
| `page-audited` | US$ 0.05 | uma vez por página aberta e checada |
| `site-report` | US$ 0.25 | uma vez por execução, só quando pelo menos uma página foi auditada |

Uma execução com o padrão de 25 páginas cobra 25 eventos `page-audited` mais 1
`site-report`, ou seja US$ 1,50. Se a execução bater o limite de cobrança, o
rastreio para, guarda o que já auditou e não cobra o `site-report`.

## Ainda não verificado

- Rótulos exatos das categorias no seletor do Console (só com a conta aberta).
- Como a Store renderiza as tabelas do README na página pública.
- Preço ainda não configurado na aba Publishing: os valores acima são os do
  `.actor/actor.json`, não uma leitura do Console.
