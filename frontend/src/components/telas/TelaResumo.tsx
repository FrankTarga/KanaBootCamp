import { AlertTriangle, ArrowRight, BarChart3, CheckCircle2, ListChecks, Loader2, ShieldCheck, Sparkles } from "lucide-react";
import type { MetaLote, ResumoLote } from "../../types/api";
import { formatarMoeda, formatarPercentual } from "../../utils/formatters";

interface TelaResumoProps {
  resumo: ResumoLote;
  meta: MetaLote;
  demo: boolean;
  motorDesligado: boolean;
  nomeLote: string | null;
  replayIdempotente: boolean;
  onIr: (destino: "estatistica" | "notas", motivo?: string | null) => void;
  onLiquidar?: () => void;
  onVerComprovante?: () => void;
  liquidando?: boolean;
  loteLiquidado?: boolean;
  erroLiquidacao?: string | null;
}

export function Cabecalho({ titulo, sub }: { titulo: string; sub: string }) {
  return (
    <header>
      <h1 className="font-display text-3xl font-semibold tracking-tight text-slate-900 sm:text-4xl">{titulo}</h1>
      <p className="mt-2 text-slate-600">{sub}</p>
    </header>
  );
}

function Linha({ rotulo, detalhe, valor, negativo }: { rotulo: string; detalhe: string; valor: number; negativo?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-3">
      <div className="min-w-0">
        <p className="font-medium text-slate-800">{rotulo}</p>
        <p className="text-sm text-slate-500">{detalhe}</p>
      </div>
      <p className={`shrink-0 font-semibold tabular-nums ${negativo ? "text-rose-700" : "text-slate-900"}`}>
        {negativo ? "− " : ""}{formatarMoeda(valor)}
      </p>
    </div>
  );
}

export function TelaResumo({
  resumo,
  meta,
  demo,
  motorDesligado,
  nomeLote,
  replayIdempotente,
  onIr,
  onLiquidar,
  onVerComprovante,
  liquidando = false,
  loteLiquidado = false,
  erroLiquidacao = null,
}: TelaResumoProps) {
  const pctAprov = resumo.total_notas ? resumo.qtd_aprovadas / resumo.total_notas : 0;
  const dia = (n: number) => n.toLocaleString("pt-BR", { maximumFractionDigits: 1 });
  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-8 px-5 py-10 sm:px-8 lg:py-14">
      <Cabecalho titulo={demo ? "Resumo do lote de demonstração" : "Resumo do lote"}
        sub={nomeLote && !motorDesligado ? `${nomeLote} · operação de ${meta.data_base_utilizada}` : `Operação de ${meta.data_base_utilizada}`} />

      {motorDesligado && (
        <p role="alert" className="flex items-start gap-2 rounded-2xl border border-rose-300 bg-rose-50 px-4 py-3 text-sm text-rose-800">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>O servidor de análise não respondeu, então <strong>estes números não são do seu arquivo</strong>: são do lote de demonstração. Ligue o servidor e envie o arquivo de novo.</span>
        </p>
      )}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
        {/* Extrato: a conta que a empresa faz de cabeça, escrita linha a linha */}
        <article aria-label="Extrato da antecipação" className="relative rounded-3xl border border-creme-linha bg-creme-claro p-6 shadow-card sm:p-8">
          <p className="eyebrow text-emerald-700">Extrato da antecipação</p>
          <div className="mt-4 divide-y divide-dashed divide-creme-linha">
            <Linha rotulo="Valor enviado" detalhe={`${resumo.total_notas.toLocaleString("pt-BR")} notas no lote`} valor={resumo.valor_bruto_total} />
            <Linha rotulo="Ficou de fora" detalhe={`${resumo.qtd_recusadas.toLocaleString("pt-BR")} notas recusadas pelas regras do fundo`} valor={resumo.valor_bruto_recusado} negativo />
            <Linha rotulo="Custo da antecipação" detalhe={`${formatarPercentual(meta.taxa_mensal_aplicada, true)} ao mês · prazo médio de ${dia(resumo.prazo_medio_ponderado_dias)} dias`} valor={resumo.desagio_total} negativo />
          </div>
          <div className="mt-2 rounded-2xl bg-floresta p-5 text-creme flex flex-col gap-4">
            <div>
              <p className="text-sm text-creme/70">Na sua conta hoje</p>
              <p className="mt-1 font-display text-4xl font-semibold tabular-nums tracking-tight sm:text-5xl">{formatarMoeda(resumo.valor_liquido_receber)}</p>
              <p className="mt-2 text-sm text-creme/70">
                {resumo.valor_bruto_total > 0 ? `${dia((resumo.valor_liquido_receber / resumo.valor_bruto_total) * 100)}% do valor enviado` : "—"}
              </p>
            </div>

            {/* Ação principal: Confirmar e Liquidar Lote Aprovado */}
            <div className="border-t border-white/10 pt-3">
              {loteLiquidado ? (
                <div className="flex items-center justify-between gap-2 rounded-xl bg-emerald-500/20 border border-emerald-400/40 p-3 text-sm text-broto">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="h-5 w-5 text-broto shrink-0" />
                    <span className="font-semibold">Lote Liquidado e Pago!</span>
                  </div>
                  {onVerComprovante && (
                    <button
                      type="button"
                      onClick={onVerComprovante}
                      className="rounded-lg bg-emerald-950/60 px-3 py-1.5 text-xs font-bold text-creme hover:bg-emerald-950 transition-colors"
                    >
                      Ver Comprovante
                    </button>
                  )}
                </div>
              ) : (
                <button
                  type="button"
                  id="btn-confirmar-liquidar"
                  disabled={liquidando || resumo.qtd_aprovadas === 0 || resumo.valor_liquido_receber <= 0}
                  onClick={onLiquidar}
                  className="flex w-full items-center justify-center gap-2 rounded-xl bg-broto px-5 py-3 text-sm font-bold text-floresta shadow-md transition-all hover:bg-emerald-300 active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-white"
                >
                  {liquidando ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin text-floresta" />
                      <span>Liquidando Operação...</span>
                    </>
                  ) : (
                    <>
                      <ShieldCheck className="h-4 w-4 text-floresta" />
                      <span>Confirmar e Liquidar Lote Aprovado</span>
                    </>
                  )}
                </button>
              )}
              {erroLiquidacao && !loteLiquidado && (
                <p role="alert" className="mt-2 flex items-start gap-2 rounded-lg bg-rose-500/20 px-3 py-2 text-xs text-rose-100">
                  <AlertTriangle className="h-4 w-4 shrink-0" /> {erroLiquidacao}
                </p>
              )}
            </div>
          </div>
          <p className="mt-4 text-xs text-slate-400">
            Analisado em {dia(meta.tempo_processamento_ms)} ms{replayIdempotente ? " · mesmo arquivo de antes, resposta reaproveitada" : ""}
          </p>
        </article>

        <div className="flex flex-col gap-4">
          <div className="rounded-3xl border border-creme-linha bg-creme-claro p-6 shadow-card">
            <div className="flex items-center gap-5">
              {/* anel: parte aprovada das notas */}
              <svg viewBox="0 0 36 36" className="h-20 w-20 shrink-0 -rotate-90" aria-hidden="true">
                <circle cx="18" cy="18" r="15.9" fill="none" strokeWidth="3.4" className="stroke-creme-linha" />
                <circle cx="18" cy="18" r="15.9" fill="none" strokeWidth="3.4" strokeLinecap="round" className="stroke-emerald-600"
                  strokeDasharray={`${pctAprov * 100} 100`} pathLength={100} />
              </svg>
              <div>
                <p className="font-display text-3xl font-semibold tabular-nums text-slate-900">
                  {resumo.qtd_aprovadas.toLocaleString("pt-BR")} <span className="text-lg font-normal text-slate-500">de {resumo.total_notas.toLocaleString("pt-BR")}</span>
                </p>
                <p className="text-sm text-slate-600">notas aprovadas · {formatarMoeda(resumo.valor_bruto_aprovado)} em valor de face</p>
              </div>
            </div>
          </div>

          {meta.ganho_otimizador_reais > 0 && (
            <div className="flex items-start gap-3 rounded-3xl border border-emerald-200 bg-emerald-50 p-5 text-emerald-900">
              <Sparkles className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600" />
              <p>O otimizador mudou a ordem das notas e liberou <strong className="tabular-nums">+{formatarMoeda(meta.ganho_otimizador_reais)}</strong> ({meta.qtd_notas_salvas_otimizador} {meta.qtd_notas_salvas_otimizador === 1 ? "nota salva" : "notas salvas"}).</p>
            </div>
          )}

          {resumo.qtd_alertas_fraude > 0 && (
            <button type="button" onClick={() => onIr("notas", "FRAUDE_OUTRO_FUNDO")}
              className="flex items-start gap-3 rounded-3xl border border-rose-300 bg-rose-50 p-5 text-left text-rose-900 hover:bg-rose-100">
              <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-rose-600" />
              <span>
                <strong>{resumo.qtd_alertas_fraude} {resumo.qtd_alertas_fraude === 1 ? "nota já está" : "notas já estão"} na carteira de outro fundo.</strong>
                <span className="block text-sm">Vender a mesma nota duas vezes é proibido. Ver quais são →</span>
              </span>
            </button>
          )}

          {resumo.qtd_recusadas === 0 && (
            <div className="flex items-center gap-3 rounded-3xl border border-emerald-200 bg-emerald-50 p-5 text-emerald-900">
              <CheckCircle2 className="h-5 w-5 text-emerald-600" /> Todas as notas passaram nas regras do fundo.
            </div>
          )}

          <div className="mt-auto grid gap-3 sm:grid-cols-2">
            <button type="button" onClick={() => onIr("estatistica")} className="btn justify-between rounded-2xl bg-floresta px-5 py-4 text-creme hover:bg-floresta-painel">
              <span className="flex items-center gap-2"><BarChart3 className="h-5 w-5" /> Ver estatística</span><ArrowRight className="h-4 w-4" />
            </button>
            <button type="button" onClick={() => onIr("notas", null)} className="btn justify-between rounded-2xl border border-creme-linha bg-creme-claro px-5 py-4 text-slate-800 hover:bg-white">
              <span className="flex items-center gap-2"><ListChecks className="h-5 w-5" /> Ver nota por nota</span><ArrowRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
