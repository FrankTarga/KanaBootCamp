# RFC-006: Integridade de Dados Financeiros e Anti-Fraude na Interface

- **Status:** Proposta
- **Data de Criação:** 24/10/2026
- **Área:** Negócio / Métricas Financeiras / Visualização de Risco

---

## 1. Contexto
No ecossistema de recebíveis do ANTECIPE PRO, decisões de compra envolvem milhões de reais. O motor de risco e precificação do backend calcula matematicamente:
- Valor bruto enviado, aprovado e recusado;
- Deságio comercial simples (`valor_nominal * taxa_mensal * (prazo / 30)`);
- Valor líquido a ser creditado na conta da empresa;
- Prazo médio ponderado da carteira;
- Triplo radar anti-fraude (duplicidade no lote, no fundo ou em 17 fundos externos).

A interface precisa apresentar esses dados com exatidão contábil, sem recalcular regras de negócio no frontend e sem gerar discrepâncias entre extrato consolidado e tabela nota a nota.

---

## 2. Problema
1. **Risco de recálculo redundante no cliente:** Em versões preliminares ou no modo mock, regras de deságio e filtros de concentração eram parcialmente duplicados em JavaScript, gerando risco de arredondamentos divergentes entre Python (onde `Decimal` ou `float` de alta precisão é utilizado) e o motor V8 do navegador.
2. **Consistência estrita entre Resumo e Tabela:** A soma de `valor_nominal` e `valor_liquido` das linhas em `itens` na `TabelaRecebiveis.tsx` deve fechar exatamente com os totais exibidos no Extrato em `TelaResumo.tsx`.
3. **Visibilidade de Alertas de Fraude Crítica:** Quando `qtd_alertas_fraude > 0`, a interface deve garantir que o operador não possa concluir ou antecipar o lote inadvertidamente sem visualizar o alerta de duplicidade cruzada entre fundos.

---

## 3. Evidências no Código
- [`frontend/src/components/telas/TelaResumo.tsx:58-62`](file:///c:/Users/Frank%20Targa/Desktop/Kanastra/KanaBootCamp/frontend/src/components/telas/TelaResumo.tsx#L58-L62):
  ```tsx
  <Linha rotulo="Valor enviado" detalhe={`${resumo.total_notas} notas`} valor={resumo.valor_bruto_total} />
  <Linha rotulo="Ficou de fora" detalhe={`${resumo.qtd_recusadas} recusadas`} valor={resumo.valor_bruto_recusado} negativo />
  <Linha rotulo="Custo da antecipação" detalhe={`...`} valor={resumo.desagio_total} negativo />
  ```
  O extrato consome diretamente os valores calculados pelo backend sem mutação.
- [`frontend/src/components/telas/graficos.tsx:22-30`](file:///c:/Users/Frank%20Targa/Desktop/Kanastra/KanaBootCamp/frontend/src/components/telas/graficos.tsx#L22-L30): O gráfico "Do enviado ao recebido" desenha a proporcionalidade das barras com base em `resumo.valor_bruto_total`.
- [`frontend/src/utils/formatters.ts:4-19`](file:///c:/Users/Frank%20Targa/Desktop/Kanastra/KanaBootCamp/frontend/src/utils/formatters.ts#L4-L19): Formatador `formatarMoeda` baseado em `Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' })`.

---

## 4. Objetivos
- Estabelecer a diretriz de **Cálculo Zero no Frontend**: a interface atua puramente como renderizador fiel dos dados validados pelo backend.
- Garantir coerência matemática absoluta entre os números exibidos nas 4 telas (`#resumo`, `#estatistica`, `#notas` e gaveta).
- Padronizar o tratamento de arredondamentos financeiros para 2 casas decimais (padrão monetário brasileiro BRL).
- Bloquear fluxos de aprovação de notas marcadas com severidade `FRAUDE` ou `DUPLICIDADE`.

---

## 5. Não Objetivos
- Implementar cálculo de IOF ou taxas acessórias de cartório/bancárias não previstas no contrato do FIDC.
- Alterar as fórmulas de deságio estabelecidas no RuleEngine Python.

---

## 6. Proposta Técnica

### 6.1. Validador de Consistência Interna (DEV Mode Assertion)
Em ambiente de desenvolvimento e testes, validar automaticamente a coerência da resposta da API:
```typescript
export function validarConsistenciaFinanceira(dados: BatchValidationResponse): void {
  const somaBrutaItens = dados.itens.reduce((acc, it) => acc + it.valor_nominal, 0);
  const diff = Math.abs(somaBrutaItens - dados.resumo.valor_bruto_total);
  if (diff > 0.05) {
    console.error(`[Inconsistência Financeira Detectada] Soma itens: ${somaBrutaItens} != Resumo: ${dados.resumo.valor_bruto_total}`);
  }
}
```

### 6.2. Banner de Alerta Crítico Não Descartável para Fraudes
Notas com severidade `FRAUDE` (identificadas pelo Triplo Radar como pertencentes a outro fundo de mercado) ativam automaticamente um banner fixo no topo da aplicação com indicação visual de risco alto (cor `rose-600` e badge pulsante), impedindo exportação cega das notas aprovadas sem ciência das fraudes no lote.

---

## 7. Alternativas Consideradas
- **Recalcular totais no client-side a cada filtro de pesquisa:** Rejeitada; filtros textuais na tabela de notas alteram a visualização dos registros exibidos, mas **nunca** devem mutar os totais financeiros do extrato consolidado do lote.

---

## 8. Impacto
- **Benefícios:** Confiança total dos analistas de risco e da diretoria do fundo nas métricas exibidas; impossibilidade de discrepâncias entre relatórios exportados em CSV e a tela.
- **Riscos:** Nenhum.

---

## 9. Plano de Adoção
1. Revisar todos os pontos de exibição de moeda garantindo o uso de `formatarMoeda`.
2. Adicionar asserções de consistência na suíte de testes unitários.
3. Certificar que exportações CSV de notas aprovadas (`gerarCsvNotasAprovadas`) filtram estritamente por `status === "APROVADA"`.

---

## 10. Critérios de Aceitação
- `valor_bruto_total` é exatamente igual a `valor_bruto_aprovado + valor_bruto_recusado`.
- `valor_liquido_receber` é exatamente igual a `valor_bruto_aprovado - desagio_total`.
- Notas recusadas exibem claramente a severidade (`REGRA_NEGOCIO`, `DUPLICIDADE` ou `FRAUDE`) e a respectiva recomendação de ação.

---

## 11. Testes Necessários
- Teste unitário comparando somatório de `itens` com `resumo`.
- Teste de renderização do banner de fraude crítica quando `qtd_alertas_fraude > 0`.

---

## 12. Dependências
- [RFC-003: Contratos e Tipagem TypeScript](RFC-003-api-contracts-and-types.md).

---

## 13. Questões em Aberto
- Nenhuma.
