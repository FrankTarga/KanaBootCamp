# RFC 0001: Back-end do ANTECIPE PRO (motor de elegibilidade, precificação e anti-fraude)
- **Status:** Rascunho
- **Autor:** Eduardo
- **Data:** 24/10/2026

## Contexto e problema

O ANTECIPE FIDC compra recebíveis (duplicatas) de empresas cedentes. Hoje o fundo precisa de um serviço que:

1. receba um **lote CSV** de notas de um cedente;
2. valide cada nota contra as **regras de risco** de `validadores_antecipe.json` e contra o **estoque histórico** (`estoque_antecipe.csv`, 100.554 títulos de 18 fundos, 10.621 deles do ANTECIPE);
3. calcule o **preço de compra** (valor nominal − deságio);
4. explique cada recusa em linguagem simples para a empresa;
5. deixe o gestor **mudar as regras sem deploy**.

Restrições:

- **Prazo:** hackathon, entrega às 18h de 24/10/2026.
- **Time:** 3 pessoas (Back-end, Front-end, Estatístico), com um contrato REST fixo entre as partes.
- **Data-base:** não pode ser a data do relógio. O dataset é de quinta-feira, 22/10/2026, e hoje é sábado.
- **Sem banco de dados:** o estoque vem só de um CSV e cabe em memória com folga.

O que o estoque mostra (perfil real dos dados):

- O patrimônio do ANTECIPE soma R$ 53.074.028,00, dos quais 203 títulos (R$ 919 mil) já estão vencidos.
- A raiz de sacado `58206002` (SERRALHERIA VIOLETA) já concentra **12,5%** do fundo, acima do teto de 10%. Pelo CNPJ completo seriam só 5,09%, por isso o agrupamento por raiz de CNPJ é obrigatório.
- O estoque não tem nenhuma chave duplicada, nem dentro de um fundo nem entre fundos; duplicidade e fraude só vêm do upload.
- 16 mil títulos têm `NU_DOCUMENTO` com zeros à esquerda, que o Excel apaga ao salvar o CSV.

## Objetivos / Não-objetivos

**Objetivos**
- Validar um lote típico (até ~500 notas) em **menos de 15 ms**, com o estoque carregado em **menos de 1 s** no startup.
- Implementar 100% dos códigos do `validadores_antecipe.json` sem nenhum limite fixo no código.
- Avaliar todas as regras ativas em todas as notas (sem short-circuit), com mensagem e ação recomendada para cada recusa.
- Aplicar os limites de concentração de forma **stateful dentro do lote**, considerando as notas já aprovadas antes.
- Maximizar o valor líquido do cedente reordenando o lote, sem nunca piorar o resultado da ordem original.
- Detectar duplicidade em 3 níveis: dentro do lote, contra o próprio fundo e contra os outros 17 fundos (fraude de dupla cessão).
- Trocar regras via API em tempo real, com persistência e what-if sem persistência.

**Não-objetivos**
- Persistir as operações aprovadas (efetivar a cessão) ou atualizar o estoque após a compra.
- Autenticação e autorização (o `PUT /validators` está aberto; ver Riscos).
- Rodar com vários processos ou réplicas horizontais.
- Consultar a Receita Federal online.
- Usar calendário de feriados (D+1 útil considera só os fins de semana).

## Proposta

### Arquitetura

```mermaid
flowchart LR
    subgraph startup[Startup - lifespan]
        CSV[(estoque_antecipe.csv)] --> IDX[stock_index.carregar_estoque]
        JSON[(validadores_antecipe.json)] --> CFG[rule_engine.carregar_config]
        CFG --> IDX
    end
    IDX --> SI[StockIndex em RAM]
    CFG --> RE[RuleEngine]
    SI --> RE
    CAD[(situacao_cadastral.json)] -.recarregado por mtime.-> RE

    UP[POST /batches/validate] --> MAIN[main.py]
    PUT[PUT /validators] --> MAIN
    MAIN --> CACHE{{Cache LRU idempotência}}
    MAIN --> RE
    RE --> QA[quant_analytics: precificar + ordens candidatas]
    RE --> BR[br_utils: parse/format BR]
    PUT --> DISK[(escrita atômica do JSON)]
```

| módulo | responsabilidade | dono |
|---|---|---|
| `backend/app/main.py` | FastAPI, CORS, lifespan, rotas, formato de erro, request id, cache de idempotência | Dev 1 |
| `backend/app/api_schemas.py` | modelos Pydantic v2 = contrato (espelhado em `frontend/src/types/api.ts`) | Dev 1 |
| `backend/app/stock_index.py` | `carregar_estoque`, `gerar_hash_titulo`, normalização de documentos e do número da nota | Dev 1 |
| `backend/app/rule_engine.py` | `RuleEngine`, `ShadowLedger`, registro `REGRAS`, handlers, tradutor de mensagens, leitura do CSV de upload | Dev 1 |
| `backend/app/br_utils.py` | parse e formatação de valores e datas no padrão BR, prazo, D+1 útil | Dev 1 |
| `backend/app/quant_analytics.py` | `precificar`, `gerar_ordens_candidatas`, `ordenar_lote_otimizado` | Estatístico |

O estado (config, índice, cache) vive em memória num **único processo uvicorn com 1 worker**.

### Índice do estoque (`stock_index.carregar_estoque`)

A leitura é feita uma única vez, com `split` quando o arquivo não tem aspas (2,5x mais rápido que o módulo `csv`) e memoização dos documentos normalizados. Estruturas montadas:

| estrutura | tipo | uso |
|---|---|---|
| `hashes_antecipe` | `dict[hash → data_aquisicao]` | `DUPLICIDADE_FUNDO` (a data entra na mensagem) |
| `hashes_outros_fundos` | `dict[hash → nome_fundo]` | `FRAUDE_OUTRO_FUNDO` |
| `exposicao_sacado`, `exposicao_sacado_raiz` | `dict[doc → R$]` | concentração por CNPJ ou por raiz |
| `exposicao_cedente`, `exposicao_cedente_raiz` | `dict[doc → R$]` | idem, por cedente |
| `patrimonio_antecipe` | `float` | denominador da concentração |

- O ANTECIPE é identificado pelo `fundo.cnpj` (ou `fundo.nome`) do JSON.
- `data_base_padrao` = próximo dia útil após a maior `DATA_AQUISICAO` (21/10 → **22/10/2026**). A env `DATA_BASE_PADRAO` e o campo `data_base` do request sobrescrevem esse valor.
- Medido: carga em ~0,7 s.

### Chave canônica e radar de duplicidade

```
doc_cedente_limpo | doc_sacado_limpo | normalizar_nu_documento(NU_DOCUMENTO) | f"{valor:.2f}" | vencimento dd/mm/aaaa
→ sha256().hexdigest()   (64 hex)
```

`normalizar_nu_documento` faz o `strip().upper()` da spec e, quando o número é só de dígitos, remove os zeros à esquerda. Sem isso, um CSV salvo pelo Excel escapa do radar. O estoque não tem nenhuma colisão com essa regra.

| código | onde é checado | severidade |
|---|---|---|
| `DUPLICIDADE_LOTE` | `ShadowLedger.hashes_vistos` (qualquer linha já processada no lote) | DUPLICIDADE |
| `DUPLICIDADE_FUNDO` | `hashes_antecipe` | DUPLICIDADE |
| `FRAUDE_OUTRO_FUNDO` | `hashes_outros_fundos` | FRAUDE |

São regras de **sistema**: rodam mesmo sem constar no JSON, e o gestor só as desliga incluindo o código com `"ativo": false`.

### Motor de regras (`rule_engine`)

- **Registro `REGRAS`:** cada `Regra` tem `codigo`, `titulo_amigavel`, `severidade`, `stateful`, `avaliar(linha, params, ctx, ledger) → (mensagem, ação) | None` e `validar_parametros`.
- **Fase estática:** as regras que não dependem da ordem (CNPJ, situação cadastral, tipo, valor, prazo, duplicidade no fundo, fraude) rodam **uma vez** por nota.
- **Fase stateful:** `DUPLICIDADE_LOTE` e as concentrações rodam a cada simulação, contra um `ShadowLedger` novo.
- **ShadowLedger:** é um overlay (a base do índice fica só para leitura, mais dicts de delta), então não copia os ~4 mil sacados a cada request. Só soma uma nota se ela teve **0 erros**.
- **Concentração:** recusa se `(E_g + V) / (P + V) · 100 > percentual_maximo`, e opcionalmente se `E_g + V > valor_maximo`. A folga exibida na mensagem é `(p·P − E_g)/(1 − p)`. O agrupamento é `RAIZ_CNPJ` ou `CNPJ`.
- **Severidade do item:** FRAUDE > DUPLICIDADE > REGRA_NEGOCIO > OK. Os erros da nota saem ordenados por severidade e depois pela posição da regra no JSON.
- **Linhas mal formatadas** (valor ou data inválidos, nº da nota, cedente ou sacado vazios) viram `FORMATO_INVALIDO` em vez de derrubar o lote.

Mapeamento do JSON atual:

| código | ativo | regra |
|---|---|---|
| CNPJ_SACADO_VALIDO | ✔ | dígito verificador de CNPJ (inclusive o novo alfanumérico) ou de CPF |
| SITUACAO_CADASTRAL_SACADO | ✔ | situação lida de `data/situacao_cadastral.json`; CNPJ ausente conta como ATIVA |
| TIPO_RECEBIVEL | ✔ | `tipos_aceitos` / `tipos_bloqueados`, sem diferenciar maiúsculas nem acentos |
| VALOR_MINIMO | ✔ | V ≥ 100 |
| NAO_VENCIDA | ✔ | vencimento ≥ data-base |
| PRAZO_MAXIMO | ✔ | prazo ≤ 180 dias |
| CONCENTRACAO_MAXIMA_SACADO | ✔ | 10%, raiz de CNPJ |
| PRAZO_MINIMO | ✘ | prazo ≥ 30 dias |
| CONCENTRACAO_MAXIMA_CEDENTE | ✘ | 8%, CNPJ completo |
| VALOR_MAXIMO, CNPJ_CEDENTE_VALIDO, DOCUMENTO_BLOQUEADO | — | extras, valem só se o gestor adicioná-los ao JSON |

### Precificação

- **Desconto simples:** deságio = `V · i · n / base_dias`. Também existe `DESCONTO_COMPOSTO`.
- **Taxa — fonte única = `precificacao.taxa_mensal_percentual` do JSON** (hoje 2,0%), exposta em `/health.taxa_mensal_padrao` (0.02).
  - O form `taxa_mensal` só serve para simulação.
  - O 0,025 é fallback, usado apenas se o JSON não tiver o bloco `precificacao`.

### Smart Batch Optimizer

```mermaid
sequenceDiagram
    participant E as RuleEngine
    participant Q as quant_analytics
    E->>E: fase estática (1x por nota)
    E->>E: simular(ordem original) → baseline
    E->>Q: gerar_ordens_candidatas(itens, restrições)
    Q-->>E: [original, quant(mochila), prazo↑, valor↓, valor↑]
    loop cada candidata
        E->>E: simular(ordem) com ShadowLedger novo
    end
    E->>E: escolhe maior Σ líquido (empate → original)
```

- **Ordem "quant":** primeiro as notas de grupos sem pressão de concentração (elas aumentam o patrimônio do fundo); depois, em cada grupo pressionado, uma mochila 0/1 por DP discretizada (capacidade = folga projetada, valor = líquido); por fim as sobras.
- **Garantias:** `ganho_otimizador_reais ≥ 0` (a original sempre é candidata), e numa duplicata do lote a primeira linha do CSV continua sendo a original.
- **Saída:** `salva_pelo_otimizador = true` quando a ordem escolhida aprova uma nota que a ordem original recusaria. Quando é o contrário (a original aprovaria e o otimizador recusou), a mensagem de concentração ganha uma explicação com o ganho total.
- **Lotes grandes:** acima de 3.000 notas, só a original e a quant são simuladas; o limite duro é `MAX_LINHAS_LOTE = 10.000`.

### API (`/api/v1`)

| método | rota | entrada | saída |
|---|---|---|---|
| GET | `/health` | — | `HealthResponse` (+ `taxa_mensal_padrao`, `tempo_carga_estoque_ms`, `versao_config`) |
| GET | `/validators` | — | JSON de validadores atual |
| PUT | `/validators` | `ValidadoresConfig` | config aplicada; 422 se inválida ou se trocar de fundo |
| POST | `/batches/validate` | multipart: `file`, `data_base?`, `taxa_mensal?`, `otimizar_lote?`, `validadores_override?` | `BatchValidationResponse` |

- **Zero-deploy:** validação semântica (códigos suportados e únicos, tipos e faixas dos parâmetros, método de precificação), escrita atômica (`mkstemp` + `os.replace`), troca da config sob lock e `versao_config++`.
- **Idempotência:** cache LRU (64 entradas) com chave `(sha256 do arquivo, data_base, taxa, otimizar, versao_config, versão do cadastro, hash do override)`. Quando a resposta vem do cache, o header é `X-Idempotent-Replay: true`.
- **Erros:** sempre `{"error": {"code", "message", "details"}}`; 413 para arquivo grande, 500 sem stack trace, com `X-Request-ID` em toda resposta.
- **Observabilidade:** logs `key=value` com `request_id` e sem documentos (CPF/CNPJ).

### Modo carteira (conformidade com o gabarito)

O gabarito oficial `resultado_esperado_100k.json` julga **cada linha do estoque** contra as regras do ANTECIPE. A análise das 100.554 linhas mostrou 3 premissas diferentes do modo lote, e todas foram reproduzidas com 0 divergências:

| ponto | modo lote (upload de notas novas) | modo carteira (gabarito) |
|---|---|---|
| data de referência | data-base única (22/10/2026) | `DATA_AQUISICAO` de cada linha |
| concentração | Shadow Ledger sequencial contra o estoque | estática por fundo, sobre as notas elegíveis; só em nota sem outro erro |
| duplicidade/fraude | 3 níveis contra o estoque | não se aplica (o arquivo é o estoque) |

Entregas: `RuleEngine.validar_carteira`, `POST /api/v1/portfolio/validate`, a CLI `python -m app.validar_carteira` e `tests/test_conformidade_gabarito.py`. Ele exige igualdade linha a linha em todas as regras que dependem do kit e falha com 275 divergências se o teto de concentração mudar de 10% para 9,9%. Pendente: a fonte da situação cadastral usada no gabarito (87 CNPJs, 2.317 linhas). Ela não veio no kit, e a Receita real diverge, porque os CNPJs do dataset são sintéticos e coincidem com outras empresas reais.

## Alternativas consideradas

| alternativa | prós | contras | decisão |
|---|---|---|---|
| **SQLite/Postgres + query por linha** | persistência e consultas ad hoc | ~100k linhas sem necessidade de banco; uma query por nota mata a meta de 15 ms; mais infra no hackathon | descartada: HashMaps em RAM |
| **Pandas para carregar o estoque** | API conhecida | +40 MB de dependência e startup mais lento que o `split` puro; não precisamos de operações vetoriais | descartada |
| **Validar cada nota contra a foto estática do estoque** | simples | permite estourar a concentração dentro do próprio lote | descartada: Shadow Ledger |
| **Otimizador só "ordenar por menor prazo"** (spec original) | trivial | pode piorar o resultado (ex.: teto 10k; nota de 10k em 60 dias vs. nota de 3k em 5 dias) | descartada: simulação de várias candidatas, com a original incluída |
| **Programação inteira exata (PuLP/OR-Tools)** | ótimo global | dependência pesada; a concentração é não linear porque o patrimônio cresce junto | descartada para v1 |
| **Chave canônica literal da spec** (`strip().upper()`) | fiel ao texto | o Excel corta os zeros e o radar perde 16 mil títulos | descartada: zeros normalizados |
| **Consulta online da situação cadastral (BrasilAPI)** | dado real | CNPJs do dataset são sintéticos (404), rate limit e latência por nota | descartada: JSON local recarregável |
| **Vários workers + config num Redis** | escala horizontal | infra a mais; a carga do hackathon não justifica | adiada |

## Riscos e mitigação

| risco | impacto | mitigação |
|---|---|---|
| `PUT /validators` sem autenticação | qualquer pessoa na rede muda as regras | v1 só na rede da demo; v2: API key por header no `PUT` (ver Perguntas) |
| Mais de 1 worker uvicorn | config diverge entre processos depois de um `PUT` | `--workers 1` fixo no Dockerfile e documentado |
| CSV enorme | CPU travada | `MAX_UPLOAD_MB=20`, `MAX_LINHAS_LOTE=10.000` e otimização reduzida acima de 3.000 notas |
| Estatístico altera a interface do `quant_analytics` | otimizador ou precificação quebram | assinaturas documentadas; testes `test_otimizador_*` e `test_precificacao_*` falham na hora; parse BR isolado em `br_utils` |
| Front manda `taxa_mensal=0.025` fixo | sobrescreve a taxa do fundo (2%) | `/health.taxa_mensal_padrao` e contrato documentado; `meta.taxa_mensal_aplicada` mostra a taxa real |
| Patrimônio inclui os 203 títulos vencidos | teto de concentração levemente mais folgado | decisão de negócio em aberto; mudar isso é uma linha em `carregar_estoque` |
| CNPJ fora do `situacao_cadastral.json` conta como ATIVA | a regra deixa passar quem não tem dado | documentado; a fonte real pode substituir o arquivo sem mudar código |
| Trocar o fundo via `PUT` | índice inconsistente | `validar_compatibilidade` → 422 "exige reiniciar" |
| Concorrência entre `PUT` e validação | lote avaliado com config mista | o lote lê uma referência imutável da config no início; a troca é atômica sob lock |

## Plano de implementação

1. ✅ `stock_index` com carga abaixo de 1 s e números conferidos com o perfil do estoque.
2. ✅ `quant_analytics` com precificação e otimizador; `br_utils` com parse BR.
3. ✅ `rule_engine` com handlers dos 9 códigos do JSON, mais 3 extras e 3 de sistema, Shadow Ledger e tradutor.
4. ✅ `main` com rotas, erros padronizados, idempotência e what-if.
5. ✅ 60 testes (`backend/tests`), cobrindo cada regra, os 3 níveis do radar, o Shadow Ledger, o ganho do otimizador ≥ 0, o PUT zero-deploy e o contrato.
6. ✅ Samples 01–03 validados no motor real (14/22 aprovadas; +R$ 1.620.133,33 no 02; 3 alertas de fraude no 03).
7. ⬜ Validar o `docker compose up` na VPS.
8. ⬜ API key no `PUT /validators` (se aprovada).
9. ⬜ Ensaio da demo com o Front consumindo `taxa_mensal_padrao` e a gaveta do gestor chamando `validadores_override`.

## Perguntas em aberto

1. Os **títulos vencidos** do estoque (R$ 919 mil) devem continuar no patrimônio e na exposição, ou o fundo os considera liquidados?
2. **CNPJ sem situação cadastral conhecida** deve aprovar (hoje) ou recusar?
3. Uma nota que **vence na própria data-base** (prazo 0) deve ser aceita? Hoje é, com deságio zero, porque `PRAZO_MINIMO` está desligado.
4. Protegemos o `PUT /validators` com API key já para a demo?
5. `regras_ativas_count` deve continuar contando só os validadores do JSON (7) ou incluir as 3 regras de sistema?
