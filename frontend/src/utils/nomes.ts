// Nomes em português comum para os códigos técnicos do motor (o JSON do fundo continua com os códigos).

export const NOMES_REGRAS: Record<string, { nome: string; explica: string }> = {
  CNPJ_SACADO_VALIDO: { nome: "CNPJ do cliente válido", explica: "Recusa notas com CNPJ do cliente incompleto ou com dígito errado." },
  CNPJ_CEDENTE_VALIDO: { nome: "CNPJ da empresa válido", explica: "Recusa notas em que o CNPJ de quem vende a nota está errado." },
  SITUACAO_CADASTRAL_SACADO: { nome: "Cliente regular na Receita", explica: "Só aceita clientes com a situação cadastral marcada abaixo." },
  TIPO_RECEBIVEL: { nome: "Tipos de título aceitos", explica: "Só compra os tipos de título marcados abaixo." },
  VALOR_MINIMO: { nome: "Valor mínimo da nota", explica: "Notas abaixo deste valor não compensam o custo da operação." },
  VALOR_MAXIMO: { nome: "Valor máximo da nota", explica: "Notas acima deste valor ficam de fora." },
  NAO_VENCIDA: { nome: "Nota ainda não vencida", explica: "Recusa notas cujo vencimento já passou." },
  PRAZO_MAXIMO: { nome: "Prazo máximo", explica: "Recusa notas que vencem depois deste número de dias." },
  PRAZO_MINIMO: { nome: "Prazo mínimo", explica: "Recusa notas que vencem antes deste número de dias." },
  CONCENTRACAO_MAXIMA_SACADO: { nome: "Limite por cliente", explica: "Nenhum cliente pode passar desta parte do patrimônio do fundo." },
  CONCENTRACAO_MAXIMA_CEDENTE: { nome: "Limite por empresa", explica: "Nenhuma empresa que vende notas pode passar desta parte do fundo." },
  DOCUMENTO_BLOQUEADO: { nome: "Lista de bloqueio", explica: "Recusa notas de clientes ou empresas bloqueados pelo fundo." },
};

export const nomeRegra = (codigo: string) =>
  NOMES_REGRAS[codigo]?.nome ?? codigo.toLowerCase().replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());

/** Opções conhecidas para os campos de lista e escolha da gaveta. */
export const OPCOES_PARAMETRO: Record<string, { valor: string; rotulo: string }[]> = {
  situacoes_aceitas: [
    { valor: "ATIVA", rotulo: "Ativa" }, { valor: "SUSPENSA", rotulo: "Suspensa" }, { valor: "INAPTA", rotulo: "Inapta" },
    { valor: "BAIXADA", rotulo: "Baixada" }, { valor: "NULA", rotulo: "Nula" },
  ],
  tipos_aceitos: [
    { valor: "Duplicata", rotulo: "Duplicata" }, { valor: "Duplicata de Serviço", rotulo: "Duplicata de serviço" },
    { valor: "Nota Comercial", rotulo: "Nota comercial" }, { valor: "CCB", rotulo: "CCB" }, { valor: "Cheque", rotulo: "Cheque" },
  ],
  agrupamento: [
    { valor: "RAIZ_CNPJ", rotulo: "Por grupo (matriz e filiais juntas)" },
    { valor: "CNPJ", rotulo: "Por CNPJ (cada filial separada)" },
  ],
};

/** Motivo curto de recusa por código (usado onde só chega o código, como a busca de notas no histórico). */
export const MOTIVOS: Record<string, string> = {
  CNPJ_SACADO_VALIDO: "CNPJ do cliente inválido",
  CNPJ_CEDENTE_VALIDO: "CNPJ da empresa inválido",
  SITUACAO_CADASTRAL_SACADO: "Cliente irregular na Receita",
  TIPO_RECEBIVEL: "Tipo de título não aceito",
  VALOR_MINIMO: "Valor abaixo do mínimo",
  VALOR_MAXIMO: "Valor acima do máximo",
  NAO_VENCIDA: "Nota já vencida",
  PRAZO_MAXIMO: "Prazo muito longo",
  PRAZO_MINIMO: "Prazo muito curto",
  CONCENTRACAO_MAXIMA_SACADO: "Limite do cliente atingido",
  CONCENTRACAO_MAXIMA_CEDENTE: "Limite da empresa atingido",
  DOCUMENTO_BLOQUEADO: "Cliente ou empresa bloqueados",
  DUPLICIDADE_LOTE: "Nota repetida no mesmo envio",
  DUPLICIDADE_FUNDO: "Nota já comprada por este fundo",
  FRAUDE_OUTRO_FUNDO: "Nota já vendida a outro fundo",
  FORMATO_INVALIDO: "Linha com dado ilegível",
};
export const nomeMotivo = (codigo: string) => MOTIVOS[codigo] ?? nomeRegra(codigo);
