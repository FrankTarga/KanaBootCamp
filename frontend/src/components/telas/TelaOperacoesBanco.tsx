import { useCallback, useEffect, useState } from "react";
import {
  CheckCircle2,
  Clock,
  Database,
  FileCheck2,
  Filter,
  Loader2,
  RefreshCw,
  Search,
  ShieldCheck,
} from "lucide-react";
import { formatarMoeda, formatarMoedaCompacta } from "../../utils/formatters";
import { listarOperacoesBanco, liquidarLote } from "../../services/api";
import type { OperacaoLote, ResultadoLiquidacao } from "../../types/api";
import { Cabecalho } from "./TelaResumo";

interface TelaOperacoesBancoProps {
  batchHashAtual?: string | null;
  onMostrarComprovante?: (liq: ResultadoLiquidacao, op: OperacaoLote) => void;
}

export function TelaOperacoesBanco({
  batchHashAtual,
  onMostrarComprovante,
}: TelaOperacoesBancoProps) {
  const [operacoes, setOperacoes] = useState<OperacaoLote[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [liquidandoHash, setLiquidandoHash] = useState<string | null>(null);
  const [filtroStatus, setFiltroStatus] = useState<"TODOS" | "LIQUIDADO" | "SIMULADO">("TODOS");
  const [busca, setBusca] = useState("");
  const [erro, setErro] = useState<string | null>(null);

  const carregar = useCallback(async () => {
    setCarregando(true);
    setErro(null);
    try {
      const dados = await listarOperacoesBanco();
      setOperacoes(dados);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao carregar operações do banco.");
    } finally {
      setCarregando(false);
    }
  }, []);

  useEffect(() => {
    carregar();
  }, [carregar]);

  const handleLiquidar = async (op: OperacaoLote) => {
    setLiquidandoHash(op.batch_hash);
    try {
      const res = await liquidarLote(op.batch_hash);
      await carregar();
      if (onMostrarComprovante) {
        onMostrarComprovante(res, op);
      }
    } catch (e) {
      alert(e instanceof Error ? e.message : "Falha ao liquidar lote.");
    } finally {
      setLiquidandoHash(null);
    }
  };

  // Métricas
  const totalOperacoes = operacoes.length;
  const liquidados = operacoes.filter((o) => o.status_operacao === "LIQUIDADO");
  const valorTotalLiquidado = liquidados.reduce((acc, cur) => acc + cur.valor_liquido_aprovado, 0);
  const ganhoTotalOtimizador = operacoes.reduce((acc, cur) => acc + (cur.ganho_otimizador || 0), 0);

  // Filtros
  const filtradas = operacoes.filter((op) => {
    if (filtroStatus !== "TODOS" && op.status_operacao !== filtroStatus) return false;
    if (busca.trim()) {
      const termo = busca.toLowerCase();
      const bateNome = op.cedente_nome.toLowerCase().includes(termo);
      const bateDoc = op.cedente_doc.includes(termo);
      const bateHash = op.batch_hash.toLowerCase().includes(termo);
      if (!bateNome && !bateDoc && !bateHash) return false;
    }
    return true;
  });

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 px-5 py-10 sm:px-8 lg:py-14 animate-in fade-in">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-800 mb-2">
            <Database className="h-3.5 w-3.5" /> Banco SQLite ACID (lotes_operacoes)
          </div>
          <Cabecalho
            titulo="Histórico de Lotes (Banco de Dados)"
            sub="Todas as simulações e liquidações registradas com garantias ACID e imutabilidade no SQLite."
          />
        </div>

        <button
          type="button"
          onClick={carregar}
          disabled={carregando}
          className="flex items-center gap-2 rounded-full border border-creme-linha bg-creme-claro px-4 py-2 text-sm font-semibold text-slate-700 hover:border-emerald-400 transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`h-4 w-4 ${carregando ? "animate-spin text-emerald-600" : ""}`} /> Atualizar Banco
        </button>
      </div>

      {erro && (
        <div role="alert" className="rounded-2xl border border-rose-200 bg-rose-50 p-4 text-xs text-rose-800">
          <strong>Aviso:</strong> {erro}
        </div>
      )}

      {/* Cartões de Métricas */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-3xl border border-creme-linha bg-creme-claro p-5 shadow-card">
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">Lotes Registrados</p>
          <p className="mt-1 font-display text-3xl font-semibold tabular-nums text-slate-900">{totalOperacoes}</p>
          <p className="mt-1 text-xs text-slate-500">simulados ou liquidados</p>
        </div>

        <div className="rounded-3xl border border-creme-linha bg-creme-claro p-5 shadow-card">
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">Lotes Liquidados</p>
          <div className="mt-1 flex items-baseline gap-2">
            <span className="font-display text-3xl font-semibold tabular-nums text-emerald-800">{liquidados.length}</span>
            <span className="text-xs font-semibold text-emerald-700 bg-emerald-100 px-2 py-0.5 rounded-full">
              {totalOperacoes > 0 ? `${Math.round((liquidados.length / totalOperacoes) * 100)}%` : "0%"}
            </span>
          </div>
          <p className="mt-1 text-xs text-slate-500">contratações efetivadas</p>
        </div>

        <div className="rounded-3xl border border-creme-linha bg-creme-claro p-5 shadow-card">
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">Volume Liquidado</p>
          <p className="mt-1 font-display text-3xl font-semibold tabular-nums text-emerald-900">
            {formatarMoedaCompacta(valorTotalLiquidado)}
          </p>
          <p className="mt-1 text-xs text-slate-500">crédito depositado aos cedentes</p>
        </div>

        <div className="rounded-3xl border border-creme-linha bg-creme-claro p-5 shadow-card">
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">Ganho Otimizador</p>
          <p className="mt-1 font-display text-3xl font-semibold tabular-nums text-emerald-800">
            +{formatarMoedaCompacta(ganhoTotalOtimizador)}
          </p>
          <p className="mt-1 text-xs text-slate-500">liberado via mochila 0/1</p>
        </div>
      </div>

      {/* Barra de Filtro e Busca */}
      <div className="flex flex-col sm:flex-row gap-3 items-center justify-between bg-white p-4 rounded-2xl border border-creme-linha shadow-sm">
        <div className="flex items-center gap-2 w-full sm:w-auto">
          <Filter className="h-4 w-4 text-slate-400" />
          <span className="text-xs font-semibold text-slate-500">Status:</span>
          {(["TODOS", "LIQUIDADO", "SIMULADO"] as const).map((st) => (
            <button
              key={st}
              type="button"
              onClick={() => setFiltroStatus(st)}
              className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors ${
                filtroStatus === st
                  ? "bg-floresta text-creme shadow-sm"
                  : "bg-creme-claro text-slate-600 hover:bg-creme"
              }`}
            >
              {st === "TODOS" ? "Todos" : st === "LIQUIDADO" ? "Liquidados" : "Simulados"}
            </button>
          ))}
        </div>

        <div className="relative w-full sm:w-72">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
          <input
            type="search"
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            placeholder="Filtrar cedente ou hash..."
            className="w-full rounded-xl border border-creme-linha bg-creme-claro pl-9 pr-3 py-1.5 text-xs text-slate-900 focus:outline-none focus:border-emerald-500"
          />
        </div>
      </div>

      {/* Tabela de Operações */}
      <div className="rounded-3xl border border-creme-linha bg-white shadow-card overflow-hidden">
        {carregando && operacoes.length === 0 ? (
          <div className="flex flex-col items-center justify-center p-12 text-slate-500">
            <Loader2 className="h-8 w-8 animate-spin text-emerald-600 mb-3" />
            <p className="text-sm">Consultando tabela lotes_operacoes do SQLite...</p>
          </div>
        ) : filtradas.length === 0 ? (
          <div className="p-12 text-center text-slate-500">
            <p className="font-semibold text-slate-700">Nenhuma operação encontrada.</p>
            <p className="text-xs text-slate-500 mt-1">
              Envie um lote para simular e clique em &quot;Confirmar e Liquidar Lote Aprovado&quot; no card verde.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-creme-claro/80 border-b border-creme-linha text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                <tr>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Data / Hora</th>
                  <th className="py-3 px-4">Cedente</th>
                  <th className="py-3 px-4 text-center">Notas (Aprov/Total)</th>
                  <th className="py-3 px-4 text-right">Valor Bruto</th>
                  <th className="py-3 px-4 text-right">Líquido Aprovado</th>
                  <th className="py-3 px-4 text-right">Ações</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-creme-linha font-sans">
                {filtradas.map((op) => {
                  const isLiquidado = op.status_operacao === "LIQUIDADO";
                  const isAtual = batchHashAtual === op.batch_hash;
                  const isProcessando = liquidandoHash === op.batch_hash;

                  return (
                    <tr
                      key={op.batch_hash}
                      className={`hover:bg-creme-claro/50 transition-colors ${
                        isAtual ? "bg-emerald-50/50" : ""
                      }`}
                    >
                      <td className="py-3.5 px-4 whitespace-nowrap">
                        {isLiquidado ? (
                          <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-semibold text-emerald-800">
                            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" /> Liquidado
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1.5 rounded-full bg-blue-50 px-2.5 py-1 text-xs font-semibold text-blue-700 border border-blue-200">
                            <Clock className="h-3.5 w-3.5" /> Simulado
                          </span>
                        )}
                      </td>

                      <td className="py-3.5 px-4 whitespace-nowrap text-xs text-slate-600 tabular-nums">
                        <div>{op.criado_em}</div>
                        {isLiquidado && op.liquidado_em && (
                          <div className="text-[10px] text-emerald-700 font-medium">
                            Liq: {op.liquidado_em.slice(11)}
                          </div>
                        )}
                      </td>

                      <td className="py-3.5 px-4">
                        <div className="font-semibold text-slate-900 truncate max-w-[200px]" title={op.cedente_nome}>
                          {op.cedente_nome}
                        </div>
                        <div className="font-mono text-[11px] text-slate-500">{op.cedente_doc}</div>
                      </td>

                      <td className="py-3.5 px-4 text-center whitespace-nowrap text-xs">
                        <span className="font-bold text-slate-900">{op.qtd_aprovadas}</span>
                        <span className="text-slate-400"> / {op.total_notas}</span>
                        {op.qtd_recusadas > 0 && (
                          <span className="block text-[10px] text-rose-600 font-medium">
                            {op.qtd_recusadas} recusadas
                          </span>
                        )}
                      </td>

                      <td className="py-3.5 px-4 text-right whitespace-nowrap text-xs font-medium text-slate-700 tabular-nums">
                        {formatarMoeda(op.valor_bruto_total)}
                      </td>

                      <td className="py-3.5 px-4 text-right whitespace-nowrap tabular-nums">
                        <div className="font-bold text-emerald-800 text-sm">
                          {formatarMoeda(op.valor_liquido_aprovado)}
                        </div>
                        {op.ganho_otimizador > 0 && (
                          <div className="text-[10px] text-emerald-600 font-medium">
                            +{formatarMoeda(op.ganho_otimizador)} otim.
                          </div>
                        )}
                      </td>

                      <td className="py-3.5 px-4 text-right whitespace-nowrap">
                        {isLiquidado ? (
                          <button
                            type="button"
                            onClick={() => {
                              if (onMostrarComprovante) {
                                onMostrarComprovante(
                                  {
                                    batch_hash: op.batch_hash,
                                    status: "LIQUIDADO",
                                    liquidado_em: op.liquidado_em || op.criado_em,
                                    qtd_titulos_comprados: op.qtd_aprovadas,
                                  },
                                  op
                                );
                              }
                            }}
                            className="inline-flex items-center gap-1.5 rounded-lg border border-emerald-300 bg-emerald-50 px-2.5 py-1.5 text-xs font-semibold text-emerald-800 hover:bg-emerald-100 transition-colors"
                          >
                            <FileCheck2 className="h-3.5 w-3.5 text-emerald-600" /> Comprovante
                          </button>
                        ) : (
                          <button
                            type="button"
                            disabled={isProcessando || op.qtd_aprovadas === 0}
                            onClick={() => handleLiquidar(op)}
                            className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-emerald-500 transition-colors disabled:opacity-50"
                          >
                            {isProcessando ? (
                              <>
                                <Loader2 className="h-3.5 w-3.5 animate-spin" /> Liquidando...
                              </>
                            ) : (
                              <>
                                <ShieldCheck className="h-3.5 w-3.5" /> Liquidar Agora
                              </>
                            )}
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
