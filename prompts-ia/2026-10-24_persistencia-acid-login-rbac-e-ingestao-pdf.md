# Histórico de IA — Persistência ACID, Autenticação RBAC e Ingestão de PDFs

- **Data:** 24/10/2026
- **Contexto:** Hackathon Antecipe FIDC (KanaBootCamp)
- **Papel:** Engenharia de Software / Arquitetura de Sistemas Financeiros (Pair Programming com IA)
- **Escopo:** RFC-001 (Persistência ACID), RFC-002 (Autenticação RBAC) e Arquitetura Híbrida para Ingestão de PDFs

---

## 1. Contexto e Objetivos da Sessão

1. **Auditoria End-to-End da Plataforma:**
   - Validação dos fluxos completos de envio de lote e histórico de operações.
   - Identificação e correção cirúrgica de inconsistência de permissão no Front-end (`TelaHistorico.tsx` chamava `/historico/regras`, que retornava 403 para a persona `CEDENTE`).
2. **Execução da RFC-001 (Persistência Transacional ACID e Liquidação Idempotente):**
   - Criação da camada relacional SQLite configurada com PRAGMAs bancários (`journal_mode=WAL`, `synchronous=FULL`, `foreign_keys=ON`, `busy_timeout=5000`).
   - Implementação de transação serializável (`BEGIN IMMEDIATE`) para prevenção de dupla cessão concorrente de recebíveis (`hash_titulo`).
   - Sincronização *Write-Through* em memória RAM com o `StockIndex` $O(1)$.
   - Aplicação rigorosa de TDD (*Test-Driven Development*): código 100% coberto por testes automatizados antes da implementação.
3. **Migração do Sistema de Login e Identidade para o Banco ACID:**
   - Modelagem da tabela `usuarios` com verificação estrita de papéis (`CHECK role IN ('CEDENTE', 'GESTOR')`).
   - Derivação de chaves segura via KDF `scrypt` ($N=2^{14}, r=8, p=1$) com salt aleatório criptográfico de 16 bytes.
   - Mitigação de ataques de enumeração de utilizadores (*timing attack*) através de `_HASH_FALSO` e comparação constante `hmac.compare_digest()`.
4. **Debate e Modelagem para Ingestão de Notas Fiscais em PDF:**
   - Análise comparativa entre OCR tradicional, Document AI, LLM Multimodal puro e a **Arquitetura Híbrida Inteligente** (Heurística SEFAZ / Chave de 44 dígitos + Fallback Multimodal Vision para NFS-e municipais).
   - Levantamento minucioso de riscos e desvantagens reais (burocracia SEFAZ, fontes não mapeadas, múltiplas duplicatas, latência variável e compliance LGPD) com suas devidas mitigações.
   - Modelagem de dados de documentos comprobatórios no SQLite (`documentos_notas_fiscais`, rastreabilidade por SHA-256 antifraude, método de extração e confiança).
5. **Execução da RFC-002 (Autenticação RBAC e Atalhos para a Banca):**
   - Criação de atalhos de 1 clique na `LoginScreen.tsx` para permitir que os jurados da banca examinadora entrem instantaneamente como Gestor ou Cedente sem atrito de digitação, mantendo a autenticação real no servidor.
   - Formalização da especificação em `docs/rfcs/RFC-002-autenticacao-e-rbac.md`.

---

## 2. Registro Cronológico dos Prompts e Respostas Técnicas

### 💬 Prompt 1: Auditoria e Teste Integrado dos Passos 7 e 17 do README
> *"teste o projeto como um todo veja se tem algo q n esta funcionando corretamente. preciso testar o envio e o historico passo 7 e 17 do readme"*

**Decisão e Resposta da IA:**
- Inspeção dos scripts de teste, endpoints da API e componentes do frontend.
- Identificação de falha: Quando logado como `empresa@antecipe.com.br` (`role: CEDENTE`), clicar na aba "Histórico" disparava uma requisição paralela para `GET /api/v1/historico/regras`, que é restrita a gestores e devolvia `HTTP 403 Forbidden`, quebrando a renderização dos lotes da empresa.
- **Correção cirúrgica:**
  - Em `frontend/src/App.tsx`, passado o booleano `ehGestor = persona?.role === "GESTOR"` para a `TelaHistorico`.
  - Em `frontend/src/components/telas/TelaHistorico.tsx`, adicionada guarda condicional e tratamento resiliente de erro com `.catch(() => [])` para que o cedente visualize normalmente seus lotes validados.
  - Recompilação do contêiner do frontend no Docker.

---

### 💬 Prompt 2: Solicitação da RFC-001 e TDD Estrito
> *"agora e o seguinte precisamos fazer um banco de dados de verdade essa e a rfc escreva os testes antes de fazer o banco por agora somente os testes aqui esta a rfc dele n pode existir codigo sem teste: RFC-001: Camada de Persistência Transacional ACID e Liquidação Idempotente..."*

**Decisão e Resposta da IA:**
- Seguir estritamente o ciclo TDD:
  1. Criação do arquivo de testes `backend/tests/test_database_acid.py` com 17 testes automatizados cobrindo:
     - PRAGMAs bancários (`WAL`, `FULL`, `foreign_keys=ON`, `busy_timeout=5000`).
     - Commit e rollback transacional automático em falha.
     - DDL, criação de índices e CHECK constraints (`taxa >= 0`, `valor_nominal > 0`, `status IN (...)`).
     - Restrição de integridade referencial (FK) rejeitando títulos órfãos.
     - Idempotência de simulação e liquidação financeira.
     - Prevenção de dupla cessão concorrente com Rollback imediato.
     - Sincronização *write-through* com a memória RAM ($O(1)$) do `StockIndex`.
     - Endpoints REST `/batches/{batch_hash}/liquidate`, `/batches/history` e `/validators/audit`.
  2. Execução dos testes no terminal para verificar a fase vermelha (*Red Phase*).

---

### 💬 Prompt 3: Implementação da Persistência Transacional ACID
> *"tudo bem pode codar o banco nos usaremos postgress?"*

**Decisão e Resposta da IA:**
- Recomendação de **SQLite com WAL**:
  - Para o contexto do Hackathon e facilidade de avaliação pela banca, o SQLite embarcado em modo WAL oferece garantias ACID reais, zero dependências externas de rede/serviço, latência de frações de milissegundo e facilidade para rodar em qualquer máquina (Windows, Mac ou Linux).
- Implementação em `backend/app/database.py`:
  - `get_acid_connection`: Context manager gerenciando transações com `BEGIN IMMEDIATE` para escrita serializável e commit/rollback automático.
  - `init_db`: Inicialização de tabelas e índices B-Tree.
  - `salvar_simulacao_lote`: Gravação do snapshot do lote.
  - `liquidar_lote_acid`: Transação de compra dos títulos com trava contra dupla venda.
  - `carregar_titulos_liquidados_db`: Carga do histórico na inicialização do servidor.
  - `registrar_auditoria_validadores` e `listar_auditoria_validadores`: Trilha de auditoria das regras do fundo.
- Integração em `backend/app/main.py` e `backend/app/stock_index.py`.
- **Resultado:** 200 testes passando (`200 passed in 55.74s`).

---

### 💬 Prompt 4: Integração do Login no Banco de Dados ACID
> *"fiz umas correcoes no databse mas e entao o banco esta pronto? ele cobre o projeto todo inclusive a parte de login? ent faca o o banco funcionar para o login tbm"*

**Decisão e Resposta da IA:**
- Escrita de testes TDD para usuários e login em `test_database_acid.py` e `test_login.py`.
- Adição da tabela `usuarios` ao `init_db()` do `database.py`.
- Implementação de KDF `scrypt` salteado com 16 bytes e proteção contra timing attack via `_HASH_FALSO`.
- Funções `salvar_usuario`, `autenticar_usuario`, `obter_usuario_por_email` e `obter_usuario_por_id`.
- Conexão do startup (`lifespan`) e do endpoint `/auth/login` em `main.py` para usar a nova tabela de usuários do banco ACID.
- **Resultado:** 204 testes passando (`204 passed in 51.30s`).

---

### 💬 Prompt 5: Arquitetura para Leitura de Notas Fiscais em PDF
> *"estamos pensando em aprimorar para q os usuarios consiguam enviar pdfs de notas fiscais e o sistema coseguir ler o pdf juntal-los banco de dados na mesma formatacao q as outra notas fiscais. n sei como fazer isso da melhor maneira me traga opcoes. leve em consideracao q nem sempre as notas fiscais sao emetidas do mesmo formato, entao o sistema precisa reconhecer todas n importa a formatacao"*

**Decisão e Resposta da IA:**
- Comparação profunda de 4 opções da indústria:
  1. LLM Multimodal / Vision com Structured Outputs (Gemini Flash / GPT-4o-mini).
  2. Arquitetura Híbrida Inteligente (Heurística SEFAZ / Chave 44 dígitos + Fallback Vision).
  3. Document AI Gerenciado (Google Document AI / AWS Textract).
  4. OCR Tradicional Local (pdfplumber + Tesseract + Regex).
- Recomendação da **Opção 2 (Híbrida)** como padrão ouro para FIDCs no Brasil.

---

### 💬 Prompt 6: Análise de Riscos e Desvantagens da Arquitetura Híbrida
> *"qual oustra desvantagem isso tem? gostei dessa"*

**Decisão e Resposta da IA:**
- Mapeamento honesto dos 5 maiores riscos operacionais e técnicos:
  1. *Burocracia da Consulta SEFAZ*: Exigência de e-CNPJ A1 e bloqueio para terceiros não autorizados $\rightarrow$ Mitigação: leitura direta dos dados impressos no PDF com validação matemática da chave (Módulo 11) sem bater nos servidores da SEFAZ.
  2. *Falso Positivo de Heurística*: Fontes Type 3 ou ordem bagunçada gerando valores truncados $\rightarrow$ Mitigação: validação cruzada do valor e chave; qualquer inconsistência desvia para a IA Vision.
  3. *Múltiplas Duplicatas/Parcelas*: Tabelas 2D em PDFs complexos $\rightarrow$ Mitigação: detecção de parcelamento direcionando para o Vision.
  4. *Latência Heterogênea*: 50ms para NF-e vs 2s para NFS-e $\rightarrow$ Mitigação: paralelização de leitura no backend via `asyncio.gather`.
  5. *LGPD e Compliance*: Envio de dados fiscais para APIs de nuvem $\rightarrow$ Mitigação: uso de endpoints enterprise com termos de *Zero Data Retention*.

---

### 💬 Prompt 7: Preparação da Camada de Banco de Dados para os PDFs
> *"agora quero so deixar o banco pronto pra isso"*

**Decisão e Resposta da IA:**
- TDD: Criação prévia de 5 testes em `test_database_acid.py` cobrindo schema, constraints, busca antifraude por hash e liquidação de títulos com chave de acesso e documento vinculado.
- Implementação em `backend/app/database.py`:
  - Nova tabela `documentos_notas_fiscais` com índices B-Tree em `batch_hash`, `chave_acesso` e `hash_arquivo_sha256`.
  - Novas colunas em `lotes_operacoes` (`origem_lote`, `qtd_documentos_pdf`) e em `titulos_adquiridos` (`chave_acesso`, `documento_id`).
  - Rotina de migração incremental automática `_migrar_schema()`.
  - Funções de persistência: `salvar_documento_nota_fiscal`, `listar_documentos_lote`, `obter_documento_por_hash_arquivo`, `obter_documento_por_chave_acesso`.
- **Resultado:** 209 testes passando (`209 passed in 52.25s`).

---

### 💬 Prompt 8: Execução da RFC-002 e Atalhos de Avaliação
> *"eu quero q vc execute a rfc qui esta ela de novo: RFC-002: Sistema de Autenticação Criptográfica, Sessão Stateless Assinada e RBAC..."*

**Decisão e Resposta da IA:**
- Criação formal do documento `docs/rfcs/RFC-002-autenticacao-e-rbac.md`.
- Implementação de botões de atalho de preenchimento rápido em `frontend/src/components/LoginScreen.tsx` ("Preencher Gestor" e "Preencher Cedente").
- Limpeza e estabilização de `carregar_settings()` em `backend/app/main.py`.
- **Resultado:** 214 testes do backend passando (`214 passed in 53.34s`) e build de produção do frontend aprovado (`tsc --noEmit && vite build`).
- Reconstrução e subida de todos os contêineres Docker (`backend`, `frontend`, `mock-receita`) em estado *healthy*.

---

## 3. Indicadores Finais de Engenharia

| Métrica | Valor Atingido |
| :--- | :--- |
| **Total de Testes Automatizados** | **214 testes aprovados** (100% verde) |
| **Tempo de Execução da Suíte** | ~53 segundos |
| **Algoritmo de Hash de Senha** | `scrypt` ($N=16384, r=8, p=1$) + Salt 16B |
| **Proteção Anti-Timing Attack** | Sim (`_HASH_FALSO` + `hmac.compare_digest`) |
| **Protocolo de Sessão** | Stateless assinado `HMAC-SHA256` (8h de validade) |
| **Modo de Persistência** | SQLite WAL com integridade transacional serializável |
| **Prevenção de Dupla Cessão** | Transacional ACID com Rollback atômico |
| **Status dos Contêineres** | `antecipe-backend` (healthy), `antecipe-frontend` (up), `antecipe-mock-receita` (healthy) |
