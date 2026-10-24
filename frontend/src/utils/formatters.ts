import type { ItemLote } from "../types/api";

/** Formata número como moeda brasileira (R$ 1.500,50) */
export function formatarMoeda(valor: number | null | undefined): string {
  if (valor === null || valor === undefined || isNaN(valor)) return "R$ 0,00";
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(valor);
}

/** Formata número como percentual (ex: 0.025 vira 2,50% ou 2.5 vira 2,50%) */
export function formatarPercentual(valor: number | null | undefined, isFracao = false): string {
  if (valor === null || valor === undefined || isNaN(valor)) return "0,00%";
  const pct = isFracao ? valor * 100 : valor;
  return `${pct.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%`;
}

/** Remove caracteres não-alfanuméricos para comparação e chaves */
export function limparDocumento(doc: string | null | undefined): string {
  if (!doc) return "";
  return doc.replace(/[^a-zA-Z0-9]/g, "").trim().toUpperCase();
}

/** Formata CNPJ ou CPF com máscara padrão brasileira */
export function formatarDocumento(doc: string | null | undefined): string {
  if (!doc) return "-";
  const limpo = limparDocumento(doc);

  if (limpo.length === 14) {
    // CNPJ: 00.000.000/0000-00
    return limpo.replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, "$1.$2.$3/$4-$5");
  }
  if (limpo.length === 11) {
    // CPF: 000.000.000-00
    return limpo.replace(/^(\d{3})(\d{3})(\d{3})(\d{2})$/, "$1.$2.$3-$4");
  }
  if (limpo.length === 8) {
    // Raiz de CNPJ: 00.000.000
    return limpo.replace(/^(\d{2})(\d{3})(\d{3})$/, "$1.$2.$3");
  }
  return doc;
}

/** Converte string ISO (yyyy-mm-dd) para formato brasileiro (dd/mm/aaaa) */
export function formatarDataInputParaBR(dataIso: string): string {
  if (!dataIso) return "";
  const partes = dataIso.split("-");
  if (partes.length !== 3) return dataIso;
  return `${partes[2]}/${partes[1]}/${partes[0]}`;
}

/** Converte formato brasileiro (dd/mm/aaaa) para formato de input date (yyyy-mm-dd) */
export function formatarDataBRParaInput(dataBr: string): string {
  if (!dataBr) return "";
  const partes = dataBr.split("/");
  if (partes.length !== 3) return dataBr;
  return `${partes[2]}-${partes[1]}-${partes[0]}`;
}

/** Formata número float para string no formato CSV brasileiro (ex: 1500.5 -> 1500,50) */
export function formatarValorCsv(valor: number): string {
  return valor.toFixed(2).replace(".", ",");
}

/** Faz o download de um arquivo gerado no client-side */
export function dispararDownloadBlob(conteudo: string, nomeArquivo: string, tipoMime = "text/csv;charset=utf-8-sig;"): void {
  const blob = new Blob([conteudo], { type: tipoMime });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.setAttribute("href", url);
  link.setAttribute("download", nomeArquivo);
  link.style.visibility = "hidden";
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

/** Gera CSV do Lote de Notas Aprovadas no padrão de colunas exato do fundo ANTECIPE */
export function gerarCsvNotasAprovadas(itens: ItemLote[], nomeFundo = "ANTECIPE FIDC", docFundo = "92.234.400/0001-80"): string {
  const cabecalho = [
    "NOME_FUNDO",
    "DOC_FUNDO",
    "NOME_CEDENTE",
    "DOC_CEDENTE",
    "NOME_SACADO",
    "DOC_SACADO",
    "NU_DOCUMENTO",
    "TIPO_RECEBIVEL",
    "VALOR_NOMINAL",
    "DATA_VENCIMENTO_ORIGINAL",
    "DATA_AQUISICAO",
  ];

  const linhas = itens
    .filter((it) => it.status === "APROVADA")
    .map((it) => [
      nomeFundo,
      docFundo,
      `"${it.nome_cedente.replace(/"/g, '""')}"`,
      formatarDocumento(it.doc_cedente),
      `"${it.nome_sacado.replace(/"/g, '""')}"`,
      formatarDocumento(it.doc_sacado),
      `"${it.nu_documento.replace(/"/g, '""')}"`,
      it.tipo_recebivel,
      formatarValorCsv(it.valor_nominal),
      it.data_vencimento,
      it.data_aquisicao,
    ]);

  const csv = [cabecalho.join(";"), ...linhas.map((l) => l.join(";"))].join("\r\n");
  return "\uFEFF" + csv; // UTF-8 com BOM para Excel
}

/** Gera Relatório de Pendências / Recusas com explicação transparente para a empresa */
export function gerarCsvRelatorioPendencias(itens: ItemLote[]): string {
  const cabecalho = [
    "LINHA_ORIGINAL",
    "NU_DOCUMENTO",
    "NOME_SACADO",
    "DOC_SACADO",
    "VALOR_NOMINAL",
    "DATA_VENCIMENTO",
    "STATUS",
    "SEVERIDADE",
    "MOTIVOS_RECUSA",
    "O_QUE_ACONTECEU",
    "COMO_RESOLVER",
  ];

  const linhas = itens
    .filter((it) => it.status === "RECUSADA")
    .map((it) => {
      const motivos = it.erros.map((e) => e.titulo_amigavel).join(" | ");
      const explicacao = it.erros.map((e) => `[${e.codigo}]: ${e.mensagem_empresa}`).join(" | ");
      const acao = it.erros.map((e) => e.acao_recomendada).join(" | ");

      return [
        it.linha_csv,
        `"${it.nu_documento.replace(/"/g, '""')}"`,
        `"${it.nome_sacado.replace(/"/g, '""')}"`,
        formatarDocumento(it.doc_sacado),
        formatarValorCsv(it.valor_nominal),
        it.data_vencimento,
        it.status,
        it.severidade,
        `"${motivos.replace(/"/g, '""')}"`,
        `"${explicacao.replace(/"/g, '""')}"`,
        `"${acao.replace(/"/g, '""')}"`,
      ];
    });

  const csv = [cabecalho.join(";"), ...linhas.map((l) => l.join(";"))].join("\r\n");
  return "\uFEFF" + csv;
}

/** Divide um valor em número e unidade para os números grandes da tela (R$ 199,3 mil · R$ 4,6 mi). */
export function dividirMoedaCompacta(valor: number): { numero: string; unidade: string } {
  const abs = Math.abs(valor);
  const [div, unidade] = abs >= 1e9 ? [1e9, "bi"] : abs >= 1e6 ? [1e6, "mi"] : abs >= 1e3 ? [1e3, "mil"] : [1, ""];
  const casas = div === 1 ? 2 : 1;
  const numero = (valor / div).toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });
  return { numero, unidade };
}

/** R$ 199,3 mil · R$ 4,6 mi · R$ 950,00 */
export function formatarMoedaCompacta(valor: number): string {
  const { numero, unidade } = dividirMoedaCompacta(valor);
  return `R$ ${numero}${unidade ? " " + unidade : ""}`;
}
