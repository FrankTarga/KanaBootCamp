# Análise das recusas: contrato para o painel

Dono: Estatístico. Código: [`backend/app/analise_recusas.py`](../backend/app/analise_recusas.py), testes em
[`backend/tests/test_analise_recusas.py`](../backend/tests/test_analise_recusas.py).

`analisar_recusas(itens)` recebe a lista `itens` da resposta de `POST /api/v1/batches/validate` e devolve os
números do painel de recusas. **O front mostra os números como vêm, sem recalcular nada.** Os percentuais já
estão arredondados para fechar exatamente em 100,0%; somar ou arredondar de novo no front quebra isso.

## Como o front recebe os dados

Hoje é uma função Python. Para a tela usar, o back-end precisa expor o resultado, e quem decide como é o Dev 1.
O caminho mais simples é incluir um campo `analise_recusas` na resposta de `POST /batches/validate`:
`analise_recusas: analisar_recusas(itens)`. Assim a tela recebe tudo numa chamada só, e ele vale também para o
what-if do gestor.

A busca por número da nota não precisa de nada novo: ela filtra os `itens` que o front já recebe, e cada
item já traz `erros[]` com `titulo_amigavel`, `mensagem_empresa` e `acao_recomendada`.

## Os grupos (visão principal do painel)

Cada nota recusada entra em **exatamente um** grupo, então os cards somam 100% das recusadas:

- `grupos.um_problema[]`: um card por problema, só com as notas que têm **apenas** aquele problema.
- `grupos.mais_de_um_problema`: um card com todas as notas que têm 2 ou mais problemas. Ao abrir:
  - `subgrupos[]`: um por quantidade de problemas (2, 3, ...).
  - `subgrupos[].combinacoes[]`: as combinações de problemas daquela quantidade.
  - Os `pct_do_grupo` de subgrupos e combinações são **relativos ao card "mais de um problema"** e somam 100%
    entre si (os subgrupos somam 100%, e todas as combinações juntas também).

| campo | significado |
|---|---|
| `qtd_notas` | notas no lote (aprovadas + recusadas) |
| `qtd_recusadas`, `pct_recusadas` | recusadas e % do lote |
| `valor_recusado` | soma do valor nominal das recusadas (R$) |
| `qtd_com_mais_de_um_erro`, `pct_com_mais_de_um_erro` | tamanho do card "mais de um problema" |
| `codigo`, `titulo_amigavel` | código técnico e o texto para mostrar |
| `qtd`, `valor` | notas do grupo e soma do valor nominal (R$) |
| `pct_das_recusadas` | % do grupo sobre as recusadas (soma 100% com os outros cards) |
| `pct_do_grupo` | % dentro do card "mais de um problema" |
| `corrigivel` | `false` para fraude e duplicidade: mostrar "não dá para corrigir" |
| `liquido_liberado` | R$ líquido (já com deságio) que a empresa recebe se corrigir **só** esse problema. `null` = sem estimativa (nota vencida: a nota nova terá outro prazo). Para prazo longo é uma estimativa conservadora (calculada com o prazo atual) |

## A visão por motivo (opcional)

`motivos[]` conta cada nota em **todos** os seus problemas, então a soma de `pct_das_recusadas` passa de 100%.
Serve para responder "em quantas notas este problema aparece". Vem ordenada pelo que mais libera dinheiro.
`qtd_so_este_erro` mostra quantas notas têm só esse problema: um problema com muitas notas e
`qtd_so_este_erro = 0` nunca aparece sozinho, então corrigir só ele não libera nada (no estoque, é o caso do prazo
máximo: R$ 112 milhões impactados e R$ 0 liberados, porque toda nota com prazo longo também é CCB ou cheque).

## Exemplo real (lote 01, listas encurtadas)

```json
{
  "qtd_notas": 22, "qtd_recusadas": 8, "pct_recusadas": 36.4, "valor_recusado": 35963.9,
  "qtd_com_mais_de_um_erro": 2, "pct_com_mais_de_um_erro": 25.0,
  "grupos": {
    "um_problema": [
      {"codigo": "PRAZO_MAXIMO", "titulo_amigavel": "Prazo de pagamento muito longo", "corrigivel": true,
       "qtd": 1, "valor": 9870.0, "pct_das_recusadas": 12.5, "liquido_liberado": 8152.62},
      {"codigo": "NAO_VENCIDA", "titulo_amigavel": "Nota já vencida", "corrigivel": true,
       "qtd": 1, "valor": 3120.0, "pct_das_recusadas": 12.5, "liquido_liberado": null}
    ],
    "mais_de_um_problema": {
      "qtd": 2, "valor": 2045.0, "pct_das_recusadas": 25.0,
      "subgrupos": [
        {"qtd_problemas": 2, "qtd": 1, "valor": 2000.0, "pct_do_grupo": 50.0, "combinacoes": [
          {"codigos": ["CNPJ_SACADO_VALIDO", "SITUACAO_CADASTRAL_SACADO"],
           "titulos": ["Documento do cliente inválido", "Cadastro do cliente irregular na Receita Federal"],
           "qtd": 1, "valor": 2000.0, "pct_do_grupo": 50.0}]},
        {"qtd_problemas": 3, "qtd": 1, "valor": 45.0, "pct_do_grupo": 50.0, "combinacoes": [
          {"codigos": ["PRAZO_MAXIMO", "TIPO_RECEBIVEL", "VALOR_MINIMO"],
           "titulos": ["Prazo de pagamento muito longo", "Tipo de título não aceito", "Valor abaixo do mínimo aceito"],
           "qtd": 1, "valor": 45.0, "pct_do_grupo": 50.0}]}
      ]
    }
  },
  "motivos": [
    {"codigo": "CONCENTRACAO_MAXIMA_SACADO", "titulo_amigavel": "Limite de crédito do cliente atingido",
     "corrigivel": true, "qtd_notas": 1, "valor_impactado": 15000.0, "qtd_so_este_erro": 1,
     "liquido_liberado": 14700.0, "pct_das_recusadas": 12.5}
  ]
}
```

## Conferido

- Nos 3 lotes de `samples/` e nas 100.554 linhas do estoque (com o gabarito oficial): os grupos somam 100%,
  subgrupos e combinações somam 100% dentro do grupo, e a quantidade de cada grupo bate com a contagem de notas.
- No estoque: 15.339 recusadas, 4.770 (31,1%) com mais de um problema. Para regerar a tabela:
  `python scripts/analise_recusas_estoque.py`.
