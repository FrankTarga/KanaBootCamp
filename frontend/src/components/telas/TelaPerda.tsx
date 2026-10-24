import { useMemo, useRef, useState } from "react";
import { Sparkles } from "lucide-react";
import type { ItemLote, MetaLote, ResumoLote } from "../../types/api";
import { formatarMoeda, formatarMoedaCompacta } from "../../utils/formatters";
import { Cabecalho } from "./TelaResumo";
import { Cartao } from "./TelaEstatistica";
import { FAIXAS } from "./graficos";

interface TelaPerdaProps {
  resumo: ResumoLote;
  meta: MetaLote;
  itens: ItemLote[];
}

const fPct = (v: number, casas = 2) => `${v.toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas })}%`;
const fInt = (v: number) => v.toLocaleString("pt-BR");

/** % do valor de face que a empresa recebe numa nota de `dias` dias (desconto simples, base 30). */
const recebePct = (dias: number, taxa: number) => 100 * (1 - (taxa * Math.max(dias, 0)) / 30);

const W = 720, H = 320, M = { esq: 76, dir: 16, topo: 16, base: 40 };

/** passo "redondo" (1, 2, 2,5 ou 5 × 10^n) para ~5 marcas no eixo */
function passoRedondo(faixa: number) {
  const bruto = faixa / 5;
  const mag = 10 ** Math.floor(Math.log10(bruto));
  const n = bruto / mag;
  return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 2.5 ? 2.5 : n <= 5 ? 5 : 10) * mag;
}

const fMoedaEixo = (v: number) =>
  v >= 1e6 ? `R$ ${(v / 1e6).toLocaleString("pt-BR", { maximumFractionDigits: 2 })} mi`
  : v >= 1e4 ? `R$ ${(v / 1e3).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} mil`
  : `R$ ${v.toLocaleString("pt-BR", { maximumFractionDigits: 2 })}`;

interface GraficoProps { itens: ItemLote[]; taxa: number; valor: number; dias: number; onDias: (d: number) => void }

/** Eixo Y em reais: quanto a empresa recebe hoje por uma nota de `valor`, para cada prazo. */
function GraficoPrazo({ itens, taxa, valor, dias, onDias }: GraficoProps) {
  const [foco, setFoco] = useState<number | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const arrastando = useRef(false);
  const pontos = useMemo(
    () => itens.filter((i) => i.valor_nominal > 0 && i.prazo_dias >= 0)
      // nota sem preço (recusada no lote de demonstração): usa a regra do fundo, só para comparar
      .map((i) => ({ i, x: i.prazo_dias, pct: i.valor_liquido > 0 ? (100 * i.valor_liquido) / i.valor_nominal : recebePct(i.prazo_dias, taxa) })),
    [itens, taxa],
  );
  const xMax = Math.max(180, Math.ceil(Math.max(0, ...pontos.map((p) => p.x)) / 30) * 30);
  const emReais = (pct: number) => (valor * pct) / 100;
  const pisoBruto = emReais(Math.min(recebePct(xMax, taxa), ...pontos.map((p) => p.pct)));
  const passoY = passoRedondo(Math.max(valor - pisoBruto, valor * 0.01));
  const yMin = Math.max(0, Math.floor(pisoBruto / passoY) * passoY - (pisoBruto % passoY === 0 ? passoY : 0));
  const sx = (x: number) => M.esq + (x / xMax) * (W - M.esq - M.dir);
  const sy = (y: number) => M.topo + ((valor - y) / (valor - yMin)) * (H - M.topo - M.base);
  const ticksY: number[] = [];
  for (let t = yMin; t <= valor + 1e-9; t += passoY) ticksY.push(t);
  if (valor - ticksY[ticksY.length - 1] > passoY * 0.35) ticksY.push(valor); // o próprio valor digitado no topo
  const ticksX = Array.from({ length: xMax / 30 + 1 }, (_, k) => k * 30);
  const maiorValor = Math.max(1, ...pontos.map((p) => p.i.valor_nominal));
  const raio = (v: number) => 4 + 9 * Math.sqrt(v / maiorValor);
  const p = foco != null ? pontos[foco] : null;

  const recebeNoMarcador = emReais(recebePct(dias, taxa));

  // clicar ou arrastar no gráfico escolhe o prazo
  const diasDoPonteiro = (clientX: number) => {
    const r = svgRef.current?.getBoundingClientRect();
    if (!r) return;
    const x = ((clientX - r.left) / r.width) * W;
    onDias(Math.round(Math.min(Math.max((x - M.esq) / (W - M.esq - M.dir), 0), 1) * xMax));
  };

  return (
    <div className="relative overflow-x-auto overscroll-x-contain">
      <div className="relative min-w-[36rem]">
      <svg ref={svgRef} viewBox={`0 0 ${W} ${H}`} className="h-auto w-full touch-pan-y select-none" role="img"
        aria-label={`Quanto uma nota de ${formatarMoeda(valor)} rende hoje por prazo: perde ${fPct(taxa * 100)} a cada 30 dias`}
        onPointerDown={(e) => { arrastando.current = true; diasDoPonteiro(e.clientX); }}
        onPointerMove={(e) => { if (arrastando.current) diasDoPonteiro(e.clientX); }}
        onPointerUp={() => { arrastando.current = false; }}
        onPointerLeave={() => { arrastando.current = false; }}>
        {ticksY.map((t) => (
          <g key={t}>
            <line x1={M.esq} x2={W - M.dir} y1={sy(t)} y2={sy(t)} className="stroke-creme-linha" strokeWidth="1" />
            <text x={M.esq - 8} y={sy(t) + 4} textAnchor="end" className="fill-slate-500 text-[11px] tabular-nums">{fMoedaEixo(t)}</text>
          </g>
        ))}
        {ticksX.map((t) => (
          <text key={t} x={sx(t)} y={H - M.base + 18} textAnchor="middle" className="fill-slate-500 text-[11px] tabular-nums">{t}</text>
        ))}
        <text x={(M.esq + W - M.dir) / 2} y={H - 4} textAnchor="middle" className="fill-slate-400 text-[11px]">dias até o vencimento</text>
        {/* área perdida até o prazo escolhido: entre o valor da nota e o que se recebe */}
        <polygon points={`${sx(0)},${sy(valor)} ${sx(dias)},${sy(valor)} ${sx(dias)},${sy(recebeNoMarcador)}`} className="fill-rose-400/25" />
        <line x1={sx(0)} x2={W - M.dir} y1={sy(valor)} y2={sy(valor)} className="stroke-slate-400" strokeWidth="1" strokeDasharray="4 3" />
        {/* a regra do fundo: reta que cai a taxa mensal a cada 30 dias */}
        <line x1={sx(0)} y1={sy(valor)} x2={sx(xMax)} y2={sy(emReais(recebePct(xMax, taxa)))} className="stroke-emerald-700" strokeWidth="2.5" strokeLinecap="round" />
        {pontos.map((pt, k) => {
          const aprov = pt.i.status === "APROVADA";
          const salva = pt.i.salva_pelo_otimizador;
          return (
            <circle key={pt.i.linha_csv} cx={sx(pt.x)} cy={sy(emReais(pt.pct))} r={raio(pt.i.valor_nominal)} tabIndex={0}
              aria-label={`Nota ${pt.i.nu_documento}, ${pt.x} dias, recebe ${fPct(pt.pct)} do valor`}
              onMouseEnter={() => setFoco(k)} onMouseLeave={() => setFoco(null)} onFocus={() => setFoco(k)} onBlur={() => setFoco(null)}
              className={`cursor-pointer outline-none transition-opacity ${salva ? "fill-broto stroke-emerald-900" : aprov ? "fill-emerald-600/70 stroke-emerald-800" : "fill-transparent stroke-slate-400"} ${foco != null && foco !== k ? "opacity-40" : ""}`}
              strokeWidth={salva ? 2 : 1.2} strokeDasharray={aprov ? undefined : "3 2"} />
          );
        })}
        {/* marcador do prazo escolhido */}
        <line x1={sx(dias)} x2={sx(dias)} y1={sy(valor)} y2={H - M.base} className="stroke-rose-600" strokeWidth="1.5" strokeDasharray="3 3" />
        <circle cx={sx(dias)} cy={sy(recebeNoMarcador)} r="7" className="fill-rose-600 stroke-creme-claro" strokeWidth="3" />
      </svg>
      {p && (
        <div className={`pointer-events-none absolute z-10 w-60 -translate-x-1/2 rounded-xl border border-creme-linha bg-creme-claro px-3 py-2 text-xs shadow-elevated ${sy(emReais(p.pct)) / H < 0.35 ? "" : "-translate-y-full"}`}
          style={{ left: `${Math.min(Math.max((sx(p.x) / W) * 100, 18), 82)}%`, top: `${(sy(emReais(p.pct)) / H) * 100}%`, marginTop: sy(emReais(p.pct)) / H < 0.35 ? 16 : -14 }}>
          <p className="font-semibold text-slate-900">Nota {p.i.nu_documento} · {p.x} dias</p>
          <p className="truncate text-slate-500">{p.i.nome_sacado}</p>
          <p className="mt-1 tabular-nums text-slate-700">{formatarMoeda(p.i.valor_nominal)} → recebe {fPct(p.pct)}</p>
          <p className="tabular-nums text-slate-700">Com {formatarMoeda(valor)}: recebe {formatarMoeda(emReais(p.pct))}</p>
          <p className={p.i.status === "APROVADA" ? "text-emerald-700" : "text-slate-500"}>
            {p.i.salva_pelo_otimizador ? "Aprovada graças ao otimizador" : p.i.status === "APROVADA" ? "Aprovada" : "Recusada (preço só para comparação)"}
          </p>
        </div>
      )}
      </div>
      <div className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-xs text-slate-600">
        <span className="flex items-center gap-1.5"><span className="h-0.5 w-5 rounded bg-emerald-700" />Quanto você recebe ({fPct(taxa * 100)} a menos a cada 30 dias)</span>
        <span className="flex items-center gap-1.5"><span className="h-3 w-3 rounded-sm bg-rose-400/40" />Quanto você perde</span>
        <span className="flex items-center gap-1.5"><span className="h-3 w-3 rounded-full border border-emerald-800 bg-emerald-600/70" />Nota aprovada</span>
        <span className="flex items-center gap-1.5"><span className="h-3 w-3 rounded-full border-2 border-emerald-900 bg-broto" />Salva pelo otimizador</span>
        <span className="flex items-center gap-1.5"><span className="h-3 w-3 rounded-full border border-dashed border-slate-400" />Recusada</span>
      </div>
    </div>
  );
}

/** Campo de valor em reais: aceita só dígitos e mostra com separador de milhar. */
function CampoValor({ valor, onValor }: { valor: number; onValor: (v: number) => void }) {
  return (
    <label className="flex flex-col gap-1.5 text-sm text-slate-700">
      Valor da nota
      <span className="relative">
        <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-500">R$</span>
        <input id="perda-valor" type="text" inputMode="numeric" autoComplete="off"
          value={valor ? valor.toLocaleString("pt-BR") : ""} placeholder="10.000"
          onChange={(e) => onValor(Number(e.target.value.replace(/\D/g, "").slice(0, 12)) || 0)}
          className="input-base w-full pl-10 font-display text-lg font-semibold tabular-nums" />
      </span>
    </label>
  );
}

export function TelaPerda({ resumo, meta, itens }: TelaPerdaProps) {
  const taxa = meta.taxa_mensal_aplicada;
  const aprovadas = itens.filter((i) => i.status === "APROVADA");
  const faixas = FAIXAS.map((f, k) => {
    const notas = aprovadas.filter((n) => n.prazo_dias <= f.max && n.prazo_dias > (k ? FAIXAS[k - 1].max : -Infinity));
    const face = notas.reduce((s, n) => s + n.valor_nominal, 0);
    const custo = notas.reduce((s, n) => s + n.desagio_reais, 0);
    return { ...f, qtd: notas.length, face, custo, pct: face ? (100 * custo) / face : 0 };
  }).filter((f) => f.qtd > 0);
  const maiorPct = Math.max(0.01, ...faixas.map((f) => f.pct));
  const pctCustoLote = resumo.valor_bruto_aprovado ? (100 * resumo.desagio_total) / resumo.valor_bruto_aprovado : 0;
  const [valor, setValor] = useState(10000);
  const [dias, setDias] = useState(60);
  const recebe = (valor * recebePct(dias, taxa)) / 100;
  const perde = valor - recebe;

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 px-5 py-10 sm:px-8 lg:py-14">
      <Cabecalho titulo="Análise de perda"
        sub="Quanto cada dia de prazo custa. Quanto mais curta a nota, mais do limite do cliente vira dinheiro hoje." />

      <div className="grid gap-4 sm:grid-cols-3">
        <div className="rounded-3xl border border-creme-linha bg-creme-claro p-5 shadow-card">
          <p className="text-sm text-slate-600">Cada 30 dias de prazo custam</p>
          <p className="font-display text-3xl font-semibold tabular-nums text-slate-900">{fPct(taxa * 100)}</p>
          <p className="text-xs text-slate-500">do valor da nota · {formatarMoeda((1000 * taxa) / 30)} por dia a cada R$ 1.000</p>
        </div>
        <div className="rounded-3xl border border-creme-linha bg-creme-claro p-5 shadow-card">
          <p className="text-sm text-slate-600">Custo deste lote</p>
          <p className="font-display text-3xl font-semibold tabular-nums text-rose-700">− {formatarMoedaCompacta(resumo.desagio_total)}</p>
          <p className="text-xs text-slate-500">{fPct(pctCustoLote)} do valor aprovado · prazo médio de {resumo.prazo_medio_ponderado_dias.toLocaleString("pt-BR", { maximumFractionDigits: 1 })} dias</p>
        </div>
        <div className={`rounded-3xl border p-5 shadow-card ${meta.ganho_otimizador_reais > 0 ? "border-emerald-200 bg-emerald-50" : "border-creme-linha bg-creme-claro"}`}>
          <p className="flex items-center gap-1.5 text-sm text-slate-600"><Sparkles className="h-4 w-4 text-emerald-600" />O otimizador usou isso</p>
          {meta.ganho_otimizador_reais > 0 ? (
            <>
              <p className="font-display text-3xl font-semibold tabular-nums text-emerald-800">+ {formatarMoedaCompacta(meta.ganho_otimizador_reais)}</p>
              <p className="text-xs text-slate-600">{meta.qtd_notas_salvas_otimizador} {meta.qtd_notas_salvas_otimizador === 1 ? "nota curta entrou" : "notas curtas entraram"} no lugar de notas longas</p>
            </>
          ) : (
            <p className="mt-1 text-sm text-slate-600">Neste lote nenhum limite de cliente apertou, então trocar a ordem das notas não mudaria o valor.</p>
          )}
        </div>
      </div>

      <Cartao titulo="Quanto você perde por esperar" nota="Digite o valor de uma nota e escolha o prazo (no controle ou clicando no gráfico).">
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1.3fr)]">
          <CampoValor valor={valor} onValor={setValor} />
          <label className="flex flex-col gap-1.5 text-sm text-slate-700">
            <span>Prazo até o vencimento: <strong className="tabular-nums">{dias} dias</strong></span>
            <input id="perda-dias" type="range" min="0" max="180" step="1" value={Math.min(dias, 180)} onChange={(e) => setDias(Number(e.target.value))} className="mt-3 accent-rose-600" />
          </label>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 md:col-span-2 xl:col-span-1" aria-live="polite">
            <div className="rounded-2xl bg-floresta px-4 py-3 text-creme">
              <p className="text-xs text-creme/70">Recebe hoje</p>
              <p className="whitespace-nowrap font-display text-lg font-semibold tabular-nums xl:text-xl">{formatarMoeda(recebe)}</p>
            </div>
            <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-rose-900">
              <p className="text-xs">Perde ({fPct(valor ? (100 * perde) / valor : 0)})</p>
              <p className="whitespace-nowrap font-display text-lg font-semibold tabular-nums xl:text-xl">− {formatarMoeda(perde)}</p>
            </div>
          </div>
        </div>
        {valor > 0 ? (
          <GraficoPrazo itens={itens} taxa={taxa} valor={valor} dias={dias} onDias={setDias} />
        ) : (
          <p className="rounded-2xl bg-creme p-6 text-center text-sm text-slate-600">Digite o valor da nota para ver o gráfico.</p>
        )}
        <p className="text-xs text-slate-500">Os círculos são as notas deste lote, mostrando quanto cada uma pagaria se valesse {formatarMoeda(valor)}. Notas que vencem em poucos dias podem pagar um custo mínimo definido pelo fundo, por isso ficam um pouco abaixo da reta.</p>
      </Cartao>

      <Cartao titulo="Mesmo valor, prazos diferentes" nota={`Uma nota de ${formatarMoeda(valor)}: quanto se perde (barra) e quanto vira dinheiro hoje`}>
        <ul className="flex flex-col gap-3">
          {[10, 30, 60, 90, 180].map((d) => {
            const v = (valor * recebePct(d, taxa)) / 100;
            const perda = valor - v;
            const perdaMax = valor - (valor * recebePct(180, taxa)) / 100;
            return (
              <li key={d} className="grid grid-cols-[4.5rem_minmax(0,1fr)_auto] items-center gap-x-3 gap-y-0.5">
                <span className="text-sm tabular-nums text-slate-600">{d} dias</span>
                <span className="flex items-center gap-2">
                  <span className="h-2 flex-1 rounded-full bg-creme-linha"><span className="block h-full rounded-full bg-rose-400" style={{ width: `${perdaMax ? (100 * perda) / perdaMax : 0}%` }} /></span>
                  <span className="w-28 whitespace-nowrap text-right text-xs tabular-nums text-rose-700">− {formatarMoeda(perda)}</span>
                </span>
                <span className="text-sm font-semibold tabular-nums text-slate-900">{formatarMoeda(v)}</span>
              </li>
            );
          })}
        </ul>
        <p className="rounded-2xl bg-creme p-4 text-sm text-slate-700">
          Quando o limite de um cliente acaba, a nota de 10 dias rende <strong className="tabular-nums">{formatarMoeda((valor * (recebePct(10, taxa) - recebePct(90, taxa))) / 100)}</strong> a mais que a de 90 dias, usando o mesmo espaço. É por isso que o otimizador prefere as notas curtas.
        </p>
      </Cartao>

      <Cartao titulo="Custo por faixa de prazo" nota="Só notas aprovadas · valor de face e custo somados por faixa">
        {faixas.length ? (
          <div className="overflow-x-auto overscroll-x-contain">
            <table className="w-full min-w-[34rem] text-sm">
              <thead>
                <tr className="text-left text-xs uppercase tracking-wider text-slate-500">
                  <th className="py-2 pr-3 font-semibold">Prazo</th>
                  <th className="py-2 pr-3 text-right font-semibold">Notas</th>
                  <th className="py-2 pr-3 text-right font-semibold">Valor de face</th>
                  <th className="py-2 pr-3 text-right font-semibold">Custo</th>
                  <th className="py-2 font-semibold">Parte perdida</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-creme-linha">
                {faixas.map((f) => (
                  <tr key={f.rotulo}>
                    <td className="py-2.5 pr-3 tabular-nums text-slate-800">{f.rotulo} dias</td>
                    <td className="py-2.5 pr-3 text-right tabular-nums">{fInt(f.qtd)}</td>
                    <td className="py-2.5 pr-3 text-right tabular-nums">{formatarMoedaCompacta(f.face)}</td>
                    <td className="py-2.5 pr-3 text-right tabular-nums text-rose-700">− {formatarMoedaCompacta(f.custo)}</td>
                    <td className="py-2.5">
                      <span className="flex items-center gap-2">
                        <span className="h-2 flex-1 rounded-full bg-creme-linha"><span className="block h-full rounded-full bg-rose-400" style={{ width: `${(100 * f.pct) / maiorPct}%` }} /></span>
                        <span className="w-14 text-right tabular-nums text-slate-700">{fPct(f.pct)}</span>
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <p className="py-6 text-center text-slate-500">Nenhuma nota aprovada neste lote.</p>}
      </Cartao>
    </div>
  );
}
