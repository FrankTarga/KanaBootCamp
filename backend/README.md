# ANTECIPE PRO — back-end

FastAPI + motor de regras zero-deploy + índice O(1) do estoque (~0,7 s para 100k linhas).

## Rodar

PowerShell (local), a partir da raiz do repositório:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\pip install -r requirements-dev.txt
cd ..
```

```powershell
# 1) mock da Receita Federal (porta 8001), num terminal separado
.\backend\.venv\Scripts\python -m uvicorn main:app --app-dir mock-receita --port 8001
```

```powershell
# 2) API (porta 8000), em outro terminal. Use 127.0.0.1: no Windows "localhost" tenta IPv6 antes e atrasa ~2 s
$env:RECEITA_API_URL = "http://127.0.0.1:8001/api/cnpj/v1"
$env:ADMIN_API_KEY = "troque-esta-chave"
cd backend
.\.venv\Scripts\python -m uvicorn app.main:app --port 8000
```

```powershell
# testes (não precisam do mock)
cd backend
.\.venv\Scripts\python -m pytest tests -q
.\.venv\Scripts\python -m pytest tests -q --cov=app --cov-branch   # cobertura (hoje 99%)
```

Sem `RECEITA_API_URL`, a situação cadastral sai de `data/situacao_cadastral.json`, e todo CNPJ que não estiver lá é **recusado** (fail-closed). Ou seja, sem o mock quase todas as notas são recusadas.

bash (VPS), na raiz do projeto:

```bash
docker compose up -d --build
```

Docs interativas: http://localhost:8000/docs

## Variáveis de ambiente

| variável | padrão | uso |
|---|---|---|
| `DATA_DIR` | `backend/data` | pasta com estoque, validadores e situação cadastral |
| `DATA_BASE_PADRAO` | D+1 útil da maior `DATA_AQUISICAO` (22/10/2026) | força a data-base (`dd/mm/aaaa`) |
| `MAX_UPLOAD_MB` | 50 | tamanho máximo do CSV de upload |
| `MAX_LINHAS_LOTE` | 10000 | máximo de notas por lote |
| `RECEITA_API_URL` | — | base da consulta de CNPJ (ex.: `http://127.0.0.1:8001/api/cnpj/v1` do mock ou `https://brasilapi.com.br/api/cnpj/v1`); sem ela, usa `situacao_cadastral.json` |
| `RECEITA_TIMEOUT_S` | 2 | timeout de cada consulta |
| `ADMIN_API_KEY` | — | chave exigida no header `X-API-Key` do `PUT /validators`; sem ela o `PUT` fica bloqueado (403) |
| `LOG_LEVEL` | INFO | nível de log |

Rode com **1 worker**: a config e o estoque vivem em memória; com mais workers um `PUT` só atualizaria um deles.

## Contrato

Segue a spec à risca. Extras retrocompatíveis:

- `POST /api/v1/batches/validate` aceita o campo opcional `validadores_override` (JSON igual ao do `GET /validators`) para o **what-if** do gestor: simula sem persistir.
- Header `X-Idempotent-Replay: true` quando a resposta vem do cache (mesmo arquivo + parâmetros + versão das regras).
- `GET /health` traz ainda `tempo_carga_estoque_ms` e `versao_config` (incrementa a cada `PUT`).
- Erros sempre em `{"error": {"code", "message", "details"}}` (422 para entrada inválida, 413 para arquivo grande, 500 sem stack trace).
- `linha_csv` = linha física do arquivo (o cabeçalho é a linha 1), igual ao número da linha no Excel.

## Regras de negócio

- Todos os códigos do `validadores_antecipe.json` estão implementados; também existem `VALOR_MAXIMO`, `CNPJ_CEDENTE_VALIDO` e `DOCUMENTO_BLOQUEADO`, que valem quando o gestor os adiciona ao JSON. Códigos desconhecidos são recusados no `PUT` com 422.
- `DUPLICIDADE_LOTE`, `DUPLICIDADE_FUNDO` e `FRAUDE_OUTRO_FUNDO` são regras de sistema: rodam sempre, a menos que o JSON as traga com `"ativo": false`.
- Concentração: `(exposição + V) / (patrimônio + V) > percentual_maximo` usando o Shadow Ledger; `agrupamento` aceita `RAIZ_CNPJ` ou `CNPJ`. Também aceita `valor_maximo` (R$).
- Situação cadastral **fail-closed**: consulta `RECEITA_API_URL` (formato BrasilAPI, `descricao_situacao_cadastral`) em paralelo, com cache de 1 h. 404 = "não encontrado", e timeout ou erro = "não foi possível confirmar"; nos dois casos a nota é recusada, e uma consulta que falhou nunca é reaproveitada pelo cache de idempotência. Sem a URL, a fonte é `data/situacao_cadastral.json` (relido quando muda) e CNPJ ausente também é recusado.
- Prazo mínimo de cobrança: deságio = `V · i · max(n, prazo_minimo_cobranca_dias) / base_dias` (o JSON usa 5 dias).
- Chave canônica da spec, com um ajuste: `NU_DOCUMENTO` numérico perde os zeros à esquerda (o Excel transforma `000351156` em `351156`, e sem isso o radar de fraude falharia).
- Taxa: form `taxa_mensal` (só quando o usuário altera) > `precificacao.taxa_mensal_percentual` do JSON (fonte oficial, exposta em `/health.taxa_mensal_padrao`) > 0,025 (só se o JSON não tiver `precificacao`).
- Lote: no máximo `MAX_LINHAS_LOTE` notas (padrão 10.000); acima de 3.000 notas o otimizador simula só a ordem original e a ordem quant.
- Trocar `fundo.nome`/`fundo.cnpj` via `PUT` ou what-if é recusado (422): o estoque é indexado no startup e exige reiniciar a API.

## Modo carteira

`POST /api/v1/batches/validate` com `modo=carteira` (resposta completa, para a tela), `POST /api/v1/portfolio/validate` e `python -m app.validar_carteira <estoque.csv> [saida.json]` reproduzem o gabarito `resultado_esperado_100k.json` (prazo pela `DATA_AQUISICAO` da linha, concentração estática por fundo, sem radar de duplicidade). Detalhes no README principal.

## Interface com o Estatístico (`app/quant_analytics.py`)

Mantenha estas assinaturas e o motor continua funcionando:

- `precificar(valor_nominal, prazo_dias, taxa_mensal, metodo, base_dias) -> ResultadoPrecificacao(desagio_reais, valor_liquido)`
- `gerar_ordens_candidatas(itens: list[ItemOtimizacao], restricoes: list[RestricaoConcentracao]) -> list[list[int]]`: a 1ª ordem deve ser a original. O motor simula todas e fica com a de maior Σ líquido.
- `parse_valor_br`, `parse_data_br`, `formatar_brl`, `formatar_data_br`, `formatar_percentual`, `calcular_prazo_dias`, `proximo_dia_util`

## Massas de demo

Ficam em [`samples/`](../samples) na raiz do repositório; o roteiro de cada arquivo está no [README principal](../README.md#roteiro-de-demo).
