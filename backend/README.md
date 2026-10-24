# ANTECIPE PRO — back-end

FastAPI + motor de regras zero-deploy + índice O(1) do estoque (~0,7 s para 100k linhas).

## Rodar

PowerShell (local):

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\pip install -r requirements-dev.txt
.\.venv\Scripts\python -m uvicorn app.main:app --port 8000
.\.venv\Scripts\python -m pytest tests -q
```

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
| `MAX_UPLOAD_MB` | 20 | tamanho máximo do CSV de upload |
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
- Situação cadastral: `data/situacao_cadastral.json` (`{"situacoes": {"CNPJ": "BAIXADA"}}`); CNPJ ausente = ATIVA. O arquivo é relido quando muda, sem restart.
- Chave canônica da spec, com um ajuste: `NU_DOCUMENTO` numérico perde os zeros à esquerda (o Excel transforma `000351156` em `351156`, e sem isso o radar de fraude falharia).
- Taxa: form `taxa_mensal` > `precificacao.taxa_mensal_percentual` do JSON > 0,025.

## Interface com o Estatístico (`app/quant_analytics.py`)

Mantenha estas assinaturas e o motor continua funcionando:

- `precificar(valor_nominal, prazo_dias, taxa_mensal, metodo, base_dias) -> ResultadoPrecificacao(desagio_reais, valor_liquido)`
- `gerar_ordens_candidatas(itens: list[ItemOtimizacao], restricoes: list[RestricaoConcentracao]) -> list[list[int]]`: a 1ª ordem deve ser a original. O motor simula todas e fica com a de maior Σ líquido.
- `parse_valor_br`, `parse_data_br`, `formatar_brl`, `formatar_data_br`, `formatar_percentual`, `calcular_prazo_dias`, `proximo_dia_util`

## Massas de demo

Ficam em [`samples/`](../samples) na raiz do repositório; o roteiro de cada arquivo está no [README principal](../README.md#roteiro-de-demo).
