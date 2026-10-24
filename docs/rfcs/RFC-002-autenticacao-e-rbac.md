# RFC-002: Sistema de Autenticação Criptográfica, Sessão Stateless Assinada e RBAC

- **Status:** Implementado / Em Produção
- **Contexto:** Plataforma Antecipe Pro (Hackathon Antecipe FIDC)
- **Módulos Afetados:** `backend/app/database.py`, `backend/app/sessao.py`, `backend/app/main.py`, `frontend/src/components/LoginScreen.tsx`
- **Padrão de Segurança:** Derivação de Chave `scrypt` (KDF) + Token Stateless Assinado via `HMAC-SHA256` + Isolamento de Escopo Multi-Tenant (`CEDENTE` vs. `GESTOR`)

---

## 1. Resumo Executivo e Motivação
Em operações de antecipação de recebíveis de um FIDC, existem dois atores com privilégios assimétricos:
1. **Empresa Cedente (`role: CEDENTE`):** Submete lotes CSV de recebíveis, simula taxas/deságio, visualiza diagnósticos de recusa e consulta exclusivamente o histórico dos lotes que a própria empresa enviou.
2. **Gestor do Fundo / Banca (`role: GESTOR`):** Audita toda a carteira histórica de todos os cedentes, analisa relatórios consolidados de perdas e altera parâmetros do motor de regras em tempo real (*Zero-Deploy Engine* via `PUT /api/v1/validators`).

O objetivo desta RFC é especificar um mecanismo de autenticação **100% verdadeiro e verificado no servidor**, utilizando apenas bibliotecas nativas do Python (`hashlib`, `hmac`, `sqlite3`) para eliminar dependências externas vulneráveis, sem bloquear a avaliação automatizada dos endpoints públicos da API pela banca examinadora.

---

## 2. Arquitetura Criptográfica e Armazenamento de Credenciais

### 2.1. Hashing de Palavras-Passe com `scrypt` e Proteção Anti-Timing Attack
Nenhuma palavra-passe é armazenada em texto limpo. Na criação ou atualização de utilizadores (`salvar_usuario` no `database.py`), o sistema aplica a função de derivação de chave **scrypt** (RFC 7914):
- **Parâmetros de Custo:** $N = 2^{14}$ (16.384 iterações), $r = 8$, $p = 1$, com `salt` criptográfico aleatório de 16 bytes (`os.urandom(16)`).
- **Formato de Persistência:** `scrypt$<salt_hex>$<digest_hex>` gravado na tabela `usuarios` do SQLite ACID.
- **Mitigação de Timing Attack (Enumeração de Utilizadores):** Quando um e-mail inexistente tenta autenticar em `POST /api/v1/auth/login`, o motor executa a verificação contra um `_HASH_FALSO` pré-computado em memória e compara os *digests* através de `hmac.compare_digest()` em tempo constante $O(1)$. Isso impede que um atacante descubra quais e-mails estão cadastrados medindo a diferença de milissegundos na resposta HTTP.

### 2.2. Tokens de Sessão Assinados (`sessao.py`)
Em vez de depender de bibliotecas externas pesadas de JWT, implementamos um protocolo de token assinado padrão RFC 2104 (`HMAC-SHA256`):
- **Estrutura do Token:** `<payload_base64url>.<assinatura_hmac_sha256_base64url>`
- **Conteúdo do Payload:** `{ "id": int, "email": str, "nome": str, "cargo": str, "role": "CEDENTE" | "GESTOR", "exp": int }`
- **Verificação:** A cada requisição autenticada (`GET /api/v1/auth/me` e `/api/v1/historico/*`), o servidor recalcula a assinatura HMAC usando o `sessao_segredo` do servidor e valida o *timestamp* de expiração (`exp`). Qualquer tentativa de adulterar o `role` de `CEDENTE` para `GESTOR` no Front-end invalida a assinatura criptográfica imediatamente (`HTTP 401`).

---

## 3. Modelo de Dados (Tabela `usuarios` no SQLite ACID)

```sql
CREATE TABLE IF NOT EXISTS usuarios (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    email      TEXT    NOT NULL UNIQUE,
    senha_hash TEXT    NOT NULL,
    nome       TEXT    NOT NULL,
    cargo      TEXT    NOT NULL,
    role       TEXT    NOT NULL CHECK (role IN ('CEDENTE', 'GESTOR')),
    criado_em  TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_usuarios_email ON usuarios(email);
```

### 3.1. Provisionamento Automático no Startup (Lifespan Seed)
Durante a inicialização da API (`lifespan` no `main.py`), o sistema garante de forma idempotente (`ON CONFLICT(email) DO UPDATE`) a existência das duas contas oficiais de avaliação:
- **Conta Cedente Padrão:** `empresa@antecipe.com.br` (`role: CEDENTE`)
- **Conta Gestor / Banca Padrão:** `banca@antecipe.com.br` (`role: GESTOR`)

---

## 4. Matriz de Controlo de Acesso (RBAC) e Compatibilidade com o Hackathon
Para cumprir simultaneamente a segurança da aplicação e o requisito do edital (*"a mesma validação disponível pela tela e por uma API"*), as rotas seguem uma política de acesso híbrida:

| Endpoint | Método | Permissão Exigida | Comportamento por Perfil |
| :--- | :--- | :--- | :--- |
| `/api/v1/auth/login` | POST | Público | Valida credenciais no SQLite e emite o token Bearer assinado. |
| `/api/v1/auth/me` | GET | Token Bearer | Valida assinatura e expiração; reconstrói estado da UI após F5. |
| `/api/v1/batches/validate` | POST | Público + Bearer Opcional | Funciona via curl/Swagger sem login. Se enviar Bearer, vincula o lote ao `usuario_id` no histórico. |
| `/api/v1/historico/lotes` | GET | Token Bearer | **CEDENTE:** Filtra apenas lotes enviados pela própria conta.<br>**GESTOR:** Visualiza todos os lotes de todas as empresas. |
| `/api/v1/historico/regras` | GET | Token Bearer (`GESTOR`) | Exclusivo para o Gestor auditar versões de regras (HTTP 403 para Cedente). |
| `/api/v1/validators` | PUT | X-API-Key + Auditoria | Altera regras sem deploy e grava o e-mail do Gestor na tabela `auditoria_regras`. |

---

## 5. Fluxo de Experiência do Utilizador no Front-end (`LoginScreen.tsx`)
1. **Seleção Explícita de Persona:** O utilizador seleciona visualmente o cartão de perfil (Empresa Cedente ou Gestor do Fundo). O sistema valida se a conta autenticada no servidor corresponde ao perfil selecionado.
2. **Sem atalho de senha na tela:** o preenchimento em 1 clique com as credenciais oficiais foi removido, porque colocava as senhas no repositório público e no JS que o navegador baixa. A banca digita a senha, combinada fora do Git.
3. **Isolamento de Sessão no Logout:** Ao clicar em "Sair", o `App.tsx` remove o token do `localStorage`, limpa os lotes em memória e fecha a gaveta de configuração do gestor, garantindo que uma empresa não visualize dados residuais de outra sessão.
