import { AlertTriangle, CheckCircle2, Clock, Sparkles } from "lucide-react";
import type { MetaLote, ResumoLote } from "../types/api";
import { dividirMoedaCompacta, formatarMoeda, formatarMoedaCompacta, formatarPercentual } from "../utils/formatters";

interface NumerosLoteProps {
  resumo: ResumoLote;
  meta: MetaLote;
  demo: boolean;
  replayIdempotente: boolean;
  onVerFraudes: () => void;
}

function Numero({ prefixo, valor, unidade, legenda, detalhe, tom = "floresta" }: {
  prefixo?: string; valor: string; unidade?: string; legenda: string; detalhe: string; tom?: "floresta" | "alerta";
}) {
  return (
    <div className="flex min-w-0 flex-col gap-4">
      <div className={`flex items-baseline gap-2 ${tom === "alerta" ? "text-rose-700" : "text-slate-900"}`}>
        {prefixo && <span className="font-display text-2xl font-light text-emerald-700">{prefixo}</span>}
        <span className="numero-fino text-5xl sm:text-6xl">{valor}</span>
        {unidade && <span className="font-display text-2xl font-light text-emerald-700">{unidade}</span>}
      </div>
      <div className="h-px w-full bg-emerald-700/40" />
      <div>
        <p className="eyebrow text-slate-700">{legenda}</p>
        <p className="mt-1.5 text-sm text-slate-500">{detalhe}</p>
      </div>
    </div>
  );
}

// Linhas de duna no rodapé da seção: eco do vídeo de abertura, desenhadas em SVG
function Dunas() {
  return (
    <svg className="pointer-events-none absolute inset-x-0 bottom-0 h-48 w-full text-emerald-900/[0.07]" viewBox="0 0 1200 200" preserveAspectRatio="none" aria-hidden="true">
      {[0, 1, 2, 3, 4, 5].map((i) => (
        <path key={i} fill="none" stroke="currentColor" strokeWidth="1.5"
          d={`M0 ${120 + i * 14} C 200 ${70 + i * 18}, 380 ${160 + i * 8}, 600 ${110 + i * 15} S 1000 ${60 + i * 20}, 1200 ${100 + i * 16}`} />
      ))}
    </svg>
  );
}

export function NumerosLote({ resumo, meta, demo, replayIdempotente, onVerFraudes }: NumerosLoteProps) {
  const liquido = dividirMoedaCompacta(resumo.valor_liquido_receber);
  const desagio = dividirMoedaCompacta(resumo.desagio_total);
  const pctRecusadas = resumo.total_notas ? (resumo.qtd_recusadas / resumo.total_notas) * 100 : 0;

  return (
    <section id="resultado" className="relative scroll-mt-24 overflow-hidden bg-creme px-5 py-24 sm:py-32">
      <Dunas />
      <div className="relative mx-auto max-w-6xl">
        <div className="text-center">
          <p className="eyebrow text-emerald-700">Resultado da análise{demo ? " · lote de demonstração" : ""}</p>
          <h2 className="titulo-secao mt-4 text-slate-900">Números do seu lote</h2>
        </div>

        <div className="mt-16 grid grid-cols-1 gap-12 sm:grid-cols-2 lg:grid-cols-4 lg:gap-10">
          <Numero prefixo="R$" valor={liquido.numero} unidade={liquido.unidade}
            legenda="Na sua conta hoje" detalhe={`${formatarMoeda(resumo.valor_liquido_receber)} já descontado o custo`} />
          <Numero valor={`${resumo.qtd_aprovadas}`} unidade={`de ${resumo.total_notas}`}
            legenda="Notas aprovadas" detalhe={`${formatarMoedaCompacta(resumo.valor_bruto_aprovado)} em valor de face`} />
          <Numero valor={pctRecusadas.toLocaleString("pt-BR", { maximumFractionDigits: 1 })} unidade="%"
            tom={resumo.qtd_recusadas ? "alerta" : "floresta"}
            legenda="Das notas ficaram de fora"
            detalhe={resumo.qtd_recusadas ? `${resumo.qtd_recusadas} notas · ${formatarMoedaCompacta(resumo.valor_bruto_recusado)}` : "Nenhuma nota recusada"} />
          <Numero prefixo="R$" valor={desagio.numero} unidade={desagio.unidade}
            legenda="Custo da antecipação"
            detalhe={`${formatarPercentual(meta.taxa_mensal_aplicada, true)} ao mês · prazo médio de ${resumo.prazo_medio_ponderado_dias.toLocaleString("pt-BR", { maximumFractionDigits: 1 })} dias`} />
        </div>

        <div className="mt-14 flex flex-wrap items-center justify-center gap-3 text-sm">
          {meta.ganho_otimizador_reais > 0 && (
            <span className="inline-flex items-center gap-2 rounded-full border border-emerald-300 bg-emerald-50 px-4 py-2 text-emerald-900">
              <Sparkles className="h-4 w-4 text-emerald-600" />
              O otimizador liberou <strong className="tabular-nums">+{formatarMoeda(meta.ganho_otimizador_reais)}</strong>
              ({meta.qtd_notas_salvas_otimizador} {meta.qtd_notas_salvas_otimizador === 1 ? "nota salva" : "notas salvas"})
            </span>
          )}
          {resumo.qtd_alertas_fraude > 0 && (
            <button type="button" onClick={onVerFraudes}
              className="inline-flex items-center gap-2 rounded-full border border-rose-300 bg-rose-50 px-4 py-2 font-medium text-rose-800 hover:bg-rose-100">
              <AlertTriangle className="h-4 w-4" />
              {resumo.qtd_alertas_fraude} {resumo.qtd_alertas_fraude === 1 ? "nota já está" : "notas já estão"} na carteira de outro fundo · ver
            </button>
          )}
          <span className="inline-flex items-center gap-2 rounded-full border border-creme-linha bg-creme-claro px-4 py-2 text-slate-600">
            <Clock className="h-4 w-4 text-slate-400" />
            Analisado em {meta.tempo_processamento_ms.toLocaleString("pt-BR", { maximumFractionDigits: 1 })} ms · operação de {meta.data_base_utilizada}
          </span>
          {replayIdempotente && (
            <span className="inline-flex items-center gap-2 rounded-full border border-creme-linha bg-creme-claro px-4 py-2 text-slate-600">
              <CheckCircle2 className="h-4 w-4 text-emerald-600" /> Mesmo arquivo de antes: resposta reaproveitada
            </span>
          )}
        </div>
      </div>
    </section>
  );
}
