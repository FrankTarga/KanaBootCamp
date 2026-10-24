# RFC-001: Arquitetura e Organização Modular do Frontend

- **Status:** Proposta
- **Data de Criação:** 24/10/2026
- **Área:** Arquitetura / Estrutura de Código

---

## 1. Contexto
O frontend do **ANTECIPE PRO** foi estruturado inicialmente como uma Single Page Application (SPA) em React 18 com TypeScript e Tailwind CSS, agrupando componentes em `frontend/src/components/`, telas em `frontend/src/components/telas/`, serviços em `frontend/src/services/` e utilitários em `frontend/src/utils/`. 

Com o crescimento das funcionalidades (Triplo Radar, Smart Batch Optimizer, Pareto de Recusas, gaveta What-If e suporte a múltiplos modos de validação), o arquivo [`frontend/src/App.tsx`](file:///c:/Users/Frank%20Targa/Desktop/Kanastra/KanaBootCamp/frontend/src/App.tsx) passou a acumular mais de 10 estados reativos interdependentes, roteamento via hash, orquestração de chamadas de API e manipulação direta de visualização.

---

## 2. Problema
1. **Acoplamento excessivo em `App.tsx`:** O componente raiz gerencia simultaneamente:
   - Roteamento hash (`#envio`, `#resumo`, `#estatistica`, `#notas`);
   - Parâmetros operacionais (`dataBase`, `taxaMensalPercentual`, `taxaAlteradaManualmente`, `otimizarLote`, `modo`);
   - Estado de resultados financeiros e lote (`resultado`, `arquivoAtual`, `loteAtual`, `fonteDados`, `replayIdempotente`);
   - Controle de UI modal/gaveta (`drawerGestorAberto`, `comparativoRegras`, `motivoFiltroAtivo`).
2. **Duplicação de responsabilidade de formatação e cálculos:** Lógicas de agregação e filtros presentes em `TabelaRecebiveis.tsx`, `TelaEstatistica.tsx` e `graficos.tsx` acessam diretamente estruturas internas de `ItemLote` sem uma camada intermediária de selectors/hooks.
3. **Escalabilidade reduzida:** Adicionar uma nova tela ou métrica exige modificar `App.tsx` e propagar *props* através de múltiplos níveis (*prop drilling*).

---

## 3. Evidências no Código
- [`frontend/src/App.tsx:19-39`](file:///c:/Users/Frank%20Targa/Desktop/Kanastra/KanaBootCamp/frontend/src/App.tsx#L19-L39): Declaração de 11 estados independentes num único componente.
- [`frontend/src/App.tsx:60-95`](file:///c:/Users/Frank%20Targa/Desktop/Kanastra/KanaBootCamp/frontend/src/App.tsx#L60-L95): Função `processarLote` orquestra chamadas de API, cálculo de comparativos de regras, controle de flags e navegação de tela.
- [`frontend/src/App.tsx:136-190`](file:///c:/Users/Frank%20Targa/Desktop/Kanastra/KanaBootCamp/frontend/src/App.tsx#L136-L190): Renderização condicional estática de todas as telas em um único JSX.

---

## 4. Objetivos
- Desacoplar o gerenciamento de estado e chamadas de rede da casca visual de roteamento.
- Criar Custom Hooks de domínio (`useLoteValidacao`, `useGestorRules`, `useNavegacaoHash`).
- Estabelecer uma separação limpa entre componentes puramente apresentacionais (*dumb components*) e componentes com estado (*smart containers*).
- Preservar o bundle leve e sem dependências pesadas de gerenciamento de estado global (como Redux ou MobX).

---

## 5. Não Objetivos
- Reescrever a interface ou alterar o design system Kanastra.
- Introduzir bibliotecas externas pesadas de roteamento (como `react-router-dom`), mantendo o roteamento leve via Hash nativo que já atende aos requisitos de recarregamento e compartilhamento de URL.

---

## 6. Proposta Técnica

### 6.1. Reestruturação das Pastas
```
frontend/src/
├── hooks/                      # Custom hooks de orquestração
│   ├── useLoteValidacao.ts    # Envio de lote, recálculo e estados de resposta
│   ├── useGestorRules.ts      # Leitura e atualização de validadores (X-API-Key)
│   └── useHashRoute.ts        # Roteamento baseado em window.location.hash
├── features/                   # Módulos verticais de domínio
│   ├── envio/                 # Tela de upload, dropzone, modo lote/carteira
│   ├── resumo/                # Extrato financeiro, deságio e métricas
│   ├── estatistica/           # Gráficos Pareto, clusters de recusa
│   ├── notas/                 # Tabela com busca, filtros e exportações CSV
│   └── gestor/                # Gaveta lateral de regras e What-If
├── services/                  # Comunicação pura com backend e client HTTP
├── types/                     # Contrato TypeScript espelhado do backend
└── utils/                     # Formatadores e helpers utilitários
```

### 6.2. Exemplo: Extração do Hook `useLoteValidacao`
```typescript
export function useLoteValidacao() {
  const [resultado, setResultado] = useState<BatchValidationResponse | null>(null);
  const [carregando, setCarregando] = useState<boolean>(false);
  const [erro, setErro] = useState<string | null>(null);

  const processar = useCallback(async (arquivo: File | null, opcoes: OpcoesValidacao) => {
    setCarregando(true);
    setErro(null);
    try {
      const res = await validarLote(arquivo, opcoes);
      setResultado(res.dados);
      return res;
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Erro na validação do lote.";
      setErro(msg);
      throw err;
    } finally {
      setCarregando(false);
    }
  }, []);

  return { resultado, carregando, erro, setErro, processar };
}
```

---

## 7. Alternativas Consideradas
- **Adoção de Redux Toolkit / Zustand:** Rejeitada por adicionar sobrecarga cognitiva e bytes extras desnecessários para uma aplicação cujo ciclo de vida está centrado em torno de um único lote ativo por sessão.
- **Manter tudo em `App.tsx`:** Inviável a médio prazo; qualquer nova tela ou validação continuará tornando o componente raiz um monólito frágil.

---

## 8. Impacto
- **Benefícios:** Testabilidade isolada de cada hook sem necessidade de renderizar a árvore inteira de componentes; redução de linhas em `App.tsx` de ~200 para ~60 linhas; legibilidade imediata para novos desenvolvedores.
- **Riscos:** Possibilidade de quebra de referências de imports durante a movimentação de arquivos.

---

## 9. Plano de Adoção
1. **Fase 1:** Criar `hooks/useHashRoute.ts` e simplificar o roteamento em `App.tsx`.
2. **Fase 2:** Criar `hooks/useLoteValidacao.ts` e isolar as chamadas `validarLote` e `simularLoteLocal`.
3. **Fase 3:** Modularizar telas e subcomponentes nas pastas de *features*.

---

## 10. Critérios de Aceitação
- `App.tsx` passa a conter apenas o container de layout e orquestração de rotas.
- Nenhum estado duplicado de arquivo ou lote entre telas.
- `npm run build` e `npm run typecheck` executam sem warnings ou erros.

---

## 11. Testes Necessários
- Testes unitários dos novos Custom Hooks usando `@testing-library/react-hooks` ou `renderHook` do Vitest.
- Teste de regressão visual e funcional em todas as 4 telas (`#envio`, `#resumo`, `#estatistica`, `#notas`).

---

## 12. Dependências
- Nenhuma dependência externa nova.

---

## 13. Questões em Aberto
- O histórico de lotes validados no SQLite do backend deverá ser consumido em uma nova tela de "Histórico" no menu lateral?
