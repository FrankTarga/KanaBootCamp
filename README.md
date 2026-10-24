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
## Modelagem Matemática, Decisões de Algoritmo e Análise de Dados

### Precificação: desconto comercial simples, pro-rata die (2% a.m.)

Cada nota é precificada por `precificar()` em `quant_analytics.py`, usando desconto comercial simples na convenção de `base_dias` (30, conforme `validadores_antecipe.json -> precificacao`):

```
deságio      = valor_nominal * (taxa_mensal / base_dias) * prazo_dias
valor_líquido = valor_nominal - deságio
```

A taxa usada é resolvida por `RuleEngine.taxa_configurada()`: se `validadores_antecipe.json` tiver o bloco `precificacao.taxa_mensal_percentual`, essa é a taxa aplicada — **2,0% a.m.**, a taxa que o fundo efetivamente configurou — e só cai para o default de 2,5% a.m. da API se o bloco não existir. O gestor pode trocar essa taxa a qualquer momento pela tela "Zero-Deploy" sem redeploy.

O módulo também suporta desconto composto (`DESCONTO_COMPOSTO`), caso o fundo decida migrar de convenção no futuro, sem alterar o contrato da API.

### Smart Batch Optimizer: mochila 0/1 real, não apenas reordenação gulosa

Quando o limite de concentração de um sacado ou cedente é insuficiente para todas as notas elegíveis de um lote, o problema é formalmente um **Knapsack Problem 0/1** sob restrição de capacidade: maximizar a soma do valor líquido das notas aceitas sem ultrapassar a folga de concentração disponível.

`ordenar_lote_otimizado()` resolve isso em três passos:

1. **Notas de grupos sem pressão de concentração** entram primeiro, ordenadas por menor prazo — elas aumentam o patrimônio do fundo e abrem espaço (folga) para os grupos que estão sob pressão, sem custo de oportunidade algum.
2. **Grupos pressionados** (onde a soma das notas elegíveis excede a folga projetada) passam por uma **mochila 0/1 por programação dinâmica** (`_mochila()`), que escolhe o subconjunto de notas que maximiza Σ valor líquido dentro da folga restante — com a capacidade discretizada em até 2.000 níveis de resolução para manter o tempo de execução em milissegundos mesmo em lotes grandes.
3. O motor (`rule_engine.gerar_ordens_candidatas`) simula essa ordem e mais 4 ordens candidatas (original do CSV, por menor prazo, por maior valor, por menor valor) e fica com a que realmente produz o maior valor líquido simulado — nunca assume que a heurística ganhou sem checar.

Essa abordagem é estritamente melhor do que apenas ordenar por eficiência de deságio: a mochila encontra a combinação ótima de notas para a folga disponível, mesmo quando a nota "mais eficiente" sozinha não é a melhor escolha em conjunto com as demais.

### Validação stateful (Shadow Ledger) e concentração por raiz de CNPJ

A concentração de crédito é avaliada de forma acumulativa dentro do próprio lote: a cada nota aprovada, seu valor nominal é somado imediatamente a um `ShadowLedger` (overlay em memória sobre as exposições do estoque) antes da próxima nota ser avaliada. Isso impede que três notas de R$ 5.000 para o mesmo sacado, com limite de R$ 10.000, sejam todas aprovadas só porque a validação olhou apenas a foto estática do estoque inicial.

`CONCENTRACAO_MAXIMA_SACADO` usa `agrupamento: "RAIZ_CNPJ"` — a exposição é somada pelos 8 primeiros dígitos do CNPJ, ignorando a filial, para que duas filiais do mesmo grupo econômico não "driblem" o teto abrindo CNPJs de filial diferentes. Para CPF (pessoa física) não existe esse conceito e o documento completo é usado.

### Triplo radar de duplicidade/fraude

A identidade canônica de um título é `doc_cedente|doc_sacado|nu_documento|valor_nominal|data_vencimento`, normalizada e transformada em SHA-256 (`stock_index.gerar_hash_titulo`). A normalização do `NU_DOCUMENTO` remove zeros à esquerda em campos puramente numéricos — um detalhe que importa na prática: o Excel converte `"000351156"` em `"351156"` ao salvar, e sem essa normalização um recebível reenviado escaparia do radar de duplicidade. Essa chave sustenta 3 níveis de verificação:

1. **`DUPLICIDADE_LOTE`** — a mesma chave aparece duas vezes no próprio arquivo enviado.
2. **`DUPLICIDADE_FUNDO`** — a chave já existe na carteira histórica do ANTECIPE FIDC.
3. **`FRAUDE_OUTRO_FUNDO`** — a chave existe no estoque associada a outro dos 17 fundos do mercado (indício de dupla cessão).

### Análise do estoque real (100.554 linhas)

Rodando `scripts/raio_x_e_gerador_samples.py` contra o `estoque_antecipe.csv` completo:

- **10.621 linhas** pertencem ao ANTECIPE FIDC, com **patrimônio de R$ 53.074.028,00**.
- Data-base detectada automaticamente: **22/10/2026** (dia útil seguinte à maior `DATA_AQUISICAO` do estoque, 21/10/2026).
- **Achado relevante para o gestor:** o sacado SERRALHERIA VIOLETA S.A. (58.206.002/0001-11) já está **exatamente no teto de 10% de concentração** (R$ 6.634.253,50 acumulados, limite R$ 5.307.402,80 projetado — ou seja, já ultrapassado hoje, considerando o patrimônio atual). Qualquer nova nota para esse sacado será recusada pela regra `CONCENTRACAO_MAXIMA_SACADO` até o patrimônio do fundo crescer ou títulos existentes dele serem liquidados. Vale mostrar esse caso real na demo para os jurados — é exatamente o cenário que o Shadow Ledger e o Smart Batch Optimizer existem para proteger.
- Entre os cedentes, os 5 maiores já ultrapassam o teto de 8% de `CONCENTRACAO_MAXIMA_CEDENTE` — mas essa regra está **inativa** no `validadores_antecipe.json` atual, então não bloqueia hoje (o gestor pode ativá-la pela tela Zero-Deploy a qualquer momento para ver esses cedentes passarem a ser limitados).

### Massas de demonstração (`samples/`)

Os 3 CSVs em `samples/` já estão ajustados aos números do "Roteiro de demo" acima e não foram alterados por esta análise. `scripts/raio_x_e_gerador_samples.py` fica disponível no repositório para regenerá-los a partir do estoque real sempre que for preciso (por exemplo, se o `estoque_antecipe.csv` for atualizado antes da apresentação) — mas regenerar troca os números citados no Roteiro de demo, então só rodar de novo com o time ciente, revisando o README junto.
