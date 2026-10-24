# Plano aprovado — back-end (Dev 1)

> Plano gerado pela IA em modo de planejamento e aprovado pelo time antes da implementação.


## Contexto
Hackathon Antecipe (prazo 18h). O Dev 1 precisa do `backend/` completo (FastAPI + motor de regras zero-deploy + índice O(1) do estoque + quant) que implementa o contrato REST da spec, para o Front e o Quant plugarem sem conflito. A pasta `C:\Users\User\Desktop\kanastra` hoje tem só `estoque_antecipe.csv` (20 MB) e `validadores_antecipe.json`. Não é repositório git, Docker não está instalado localmente e o Python é o 3.13 sem pacotes web.

### Fatos levantados no estoque (perfilado)
- UTF-8 sem BOM, separador `;`, LF, decimal `,` sem milhar. 100.554 linhas, 18 fundos, nenhum valor/data malformado.
- ANTECIPE FIDC (CNPJ 92.234.400/0001-80): 10.621 títulos, patrimônio **R$ 53.074.028,00**, sendo 203 títulos já vencidos (todos entram no patrimônio, como diz a spec). Só tem Duplicata e Duplicata de Serviço.
- Maior `DATA_AQUISICAO` = 21/10/2026 (quarta). **Decisão: data-base padrão = D+1 útil = 22/10/2026**, que pode ser sobrescrita pela env `DATA_BASE_PADRAO` e pelo form `data_base`.
- Todos os 4.209 sacados e 122 cedentes têm DV de CNPJ válido. Nenhuma chave canônica repete, nem dentro de um fundo nem entre fundos. Os casos de erro vão vir do CSV de upload.
- A raiz de sacado **58206002 (SERRALHERIA VIOLETA) já tem 12,5% da carteira**, acima do teto de 10%, então qualquer nota nova dela é recusada (bom caso para a demo). Pelo CNPJ completo seria 5,09%, por isso o agrupamento `RAIZ_CNPJ` é crítico.
- O cedente 10062050000157 (NLR) tem 22,6% da carteira, o que importa se `CONCENTRACAO_MAXIMA_CEDENTE` (hoje inativo, 8%) for ligado.

## Mapeamento dos validadores (`validadores_antecipe.json`)
| codigo | ativo | parametros | regra (V = valor nominal, n = prazo em dias corridos = venc − data_base) |
|---|---|---|---|
| CNPJ_SACADO_VALIDO | ✔ | {} | `DOC_SACADO` limpo: 14 dígitos → DV de CNPJ; 11 → DV de CPF; outro tamanho ou dígitos todos iguais → inválido |
| SITUACAO_CADASTRAL_SACADO | ✔ | situacoes_aceitas ["ATIVA"] | situação lida de `data/situacao_cadastral.json` (CNPJ → situação); CNPJ ausente = "ATIVA"; recusa se não estiver na lista (comparação case-insensitive) |
| TIPO_RECEBIVEL | ✔ | tipos_aceitos [...] | tipo normalizado (casefold, sem acento, espaços colapsados) ∈ aceitos; aceita também `tipos_bloqueados` opcional |
| VALOR_MINIMO | ✔ | valor_minimo 100.0 | V ≥ valor_minimo |
| NAO_VENCIDA | ✔ | {} | venc ≥ data_base (n ≥ 0) |
| PRAZO_MAXIMO | ✔ | prazo_maximo_dias 180 | n ≤ prazo_maximo_dias |
| CONCENTRACAO_MAXIMA_SACADO | ✔ | percentual_maximo 10.0, agrupamento RAIZ_CNPJ | grupo = 8 primeiros dígitos (CNPJ) ou documento completo (CPF, ou agrupamento `CNPJ`). Recusa se (E_g + V)/(P + V)·100 > pct; aceita também `valor_maximo` absoluto, opcional (E_g + V > valor_maximo). E_g e P vêm do Shadow Ledger. A folga mostrada na mensagem é (pct·P − E_g)/(1 − pct) |
| PRAZO_MINIMO | ✘ | prazo_minimo_dias 30 | n ≥ prazo_minimo_dias |
| CONCENTRACAO_MAXIMA_CEDENTE | ✘ | percentual_maximo 8.0 | mesma matemática do sacado; agrupamento padrão = CNPJ completo |
| *VALOR_MAXIMO, CNPJ_CEDENTE_VALIDO, DOCUMENTO_BLOQUEADO* | — | — | handlers extras que a spec pede ("trate também"); só rodam se o gestor incluir o código no JSON |
| DUPLICIDADE_LOTE / DUPLICIDADE_FUNDO / FRAUDE_OUTRO_FUNDO | sistema | — | sempre ligados, a menos que o JSON traga o código com `ativo:false`; usam o SHA-256 da chave canônica da spec |

Precificação: `DESCONTO_SIMPLES` (comercial): deságio = V·i·n/base_dias, líquido = V − deságio. A taxa usada segue esta ordem: form `taxa_mensal` (decimal) > JSON `taxa_mensal_percentual`/100 (= 0,02) > 0,025. Também implemento `DESCONTO_COMPOSTO` (V/(1+i)^(n/base)); qualquer outro método dá 422 no PUT.

## Arquivos a criar (todos novos)
```
backend/app/__init__.py
backend/app/api_schemas.py      # Pydantic v2: Health, ValidadoresConfig (+ validação por código), BatchResponse/Meta/Resumo/Item/Erro/ContagemMotivo
backend/app/quant_analytics.py  # parse_valor_br, parse_data_br, formatar_brl, calcular_prazo_dias, precificar(), proximo_dia_util, otimizador
backend/app/stock_index.py      # normalizar_documento, gerar_hash_titulo, StockIndex.carregar()
backend/app/rule_engine.py      # RuleEngine (config em memória + lock + persistência atômica), ShadowLedger, handlers, tradutor de mensagens, parse do upload
backend/app/main.py             # FastAPI, lifespan, CORS *, rotas, cache de idempotência
backend/data/estoque_antecipe.csv, validadores_antecipe.json  # CÓPIAS dos arquivos da raiz (originais intactos)
backend/data/situacao_cadastral.json   # {"cnpjs": {"<14 dígitos>": "BAIXADA", ...}} com 1–2 CNPJs de demo
backend/data/exemplos/lote_demo.csv    # lote que dispara cada regra + caso do otimizador
backend/tests/test_engine.py, test_api.py
backend/requirements.txt, requirements-dev.txt, Dockerfile, .dockerignore, README.md (curto: como rodar + campos extras)
docker-compose.yml (raiz)
```

## Design-chave
- **stock_index** (`csv.reader` com índice de colunas, datas parseadas por `split('/')` em vez de `strptime`, meta < 1 s): `hashes_antecipe: dict[hash → data_aquisicao]` (lookup O(1), e a data entra na mensagem), `hashes_outros_fundos: dict[hash → nome_fundo]`, `exposicao_sacado`/`exposicao_sacado_raiz`/`exposicao_cedente`/`exposicao_cedente_raiz`, `patrimonio_antecipe`, contadores para o /health. O ANTECIPE é identificado pelo `fundo.cnpj` do JSON, com fallback para o nome contendo "ANTECIPE".
- **Chave canônica** (exatamente a da spec): `doc_ced|doc_sac|NU_DOC.strip().upper()|f"{V:.2f}"|venc dd/mm/aaaa normalizada` → `sha256().hexdigest()` (64 hex).
- **ShadowLedger**: overlay (base do índice só para leitura + dicts de delta), sem copiar os 4 mil sacados por request. Só soma quando a nota tem 0 erros. `hashes_vistos` registra toda linha processada.
- **Avaliação sem short-circuit**: cada handler devolve 0..1 `Erro`. As regras se dividem em *estáticas* (independem da ordem: DV, tipo, valor, prazo, situação, DUPLICIDADE_FUNDO, FRAUDE) e *stateful* (DUPLICIDADE_LOTE, concentrações). As estáticas rodam uma vez só; cada passagem do otimizador reroda apenas as stateful.
- **Smart Batch Optimizer**: o `quant_analytics.gerar_ordens_candidatas(itens, restricoes)` devolve permutações: (1) original; (2) "quant": notas de grupos sem pressão primeiro (fazem P crescer, por prazo crescente), depois, por grupo pressionado, uma mochila 0/1 por DP em escala (capacidade = folga projetada; valor = líquido), escolhidas antes e sobras por valor crescente; (3) prazo crescente; (4) valor decrescente. O motor simula todas e fica com o maior Σ líquido (no empate vence a original), o que garante `ganho_otimizador_reais ≥ 0`. `salva_pelo_otimizador` = aprovada na melhor ordem e recusada na original, comparando pela linha. Com `otimizar_lote=false` roda uma passagem só, com ganho 0. O sort estável mantém a primeira ocorrência do CSV como "original" nas duplicatas do lote.
- **Resposta**: `itens` ordenados por `linha_csv` (1 = primeira linha de dados) e `ordem_avaliacao` = posição na ordem escolhida. Severidade do item: FRAUDE > DUPLICIDADE > REGRA_NEGOCIO > OK. Erros só com os 4 campos do contrato. O `resumo` agrega só aprovadas (deságio, líquido, prazo médio ponderado por V). `contagem_por_motivo` ordenada por quantidade.
- **Tradutor de economês**: mensagens com números reais em BRL ("R$ 1.500,50"), CNPJ formatado, nome do sacado, data em que a nota passa a ser elegível (PRAZO_MAXIMO: venc − 180 d), folga restante do cliente, linha da primeira ocorrência (DUPLICIDADE_LOTE), data da aquisição anterior (DUPLICIDADE_FUNDO) e nome do outro fundo (FRAUDE).
- **Parse resiliente do upload**: tenta utf-8-sig e cai para cp1252 (CSV salvo pelo Excel); detecta o delimitador entre `;` `,` `\t`; cabeçalho case/espaço-insensível; colunas obrigatórias = DOC_CEDENTE, DOC_SACADO, NU_DOCUMENTO, TIPO_RECEBIVEL, VALOR_NOMINAL, DATA_VENCIMENTO_ORIGINAL (nomes, fundo e aquisição são opcionais). Valores do tipo "1.500,50", "1500,50", "1500.50", "R$ 1.500,50"; datas dd/mm/aaaa, d/m/aaaa e ISO. Linha com valor/data impossível vira RECUSADA com erro `FORMATO_INVALIDO` em vez de derrubar o lote. Sem cabeçalho ou faltando coluna → 422 com mensagem clara.
- **Zero-Deploy**: `PUT /validators` valida com Pydantic (códigos únicos e suportados, tipos de parâmetros, pct entre 0 e 100, método de precificação), troca a config de forma atômica sob lock, grava via arquivo temporário + `os.replace` (indent 2, `ensure_ascii=False`) e incrementa `versao_config`. Extra retrocompatível: campo opcional `validadores_override` (JSON) no `POST /batches/validate` = sandbox what-if que não persiste.
- **Idempotência**: `batch_hash_idempotencia` = sha256 dos bytes do arquivo. Cache LRU (64) com chave (hash, data_base, taxa, otimizar, versao_config/override) que devolve a mesma resposta com header `X-Idempotent-Replay: true`.
- **/health**: os campos do contrato (`regras_ativas_count` = ativos do JSON) + extras `tempo_carga_estoque_ms` e `versao_config`.
- **Docker**: `python:3.12-slim`, **1 worker só** (o estado fica em memória; com mais workers o PUT divergiria). O compose monta `./backend/data:/app/data` para o PUT persistir no host e faz healthcheck via `python -c urllib`.
- Dependências fixadas, compatíveis com Py 3.12/3.13: fastapi, uvicorn[standard], python-multipart, pydantic 2.x; dev: pytest, httpx.

## Lote de demo (`lote_demo.csv`)
Um caso por regra: aprovada; vencida; prazo > 180; valor < 100; Cheque; CNPJ com DV inválido; sacado BAIXADA (do `situacao_cadastral.json`); linha repetida; cópia de uma linha do ANTECIPE (DUPLICIDADE_FUNDO); cópia de uma linha de outro fundo (FRAUDE); nota para a raiz 58206002 (concentração); uma nota com 3 violações ao mesmo tempo. Roteiro do otimizador (documentado no README): o sandbox reduz `CONCENTRACAO_MAXIMA_SACADO` para 2,2%, a DIVINÓPOLIS (raiz 32965964) fica com cerca de R$ 6,3 mil de folga e as notas 5.000 (60 d), 3.000 (10 d) e 3.000 (12 d) mostram ganho > 0 e `salva_pelo_otimizador`.

## Verificação
1. `python -m venv backend/.venv` + `pip install -r requirements-dev.txt` (PowerShell).
2. `pytest backend/tests` via subagent test-runner. Cobre: parse BR, DV de CNPJ/CPF, deságio (10.000 em 30 d a 2,5% = 250), Shadow Ledger (3 notas de 5k com 10k de folga → 2 aprovadas e 1 recusada), os 3 níveis de duplicidade, sem short-circuit (3 erros numa nota), ganho do otimizador ≥ 0 e > 0 no cenário de demo, PUT inválido → 422, PUT válido persiste e revalida sem restart, e o shape do contrato via TestClient.
3. Subir `uvicorn app.main:app` e medir o tempo de carga do estoque; `curl /api/v1/health` (esperado: 100554 / 10621 / 53074028.0 / 18 / 7 / "22/10/2026"); `curl -F file=@data/exemplos/lote_demo.csv .../batches/validate` e conferir cada caso e o `tempo_processamento_ms`.
4. Docker não está instalado localmente: Dockerfile e compose ficam sem validação de build (aviso na entrega).
