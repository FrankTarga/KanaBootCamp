import { useState, type ReactNode } from "react";
import { ChevronDown } from "lucide-react";
import type { AnaliseRecusas, ItemLote, ResumoLote } from "../../types/api";
import { formatarMoedaCompacta } from "../../utils/formatters";
import { Cabecalho } from "./TelaResumo";
import { BrutoAoLiquido, GRAVE, Motivos, Vencimentos } from "./graficos";

interface TelaEstatisticaProps {
  resumo: ResumoLote;
  itens: ItemLote[];
  analise?: AnaliseRecusas;
  onVerNotas: (codigo: string | null) => void;
}

const fPct = (v: number) => `${v.toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%`;
// tons por posição para os grupos de problema único; "mais de um problema" tem cor própria
const TONS = ["bg-emerald-700", "bg-emerald-500", "bg-teal-400", "bg-emerald-300", "bg-teal-600", "bg-emerald-200", "bg-teal-300"];

export function Cartao({ titulo, nota, children, className = "" }: { titulo: string; nota: string; children: ReactNode; className?: string }) {
  return (
    <section className={`flex min-w-0 flex-col gap-4 rounded-3xl border border-creme-linha bg-creme-claro p-6 shadow-card ${className}`}>
      <header className="border-l-4 border-emerald-600 pl-3">
        <h2 className="font-display text-xl font-semibold text-slate-900">{titulo}</h2>
        <p className="text-sm text-slate-500">{nota}</p>
      </header>
      {children}
    </section>
  );
}

function GruposRecusas({ analise, onVerNotas }: { analise: AnaliseRecusas; onVerNotas: (c: string | null) => void }) {
  const [aberto, setAberto] = useState(false);
  const { um_problema: um, mais_de_um_problema: multi } = analise.grupos;
  if (!analise.qtd_recusadas) return <p className="py-6 text-center text-slate-500">Nenhuma nota recusada neste lote.</p>;
  return (
    <div className="flex flex-col gap-5">
      {/* barra de 100%: cada nota recusada está em exatamente um pedaço */}
      <div className="flex h-4 overflow-hidden rounded-full bg-creme-linha" aria-hidden="true">
        {um.map((g, i) => <span key={g.codigo} className={GRAVE.has(g.codigo) ? "bg-rose-500" : TONS[i % TONS.length]} style={{ width: `${g.pct_das_recusadas}%` }} />)}
        {multi.qtd > 0 && <span className="bg-amber-500" style={{ width: `${multi.pct_das_recusadas}%` }} />}
      </div>

      <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {um.map((g, i) => (
          <li key={g.codigo}>
            <button type="button" onClick={() => onVerNotas(g.codigo)}
              className="flex h-full w-full flex-col gap-1 rounded-2xl border border-creme-linha bg-creme p-4 text-left hover:border-emerald-400 focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-700">
              <span className="flex items-center gap-2 text-sm font-medium text-slate-800">
                <span className={`h-2.5 w-2.5 shrink-0 rounded-sm ${GRAVE.has(g.codigo) ? "bg-rose-500" : TONS[i % TONS.length]}`} />{g.titulo_amigavel}
              </span>
              <span className="font-display text-3xl font-semibold tabular-nums text-slate-900">{fPct(g.pct_das_recusadas)}</span>
              <span className="text-xs tabular-nums text-slate-500">{g.qtd.toLocaleString("pt-BR")} {g.qtd === 1 ? "nota" : "notas"} · {formatarMoedaCompacta(g.valor)}</span>
              <span className={`mt-1 text-xs font-medium ${!g.corrigivel ? "text-rose-700" : g.liquido_liberado ? "text-emerald-700" : "text-slate-500"}`}>
                {!g.corrigivel ? "Não dá para corrigir" : g.liquido_liberado == null ? "Sem estimativa de quanto libera" : `Corrigir libera ${formatarMoedaCompacta(g.liquido_liberado)}`}
              </span>
            </button>
          </li>
        ))}
        {multi.qtd > 0 && (
          <li>
            <button type="button" onClick={() => setAberto(!aberto)} aria-expanded={aberto} aria-controls="painel-multiplos"
              className={`flex h-full w-full flex-col gap-1 rounded-2xl border-2 border-dashed p-4 text-left focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-700 ${aberto ? "border-amber-500 bg-amber-50" : "border-amber-400/70 bg-creme hover:bg-amber-50"}`}>
              <span className="flex items-center gap-2 text-sm font-medium text-slate-800"><span className="h-2.5 w-2.5 rounded-sm bg-amber-500" />Mais de um problema</span>
              <span className="font-display text-3xl font-semibold tabular-nums text-slate-900">{fPct(multi.pct_das_recusadas)}</span>
              <span className="text-xs tabular-nums text-slate-500">{multi.qtd.toLocaleString("pt-BR")} notas · {formatarMoedaCompacta(multi.valor)}</span>
              <span className="mt-1 flex items-center gap-1 text-xs font-medium text-amber-800">
                {aberto ? "Fechar detalhes" : "Ver por quantidade e combinação"} <ChevronDown className={`h-3.5 w-3.5 transition-transform ${aberto ? "rotate-180" : ""}`} />
              </span>
            </button>
          </li>
        )}
      </ul>

      {aberto && multi.qtd > 0 && (
        <div id="painel-multiplos" className="rounded-2xl border border-amber-200 bg-amber-50/60 p-5">
          <p className="text-sm text-slate-600">Dentro do grupo <strong>mais de um problema</strong>: os percentuais somam 100% entre si.</p>
          <div className="mt-4 flex flex-col gap-5">
            {multi.subgrupos.map((s) => (
              <div key={s.qtd_problemas}>
                <p className="flex flex-wrap items-baseline justify-between gap-2">
                  <strong className="font-display text-lg text-slate-900">{s.qtd_problemas} problemas</strong>
                  <span className="text-sm tabular-nums text-slate-600">{fPct(s.pct_do_grupo)} do grupo · {s.qtd.toLocaleString("pt-BR")} {s.qtd === 1 ? "nota" : "notas"}</span>
                </p>
                <ul className="mt-2 flex flex-col gap-2">
                  {s.combinacoes.map((c) => (
                    <li key={c.codigos.join("+")} className="rounded-xl border border-amber-200 bg-creme-claro p-3">
                      <div className="flex items-baseline justify-between gap-3">
                        <span className="text-sm text-slate-800">{c.titulos.join(" + ")}</span>
                        <span className="shrink-0 text-sm font-semibold tabular-nums text-slate-900">{fPct(c.pct_do_grupo)}</span>
                      </div>
                      <div className="mt-2 h-1.5 rounded-full bg-amber-100"><span className="block h-full rounded-full bg-amber-500" style={{ width: `${c.pct_do_grupo}%` }} /></div>
                      <p className="mt-1 text-xs tabular-nums text-slate-500">{c.qtd.toLocaleString("pt-BR")} {c.qtd === 1 ? "nota" : "notas"} · {formatarMoedaCompacta(c.valor)}</p>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export function TelaEstatistica({ resumo, itens, analise, onVerNotas }: TelaEstatisticaProps) {
  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 px-5 py-10 sm:px-8 lg:py-14">
      <Cabecalho titulo="Estatística do lote" sub="Onde está o dinheiro, por que algumas notas ficaram de fora e quando as aprovadas vencem. Clique num problema para ver as notas." />

      <Cartao titulo="Por que as notas foram recusadas" nota="Cada nota recusada entra em um único grupo, então os percentuais somam 100%.">
        {analise ? <GruposRecusas analise={analise} onVerNotas={onVerNotas} />
          : <p className="rounded-2xl bg-creme p-4 text-sm text-slate-600">Os grupos de recusa aparecem quando a análise do servidor está ligada. No modo demonstração, veja o valor por problema abaixo.</p>}
      </Cartao>

      <div className="grid gap-6 lg:grid-cols-3">
        <Cartao titulo="Liquidez" nota="Do valor enviado ao que cai na conta"><BrutoAoLiquido resumo={resumo} /></Cartao>
        <Cartao titulo="Valor por problema" nota="Quanto dinheiro cada problema envolve"><Motivos motivos={resumo.contagem_por_motivo} onVerMotivo={onVerNotas} /></Cartao>
        <Cartao titulo="Vencimentos" nota="Notas mais curtas pagam menos custo"><Vencimentos itens={itens} prazoMedio={resumo.prazo_medio_ponderado_dias} /></Cartao>
      </div>
    </div>
  );
}
