import { useState, useRef } from "react";
import {
  AlertTriangle,
  ArrowDownRight,
  CheckCircle2,
  FileSpreadsheet,
  Sparkles,
  TrendingDown,
  UploadCloud,
  Wallet,
  XCircle,
} from "lucide-react";
import type { MetaLote, ResumoLote } from "../types/api";
import { formatarMoeda, formatarPercentual } from "../utils/formatters";

interface CheckoutLiquidezProps {
  resumo: ResumoLote | null;
  meta: MetaLote | null;
  carregando: boolean;
  arquivoSelecionado: File | null;
  onArquivoUpload: (arquivo: File) => void;
  replayIdempotente?: boolean;
}

export function CheckoutLiquidez({
  resumo,
  meta,
  carregando,
  arquivoSelecionado,
  onArquivoUpload,
  replayIdempotente,
}: CheckoutLiquidezProps) {
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = () => {
    setIsDragOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      onArquivoUpload(e.dataTransfer.files[0]);
    }
  };

  const pctAprovado = resumo && resumo.valor_bruto_total > 0
    ? Math.round((resumo.valor_bruto_aprovado / resumo.valor_bruto_total) * 100)
    : 0;

  return (
    <div className="space-y-6">
      {/* Zona de Upload Drag & Drop */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`relative cursor-pointer overflow-hidden rounded-2xl border-2 border-dashed p-6 text-center transition-all ${
          isDragOver
            ? "border-emerald-500 bg-emerald-50/50 scale-[1.005]"
            : "border-slate-300 hover:border-slate-400 bg-white hover:bg-slate-50/50"
        } shadow-2xs`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv,text/csv"
          disabled={carregando}
          onChange={(e) => {
            if (e.target.files && e.target.files[0]) {
              onArquivoUpload(e.target.files[0]);
            }
          }}
          className="sr-only"
        />

        <div className="flex flex-col items-center justify-center gap-2">
          <div
            className={`flex h-12 w-12 items-center justify-center rounded-2xl transition-transform ${
              carregando
                ? "bg-amber-100 text-amber-600 animate-bounce"
                : "bg-slate-100 text-slate-600 group-hover:scale-110"
            }`}
          >
            {carregando ? (
              <Sparkles className="h-6 w-6 animate-spin" />
            ) : (
              <UploadCloud className="h-6 w-6 text-emerald-600" />
            )}
          </div>

          <div>
            <p className="text-sm font-semibold text-slate-800">
              {carregando
                ? "Processando lote contra 100k notas em RAM..."
                : arquivoSelecionado
                ? `Lote carregado: ${arquivoSelecionado.name}`
                : "Clique para carregar ou arraste seu arquivo CSV de recebíveis"}
            </p>
            <p className="text-xs text-slate-500 mt-0.5">
              Formato esperado: CSV separado por ponto e vírgula (;), decimal com vírgula e datas em dd/mm/aaaa
            </p>
          </div>

          {arquivoSelecionado && (
            <div className="mt-1 flex items-center gap-2 text-xs text-emerald-800 bg-emerald-50 border border-emerald-200/80 px-2.5 py-1 rounded-full">
              <FileSpreadsheet className="h-3.5 w-3.5 text-emerald-600" />
              <span>
                {(arquivoSelecionado.size / 1024).toFixed(1)} KB · Clique para trocar de arquivo
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Recibo de Caixa: 4 Grandes Cards de Checkout */}
      {resumo && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Checkout de Liquidez da Operação
            </h2>
            {replayIdempotente && (
              <span className="inline-flex items-center gap-1 text-[11px] font-medium text-slate-600 bg-slate-100 border border-slate-200 px-2 py-0.5 rounded">
                <CheckCircle2 className="h-3 w-3 text-emerald-600" />
                Resposta recuperada do cache de idempotência
              </span>
            )}
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {/* Bloco 1: Valor Bruto Submetido */}
            <div className="card p-5 relative overflow-hidden flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between text-slate-500 mb-1">
                  <span className="text-xs font-medium uppercase tracking-wider">Valor Bruto Submetido</span>
                  <FileSpreadsheet className="h-4 w-4 text-slate-400" />
                </div>
                <div className="text-2xl font-bold tracking-tight text-slate-900 money">
                  {formatarMoeda(resumo.valor_bruto_total)}
                </div>
              </div>
              <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
                <span>Total de títulos no lote:</span>
                <strong className="text-slate-800">{resumo.total_notas} notas</strong>
              </div>
            </div>

            {/* Bloco 2: Inelegíveis / Recusadas */}
            <div
              className={`card p-5 relative overflow-hidden flex flex-col justify-between ${
                resumo.qtd_alertas_fraude > 0 ? "border-rose-300 bg-rose-50/20" : ""
              }`}
            >
              <div>
                <div className="flex items-center justify-between text-slate-500 mb-1">
                  <div className="flex items-center gap-1.5">
                    <span className="text-xs font-medium uppercase tracking-wider">Recusadas / Inelegíveis</span>
                    {resumo.qtd_alertas_fraude > 0 && (
                      <span className="relative flex h-2 w-2">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75" />
                        <span className="relative inline-flex rounded-full h-2 w-2 bg-rose-600" />
                      </span>
                    )}
                  </div>
                  <XCircle
                    className={`h-4 w-4 ${
                      resumo.qtd_alertas_fraude > 0 ? "text-rose-600" : "text-amber-500"
                    }`}
                  />
                </div>
                <div className="text-2xl font-bold tracking-tight text-rose-600 money">
                  {formatarMoeda(resumo.valor_bruto_recusado)}
                </div>
              </div>

              <div className="mt-4 pt-3 border-t border-slate-100 space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-500">{resumo.qtd_recusadas} de {resumo.total_notas} notas</span>
                  <span className="font-semibold text-slate-700">{pctAprovado}% aprovadas</span>
                </div>
                {/* Barra de Progresso Aprovado vs Recusado */}
                <div className="h-1.5 w-full bg-rose-200 rounded-full overflow-hidden flex">
                  <div
                    className="h-full bg-emerald-500 rounded-full transition-all duration-500"
                    style={{ width: `${pctAprovado}%` }}
                  />
                </div>
                {resumo.qtd_alertas_fraude > 0 && (
                  <div className="flex items-center gap-1 text-[11px] font-semibold text-rose-700 bg-rose-100/80 px-2 py-0.5 rounded">
                    <AlertTriangle className="h-3 w-3 shrink-0" />
                    <span>{resumo.qtd_alertas_fraude} alerta crítico de dupla cessão</span>
                  </div>
                )}
              </div>
            </div>

            {/* Bloco 3: Deságio / Custo Financeiro */}
            <div className="card p-5 relative overflow-hidden flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between text-slate-500 mb-1">
                  <span className="text-xs font-medium uppercase tracking-wider">Deságio Financeiro</span>
                  <TrendingDown className="h-4 w-4 text-slate-400" />
                </div>
                <div className="text-2xl font-bold tracking-tight text-slate-700 money flex items-center">
                  <span>- {formatarMoeda(resumo.desagio_total)}</span>
                </div>
              </div>

              <div className="mt-4 pt-3 border-t border-slate-100 text-xs text-slate-500 space-y-1">
                <div className="flex items-center justify-between">
                  <span>Prazo Médio Ponderado:</span>
                  <strong className="text-slate-800">{resumo.prazo_medio_ponderado_dias.toFixed(1)} dias</strong>
                </div>
                <div className="flex items-center justify-between text-[11px] text-slate-400">
                  <span>Taxa aplicada:</span>
                  <span>{formatarPercentual(meta?.taxa_mensal_aplicada ?? 0.02, true)} a.m.</span>
                </div>
              </div>
            </div>

            {/* Bloco 4: Card Principal - Líquido na Conta Hoje */}
            <div className="card p-5 bg-gradient-to-br from-emerald-600 via-emerald-700 to-teal-800 text-white relative overflow-hidden shadow-glow flex flex-col justify-between">
              <div className="absolute top-0 right-0 -mt-4 -mr-4 h-28 w-28 rounded-full bg-white/10 blur-xl pointer-events-none" />

              <div>
                <div className="flex items-center justify-between text-emerald-100/90 mb-1">
                  <span className="text-xs font-semibold uppercase tracking-wider flex items-center gap-1.5">
                    <Wallet className="h-3.5 w-3.5 text-emerald-300" />
                    Valor Líquido na Conta Hoje
                  </span>
                  <ArrowDownRight className="h-4 w-4 text-emerald-300" />
                </div>
                <div className="text-3xl font-extrabold tracking-tight text-white money drop-shadow-xs">
                  {formatarMoeda(resumo.valor_liquido_receber)}
                </div>
              </div>

              <div className="mt-4 pt-3 border-t border-white/20">
                {meta && meta.ganho_otimizador_reais > 0 ? (
                  <div className="flex items-start gap-1.5 bg-white/15 backdrop-blur-xs px-2.5 py-1.5 rounded-lg text-emerald-50 text-xs font-medium">
                    <Sparkles className="h-3.5 w-3.5 text-amber-300 shrink-0 mt-0.5 animate-pulse" />
                    <span>
                      <strong>+ {formatarMoeda(meta.ganho_otimizador_reais)}</strong> liberados pelo Otimizador (
                      {meta.qtd_notas_salvas_otimizador} notas salvas do corte)
                    </span>
                  </div>
                ) : (
                  <div className="flex items-center justify-between text-xs text-emerald-100">
                    <span>{resumo.qtd_aprovadas} notas aprovadas</span>
                    <span className="text-[11px] opacity-80">Pronto para cessão</span>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
