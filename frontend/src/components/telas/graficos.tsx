import type { ContagemMotivo, ItemLote, ResumoLote } from "../../types/api";
import { formatarMoedaCompacta } from "../../utils/formatters";


export const pct = (parte: number, todo: number) => (todo > 0 ? (parte / todo) * 100 : 0);
const fPct = (v: number) => `${v.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}%`;

const ABREVIACAO: Record<string, string> = {
  TIPO_RECEBIVEL: "TIPO", PRAZO_MAXIMO: "PRAZO", PRAZO_MINIMO: "PRAZO", VALOR_MINIMO: "VALOR", VALOR_MAXIMO: "VALOR",
  NAO_VENCIDA: "VENC", CONCENTRACAO_MAXIMA_SACADO: "LIMITE", CONCENTRACAO_MAXIMA_CEDENTE: "LIMITE",
  SITUACAO_CADASTRAL_SACADO: "RECEITA", CNPJ_SACADO_VALIDO: "CNPJ", CNPJ_CEDENTE_VALIDO: "CNPJ",
  DOCUMENTO_BLOQUEADO: "BLOQ", FRAUDE_OUTRO_FUNDO: "FRAUDE", DUPLICIDADE_FUNDO: "REPET", DUPLICIDADE_LOTE: "REPET",
  FORMATO_INVALIDO: "FORMATO",
};
export const GRAVE = new Set(["FRAUDE_OUTRO_FUNDO", "DUPLICIDADE_FUNDO", "DUPLICIDADE_LOTE"]);

const FAIXAS = [
  { rotulo: "até 15", max: 15 }, { rotulo: "16–30", max: 30 }, { rotulo: "31–60", max: 60 },
  { rotulo: "61–90", max: 90 }, { rotulo: "91–180", max: 180 }, { rotulo: "+180", max: Infinity },
];

export function BrutoAoLiquido({ resumo }: { resumo: ResumoLote }) {
  const B = resumo.valor_bruto_total;
  const linhas = [
    { sigla: "ENV", nome: "Valor enviado", valor: B, de: 0, ate: 100, cor: "bg-slate-400" },
    { sigla: "REC", nome: "Ficou de fora", valor: -resumo.valor_bruto_recusado, de: pct(resumo.valor_bruto_aprovado, B), ate: 100, cor: "bg-rose-500" },
    { sigla: "CUS", nome: "Custo da antecipação", valor: -resumo.desagio_total, de: pct(resumo.valor_liquido_receber, B), ate: pct(resumo.valor_bruto_aprovado, B), cor: "bg-amber-500" },
    { sigla: "LÍQ", nome: "Na sua conta hoje", valor: resumo.valor_liquido_receber, de: 0, ate: pct(resumo.valor_liquido_receber, B), cor: "bg-broto" },
  ];
  return (
    <div>
      <p className="eyebrow text-slate-500">Do enviado ao recebido</p>
      <ul className="mt-4 space-y-4">
        {linhas.map((l) => (
          <li key={l.sigla} className="grid grid-cols-[minmax(0,1fr)_auto] items-baseline gap-x-3 gap-y-1.5">
            <span className="text-sm text-slate-700">
              <span className="mr-2 text-[11px] font-bold tracking-wider text-slate-500">{l.sigla}</span>{l.nome}
            </span>
            <span className={`text-sm font-semibold tabular-nums ${l.valor < 0 ? "text-rose-700" : "text-slate-900"}`}>
              {l.valor < 0 ? "− " : ""}{formatarMoedaCompacta(Math.abs(l.valor))}
            </span>
            <div className="relative col-span-2 h-1.5 rounded-full bg-creme-linha">
              <span className={`absolute inset-y-0 rounded-full ${l.cor}`} style={{ left: `${l.de}%`, width: `${Math.max(l.ate - l.de, 0.6)}%` }} />
            </div>
            <span className="col-span-2 -mt-1 text-right text-[11px] tabular-nums text-slate-400">{fPct(l.ate - l.de)} do enviado</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function Motivos({ motivos, onVerMotivo }: { motivos: ContagemMotivo[]; onVerMotivo: (c: string) => void }) {
  const lista = [...motivos].sort((a, b) => b.valor_impactado - a.valor_impactado).slice(0, 5);
  const maior = lista[0]?.valor_impactado ?? 0;
  if (!lista.length) return <p className="py-10 text-center text-sm text-slate-500">Nenhuma nota ficou de fora neste lote.</p>;
  return (
    <div>
      <p className="eyebrow text-slate-500">Valor por problema</p>
      <ul className="mt-4 space-y-1">
        {lista.map((m) => (
          <li key={m.codigo}>
            <button type="button" onClick={() => onVerMotivo(m.codigo)}
              className="grid w-full grid-cols-[minmax(0,1fr)_auto] items-baseline gap-x-3 gap-y-1 rounded-lg px-2 py-2 text-left hover:bg-creme focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-700">
              <span className={`text-[11px] font-bold tracking-wider ${GRAVE.has(m.codigo) ? "text-rose-700" : "text-slate-500"}`}>
                {ABREVIACAO[m.codigo] ?? "OUTRO"}
              </span>
              <span className="text-sm font-semibold tabular-nums text-slate-900">{formatarMoedaCompacta(m.valor_impactado)}</span>
              <span className="col-span-2 text-sm text-slate-700">{m.titulo_amigavel}</span>
              <div className="col-span-2 mt-0.5 h-1.5 rounded-full bg-creme-linha">
                <span className={`block h-full rounded-full ${GRAVE.has(m.codigo) ? "bg-rose-500" : "bg-emerald-600"}`}
                  style={{ width: `${Math.max(pct(m.valor_impactado, maior), 2)}%` }} />
              </div>
              <span className="col-span-2 text-right text-[11px] tabular-nums text-slate-400">
                {m.quantidade} {m.quantidade === 1 ? "nota" : "notas"}
              </span>
            </button>
          </li>
        ))}
      </ul>
      <p className="mt-3 text-[11px] text-slate-400">Uma nota pode ter mais de um problema, então ela aparece em cada um deles.</p>
    </div>
  );
}

export function Vencimentos({ itens, prazoMedio }: { itens: ItemLote[]; prazoMedio: number }) {
  const aprovadas = itens.filter((i) => i.status === "APROVADA");
  const somas = FAIXAS.map((f, i) => aprovadas
    .filter((n) => n.prazo_dias <= f.max && n.prazo_dias > (i ? FAIXAS[i - 1].max : -Infinity))
    .reduce((s, n) => s + n.valor_nominal, 0));
  const usadas = FAIXAS.map((f, i) => ({ ...f, valor: somas[i] })).filter((f, i) => f.max !== Infinity || somas[i] > 0);
  const maior = Math.max(...usadas.map((f) => f.valor), 0);
  return (
    <div>
      <p className="eyebrow text-slate-500">Prazo médio das aprovadas</p>
      <p className="mt-2 numero-fino text-4xl text-emerald-800">
        {prazoMedio.toLocaleString("pt-BR", { maximumFractionDigits: 1 })} <span className="text-xl">dias</span>
      </p>
      {maior > 0 ? (
        <div className="mt-5">
          <div className="flex h-40 items-end gap-2 border-b border-creme-linha">
            {usadas.map((f) => (
              <div key={f.rotulo} className="flex h-full min-w-0 flex-1 flex-col items-center justify-end gap-1">
                <span className="whitespace-nowrap text-[10px] tabular-nums text-slate-500">{f.valor ? formatarMoedaCompacta(f.valor).replace("R$ ", "") : ""}</span>
                <span className={`w-full rounded-t-md ${f.valor === maior ? "bg-broto" : "bg-emerald-200"}`}
                  style={{ height: `${Math.max(pct(f.valor, maior), f.valor ? 3 : 0)}%` }} />
              </div>
            ))}
          </div>
          <div className="mt-1.5 flex gap-2">
            {usadas.map((f) => <span key={f.rotulo} className="flex-1 text-center text-[10px] text-slate-500">{f.rotulo}</span>)}
          </div>
          <p className="mt-1 text-center text-[11px] text-slate-400">dias até o vencimento · valor de face aprovado (R$)</p>
        </div>
      ) : (
        <p className="py-10 text-center text-sm text-slate-500">Nenhuma nota aprovada neste lote.</p>
      )}
    </div>
  );
}
