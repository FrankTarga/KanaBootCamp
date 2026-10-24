# RFC-003: Sincronização de Contratos e Tipagem Estrita TypeScript

- **Status:** Proposta
- **Data de Criação:** 24/10/2026
- **Área:** Tipagem / Schemas / Contratos

---

## 1. Contexto
A integridade entre frontend e backend no ANTECIPE PRO apoia-se no espelhamento direto entre os modelos Pydantic v2 em [`backend/app/api_schemas.py`](file:///c:/Users/Frank%20Targa/Desktop/Kanastra/KanaBootCamp/backend/app/api_schemas.py) e as interfaces TypeScript em [`frontend/src/types/api.ts`](file:///c:/Users/Frank%20Targa/Desktop/Kanastra/KanaBootCamp/frontend/src/types/api.ts).

A regra central do repositório dita: *"O código do back-end é a fonte da verdade do contrato. Mudou um, muda o outro no mesmo commit."*

---

## 2. Problema
1. **Descompasso após novas features no backend:** As recentes rotas de histórico SQLite adicionadas no backend (`GET /api/v1/historico/lotes` e `GET /api/v1/historico/regras`) criaram modelos Pydantic (`HistoricoLote`, `MudancaRegras`, `PaginaHistoricoLotes`, `PaginaMudancasRegras`) que ainda não foram tipados no frontend, impedindo a criação de uma tela de histórico auditável.
2. **Tipagem frouxa de parâmetros de validação:** No frontend, `ValidadorConfig.parametros` está tipado como `Record<string, ValorParametro>`, enquanto o backend possui parâmetros específicos e conhecidos por validador (ex.: `situacoes_aceitas: string[]`, `percentual_maximo: number`, `agrupamento: "RAIZ_CNPJ" | "CNPJ_COMPLETO"`). A falta de união discriminada impede o autocompletion e validação estática no TypeScript.
3. **Ausência de validação de schema em tempo de execução (Runtime Validation):** Se o backend alterar a serialização de um campo numérico (ex.: Decimal serializado como string ou data com formato ISO em vez de `dd/mm/aaaa`), o frontend não captura o erro no momento do recebimento, propagando valores `NaN` ou quebrando componentes na renderização.

---

## 3. Evidências no Código
- [`backend/app/api_schemas.py:212-256`](file:///c:/Users/Frank%20Targa/Desktop/Kanastra/KanaBootCamp/backend/app/api_schemas.py#L212-L256): Modelos Pydantic `HistoricoLote`, `PaginaHistoricoLotes`, `MudancaRegras` presentes no backend, sem contrapartida em `frontend/src/types/api.ts`.
- [`frontend/src/types/api.ts:58-62`](file:///c:/Users/Frank%20Targa/Desktop/Kanastra/KanaBootCamp/frontend/src/types/api.ts#L58-L62):
  ```typescript
  export type ValorParametro = string | number | boolean | string[] | number[] | null;
  export interface ValidadorConfig {
    codigo: string;
    ativo: boolean;
    parametros: Record<string, ValorParametro>;
  }
  ```
  Permite qualquer chave/valor arbitrário, levando a verificações manuais propensas a falha na `GavetaGestor.tsx`.

---

## 4. Objetivos
- Completar o espelhamento de 100% dos modelos Pydantic no TypeScript, incluindo as novas rotas de Histórico SQLite.
- Tipar com uniões discriminadas os parâmetros conhecidos de cada validador do `validadores_antecipe.json`.
- Estabelecer um script de checagem automatizada de contrato entre `api_schemas.py` e `api.ts`.
- Tipar explicitamente formatos estritos (ex.: `DataBR = `${number}/${number}/${number}``).

---

## 5. Não Objetivos
- Adicionar bibliotecas pesadas de validação em runtime (como `Zod` de 60 kB), a menos que estritamente justificável; asserções leves de tipagem com Type Guards nativos são preferíveis.

---

## 6. Proposta Técnica

### 6.1. Adição dos Tipos de Histórico SQLite
```typescript
// frontend/src/types/api.ts

export interface HistoricoLote {
  id: number;
  criado_em: string; // ISO 8601 UTC
  request_id: string;
  chave_idempotencia: string;
  batch_hash: string;
  modo: ModoValidacao;
  data_base: string;
  taxa_mensal: number;
  otimizar_lote: boolean;
  versao_config: number;
  what_if: boolean;
  replay: boolean;
  total_notas: number;
  qtd_aprovadas: number;
  qtd_recusadas: number;
  qtd_alertas_fraude: number;
  valor_bruto_total: number;
  valor_liquido_receber: number;
  tempo_processamento_ms: number;
}

export interface PaginaHistoricoLotes {
  total: number;
  limite: number;
  offset: number;
  itens: HistoricoLote[];
}
```

### 6.2. Tipagem Discriminada dos Parâmetros das 12 Regras
```typescript
export interface ParametrosConcentracaoSacado {
  percentual_maximo: number;
  agrupamento?: "RAIZ_CNPJ" | "CNPJ_COMPLETO";
}

export interface ParametrosSituacaoCadastral {
  situacoes_aceitas: string[];
}

export interface ParametrosValorMinimo {
  valor_minimo: number;
}

export interface ParametrosPrazoMaximo {
  prazo_maximo_dias: number;
}
```

---

## 7. Alternativas Consideradas
- **Geração automática via OpenAPI (openapi-typescript):** Altamente recomendada para projetos com CI contínua, mas requer que a API esteja rodando para gerar o `openapi.json` ou exportar estaticamente. No hackathon, a manutenção manual estrita com teste de contrato é mais rápida.

---

## 8. Impacto
- **Benefícios:** Autocomplete perfeito nos componentes de UI; eliminação de bugs onde nomes de parâmetros eram digitados errados na gaveta do gestor; preparação do frontend para consumir o histórico SQLite.
- **Riscos:** Nenhum; alterações são puramente aditivas e melhoram a tipagem existente.

---

## 9. Plano de Adoção
1. Adicionar os tipos de histórico no `api.ts`.
2. Adicionar type guards para os parâmetros dos validadores.
3. Criar teste de regressão de tipos no CI (`tsc --noEmit`).

---

## 10. Critérios de Aceitação
- `frontend/src/types/api.ts` contém 100% dos modelos do `backend/app/api_schemas.py`.
- Nenhum uso de `any` em `frontend/src/types/api.ts`.
- `npm run typecheck` compila com 0 erros.

---

## 11. Testes Necessários
- Teste de compilação estática (`tsc --noEmit`).
- Teste unitário de integridade que compara chaves de schema de mock com interfaces.

---

## 12. Dependências
- Nenhuma.

---

## 13. Questões em Aberto
- O campo `pct_das_recusadas` em `GrupoUmProblema` deve ser tratado no frontend como float `0.0 a 100.0` ou fração `0.0 a 1.0`? (Confirmado no backend: já vem calculado de 0 a 100).
