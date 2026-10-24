# RFC-004: Gerenciamento de Estado e Ciclo de Vida Assíncrono

- **Status:** Proposta
- **Data de Criação:** 24/10/2026
- **Área:** Estado / Fluxo Assíncrono / Concorrência

---

## 1. Contexto
No **ANTECIPE PRO**, a interface precisa reagir a fluxos assíncronos que envolvem upload de arquivos (de poucos KB até 50 MB), processamento analítico no backend (7 a 16s para 100 mil notas), simulações What-If em tempo real e atualização de políticas de risco pelo gestor.

O estado atual reside primordialmente em `useState` distribuídos em [`frontend/src/App.tsx`](file:///c:/Users/Frank%20Targa/Desktop/Kanastra/KanaBootCamp/frontend/src/App.tsx), associados a callbacks assíncronos em `processarLote`.

---

## 2. Problema
1. **Risco de sobrescrita por respostas concorrentes (*Race Conditions*):** Se o operador altera a data-base ou a taxa mensal rapidamente enquanto uma validação de arquivo pesado ainda está em trânsito, múltiplas promessas de `validarLote` ficam ativas simultaneamente. A resposta que chegar por último sobrescreve o estado da tela, independentemente de corresponder ou não aos parâmetros atuais da interface.
2. **Ciclo de vida de carregamento não atômico:** `carregando`, `resultado`, `erroGeral` e `comparativoRegras` são atualizados por chamadas separadas de `setState`, podendo provocar renderizações intermediárias inconsistentes.
3. **Ausência de cancelamento na desmontagem:** Se o usuário navegar ou trocar de contexto enquanto o upload ou a simulação estão em andamento, promessas pendentes continuam executando e tentam atualizar componentes desmontados.

---

## 3. Evidências no Código
- [`frontend/src/App.tsx:59-95`](file:///c:/Users/Frank%20Targa/Desktop/Kanastra/KanaBootCamp/frontend/src/App.tsx#L59-L95): `processarLote` manipula `carregando`, `erroGeral`, `resultado`, `fonteDados`, `replayIdempotente` e `comparativoRegras` sem controle de versão de requisição ou identificador de sequência (*sequence counter* / AbortController).
- [`frontend/src/components/GavetaGestor.tsx:111-125`](file:///c:/Users/Frank%20Targa/Desktop/Kanastra/KanaBootCamp/frontend/src/components/GavetaGestor.tsx#L111-L125): `handleSalvarEPermutar` executa `onAplicarRegras` e ativa temporizador de 3 segundos `setTimeout(() => setSucesso(false), 3000)` sem limpar o timer na desmontagem do componente.

---

## 4. Objetivos
- Eliminar condições de corrida entre requisições assíncronas concorrentes usando tokens de cancelamento (`AbortController`) ou contadores de versão de requisição.
- Unificar os estados de resultado de lote sob um Reducer atômico (`useReducer`) ou máquina de estados finita simples (IDLE, VALIDATING, SUCCESS, ERROR).
- Garantir que estados de erro e loading sejam limpos de maneira determinística antes de cada nova execução.

---

## 5. Não Objetivos
- Introduzir bibliotecas de state machine complexas (como XState).
- Implementar sincronização multi-aba via BroadcastChannel.

---

## 6. Proposta Técnica

### 6.1. Reducer de Estado Operacional
```typescript
type EstadoOperacao =
  | { status: "IDLE"; dados: null; erro: null }
  | { status: "CARREGANDO"; dados: BatchValidationResponse | null; erro: null }
  | { status: "SUCESSO"; dados: BatchValidationResponse; fonte: FonteDados; replay: boolean; erro: null }
  | { status: "ERRO"; dados: BatchValidationResponse | null; erro: string };

type AcaoOperacao =
  | { tipo: "INICIAR_PROCESSAMENTO" }
  | { tipo: "SUCESSO"; payload: { dados: BatchValidationResponse; fonte: FonteDados; replay: boolean } }
  | { tipo: "FALHA"; payload: { erro: string } }
  | { tipo: "LIMPAR_ERRO" };
```

### 6.2. Gerenciador de Concorrência com Sequência
```typescript
const idRequisicaoAtual = useRef(0);

const processarLoteSeguro = useCallback(async (arquivo: File | null, opcoes: OpcoesValidacao) => {
  const seq = ++idRequisicaoAtual.current;
  dispatch({ tipo: "INICIAR_PROCESSAMENTO" });

  try {
    const res = await validarLote(arquivo, opcoes);
    // Descarta se uma requisição mais recente já foi disparada
    if (seq !== idRequisicaoAtual.current) return;
    dispatch({ tipo: "SUCESSO", payload: { dados: res.dados, fonte: res.fonte, replay: res.replayIdempotente } });
  } catch (err) {
    if (seq !== idRequisicaoAtual.current) return;
    dispatch({ tipo: "FALHA", payload: { erro: err instanceof Error ? err.message : "Erro desconhecido." } });
  }
}, []);
```

---

## 7. Alternativas Consideradas
- **React Query / TanStack Query:** Excelente solução para cache de consultas REST, porém adiciona dependências e sobrecarga desnecessária para uma aplicação que é majoritariamente baseada em mutações `POST` de upload de arquivo.
- **Manter múltiplos `useState`:** Mantém o risco latente de inconsistências visuais durante carregamento e transições de tela.

---

## 8. Impacto
- **Benefícios:** Elimina telas congeladas em "Analisando suas notas..." causadas por respostas assíncronas defasadas; garante que a UI represente fielmente os parâmetros selecionados.
- **Riscos:** Necessidade de refatorar chamadas existentes de `setResultado` e `setCarregando`.

---

## 9. Plano de Adoção
1. Criar o reducer `operacaoLoteReducer.ts`.
2. Integrar o controle de sequência no hook `useLoteValidacao`.
3. Validar a ausência de flashes e race conditions em testes de carga.

---

## 10. Critérios de Aceitação
- Disparar 5 requisições rápidas de alteração de taxa resulta apenas na renderização do resultado da última requisição.
- Nenhum aviso de memory leak ou atualização de estado em componente desmontado no console do navegador.

---

## 11. Testes Necessários
- Teste unitário simulando promessas com tempos de resposta invertidos (segunda responde antes da primeira).
- Teste de cancelamento e limpeza de timers em `GavetaGestor`.

---

## 12. Dependências
- [RFC-001: Arquitetura e Organização Modular do Frontend](RFC-001-frontend-architecture.md).
- [RFC-002: Camada Padronizada de Comunicação com a API](RFC-002-api-client.md).

---

## 13. Questões em Aberto
- Devemos persistir o lote ativo em `sessionStorage` para restaurar o estado caso o usuário dê refresh acidental na página?
