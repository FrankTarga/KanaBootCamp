# CONTRATO DE API — ANTECIPE PRO (REST /api/v1)

Documento de auditoria técnica do contrato entre Frontend e Backend (FastAPI).
Fonte canônica da verdade: código-fonte do Backend (`backend/app/main.py`, `backend/app/api_schemas.py`, `backend/app/rule_engine.py`).

---

## 1. Visão Geral de Arquitetura, Segurança e CORS

- **Base URL:** `/api/v1` (porta padrão `8000`).
- **Autenticação:**
  - Header: `X-API-Key` (lido via `Header(None)` no FastAPI como `x_api_key`).
  - Rotas protegidas: exclusivamente `PUT /api/v1/validators`. `GET /api/v1/validators`, `GET /api/v1/health` e `POST /api/v1/batches/validate` são públicos.
  - Origem da chave: variável de ambiente `ADMIN_API_KEY`.
  - Valor default embutido: nenhum. Se `ADMIN_API_KEY` não for configurada no servidor, o endpoint `PUT /validators` é bloqueado com status `403` (`PUT_DESABILITADO`).
  - Comparação em tempo constante: implementada via `hmac.compare_digest(x_api_key.encode(), chave.encode())` prevenindo ataques de timing.
  - Chave em logs: a chave **nunca** é logada. O middleware `request_id_e_log` registra apenas `request_id`, `method`, `path`, `status` e `duracao_ms`.
- **CORS:**
  - Origens permitidas (`allow_origins`): `["*"]`
  - Métodos permitidos (`allow_methods`): `["*"]` (inclui `GET`, `POST`, `PUT`, `OPTIONS`)
  - Cabeçalhos permitidos (`allow_headers`): `["*"]` (permite `X-API-Key`, `Content-Type`, etc.)
  - Headers expostos (`expose_headers`): `["X-Idempotent-Replay", "X-Request-ID"]`
- **Padrão Único de Erro:**
  ```json
  {
    "error": {
      "code": "CODIGO_DO_ERRO",
      "message": "Mensagem descritiva em português",
      "details": []
    }
  }
  ```

---

## 2. Tabelas por Endpoint

### 2.1. `GET /api/v1/health`
Status de prontidão do motor e dados agregados de estoque.

- **Autenticação:** Nenhuma (pública).
- **Request:** Sem parâmetros.
- **Response (200 OK):**
  | Campo | Tipo JSON | Formato / Exemplo | Descrição |
  |---|---|---|---|
  | `status` | string | `"ready"` ou `"loading"` | Estado do motor |
  | `data_base_padrao` | string | `"dd/mm/aaaa"` (ex.: `"22/10/2026"`) | Data-base padrão detectada no estoque |
  | `estoque_total_linhas` | integer | `100554` | Total de linhas do CSV de estoque |
  | `estoque_antecipe_linhas` | integer | `10621` | Linhas pertencentes ao ANTECIPE FIDC |
  | `patrimonio_antecipe_fidc` | number (float) | `53074028.0` | Patrimônio líquido em reais do fundo |
  | `fundos_monitorados` | integer | `18` | Total de fundos carregados em RAM |
  | `regras_ativas_count` | integer | `7` | Quantidade de validadores ativos |
  | `taxa_mensal_padrao` | number (float) | `0.02` (fração decimal) | Taxa mensal padrão definida na precificação (`0.02` = 2,0% a.m.) |
  | `tempo_carga_estoque_ms` | number (float) | `513.1` | Tempo de carga inicial em milissegundos |
  | `versao_config` | integer | `1` | Versão atual da configuração de validadores |
- **Possíveis Erros:** `500` (`ERRO_INTERNO`).

---

### 2.2. `GET /api/v1/validators`
Retorna a configuração completa e ativa de validadores e precificação.

- **Autenticação:** Nenhuma (pública).
- **Request:** Sem parâmetros.
- **Response (200 OK):**
  | Campo | Tipo JSON | Formato / Exemplo | Descrição |
  |---|---|---|---|
  | `fundo.nome` | string | `"ANTECIPE FIDC"` | Nome do fundo |
  | `fundo.cnpj` | string | `"92.234.400/0001-80"` | CNPJ cadastrado |
  | `validadores` | array[object] | `[{ "codigo": "...", "ativo": true, "parametros": {...} }]` | Lista de regras e parâmetros |
  | `precificacao.metodo` | string | `"DESCONTO_SIMPLES"` | Método de cálculo de deságio |
  | `precificacao.taxa_mensal_percentual` | number \| null | `2.0` (percentual no JSON) | Taxa mensal em % configurada |
  | `precificacao.base_dias` | integer | `30` | Base de dias para deságio |
  | `precificacao.prazo_minimo_cobranca_dias` | integer | `5` | Prazo mínimo para cobrança |
- **Possíveis Erros:** `500` (`ERRO_INTERNO`).

---

### 2.3. `PUT /api/v1/validators`
Atualiza regras em disco e recarrega motor atômico em memória.

- **Autenticação:** Obrigatória via header `X-API-Key` (comparada com `ADMIN_API_KEY`).
- **Request Body (JSON):**
  - Objeto `ValidadoresConfig` completo (mesma estrutura retornada pelo `GET`).
- **Response (200 OK):**
  - Objeto `ValidadoresConfig` persistido, com incremento de versão.
- **Possíveis Erros:**
  | Status | Code | Motivo |
  |---|---|---|
  | `401 Unauthorized` | `NAO_AUTORIZADO` | Header `X-API-Key` ausente ou chave incorreta |
  | `403 Forbidden` | `PUT_DESABILITADO` | `ADMIN_API_KEY` não foi configurada nas variáveis de ambiente do backend |
  | `422 Unprocessable` | `CONFIGURACAO_INVALIDA` / `REQUISICAO_INVALIDA` | JSON fora do schema ou regras incompatíveis |
  | `500 Internal Error` | `FALHA_PERSISTENCIA` | Erro ao gravar `validadores_antecipe.json` em disco |

---

### 2.4. `POST /api/v1/batches/validate`
Processa e valida lote de recebíveis, com triplo radar e otimizador de liquidez.

- **Autenticação:** Nenhuma (pública).
- **Request (`multipart/form-data`):**
  | Campo | Tipo Form | Obrigatório? | Descrição e Formato |
  |---|---|---|---|
  | `file` | File (UploadFile) | **Sim** | Arquivo CSV (separador `;`, datas `dd/mm/aaaa`, valores com `,` ou `.`) |
  | `data_base` | string | Não | Data de referência no formato `dd/mm/aaaa`. Se omitido, usa a do estoque (`22/10/2026`) |
  | `taxa_mensal` | string / float | Não | Taxa em **fração decimal** no intervalo `[0, 1[` (ex.: `0.025` para 2,5% a.m.). Se omitido, usa a da precificação |
  | `otimizar_lote` | string / bool | Não | `"true"` (padrão) ou `"false"` para habilitar o algoritmo guloso de maximização de caixa |
  | `validadores_override` | string (JSON) | Não | JSON completo de `ValidadoresConfig` para simulação what-if sem persistência |
- **Limites Operacionais:**
  - Tamanho máximo: 50 MB (`MAX_UPLOAD_MB`). Ultrapassar retorna `413` (`ARQUIVO_GRANDE_DEMAIS`).
  - Linhas máximas: 10.000 linhas (`MAX_LINHAS_LOTE`). Ultrapassar retorna `422` (`ARQUIVO_INVALIDO`).
  - Arquivo vazio: retorna `422` (`ARQUIVO_INVALIDO`).
- **Response (200 OK):**
  - `meta`: telemetria, taxa aplicada (`taxa_mensal_aplicada` em fração decimal), ganhos do otimizador e hash de idempotência.
  - `resumo`: consolidação financeira (`valor_bruto_total`, `desagio_total`, `valor_liquido_receber`, contagem por motivo de recusa).
  - `itens`: listagem nota a nota (`ItemLote`), com status (`APROVADA` / `RECUSADA`), severidade (`OK`, `REGRA_NEGOCIO`, `DUPLICIDADE`, `FRAUDE`), valores e erros.
  - Headers expostos: `X-Idempotent-Replay` (`true` ou `false`), `X-Request-ID`.
- **Possíveis Erros:**
  | Status | Code | Motivo |
  |---|---|---|
  | `413 Payload Too Large` | `ARQUIVO_GRANDE_DEMAIS` | Arquivo excede o limite configurado (`MAX_UPLOAD_MB`) |
  | `422 Unprocessable` | `ARQUIVO_INVALIDO` | Arquivo vazio ou acima de 10.000 linhas |
  | `422 Unprocessable` | `DATA_BASE_INVALIDA` | Formato não é `dd/mm/aaaa` |
  | `422 Unprocessable` | `TAXA_INVALIDA` | Taxa fora de `[0, 1[` ou formato inválido |
  | `422 Unprocessable` | `OTIMIZAR_LOTE_INVALIDO` | Valor booleano inválido |
  | `422 Unprocessable` | `OVERRIDE_INVALIDO` | JSON what-if inválido ou regras inconsistentes |
  | `500 Internal Error` | `ERRO_INTERNO` | Exceção não tratada no motor |

---

## 3. Divergências Detectadas entre Front-end e Back-end

1. **Falha A — `PUT /validators` sem `X-API-Key`:**
   - *Backend:* Exige `X-API-Key` correspondente a `ADMIN_API_KEY`. Responde `401` com `NAO_AUTORIZADO` se ausente ou inválida.
   - *Frontend:* `salvarValidadores` em `frontend/src/services/api.ts` não envia o header `X-API-Key`. Ao receber o `401`, caía em bloco `catch (e)` que salvava apenas em memória e retornava `{ fonte: "demo" }`, passando a falsa impressão de persistência.
2. **Falha B — Fallback indiscriminado em `validarLote`:**
   - *Backend:* Retorna `413` para arquivos grandes e `422` para erros de negócio e formato (`ARQUIVO_INVALIDO`, `TAXA_INVALIDA`, etc.) com mensagem clara e código específico.
   - *Frontend:* O método `validarLote` capturava qualquer exceção (`catch (err)`) e retornava dados simulados de demonstração (`simularLoteLocal`), mascarando o erro real e exibindo dados fictícios à empresa. O fallback só pode ser acionado em caso de indisponibilidade da API (`status === 0` / erro de rede).
3. **Falha C — Taxa fixa em 2% e envio redundante:**
   - *Backend:* Fornece `taxa_mensal_padrao` em `GET /health` (ex.: `0.02`) e permite omitir `taxa_mensal` no `POST /batches/validate` para usar o padrão do fundo.
   - *Frontend:* `App.tsx` mantinha estado estático fixo em `2.0%`, o tipo `HealthResponse` omitia `taxa_mensal_padrao`, e o formulário sempre enviava `taxa_mensal` mesmo quando o usuário nunca tocou no campo.
4. **Falha D — Dependências e `.npmrc` inseguro:**
   - *Frontend:* Arquivo `frontend/.npmrc` continha `strict-ssl=false` e apontava para mirror chinês, com 74 pacotes no `package-lock.json` instalados sem verificação de certificado SSL.

---

## 4. Resultados dos Testes Reais (Fase 1)

Testes executados contra a API local do ANTECIPE PRO (FastAPI) em `http://localhost:8000`:

1. **`GET /health` (200 OK):**
   - Retornou status `200`.
   - Contém `taxa_mensal_padrao: 0.02` (2,0% a.m.), `data_base_padrao: "22/10/2026"`, `estoque_total_linhas: 100554`.
2. **`PUT /validators` (Autenticação):**
   - Sem header `X-API-Key`: Retornou `401 Unauthorized` (`NAO_AUTORIZADO: API key ausente ou inválida (header X-API-Key).`).
   - Com header `X-API-Key` (chave configurada no servidor): Retornou `200 OK` com o payload de regras persistido.
3. **Preflight CORS (`OPTIONS /validators`):**
   - Requisição com `Origin: http://localhost:5173`, `Access-Control-Request-Method: PUT`, `Access-Control-Request-Headers: x-api-key,content-type`.
   - Resposta: `200 OK`, `Access-Control-Allow-Origin: *`, `Access-Control-Allow-Methods: DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT, QUERY`, `Access-Control-Allow-Headers: x-api-key,content-type`. Preflight liberado com sucesso.
4. **Erros no `POST /batches/validate`:**
   - CSV malformado: Retornou `422 Unprocessable Entity` com `code: "ARQUIVO_INVALIDO"` e mensagem detalhada das colunas esperadas.
   - Arquivo acima do limite (> 50 MB): Retornou `413 Payload Too Large` com `code: "ARQUIVO_GRANDE_DEMAIS"` e mensagem `"O arquivo passa do limite de 50 MB."`.

---

## 5. Pendências do Dev Back-end

Nenhuma pendência impeditiva no momento. O backend implementa CORS permissivo (`allow_origins=["*"]`, `allow_methods=["*"]`, `allow_headers=["*"]`) e timing-safe comparison em `PUT /validators`.
Aviso para o time de infraestrutura: certificar-se de definir `ADMIN_API_KEY` no ambiente de produção para que o endpoint de alteração de validadores esteja liberado para o perfil do gestor.
