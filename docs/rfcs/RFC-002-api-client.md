# RFC-002: Camada Padronizada de Comunicação com a API (Client HTTP)

- **Status:** Proposta
- **Data de Criação:** 24/10/2026
- **Área:** Serviços / Rede / Cliente HTTP

---

## 1. Contexto
A comunicação entre o frontend e a API REST do ANTECIPE PRO (`/api/v1`) é centralizada no arquivo [`frontend/src/services/api.ts`](file:///c:/Users/Frank%20Targa/Desktop/Kanastra/KanaBootCamp/frontend/src/services/api.ts), baseando-se na API nativa `fetch` com encapsulamento na função utilitária `requisitar<T>`.

As correções cirúrgicas recentes estabeleceram que falhas HTTP com status diferente de zero (ex.: 401, 413, 422) devem ser propagadas imediatamente, restringindo o fallback de demonstração unicamente a `status === 0` (servidor offline / erro de rede).

---

## 2. Problema
1. **Tratamento de timeout estático e sem cancelamento de requisições concorrentes:** O timeout de 8.000 ms é fixo para todas as chamadas. Para arquivos CSV grandes (até 50 MB permitidos pelo backend), 8 segundos podem ser insuficientes em redes instáveis. Além disso, se o usuário arrasta um novo lote enquanto uma validação anterior ainda está em trânsito, a primeira requisição continua rodando e pode sobrescrever o resultado mais recente (*race condition*).
2. **Desserialização de erros complexos:** Quando a API responde `422 Unprocessable Entity` com arrays detalhados no campo `details` (ex.: lista de colunas faltantes ou inconsistências de regras), a classe `ApiError` guarda os dados, mas não existe um helper utilitário para formatar esses detalhes de maneira padronizada para apresentação na UI.
3. **Ausência de retry automático para operações idempotentes seguras:** Requisições `GET /health` e `GET /validators` falham definitivamente se houver uma oscilação momentânea de rede, mesmo sendo 100% idempotentes e seguras para repetição imediata.

---

## 3. Evidências no Código
- [`frontend/src/services/api.ts:124-154`](file:///c:/Users/Frank%20Targa/Desktop/Kanastra/KanaBootCamp/frontend/src/services/api.ts#L124-L154):
  ```typescript
  async function requisitar<T>(caminho: string, init?: RequestInit, timeoutMs = 8000): Promise<{ dados: T; resposta: Response }> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    // Timeout fixo de 8s, sem expor abortSignal para cancelamento manual pelo chamador
  ```
- [`frontend/src/services/api.ts:16-26`](file:///c:/Users/Frank%20Targa/Desktop/Kanastra/KanaBootCamp/frontend/src/services/api.ts#L16-L26): Definição de `ApiError` com `details: unknown[] = []`, sem tipagem discriminada dos formatos do FastAPI (`{"campo": string, "mensagem": string}` vs strings simples).

---

## 4. Objetivos
- Padronizar o cliente HTTP em um módulo dedicado `ApiClient`.
- Permitir cancelamento explícito de requisições pendentes de upload ao submeter novo lote.
- Configurar timeouts dinâmicos adequados ao tipo de operação (ex.: 5s para `GET /health`, 60s para upload de arquivos grandes no `POST /batches/validate`).
- Implementar mecanismo de retry exponencial leve exclusivo para métodos `GET`.
- Extrair e tipar adequadamente `details` para fácil renderização na interface.

---

## 5. Não Objetivos
- Instalar bibliotecas externas pesadas como `axios`. O `fetch` nativo moderno com `AbortController` atende plenamente sem inflar o bundle.

---

## 6. Proposta Técnica

### 6.1. Interface de Erro Tipada
```typescript
export interface DetalheErroApi {
  campo?: string;
  mensagem: string;
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
    public readonly details: (string | DetalheErroApi)[] = [],
    public readonly requestId?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }

  get mensagemCompleta(): string {
    if (!this.details.length) return this.message;
    const detalhesFormatados = this.details
      .map((d) => (typeof d === "string" ? d : `${d.campo ? d.campo + ": " : ""}${d.mensagem}`))
      .join(" | ");
    return `${this.message} (${detalhesFormatados})`;
  }
}
```

### 6.2. Timeout Configurável e Suporte a Cancelamento
```typescript
export interface RequisicaoOpcoes extends RequestInit {
  timeoutMs?: number;
  retries?: number;
  signalExterno?: AbortSignal;
}

export async function requisitarHttp<T>(
  caminho: string,
  opcoes: RequisicaoOpcoes = {},
): Promise<{ dados: T; headers: Headers }> {
  const { timeoutMs = 10000, retries = 0, signalExterno, ...init } = opcoes;
  // Combina signal externo com timeout interno
}
```

---

## 7. Alternativas Consideradas
- **Utilizar Axios:** Traz interceptors nativos, mas adiciona ~15 kB ao bundle final e reintroduz abstrações desnecessárias para uma API com apenas 4 endpoints.
- **Manter `requisitar` monolítico em `api.ts`:** Dificulta a separação de testes unitários da camada de transporte e mistura regras de mock com chamadas de rede.

---

## 8. Impacto
- **Benefícios:** Elimina congelamentos em uploads de lotes volumosos; previne condições de corrida quando o usuário altera parâmetros repetidamente; melhora a legibilidade dos logs de telemetria com `X-Request-ID`.
- **Riscos:** Necessidade de garantir que sinais de aborto não sejam confundidos com erros de rede `status === 0`.

---

## 9. Plano de Adoção
1. Refatorar a classe `ApiError` mantendo total retrocompatibilidade com o código atual.
2. Adicionar o parâmetro de timeout adaptativo (`upload` vs `query`).
3. Conectar o cancelamento no hook `useLoteValidacao`.

---

## 10. Critérios de Aceitação
- Uploads de arquivos de até 50 MB não sofrem timeout prematuro antes de 60 segundos.
- Submeter dois lotes em rápida sucessão cancela a primeira requisição sem quebrar o estado da aplicação.
- Códigos de erro HTTP (401, 403, 413, 422, 500) retornam instâncias de `ApiError` com `requestId` populado pelo header `X-Request-ID`.

---

## 11. Testes Necessários
- Teste unitário de timeout simulando resposta lenta.
- Teste de cancelamento via `AbortController`.
- Teste de extração correta de cabeçalhos `X-Idempotent-Replay` e `X-Request-ID`.

---

## 12. Dependências
- [RFC-003: Contratos e Tipagem TypeScript](RFC-003-api-contracts-and-types.md).

---

## 13. Questões em Aberto
- O frontend deve exibir um botão para copiar o `X-Request-ID` em caso de erro 500 para facilitar suporte técnico?
