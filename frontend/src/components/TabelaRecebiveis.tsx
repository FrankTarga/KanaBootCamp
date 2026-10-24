import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import {
  AlertOctagon,
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Download,
  Lightbulb,
  Search,
  Sparkles,
  X,
  XCircle,
} from "lucide-react";
import type { ItemLote } from "../types/api";
import {
  dispararDownloadBlob,
  formatarDocumento,
  formatarMoeda,
  gerarCsvNotasAprovadas,
  gerarCsvRelatorioPendencias,
} from "../utils/formatters";

type AbaFiltro = "TODAS" | "APROVADAS" | "RECUSADAS" | "SALVAS" | "FRAUDE";

interface TabelaRecebiveisProps {
  itens: ItemLote[];
  motivoFiltroAtivo: string | null;
  onLimparMotivoFiltro: () => void;
  /** texto que já vem na busca (ex.: número de nota procurado no histórico) */
  buscaInicial?: string;
}

const LIMITE_LINHAS = 300;
const fDias = (d: number) => (d >= 0 ? `${d} ${d === 1 ? "dia" : "dias"}` : `venceu há ${Math.abs(d)} dias`);

function Situacao({ item }: { item: ItemLote }) {
  const base = "inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2.5 py-0.5 text-[11px] font-semibold";
  if (item.status === "APROVADA") return <span className={`${base} bg-emerald-100/80 text-emerald-800`}><CheckCircle2 className="h-3 w-3 text-emerald-600" />Aprovada</span>;
  if (item.severidade === "FRAUDE") return <span className={`${base} border border-rose-200 bg-rose-100 text-rose-800`}><AlertOctagon className="h-3 w-3 text-rose-600" />Vendida a outro fundo</span>;
  if (item.severidade === "DUPLICIDADE") return <span className={`${base} border border-purple-200 bg-purple-100 text-purple-800`}><AlertTriangle className="h-3 w-3 text-purple-600" />Nota repetida</span>;
  return <span className={`${base} bg-amber-100 text-amber-800`}><XCircle className="h-3 w-3 text-amber-600" />Recusada</span>;
}

function Motivo({ item }: { item: ItemLote }) {
  if (item.status === "APROVADA" || !item.erros.length) return null;
  return (
    <span className="block text-[11px] leading-snug text-slate-500">
      {item.erros[0].titulo_amigavel}
      {item.erros.length > 1 && <span className="ml-1 font-bold text-amber-700">+{item.erros.length - 1}</span>}
    </span>
  );
}

/** Explicação aberta ao clicar numa nota: o que aconteceu e como resolver. */
function Detalhe({ item }: { item: ItemLote }) {
  const aprovada = item.status === "APROVADA";
  return (
    <div className="space-y-3 p-4 sm:p-5">
      <p className="text-sm text-slate-700">
        <strong className="text-slate-900">Nota {item.nu_documento}</strong> · {item.nome_sacado}
        <span className="ml-1 font-mono text-[11px] text-slate-400">{formatarDocumento(item.doc_sacado)}</span>
      </p>
      {aprovada ? (
        <div className="flex items-start gap-3 rounded-xl border border-emerald-200 bg-emerald-50/60 p-4 text-emerald-950">
          <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600" />
          <div className="space-y-1 text-xs leading-relaxed text-emerald-900">
            <p className="font-semibold">Pode antecipar hoje.</p>
            <p>
              A nota passou em todas as regras do fundo. De {formatarMoeda(item.valor_nominal)}, o custo é de {formatarMoeda(item.desagio_reais)} pelos{" "}
              {item.prazo_dias} dias até o vencimento ({item.data_vencimento}), e você recebe {formatarMoeda(item.valor_liquido)}.
            </p>
            {item.salva_pelo_otimizador && (
              <p className="pt-1 font-medium text-teal-800">
                Na ordem do arquivo ela passaria do limite do cliente. O sistema reorganizou o lote para que ela coubesse.
              </p>
            )}
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          <p className="text-xs font-semibold text-slate-700">
            Por que ficou de fora ({item.erros.length} {item.erros.length === 1 ? "motivo" : "motivos"}):
          </p>
          {item.erros.map((erro, idx) => (
            <div key={erro.codigo + "_" + idx} className="space-y-2.5 rounded-xl border border-creme-linha bg-white p-4">
              <h4 className="flex items-center gap-2 text-xs font-bold text-slate-800">
                <span className="h-2 w-2 shrink-0 rounded-full bg-amber-500" />{erro.titulo_amigavel}
              </h4>
              <p className="text-xs leading-relaxed text-slate-700">{erro.mensagem_empresa}</p>
              <div className="flex items-start gap-2.5 rounded-lg border border-emerald-200/60 bg-emerald-50/60 p-3">
                <Lightbulb className="mt-0.5 h-4 w-4 shrink-0 text-emerald-700" />
                <p className="text-xs leading-relaxed text-emerald-900"><strong>Como resolver: </strong>{erro.acao_recomendada}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function Aba({ ativa, onClick, children, tom = "padrao" }: { ativa: boolean; onClick: () => void; children: ReactNode; tom?: "padrao" | "fraude" }) {
  const cor = tom === "fraude"
    ? ativa ? "bg-rose-600 text-white" : "text-rose-700 hover:bg-rose-50"
    : ativa ? "bg-white text-slate-900 shadow-2xs" : "text-slate-600 hover:text-slate-900";
  return (
    <button type="button" onClick={onClick} aria-pressed={ativa} className={`shrink-0 whitespace-nowrap rounded-lg px-3 py-1.5 font-semibold transition-colors ${cor}`}>
      {children}
    </button>
  );
}

export function TabelaRecebiveis({ itens, motivoFiltroAtivo, onLimparMotivoFiltro, buscaInicial = "" }: TabelaRecebiveisProps) {
  const [abaAtiva, setAbaAtiva] = useState<AbaFiltro>("TODAS");
  const [busca, setBusca] = useState(buscaInicial);
  const [linhasExpandidas, setLinhasExpandidas] = useState<Set<number>>(new Set());

  // largura visível da área da tabela: a explicação aberta fica presa nela mesmo com rolagem lateral
  const areaRef = useRef<HTMLDivElement>(null);
  const [larguraArea, setLarguraArea] = useState(0);
  useEffect(() => {
    const el = areaRef.current;
    if (!el) return;
    const obs = new ResizeObserver(() => setLarguraArea(el.clientWidth));
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  const contadores = useMemo(() => ({
    todas: itens.length,
    aprovadas: itens.filter((i) => i.status === "APROVADA").length,
    recusadas: itens.filter((i) => i.status === "RECUSADA").length,
    salvas: itens.filter((i) => i.salva_pelo_otimizador).length,
    fraude: itens.filter((i) => i.severidade === "FRAUDE").length,
  }), [itens]);

  const nomeMotivo = useMemo(() => {
    if (!motivoFiltroAtivo) return null;
    for (const i of itens) for (const e of i.erros) if (e.codigo === motivoFiltroAtivo) return e.titulo_amigavel;
    return "motivo selecionado";
  }, [itens, motivoFiltroAtivo]);

  const itensFiltrados = useMemo(() => {
    const termo = busca.trim().toLowerCase();
    return itens.filter((item) => {
      if (abaAtiva === "APROVADAS" && item.status !== "APROVADA") return false;
      if (abaAtiva === "RECUSADAS" && item.status !== "RECUSADA") return false;
      if (abaAtiva === "SALVAS" && !item.salva_pelo_otimizador) return false;
      if (abaAtiva === "FRAUDE" && item.severidade !== "FRAUDE") return false;
      if (motivoFiltroAtivo && !item.erros.some((e) => e.codigo === motivoFiltroAtivo)) return false;
      if (termo) {
        const achou = item.nu_documento.toLowerCase().includes(termo)
          || item.nome_sacado.toLowerCase().includes(termo) || item.doc_sacado.includes(termo)
          || item.nome_cedente.toLowerCase().includes(termo) || item.doc_cedente.includes(termo)
          || item.tipo_recebivel.toLowerCase().includes(termo);
        if (!achou) return false;
      }
      return true;
    });
  }, [itens, abaAtiva, busca, motivoFiltroAtivo]);
  // desenha só as primeiras linhas (a busca cobre todas), para o estoque de 100 mil não travar
  const visiveis = itensFiltrados.slice(0, LIMITE_LINHAS);

  const toggleLinha = (linhaCsv: number) => {
    setLinhasExpandidas((prev) => {
      const proximo = new Set(prev);
      if (proximo.has(linhaCsv)) proximo.delete(linhaCsv); else proximo.add(linhaCsv);
      return proximo;
    });
  };

  // trocar de filtro volta a área da tabela para o topo
  useEffect(() => { areaRef.current?.scrollTo({ top: 0 }); }, [abaAtiva, busca, motivoFiltroAtivo]);

  const vazio = <p className="py-12 text-center text-sm text-slate-400">Nenhuma nota encontrada com esses filtros.</p>;

  return (
    <div className="card min-w-0 overflow-hidden">
      <div className="space-y-3 border-b border-creme-linha bg-white p-4">
        <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
          {/* abas: no celular rolam de lado dentro da própria faixa */}
          <div className="-mx-1 overflow-x-auto overscroll-x-contain px-1">
            <div className="flex w-max items-center gap-1 rounded-xl bg-slate-100/80 p-1 text-xs">
              <Aba ativa={abaAtiva === "TODAS"} onClick={() => setAbaAtiva("TODAS")}>Todas ({contadores.todas})</Aba>
              <Aba ativa={abaAtiva === "APROVADAS"} onClick={() => setAbaAtiva("APROVADAS")}>Aprovadas ({contadores.aprovadas})</Aba>
              <Aba ativa={abaAtiva === "RECUSADAS"} onClick={() => setAbaAtiva("RECUSADAS")}>Recusadas ({contadores.recusadas})</Aba>
              <Aba ativa={abaAtiva === "SALVAS"} onClick={() => setAbaAtiva("SALVAS")}>Salvas pela reorganização ({contadores.salvas})</Aba>
              {contadores.fraude > 0 && (
                <Aba tom="fraude" ativa={abaAtiva === "FRAUDE"} onClick={() => setAbaAtiva("FRAUDE")}>Suspeita de fraude ({contadores.fraude})</Aba>
              )}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button type="button" onClick={() => dispararDownloadBlob(gerarCsvNotasAprovadas(itens), "lote_notas_aprovadas_antecipe.csv")}
              disabled={contadores.aprovadas === 0} className="btn btn-secondary px-3 py-1.5 text-xs" title="Planilha só com as notas aprovadas">
              <Download className="h-3.5 w-3.5 text-emerald-600" /><span>Baixar aprovadas</span>
            </button>
            <button type="button" onClick={() => dispararDownloadBlob(gerarCsvRelatorioPendencias(itens), "relatorio_pendencias_antecipe.csv")}
              disabled={contadores.recusadas === 0} className="btn btn-secondary px-3 py-1.5 text-xs" title="Planilha com cada recusa explicada e o que fazer">
              <Download className="h-3.5 w-3.5 text-amber-600" /><span>Relatório de recusas</span>
            </button>
          </div>
        </div>

        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div className="relative w-full sm:max-w-md">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input type="search" placeholder="Buscar nota, cliente, CNPJ ou tipo" value={busca} onChange={(e) => setBusca(e.target.value)}
              aria-label="Buscar notas"
              className="w-full rounded-lg border border-slate-200 py-2 pl-9 pr-3 text-sm outline-none placeholder:text-slate-400 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/10" />
          </div>
          {nomeMotivo && (
            <span className="flex items-center gap-2 self-start rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-xs text-emerald-900 sm:self-auto">
              Só notas com: <strong>{nomeMotivo}</strong>
              <button type="button" onClick={onLimparMotivoFiltro} aria-label="Tirar filtro" className="rounded p-0.5 text-emerald-700 hover:bg-emerald-100"><X className="h-3.5 w-3.5" /></button>
            </span>
          )}
          <span className="text-xs text-slate-500">
            {itensFiltrados.length > LIMITE_LINHAS
              ? <>Mostrando <strong>{LIMITE_LINHAS}</strong> de {itensFiltrados.length.toLocaleString("pt-BR")} notas · use a busca</>
              : <><strong>{itensFiltrados.length.toLocaleString("pt-BR")}</strong> de {itens.length.toLocaleString("pt-BR")} notas</>}
          </span>
        </div>
      </div>

      {/* Celular: uma nota por cartão, dentro de uma área com rolagem própria */}
      <ul className="max-h-[70vh] divide-y divide-creme-linha overflow-y-auto overscroll-contain md:hidden">
        {visiveis.length === 0 ? <li>{vazio}</li> : visiveis.map((item) => {
          const aberta = linhasExpandidas.has(item.linha_csv);
          return (
            <li key={item.hash_titulo + "_" + item.linha_csv} className={aberta ? "bg-creme/70" : ""}>
              <button type="button" onClick={() => toggleLinha(item.linha_csv)} aria-expanded={aberta} className="flex w-full items-start gap-3 p-4 text-left">
                <ChevronRight className={`mt-0.5 h-4 w-4 shrink-0 text-slate-400 transition-transform ${aberta ? "rotate-90" : ""}`} />
                <span className="min-w-0 flex-1 space-y-1">
                  <span className="flex items-baseline justify-between gap-2">
                    <span className="font-mono text-sm font-medium text-slate-900">{item.nu_documento}</span>
                    <span className={`whitespace-nowrap text-sm font-bold tabular-nums ${item.status === "APROVADA" ? "text-emerald-700" : "text-slate-400"}`}>
                      {item.status === "APROVADA" ? formatarMoeda(item.valor_liquido) : formatarMoeda(item.valor_nominal)}
                    </span>
                  </span>
                  <span className="block truncate text-sm text-slate-700">{item.nome_sacado || "Cliente não informado"}</span>
                  <span className="block text-[11px] text-slate-500">{item.tipo_recebivel} · vence {item.data_vencimento} ({fDias(item.prazo_dias)})</span>
                  <span className="flex flex-wrap items-center gap-1.5 pt-0.5"><Situacao item={item} /><Motivo item={item} /></span>
                </span>
              </button>
              {aberta && <div className="border-t border-creme-linha"><Detalhe item={item} /></div>}
            </li>
          );
        })}
      </ul>

      {/* Tela maior: tabela com rolagem própria; o cabeçalho fica parado no topo da área */}
      <div ref={areaRef} className="hidden max-h-[70vh] overflow-auto overscroll-contain md:block">
        <table className="w-full border-separate border-spacing-0 text-left text-xs">
          <thead className="sticky top-0 z-10">
            <tr className="bg-slate-50 text-[11px] font-semibold uppercase tracking-wider text-slate-500 [&>th]:border-b [&>th]:border-slate-200">
              <th className="w-10 px-2.5 py-3"><span className="sr-only">Abrir</span></th>
              <th className="px-3 py-3">Nota</th>
              <th className="px-3 py-3">Cliente</th>
              <th className="px-3 py-3">Tipo</th>
              <th className="px-3 py-3">Vencimento</th>
              <th className="px-3 py-3 text-right">Valor da nota</th>
              <th className="px-3 py-3 text-right">Custo</th>
              <th className="px-3 py-3 text-right text-slate-800">Você recebe</th>
              <th className="px-3 py-3">Situação</th>
            </tr>
          </thead>
          <tbody>
            {visiveis.length === 0 ? (
              <tr><td colSpan={9}>{vazio}</td></tr>
            ) : visiveis.map((item) => {
              const aberta = linhasExpandidas.has(item.linha_csv);
              const aprovada = item.status === "APROVADA";
              const chave = item.hash_titulo + "_" + item.linha_csv;
              return [
                <tr key={chave} onClick={() => toggleLinha(item.linha_csv)}
                  className={`group cursor-pointer transition-colors [&>td]:border-b [&>td]:border-slate-100 ${
                    aberta ? "bg-creme/80" : item.severidade === "FRAUDE" ? "bg-rose-50/30 hover:bg-rose-50/60" : aprovada ? "hover:bg-slate-50/70" : "hover:bg-amber-50/40"}`}>
                  <td className="px-3 py-3 text-center">
                    <button type="button" aria-expanded={aberta} aria-label={`${aberta ? "Fechar" : "Abrir"} detalhes da nota ${item.nu_documento}`}
                      onClick={(e) => { e.stopPropagation(); toggleLinha(item.linha_csv); }} className="rounded p-0.5 text-slate-400 group-hover:text-slate-600">
                      {aberta ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                    </button>
                  </td>
                  <td className="whitespace-nowrap px-2.5 py-3 font-mono font-medium text-slate-900">
                    {item.nu_documento}
                    <span className="block font-sans text-[10px] text-slate-400">linha {item.linha_csv}</span>
                  </td>
                  <td className="max-w-[13rem] px-2.5 py-3">
                    <div className="truncate font-semibold text-slate-900" title={item.nome_sacado}>{item.nome_sacado || "Cliente não informado"}</div>
                    <div className="font-mono text-[11px] text-slate-500">{formatarDocumento(item.doc_sacado)}</div>
                  </td>
                  <td className="whitespace-nowrap px-2.5 py-3"><span className="rounded bg-slate-100 px-2 py-0.5 text-[11px] text-slate-600">{item.tipo_recebivel}</span></td>
                  <td className="whitespace-nowrap px-2.5 py-3">
                    <div className="font-medium text-slate-800">{item.data_vencimento}</div>
                    <div className="text-[11px] text-slate-400">{fDias(item.prazo_dias)}</div>
                  </td>
                  <td className="whitespace-nowrap px-2.5 py-3 text-right font-medium tabular-nums text-slate-700">{formatarMoeda(item.valor_nominal)}</td>
                  <td className="whitespace-nowrap px-2.5 py-3 text-right tabular-nums text-slate-500">{aprovada ? `− ${formatarMoeda(item.desagio_reais)}` : "–"}</td>
                  <td className="whitespace-nowrap px-2.5 py-3 text-right font-bold tabular-nums">
                    {aprovada ? <span className="text-sm text-emerald-700">{formatarMoeda(item.valor_liquido)}</span> : <span className="text-slate-400">–</span>}
                  </td>
                  <td className="min-w-[9.5rem] max-w-[12rem] px-2.5 py-3">
                    <div className="flex flex-col items-start gap-1">
                      <Situacao item={item} />
                      {item.salva_pelo_otimizador && (
                        <span className="inline-flex items-center gap-1 whitespace-nowrap rounded-full border border-teal-300 bg-teal-100 px-2 py-0.5 text-[10px] font-semibold text-teal-800">
                          <Sparkles className="h-2.5 w-2.5 text-teal-600" />Salva pela reorganização
                        </span>
                      )}
                      <Motivo item={item} />
                    </div>
                  </td>
                </tr>,
                aberta && (
                  // a explicação abre logo abaixo da nota clicada e fica do tamanho da área visível
                  <tr key={chave + "_detalhe"} className="bg-creme/60">
                    <td colSpan={9} className="border-b border-creme-linha p-0">
                      <div className="sticky left-0" style={{ width: larguraArea || undefined }}><Detalhe item={item} /></div>
                    </td>
                  </tr>
                ),
              ];
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
