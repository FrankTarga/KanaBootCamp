# ANTECIPE PRO

Plataforma de antecipação de recebíveis para o **ANTECIPE FIDC** (Hackathon Antecipe).

A empresa (cedente) envia um lote CSV de notas e recebe na hora quanto vai receber, quais notas foram aprovadas e, para cada recusa, uma explicação em português claro com o que fazer. O gestor do fundo liga, desliga e ajusta as regras de risco pela tela ou pela API, sem deploy, e revalida o lote em tempo real.

## Subir tudo

bash (VPS ou qualquer máquina com Docker):

```bash
docker compose up -d --build
```

- Front-end: http://localhost:5173
- API: http://localhost:8000/api/v1 · docs interativas em http://localhost:8000/docs

Sem Docker (PowerShell, Windows):

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\pip install -r requirements-dev.txt
.\.venv\Scripts\python -m uvicorn app.main:app --port 8000
```

```powershell
cd frontend
npm install
npm run dev
```

Testes do back-end: `cd backend; .\.venv\Scripts\python -m pytest tests -q`

## Estrutura

```
├── backend/                  FastAPI (Python 3.12+)
│   ├── app/
│   │   ├── main.py           rotas REST, CORS, lifespan, erros padronizados, cache de idempotência
│   │   ├── api_schemas.py    modelos Pydantic v2 = contrato da API
│   │   ├── stock_index.py    índice O(1) em RAM do estoque (100k linhas em ~0,7 s)
│   │   ├── rule_engine.py    motor de regras zero-deploy, Shadow Ledger, anti-fraude, tradutor de erros
│   │   └── quant_analytics.py precificação, parse BR e Smart Batch Optimizer (Estatístico)
│   ├── data/                 estoque, validadores_antecipe.json, situacao_cadastral.json
│   └── tests/                pytest (motor + API)
├── frontend/                 React + Vite + Tailwind + TypeScript
│   └── src/
│       ├── components/       componentes visuais
│       ├── services/         cliente da API (api.ts) + mock (mockLote.json)
│       ├── types/            tipos TS espelhados do contrato (api.ts)
│       └── App.tsx
├── samples/                  massas de demo para os jurados
├── prompts-ia/               histórico das conversas com IA (requisito do hackathon)
└── docker-compose.yml
```

| pasta | dono |
|---|---|
| `backend/app/` (menos `quant_analytics.py`), `docker-compose.yml` | Dev 1 · Back-end |
| `frontend/` | Dev 2 · Front-end |
| `backend/app/quant_analytics.py`, `samples/` | Estatístico · Quant |

## Contrato da API

| método | rota | uso |
|---|---|---|
| GET | `/api/v1/health` | estado do motor e estatísticas do estoque |
| GET | `/api/v1/validators` | JSON de regras atual |
| PUT | `/api/v1/validators` | troca as regras em memória e salva em disco (sem restart) |
| POST | `/api/v1/batches/validate` | `multipart/form-data`: `file`, `data_base?`, `taxa_mensal?`, `otimizar_lote?`, `validadores_override?` |

Os tipos exatos estão em [`frontend/src/types/api.ts`](frontend/src/types/api.ts), espelho de [`backend/app/api_schemas.py`](backend/app/api_schemas.py). Mudou um, muda o outro no mesmo commit.

- `validadores_override` (opcional): JSON de regras só para aquela validação. É o **what-if** do gestor e não persiste nada.
- Header `X-Idempotent-Replay: true` quando o mesmo arquivo, com os mesmos parâmetros e a mesma versão de regras, já foi processado.
- Erros sempre em `{"error": {"code", "message", "details"}}`.
- `linha_csv` é a linha física do arquivo (cabeçalho = linha 1), igual ao número da linha no Excel.

## Diferenciais técnicos

1. **Índice O(1) em RAM.** No startup, as 100.554 linhas do estoque viram HashMaps: títulos do ANTECIPE, títulos dos outros 17 fundos e exposição por sacado e cedente (por CNPJ e por raiz).
2. **Shadow Ledger.** Cada nota aprovada soma imediatamente na exposição do sacado, do cedente e do patrimônio antes da próxima ser avaliada, então limites estouram no meio do lote com precisão.
3. **Smart Batch Optimizer.** O motor simula várias ordens de avaliação (original, mochila 0/1 por grupo de concentração, menor prazo, maior valor) e devolve a de maior valor líquido para a empresa, marcando as notas `salva_pelo_otimizador`.
4. **Triplo radar anti-fraude.** A chave canônica (cedente, sacado, nº da nota, valor, vencimento) vira um SHA-256 e detecta nota repetida no lote, nota já comprada pelo ANTECIPE e nota já vendida a outro fundo (dupla cessão). Zeros à esquerda do número da nota são ignorados, porque o Excel os apaga.
5. **Sem short-circuit + tradutor de economês.** Todas as regras ativas rodam em todas as notas; cada recusa traz título curto, mensagem com os números reais da nota e uma ação recomendada.
6. **Zero-Deploy.** O `PUT /validators` valida o schema (códigos, tipos e faixas dos parâmetros), troca a config de forma atômica e grava o JSON; o what-if simula sem salvar.

Data-base padrão: **22/10/2026**, o próximo dia útil após a maior `DATA_AQUISICAO` do estoque (21/10). Nunca é a data do relógio; pode ser forçada pela env `DATA_BASE_PADRAO` ou pelo campo `data_base`.

## Roteiro de demo

| arquivo | o que mostra |
|---|---|
| [`01_lote_empresarial_padrao.csv`](samples/01_lote_empresarial_padrao.csv) | lote típico da FÁBRICA DE TINTAS VARGINHA: 22 notas, 14 aprovadas (R$ 199.343,36 líquidos) e recusas por vencida, prazo > 180 dias, valor < R$ 100, cheque, CNPJ inválido, CNPJ baixado na Receita, concentração (a SERRALHERIA VIOLETA já tem 12,5% da carteira) e uma nota com 3 violações ao mesmo tempo |
| [`02_demo_otimizador_concentracao.csv`](samples/02_demo_otimizador_concentracao.csv) | DIVINÓPOLIS perto do teto de 10%: na ordem do CSV a nota de R$ 3 mi (75 dias) consome o limite; o otimizador aprova as de R$ 2,3 mi e R$ 2,2 mi (8 e 12 dias): **+R$ 1.620.133,33** e 2 notas salvas |
| [`03_demo_radar_antifraude.csv`](samples/03_demo_radar_antifraude.csv) | nota repetida no lote, 2 notas já compradas pelo ANTECIPE (uma com os zeros cortados pelo Excel) e 3 notas já na carteira de outros fundos (alerta de fraude) |

Zero-deploy ao vivo: suba o `01`, desative `VALOR_MINIMO` ou ative `PRAZO_MINIMO` (gaveta do gestor ou `PUT /api/v1/validators`) e revalide; o resultado muda sem reiniciar nada.
