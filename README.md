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

Sem Docker (PowerShell, Windows), um terminal por serviço:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\pip install -r requirements-dev.txt
```

```powershell
# mock da Receita Federal (porta 8001)
.\backend\.venv\Scripts\python -m uvicorn main:app --app-dir mock-receita --port 8001
```

```powershell
# API (porta 8000); use 127.0.0.1, porque no Windows "localhost" tenta IPv6 antes e atrasa ~2 s
$env:RECEITA_API_URL = "http://127.0.0.1:8001/api/cnpj/v1"
$env:ADMIN_API_KEY = "troque-esta-chave"
cd backend
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
├── mock-receita/             mock da consulta de CNPJ da Receita (formato BrasilAPI)
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
| PUT | `/api/v1/validators` | troca as regras em memória e salva em disco (sem restart); exige header `X-API-Key` = env `ADMIN_API_KEY` (401 sem a chave, 403 se a env não estiver definida) |
| POST | `/api/v1/portfolio/validate` | `multipart/form-data`: `file` (carteira/estoque inteiro). Saída no formato do gabarito oficial; ver *Modo carteira* |
| POST | `/api/v1/batches/validate` | `multipart/form-data`: `file`, `data_base?`, `taxa_mensal?`, `otimizar_lote?`, `validadores_override?` |

Os tipos exatos estão em [`frontend/src/types/api.ts`](frontend/src/types/api.ts), espelho de [`backend/app/api_schemas.py`](backend/app/api_schemas.py). Mudou um, muda o outro no mesmo commit.

- **Taxa de deságio: fonte única = `precificacao.taxa_mensal_percentual` do JSON** (hoje 2,0% a.m.). O `/health` devolve essa taxa já em decimal em `taxa_mensal_padrao` (0.02) para o Front preencher o input. O campo `taxa_mensal` do form só deve ser enviado quando o usuário altera a taxa (simulação); o 0,025 vale apenas se o JSON não tiver o bloco `precificacao`. A taxa usada de fato sempre volta em `meta.taxa_mensal_aplicada`. Para mudar a taxa do fundo: `PUT /validators`.
- **Situação cadastral fail-closed:** o back-end consulta `RECEITA_API_URL` (BrasilAPI real ou `mock-receita/`) para cada CNPJ de sacado do lote, em paralelo e com cache de 1 h. CNPJ não encontrado ou consulta que falhou = nota recusada. Sem `RECEITA_API_URL`, a fonte é `backend/data/situacao_cadastral.json` (e CNPJ ausente do arquivo também é recusado).
- **Prazo mínimo de cobrança:** `precificacao.prazo_minimo_cobranca_dias` (hoje 5). Nota que vence em menos dias, inclusive na própria data-base, é aceita se passar nas regras, mas paga deságio de 5 dias.
- **API key na gaveta do gestor:** o gestor digita a chave e o Front guarda em `sessionStorage`. Nunca coloque a chave em `VITE_*`, porque vai parar no JavaScript público.
- `validadores_override` (opcional): JSON de regras só para aquela validação. É o **what-if** do gestor e não persiste nada.
- Header `X-Idempotent-Replay: true` quando o mesmo arquivo, com os mesmos parâmetros e a mesma versão de regras, já foi processado.
- Erros sempre em `{"error": {"code", "message", "details"}}`.
- `linha_csv` é a linha física do arquivo (cabeçalho = linha 1), igual ao número da linha no Excel.

## Modo carteira (gabarito oficial)

`POST /api/v1/portfolio/validate` (multipart `file`) ou a CLI julgam **cada linha de um estoque** contra as regras do fundo e devolvem exatamente o formato de `resultado_esperado_100k.json`: `[{"linha", "id", "status": "APROVADO" | "BARRADO", "barrado_por"?}]`.

```powershell
cd backend
.\.venv\Scripts\python -m app.validar_carteira data\estoque_antecipe.csv saida.json
```

Diferenças em relação ao modo lote:
- prazo e vencimento contam a partir da `DATA_AQUISICAO` da própria linha;
- a concentração é **estática por fundo**: se a raiz do sacado passa do teto sobre as notas elegíveis daquele fundo, todas as notas dela são barradas (e ela só é avaliada em nota sem outro erro);
- não há radar de duplicidade, porque o arquivo é o próprio estoque.

`tests/test_conformidade_gabarito.py` compara as 100.554 linhas com o gabarito: **todas as regras que dependem só do kit batem linha a linha**. As únicas divergências são as 2.317 linhas de `SITUACAO_CADASTRAL_SACADO` (87 CNPJs), porque a situação usada pela organização não veio no kit, e a Receita real (BrasilAPI) dá outra situação para esses CNPJs sintéticos. A igualdade total fica marcada como pendência (`xfail` estrito) até a fonte oficial chegar.

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
