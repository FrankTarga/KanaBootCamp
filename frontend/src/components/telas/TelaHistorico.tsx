import { useCallback, useEffect, useRef, useState } from "react";
import { ChevronRight, Loader2, RefreshCw, Search, ServerOff, X } from "lucide-react";
import type { DetalheLoteHistorico, HistoricoLote, ItemLote, MudancaRegras, NotaHistorico, OcorrenciaNota } from "../../types/api";
import { buscarNotaHistorico, listarHistoricoLotes, listarHistoricoRegras, obterLoteHistorico } from "../../services/api";
import { formatarMoeda, formatarMoedaCompacta } from "../../utils/formatters";
import { nomeMotivo } from "../../utils/nomes";
import { TabelaRecebiveis } from "../TabelaRecebiveis";
import { Cabecalho } from "./TelaResumo";
import { Cartao } from "./TelaEstatistica";

interface TelaHistoricoProps {
  /** hash do arquivo aberto agora, para marcar "este lote" na lista */
  batchHashAtual: string | null;
}

const POR_PAGINA = 25;
const fData = (iso: string) =>
  new Date(iso).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
const fInt = (v: number) => v.toLocaleString("pt-BR");
const fTempo = (ms: number) => (ms >= 1000 ? `${(ms / 1000).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} s` : `${Math.round(ms)} ms`);

/** a tabela de notas usa o formato da validação; o histórico não guarda os campos internos */
const paraItem = (n: NotaHistorico, loteId: number): ItemLote => ({
  ...n, hash_titulo: `${loteId}-${n.linha_csv}`, ordem_avaliacao: n.linha_csv, data_aquisicao: "",
});

function Etiqueta({ children, tom }: { children: string; tom: "ambar" | "cinza" | "verde" }) {
  const cor = { ambar: "bg-amber-100 text-amber-900", cinza: "bg-creme-linha text-slate-600", verde: "bg-emerald-100 text-emerald-900" }[tom];
  return <span className={`whitespace-nowrap rounded-full px-2 py-0.5 text-[11px] font-semibold ${cor}`}>{children}</span>;
}

export function TelaHistorico({ batchHashAtual }: TelaHistoricoProps) {
  const [lotes, setLotes] = useState<HistoricoLote[]>([]);
  const [totalLotes, setTotalLotes] = useState(0);
  const [regras, setRegras] = useState<MudancaRegras[]>([]);
  const [totalRegras, setTotalRegras] = useState(0);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);

  // lote antigo aberto (notas guardadas no banco)
  const [aberto, setAberto] = useState<{ detalhe: DetalheLoteHistorico; busca: string } | null>(null);
  const [abrindo, setAbrindo] = useState<number | null>(null);
  const [erroLote, setErroLote] = useState<string | null>(null);
  const painelLoteRef = useRef<HTMLDivElement>(null);

  // busca de um número de nota em todos os lotes
  const [numero, setNumero] = useState("");
  const [ocorrencias, setOcorrencias] = useState<{ termo: string; itens: OcorrenciaNota[]; total: number } | null>(null);
  const [buscando, setBuscando] = useState(false);
  const [erroBusca, setErroBusca] = useState<string | null>(null);

  const abrirLote = async (id: number, busca = "") => {
    setAbrindo(id);
    setErroLote(null);
    try {
      const detalhe = await obterLoteHistorico(id);
      setAberto({ detalhe, busca });
      requestAnimationFrame(() => painelLoteRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }));
    } catch (e) {
      setErroLote(e instanceof Error ? e.message : "Não foi possível abrir o lote.");
    } finally {
      setAbrindo(null);
    }
  };

  const procurarNota = async (e: React.FormEvent) => {
    e.preventDefault();
    const termo = numero.trim();
    if (!termo) return;
    setBuscando(true);
    setErroBusca(null);
    try {
      const r = await buscarNotaHistorico(termo);
      setOcorrencias({ termo, itens: r.itens, total: r.total });
    } catch (err) {
      setErroBusca(err instanceof Error ? err.message : "Não foi possível procurar a nota.");
    } finally {
      setBuscando(false);
    }
  };

  const carregar = useCallback(async () => {
    setCarregando(true);
    setErro(null);
    try {
      const [l, r] = await Promise.all([listarHistoricoLotes(POR_PAGINA, 0), listarHistoricoRegras(10, 0)]);
      setLotes(l.itens); setTotalLotes(l.total);
      setRegras(r.itens); setTotalRegras(r.total);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Não foi possível ler o histórico.");
    } finally {
      setCarregando(false);
    }
  }, []);

  useEffect(() => { carregar(); }, [carregar]);

  const carregarMais = async () => {
    setCarregando(true);
    try {
      const l = await listarHistoricoLotes(POR_PAGINA, lotes.length);
      setLotes((atual) => [...atual, ...l.itens]); setTotalLotes(l.total);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Não foi possível ler o histórico.");
    } finally {
      setCarregando(false);
    }
  };

  const reais = lotes.filter((l) => !l.what_if);
  // "aberto agora" = a validação mais recente do arquivo que está na tela (lista vem do mais recente)
  const idAberto = batchHashAtual ? lotes.find((l) => l.batch_hash === batchHashAtual)?.id ?? null : null;
  const notasValidadas = reais.reduce((s, l) => s + l.total_notas, 0);
  const liquido = reais.reduce((s, l) => s + l.valor_liquido_receber, 0);

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 px-5 py-10 sm:px-8 lg:py-14">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <Cabecalho titulo="Histórico" sub="Todos os lotes já validados e cada mudança nas regras do fundo. Fica salvo no servidor, então não some ao fechar a página." />
        <button type="button" onClick={carregar} disabled={carregando}
          className="flex items-center gap-2 rounded-full border border-creme-linha bg-creme-claro px-4 py-2 text-sm font-semibold text-slate-700 hover:border-emerald-400 disabled:opacity-50">
          <RefreshCw className={`h-4 w-4 ${carregando ? "animate-spin" : ""}`} /> Atualizar
        </button>
      </div>

      {erro && (
        <div className="flex items-start gap-3 rounded-3xl border border-rose-200 bg-rose-50 p-5 text-rose-900" role="alert">
          <ServerOff className="mt-0.5 h-5 w-5 shrink-0" />
          <div className="text-sm">
            <p className="font-semibold">O histórico não respondeu.</p>
            <p>Ele fica no banco do servidor; com o backend desligado não há o que mostrar. Detalhe: {erro}</p>
          </div>
        </div>
      )}

      {!erro && (
        <div className="grid gap-4 sm:grid-cols-3">
          <div className="rounded-3xl border border-creme-linha bg-creme-claro p-5 shadow-card">
            <p className="text-sm text-slate-600">Validações registradas</p>
            <p className="font-display text-3xl font-semibold tabular-nums text-slate-900">{fInt(totalLotes)}</p>
            <p className="text-xs text-slate-500">inclui simulações do gestor e repetições</p>
          </div>
          <div className="rounded-3xl border border-creme-linha bg-creme-claro p-5 shadow-card">
            <p className="text-sm text-slate-600">Notas analisadas</p>
            <p className="font-display text-3xl font-semibold tabular-nums text-slate-900">{fInt(notasValidadas)}</p>
            <p className="text-xs text-slate-500">nas {fInt(reais.length)} validações listadas abaixo, sem simulações</p>
          </div>
          <div className="rounded-3xl border border-creme-linha bg-creme-claro p-5 shadow-card">
            <p className="text-sm text-slate-600">Líquido calculado</p>
            <p className="font-display text-3xl font-semibold tabular-nums text-emerald-800">{formatarMoedaCompacta(liquido)}</p>
            <p className="text-xs text-slate-500">soma das mesmas validações</p>
          </div>
        </div>
      )}

      <Cartao titulo="Procurar uma nota" nota="Digite o número da nota para ver em quais envios ela apareceu e o que aconteceu em cada um.">
        <form onSubmit={procurarNota} className="flex flex-col gap-2 sm:flex-row">
          <label className="relative flex-1">
            <span className="sr-only">Número da nota</span>
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input id="busca-nota-historico" type="search" inputMode="numeric" value={numero} onChange={(e) => setNumero(e.target.value)}
              placeholder="Ex.: 353104 (zeros à esquerda não importam)" className="input-base w-full pl-9 text-sm" />
          </label>
          <button type="submit" disabled={buscando || !numero.trim()} className="btn btn-emerald justify-center px-5 py-2 text-sm disabled:opacity-50">
            {buscando ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />} Procurar
          </button>
        </form>
        {erroBusca && <p role="alert" className="rounded-xl bg-rose-50 px-3 py-2 text-sm text-rose-800">{erroBusca}</p>}
        {ocorrencias && (
          ocorrencias.itens.length === 0 ? (
            <p className="rounded-xl bg-creme p-4 text-sm text-slate-600">A nota <strong>{ocorrencias.termo}</strong> não aparece em nenhum envio guardado.</p>
          ) : (
            <div className="flex flex-col gap-2">
              <p className="text-sm text-slate-600">
                A nota <strong>{ocorrencias.termo}</strong> apareceu em {fInt(ocorrencias.total)} {ocorrencias.total === 1 ? "envio" : "envios"}
                {ocorrencias.total > ocorrencias.itens.length && ` (mostrando ${ocorrencias.itens.length})`}. Clique para ver o envio completo.
              </p>
              <ul className="max-h-[50vh] divide-y divide-creme-linha overflow-y-auto overscroll-contain rounded-2xl border border-creme-linha bg-white">
                {ocorrencias.itens.map((o) => {
                  const aprovada = o.status === "APROVADA";
                  return (
                    <li key={`${o.lote_id}-${o.linha_csv}`}>
                      <button type="button" onClick={() => abrirLote(o.lote_id, o.nu_documento)} disabled={abrindo !== null}
                        className="flex w-full items-start gap-3 p-3 text-left hover:bg-creme/60 disabled:cursor-wait">
                        <span className="min-w-0 flex-1">
                          <span className="flex flex-wrap items-center gap-2 text-sm">
                            <strong className="font-mono text-slate-900">{o.nu_documento}</strong>
                            <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${aprovada ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800"}`}>{aprovada ? "Aprovada" : "Recusada"}</span>
                            {o.what_if && <Etiqueta tom="ambar">Simulação</Etiqueta>}
                            <span className="text-xs text-slate-500">envio de {fData(o.criado_em)}</span>
                          </span>
                          <span className="block truncate text-xs text-slate-600">{o.nome_sacado} · {o.tipo_recebivel} · {formatarMoeda(o.valor_nominal)} · vence {o.data_vencimento}</span>
                          {aprovada
                            ? <span className="block text-xs text-emerald-800">Recebeu {formatarMoeda(o.valor_liquido)}</span>
                            : <span className="block text-xs text-amber-800">{o.codigos_erro.map(nomeMotivo).join(" · ")}</span>}
                        </span>
                        {abrindo === o.lote_id ? <Loader2 className="mt-1 h-4 w-4 shrink-0 animate-spin text-slate-400" /> : <ChevronRight className="mt-1 h-4 w-4 shrink-0 text-slate-400" />}
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>
          )
        )}
      </Cartao>

      <Cartao titulo="Lotes validados" nota="Do mais recente para o mais antigo. Clique num envio para ver as notas dele.">
        {!erro && !carregando && lotes.length === 0 ? (
          <p className="py-6 text-center text-slate-500">Nenhum lote validado ainda. Envie notas para começar o histórico.</p>
        ) : (
          <div className="max-h-[60vh] overflow-auto overscroll-contain rounded-xl">
            <table className="w-full min-w-[46rem] text-sm">
              <thead className="sticky top-0 z-10 bg-creme-claro">
                <tr className="text-left text-xs uppercase tracking-wider text-slate-500">
                  <th className="py-2 pr-3 font-semibold">Quando</th>
                  <th className="py-2 pr-3 font-semibold">Tipo</th>
                  <th className="py-2 pr-3 text-right font-semibold">Notas</th>
                  <th className="py-2 pr-3 text-right font-semibold">Aprovadas</th>
                  <th className="py-2 pr-3 text-right font-semibold">Recusadas</th>
                  <th className="py-2 pr-3 text-right font-semibold">Enviado</th>
                  <th className="py-2 pr-3 text-right font-semibold">Líquido</th>
                  <th className="py-2 pr-3 text-right font-semibold">Tempo</th>
                  <th className="py-2 font-semibold"><span className="sr-only">Abrir</span></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-creme-linha">
                {lotes.map((l) => (
                  <tr key={l.id} onClick={() => abrindo === null && abrirLote(l.id)}
                    className={`cursor-pointer hover:bg-creme/70 ${aberto?.detalhe.lote.id === l.id ? "bg-creme" : l.id === idAberto ? "bg-emerald-50/70" : ""}`}>
                    <td className="py-2.5 pr-3 tabular-nums text-slate-800">
                      {fData(l.criado_em)}
                      <span className="block text-[11px] text-slate-500">data-base {l.data_base} · {(l.taxa_mensal * 100).toLocaleString("pt-BR", { maximumFractionDigits: 2 })}% a.m.</span>
                    </td>
                    <td className="py-2.5 pr-3">
                      <span className="flex flex-wrap gap-1">
                        <Etiqueta tom="cinza">{l.modo === "carteira" ? "Carteira" : "Lote"}</Etiqueta>
                        {l.what_if && <Etiqueta tom="ambar">Simulação</Etiqueta>}
                        {l.replay && <Etiqueta tom="cinza">Repetido</Etiqueta>}
                        {l.id === idAberto && <Etiqueta tom="verde">Aberto agora</Etiqueta>}
                      </span>
                    </td>
                    <td className="py-2.5 pr-3 text-right tabular-nums">{fInt(l.total_notas)}</td>
                    <td className="py-2.5 pr-3 text-right tabular-nums text-emerald-800">{fInt(l.qtd_aprovadas)}</td>
                    <td className="py-2.5 pr-3 text-right tabular-nums text-rose-700">
                      {fInt(l.qtd_recusadas)}
                      {l.qtd_alertas_fraude > 0 && <span className="block text-[11px]">{fInt(l.qtd_alertas_fraude)} fraude</span>}
                    </td>
                    <td className="py-2.5 pr-3 text-right tabular-nums">{formatarMoedaCompacta(l.valor_bruto_total)}</td>
                    <td className="py-2.5 pr-3 text-right font-semibold tabular-nums text-slate-900">{formatarMoedaCompacta(l.valor_liquido_receber)}</td>
                    <td className="py-2.5 pr-3 text-right tabular-nums text-slate-500">{fTempo(l.tempo_processamento_ms)}</td>
                    <td className="py-2.5 text-right">
                      <button type="button" onClick={(e) => { e.stopPropagation(); abrirLote(l.id); }} disabled={abrindo !== null}
                        aria-label={`Ver notas do envio de ${fData(l.criado_em)}`}
                        className="inline-flex items-center gap-1 whitespace-nowrap rounded-full border border-creme-linha px-2.5 py-1 text-xs font-semibold text-slate-700 hover:border-emerald-400">
                        {abrindo === l.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <>Ver notas <ChevronRight className="h-3.5 w-3.5" /></>}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {lotes.length < totalLotes && (
          <button type="button" onClick={carregarMais} disabled={carregando}
            className="self-center rounded-full border border-creme-linha px-4 py-2 text-sm font-semibold text-slate-700 hover:border-emerald-400 disabled:opacity-50">
            Ver mais ({fInt(totalLotes - lotes.length)} restantes)
          </button>
        )}
        {erroLote && <p role="alert" className="rounded-xl bg-rose-50 px-3 py-2 text-sm text-rose-800">{erroLote}</p>}
        <p className="text-xs text-slate-500">"Repetido" = o mesmo arquivo com os mesmos parâmetros; o servidor devolveu a resposta guardada sem recalcular. "Simulação" = teste de regras do gestor, que não muda as regras do fundo.</p>
      </Cartao>

      {aberto && (
        <div ref={painelLoteRef} className="scroll-mt-20 flex flex-col gap-4">
          <div className="flex flex-wrap items-start justify-between gap-3 rounded-3xl border border-creme-linha bg-creme-claro p-5 shadow-card">
            <div>
              <h2 className="font-display text-xl font-semibold text-slate-900">Envio de {fData(aberto.detalhe.lote.criado_em)}</h2>
              <p className="text-sm text-slate-600">
                {aberto.detalhe.lote.modo === "carteira" ? "Carteira" : "Lote"} · {fInt(aberto.detalhe.lote.total_notas)} notas · {fInt(aberto.detalhe.lote.qtd_aprovadas)} aprovadas ·{" "}
                líquido de {formatarMoeda(aberto.detalhe.lote.valor_liquido_receber)}
                {aberto.detalhe.lote.replay && " · repetição: as notas são as do envio original"}
              </p>
            </div>
            <button type="button" onClick={() => setAberto(null)} className="inline-flex items-center gap-1 rounded-full border border-creme-linha px-3 py-1.5 text-sm font-semibold text-slate-700 hover:border-emerald-400">
              <X className="h-4 w-4" /> Fechar
            </button>
          </div>
          {aberto.detalhe.notas_guardadas ? (
            <>
              <TabelaRecebiveis key={`${aberto.detalhe.lote.id}-${aberto.busca}`} buscaInicial={aberto.busca}
                itens={aberto.detalhe.notas.map((n) => paraItem(n, aberto.detalhe.notas_de_lote_id))}
                motivoFiltroAtivo={null} onLimparMotivoFiltro={() => {}} />
              {aberto.detalhe.total_notas_guardadas > aberto.detalhe.notas.length && (
                <p className="text-xs text-slate-500">Mostrando as primeiras {fInt(aberto.detalhe.notas.length)} de {fInt(aberto.detalhe.total_notas_guardadas)} notas deste envio.</p>
              )}
            </>
          ) : (
            <p className="rounded-3xl border border-creme-linha bg-creme-claro p-5 text-sm text-slate-600">
              {aberto.detalhe.lote.modo === "carteira"
                ? "Na análise da carteira inteira o servidor guarda só o resumo, não nota por nota."
                : "Este envio é anterior ao banco de notas, então só o resumo foi guardado."}
            </p>
          )}
        </div>
      )}

      <Cartao titulo="Mudanças nas regras" nota="Cada vez que o gestor salvou novas regras">
        {regras.length === 0 ? (
          <p className="py-4 text-center text-sm text-slate-500">{erro ? "Sem conexão com o servidor." : "As regras ainda não foram alteradas pelo painel do gestor."}</p>
        ) : (
          <ul className="flex flex-col divide-y divide-creme-linha">
            {regras.map((r) => (
              <li key={r.id} className="flex flex-wrap items-baseline justify-between gap-2 py-2.5 text-sm">
                <span className="font-semibold text-slate-800">Versão {r.versao_config}</span>
                <span className="text-slate-600">{r.regras_ativas} regras ativas</span>
                <span className="tabular-nums text-slate-500">{fData(r.criado_em)}</span>
              </li>
            ))}
          </ul>
        )}
        {totalRegras > regras.length && <p className="text-xs text-slate-500">Mostrando as {regras.length} mais recentes de {fInt(totalRegras)}.</p>}
      </Cartao>
    </div>
  );
}
