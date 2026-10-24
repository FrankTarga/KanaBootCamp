import { useState } from "react";
import { ArrowRight, Check, CheckCircle2, Copy, Printer, ShieldCheck, X } from "lucide-react";
import { formatarMoeda, formatarPercentual } from "../utils/formatters";
import type { ResultadoLiquidacao, BatchValidationResponse } from "../types/api";

interface ModalComprovantePixProps {
  aberto: boolean;
  onFechar: () => void;
  onVerHistorico?: () => void;
  resultadoLiquidacao: ResultadoLiquidacao | null;
  resultadoLote: BatchValidationResponse;
}

export function ModalComprovantePix({
  aberto,
  onFechar,
  onVerHistorico,
  resultadoLiquidacao,
  resultadoLote,
}: ModalComprovantePixProps) {
  const [copiado, setCopiado] = useState(false);

  if (!aberto || !resultadoLiquidacao) return null;

  const { resumo, meta, itens } = resultadoLote;
  const primeiroItem = itens.find((i) => i.status === "APROVADA") ?? itens[0];
  const cedenteNome = primeiroItem?.nome_cedente || "Empresa Cedente";
  const cedenteDoc = primeiroItem?.doc_cedente || "CNPJ não informado";
  const batchHash = resultadoLiquidacao.batch_hash || meta.batch_hash_idempotencia;
  const dataLiquidacao = resultadoLiquidacao.liquidado_em || new Date().toLocaleString("pt-BR");

  const copiarHash = () => {
    navigator.clipboard.writeText(batchHash);
    setCopiado(true);
    setTimeout(() => setCopiado(false), 2000);
  };

  const imprimir = () => {
    window.print();
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="titulo-comprovante"
      className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-slate-950/70 p-4 backdrop-blur-sm animate-in fade-in"
    >
      <div className="relative w-full max-w-lg rounded-3xl bg-white p-6 shadow-2xl sm:p-8 border border-slate-100 print:shadow-none print:border-none">
        {/* Botão Fechar */}
        <button
          type="button"
          onClick={onFechar}
          className="absolute right-4 top-4 rounded-full p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700 transition-colors print:hidden"
          title="Fechar comprovante"
        >
          <X className="h-5 w-5" />
        </button>

        {/* Cabeçalho de Sucesso */}
        <div className="flex flex-col items-center text-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-emerald-100 text-emerald-600 shadow-inner">
            <CheckCircle2 className="h-10 w-10 text-emerald-600 animate-in zoom-in-75 duration-300" />
          </div>

          <span className="mt-4 inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700 border border-emerald-200">
            <ShieldCheck className="h-3.5 w-3.5" /> Liquidação Concluída com Sucesso (ACID)
          </span>

          <h2 id="titulo-comprovante" className="mt-3 font-display text-2xl font-bold text-slate-900 sm:text-3xl">
            Comprovante de Liquidação
          </h2>

          <div className="mt-3 rounded-2xl bg-emerald-600 px-5 py-4 text-white shadow-md w-full text-center">
            <p className="text-xs uppercase tracking-wider text-emerald-100 font-medium">TED / PIX Liberado</p>
            <p className="mt-1 font-display text-3xl font-extrabold sm:text-4xl tabular-nums">
              {formatarMoeda(resumo.valor_liquido_receber)}
            </p>
            <p className="mt-1 text-xs text-emerald-100 font-medium">
              Operação contratada! Liberados para a conta do Cedente
            </p>
          </div>
        </div>

        {/* Detalhes da Transação */}
        <div className="mt-6 space-y-3 divide-y divide-slate-100 text-sm">
          <div className="flex justify-between items-center pt-2">
            <span className="text-slate-500">Cedente Favorecido</span>
            <div className="text-right">
              <span className="font-semibold text-slate-900 block truncate max-w-[200px]" title={cedenteNome}>
                {cedenteNome}
              </span>
              <span className="text-xs text-slate-500">{cedenteDoc}</span>
            </div>
          </div>

          <div className="flex justify-between items-center pt-2">
            <span className="text-slate-500">Fundo Comprador</span>
            <div className="text-right">
              <span className="font-semibold text-slate-900 block">ANTECIPE FIDC</span>
              <span className="text-xs text-slate-500">CNPJ: 92.234.400/0001-80</span>
            </div>
          </div>

          <div className="flex justify-between items-center pt-2">
            <span className="text-slate-500">Títulos Adquiridos</span>
            <span className="font-semibold text-slate-900">
              {resumo.qtd_aprovadas} {resumo.qtd_aprovadas === 1 ? "nota" : "notas"} ({formatarMoeda(resumo.valor_bruto_aprovado)})
            </span>
          </div>

          <div className="flex justify-between items-center pt-2">
            <span className="text-slate-500">Deságio Aplicado</span>
            <span className="font-semibold text-rose-700">
              - {formatarMoeda(resumo.desagio_total)} ({formatarPercentual(meta.taxa_mensal_aplicada, true)} a.m.)
            </span>
          </div>

          <div className="flex justify-between items-center pt-2">
            <span className="text-slate-500">Data e Hora da Operação</span>
            <span className="font-medium text-slate-900 tabular-nums">{dataLiquidacao}</span>
          </div>

          <div className="flex justify-between items-start pt-2">
            <span className="text-slate-500">Protocolo / Hash</span>
            <div className="flex items-center gap-1.5">
              <span className="font-mono text-xs text-slate-600 truncate max-w-[170px]" title={batchHash}>
                {batchHash.slice(0, 16)}...
              </span>
              <button
                type="button"
                onClick={copiarHash}
                className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
                title="Copiar hash completo"
              >
                {copiado ? <Check className="h-3.5 w-3.5 text-emerald-600" /> : <Copy className="h-3.5 w-3.5" />}
              </button>
            </div>
          </div>
        </div>

        {/* Garantias de Auditoria */}
        <div className="mt-5 rounded-xl border border-emerald-100 bg-emerald-50/70 p-3 text-xs text-emerald-900 flex items-start gap-2.5">
          <ShieldCheck className="h-4 w-4 shrink-0 text-emerald-600 mt-0.5" />
          <p>
            <strong>Garantia ACID:</strong> Títulos gravados de forma imutável na tabela <code className="bg-emerald-100 px-1 py-0.5 rounded font-mono">titulos_adquiridos</code> e atualizados no motor em memória RAM <code className="bg-emerald-100 px-1 py-0.5 rounded font-mono">StockIndex</code> (Write-Through).
          </p>
        </div>

        {/* Botões de Ação */}
        <div className="mt-6 flex flex-col gap-2.5 sm:flex-row print:hidden">
          {onVerHistorico && (
            <button
              type="button"
              onClick={() => {
                onFechar();
                onVerHistorico();
              }}
              className="flex-1 flex items-center justify-center gap-2 rounded-xl bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-slate-800 transition-colors"
            >
              Ver no Histórico <ArrowRight className="h-4 w-4" />
            </button>
          )}

          <button
            type="button"
            onClick={imprimir}
            className="flex items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50 transition-colors"
          >
            <Printer className="h-4 w-4 text-slate-500" /> Imprimir
          </button>

          <button
            type="button"
            onClick={onFechar}
            className="flex items-center justify-center rounded-xl border border-slate-200 bg-slate-100 px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-200 transition-colors"
          >
            Concluir
          </button>
        </div>
      </div>
    </div>
  );
}
