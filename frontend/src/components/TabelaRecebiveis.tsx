import { useState, useMemo } from "react";
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
}

export function TabelaRecebiveis({
  itens,
  motivoFiltroAtivo,
  onLimparMotivoFiltro,
}: TabelaRecebiveisProps) {
  const [abaAtiva, setAbaAtiva] = useState<AbaFiltro>("TODAS");
  const [busca, setBusca] = useState("");
  const [linhasExpandidas, setLinhasExpandidas] = useState<Set<number>>(new Set());

  // Contadores para as abas
  const contadores = useMemo(() => {
    return {
      todas: itens.length,
      aprovadas: itens.filter((i) => i.status === "APROVADA").length,
      recusadas: itens.filter((i) => i.status === "RECUSADA").length,
      salvas: itens.filter((i) => i.salva_pelo_otimizador).length,
      fraude: itens.filter((i) => i.severidade === "FRAUDE").length,
    };
  }, [itens]);

  // Filtragem combinada: Aba + Busca + Motivo do Raio-X
  const itensFiltrados = useMemo(() => {
    return itens.filter((item) => {
      // Filtro de aba
      if (abaAtiva === "APROVADAS" && item.status !== "APROVADA") return false;
      if (abaAtiva === "RECUSADAS" && item.status !== "RECUSADA") return false;
      if (abaAtiva === "SALVAS" && !item.salva_pelo_otimizador) return false;
      if (abaAtiva === "FRAUDE" && item.severidade !== "FRAUDE") return false;

      // Filtro por motivo selecionado no Raio-X
      if (motivoFiltroAtivo) {
        const possuiMotivo = item.erros.some((e) => e.codigo === motivoFiltroAtivo);
        if (!possuiMotivo) return false;
      }

      // Filtro de busca textual
      if (busca.trim()) {
        const termo = busca.toLowerCase();
        const coincideDoc = item.nu_documento.toLowerCase().includes(termo);
        const coincideSacado =
          item.nome_sacado.toLowerCase().includes(termo) ||
          item.doc_sacado.includes(termo);
        const coincideCedente =
          item.nome_cedente.toLowerCase().includes(termo) ||
          item.doc_cedente.includes(termo);
        const coincideTipo = item.tipo_recebivel.toLowerCase().includes(termo);

        if (!coincideDoc && !coincideSacado && !coincideCedente && !coincideTipo) {
          return false;
        }
      }

      return true;
    });
  }, [itens, abaAtiva, busca, motivoFiltroAtivo]);

  const toggleLinha = (linhaCsv: number) => {
    setLinhasExpandidas((prev) => {
      const proximo = new Set(prev);
      if (proximo.has(linhaCsv)) {
        proximo.delete(linhaCsv);
      } else {
        proximo.add(linhaCsv);
      }
      return proximo;
    });
  };

  const handleExportarAprovadas = () => {
    const csv = gerarCsvNotasAprovadas(itens);
    dispararDownloadBlob(csv, "lote_notas_aprovadas_antecipe.csv");
  };

  const handleExportarPendencias = () => {
    const csv = gerarCsvRelatorioPendencias(itens);
    dispararDownloadBlob(csv, "relatorio_pendencias_antecipe.csv");
  };

  return (
    <div className="card overflow-hidden">
      {/* Barra de Ferramentas Superior */}
      <div className="border-b border-slate-200 bg-white p-4 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          {/* Abas de Navegação */}
          <div className="flex flex-wrap items-center gap-1.5 p-1 bg-slate-100/80 rounded-xl text-xs font-semibold text-slate-600">
            <button
              type="button"
              onClick={() => setAbaAtiva("TODAS")}
              className={`px-3 py-1.5 rounded-lg transition-all ${
                abaAtiva === "TODAS"
                  ? "bg-white text-slate-900 shadow-2xs font-bold"
                  : "hover:text-slate-900"
              }`}
            >
              Todas ({contadores.todas})
            </button>
            <button
              type="button"
              onClick={() => setAbaAtiva("APROVADAS")}
              className={`px-3 py-1.5 rounded-lg transition-all ${
                abaAtiva === "APROVADAS"
                  ? "bg-white text-emerald-800 shadow-2xs font-bold"
                  : "hover:text-emerald-700"
              }`}
            >
              Aprovadas ({contadores.aprovadas})
            </button>
            <button
              type="button"
              onClick={() => setAbaAtiva("RECUSADAS")}
              className={`px-3 py-1.5 rounded-lg transition-all ${
                abaAtiva === "RECUSADAS"
                  ? "bg-white text-rose-700 shadow-2xs font-bold"
                  : "hover:text-rose-600"
              }`}
            >
              Recusadas ({contadores.recusadas})
            </button>
            <button
              type="button"
              onClick={() => setAbaAtiva("SALVAS")}
              className={`px-3 py-1.5 rounded-lg transition-all ${
                abaAtiva === "SALVAS"
                  ? "bg-white text-teal-800 shadow-2xs font-bold"
                  : "hover:text-teal-700"
              }`}
            >
              Salvas pelo Otimizador ({contadores.salvas})
            </button>
            {contadores.fraude > 0 && (
              <button
                type="button"
                onClick={() => setAbaAtiva("FRAUDE")}
                className={`px-3 py-1.5 rounded-lg transition-all ${
                  abaAtiva === "FRAUDE"
                    ? "bg-rose-600 text-white shadow-2xs font-bold"
                    : "text-rose-600 hover:bg-rose-50"
                }`}
              >
                Alertas de Fraude ({contadores.fraude})
              </button>
            )}
          </div>

          {/* Botões de Exportação CSV */}
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleExportarAprovadas}
              disabled={contadores.aprovadas === 0}
              className="btn btn-secondary text-xs py-1.5 px-3"
              title="Baixa um CSV formatado apenas com as notas aprovadas"
            >
              <Download className="h-3.5 w-3.5 text-emerald-600" />
              <span>Baixar Aprovadas</span>
            </button>

            <button
              type="button"
              onClick={handleExportarPendencias}
              disabled={contadores.recusadas === 0}
              className="btn btn-secondary text-xs py-1.5 px-3"
              title="Baixa relatório com as explicações humanas e acionáveis das recusas"
            >
              <Download className="h-3.5 w-3.5 text-amber-600" />
              <span>Relatório de Recusas</span>
            </button>
          </div>
        </div>

        {/* Linha de Busca e Filtro Ativo */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
            <input
              type="text"
              placeholder="Buscar por Nº Doc, Sacado, CNPJ ou tipo..."
              value={busca}
              onChange={(e) => setBusca(e.target.value)}
              className="w-full pl-9 pr-4 py-1.5 text-xs rounded-lg border border-slate-200 outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/10 placeholder:text-slate-400"
            />
          </div>

          {motivoFiltroAtivo && (
            <div className="flex items-center gap-2 text-xs bg-emerald-50 border border-emerald-200 text-emerald-900 px-3 py-1.5 rounded-lg">
              <span>
                Filtrando pelo motivo: <strong>{motivoFiltroAtivo}</strong>
              </span>
              <button
                type="button"
                onClick={onLimparMotivoFiltro}
                className="text-emerald-700 hover:text-emerald-950 font-bold ml-1 text-sm leading-none"
              >
                ×
              </button>
            </div>
          )}

          <div className="text-xs text-slate-500 self-center">
            Exibindo <strong>{itensFiltrados.length}</strong> de {itens.length} títulos
          </div>
        </div>
      </div>

      {/* Tabela de Recebíveis */}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs border-collapse">
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50/80 text-slate-500 uppercase tracking-wider font-semibold text-[11px]">
              <th className="py-3 px-4 w-10"></th>
              <th className="py-3 px-3">Nº Doc</th>
              <th className="py-3 px-3">Sacado (Cliente Devedor)</th>
              <th className="py-3 px-3">Tipo</th>
              <th className="py-3 px-3">Vencimento</th>
              <th className="py-3 px-3 text-right">Valor Nominal</th>
              <th className="py-3 px-3 text-right">Deságio</th>
              <th className="py-3 px-3 text-right font-bold text-slate-800">Valor Líquido</th>
              <th className="py-3 px-4">Status / Diagnóstico</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {itensFiltrados.length === 0 ? (
              <tr>
                <td colSpan={9} className="py-12 text-center text-slate-400">
                  Nenhum título encontrado com os filtros aplicados.
                </td>
              </tr>
            ) : (
              itensFiltrados.map((item) => {
                const isExpandida = linhasExpandidas.has(item.linha_csv);
                const isAprovada = item.status === "APROVADA";
                const isFraude = item.severidade === "FRAUDE";
                const isDuplicidade = item.severidade === "DUPLICIDADE";

                return (
                  <tr
                    key={item.hash_titulo + "_" + item.linha_csv}
                    onClick={() => toggleLinha(item.linha_csv)}
                    className={`cursor-pointer transition-colors group ${
                      isExpandida
                        ? "bg-slate-50/80"
                        : isFraude
                        ? "bg-rose-50/30 hover:bg-rose-50/50"
                        : isAprovada
                        ? "hover:bg-slate-50/60"
                        : "hover:bg-amber-50/30"
                    }`}
                  >
                    {/* Botão Expansor */}
                    <td className="py-3 px-4 text-center">
                      {isExpandida ? (
                        <ChevronDown className="h-4 w-4 text-slate-400 group-hover:text-slate-600 inline" />
                      ) : (
                        <ChevronRight className="h-4 w-4 text-slate-400 group-hover:text-slate-600 inline" />
                      )}
                    </td>

                    {/* Nº Documento */}
                    <td className="py-3 px-3 font-mono font-medium text-slate-900 whitespace-nowrap">
                      {item.nu_documento}
                      <span className="block text-[10px] text-slate-400 font-sans">
                        Linha {item.linha_csv}
                      </span>
                    </td>

                    {/* Sacado */}
                    <td className="py-3 px-3 max-w-xs">
                      <div className="font-semibold text-slate-900 truncate" title={item.nome_sacado}>
                        {item.nome_sacado || "Sacado não informado"}
                      </div>
                      <div className="text-[11px] text-slate-500 font-mono">
                        {formatarDocumento(item.doc_sacado)}
                      </div>
                    </td>

                    {/* Tipo Recebível */}
                    <td className="py-3 px-3 whitespace-nowrap">
                      <span className="text-slate-600 bg-slate-100 px-2 py-0.5 rounded text-[11px]">
                        {item.tipo_recebivel}
                      </span>
                    </td>

                    {/* Vencimento e Prazo */}
                    <td className="py-3 px-3 whitespace-nowrap">
                      <div className="text-slate-800 font-medium">{item.data_vencimento}</div>
                      <div className="text-[11px] text-slate-400">
                        {item.prazo_dias >= 0 ? `${item.prazo_dias} dias` : `${Math.abs(item.prazo_dias)} dias atrás`}
                      </div>
                    </td>

                    {/* Valor Nominal */}
                    <td className="py-3 px-3 text-right font-medium text-slate-700 money whitespace-nowrap">
                      {formatarMoeda(item.valor_nominal)}
                    </td>

                    {/* Deságio */}
                    <td className="py-3 px-3 text-right text-slate-500 money whitespace-nowrap">
                      {isAprovada ? `- ${formatarMoeda(item.desagio_reais)}` : "-"}
                    </td>

                    {/* Valor Líquido */}
                    <td className="py-3 px-3 text-right font-bold money whitespace-nowrap">
                      {isAprovada ? (
                        <span className="text-emerald-700 text-sm">
                          {formatarMoeda(item.valor_liquido)}
                        </span>
                      ) : (
                        <span className="text-slate-400">-</span>
                      )}
                    </td>

                    {/* Status & Diagnóstico */}
                    <td className="py-3 px-4">
                      <div className="flex flex-wrap items-center gap-1.5">
                        {isAprovada ? (
                          <span className="inline-flex items-center gap-1 text-emerald-800 bg-emerald-100/80 px-2.5 py-0.5 rounded-full font-semibold text-[11px]">
                            <CheckCircle2 className="h-3 w-3 text-emerald-600" />
                            Aprovada
                          </span>
                        ) : isFraude ? (
                          <span className="inline-flex items-center gap-1 text-rose-800 bg-rose-100 px-2.5 py-0.5 rounded-full font-semibold text-[11px] border border-rose-200">
                            <AlertOctagon className="h-3 w-3 text-rose-600" />
                            Dupla Cessão (Fraude)
                          </span>
                        ) : isDuplicidade ? (
                          <span className="inline-flex items-center gap-1 text-purple-800 bg-purple-100 px-2.5 py-0.5 rounded-full font-semibold text-[11px] border border-purple-200">
                            <AlertTriangle className="h-3 w-3 text-purple-600" />
                            Duplicidade
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-amber-800 bg-amber-100 px-2.5 py-0.5 rounded-full font-semibold text-[11px]">
                            <XCircle className="h-3 w-3 text-amber-600" />
                            Recusada
                          </span>
                        )}

                        {item.salva_pelo_otimizador && (
                          <span className="inline-flex items-center gap-1 text-teal-800 bg-teal-100 px-2 py-0.5 rounded-full font-semibold text-[10px] border border-teal-300">
                            <Sparkles className="h-2.5 w-2.5 text-teal-600" />
                            Salva pelo Otimizador
                          </span>
                        )}

                        {!isAprovada && item.erros.length > 0 && (
                          <span className="text-[11px] text-slate-500 font-medium">
                            {item.erros[0].titulo_amigavel}
                            {item.erros.length > 1 && (
                              <span className="ml-1 text-amber-700 font-bold">
                                (+{item.erros.length - 1})
                              </span>
                            )}
                          </span>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Painéis Expandidos com Explicação Humana e Acionável */}
      {itensFiltrados.map((item) => {
        if (!linhasExpandidas.has(item.linha_csv)) return null;

        const isAprovada = item.status === "APROVADA";

        return (
          <div
            key={"expandido_" + item.linha_csv}
            className="border-t border-slate-200 bg-slate-50/90 p-5 space-y-4"
          >
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200/60 pb-3">
              <div className="flex items-center gap-2">
                <span className="font-bold text-slate-800">
                  Raio-X do Título {item.nu_documento}
                </span>
                <span className="text-slate-400">·</span>
                <span className="text-slate-600">{item.nome_sacado}</span>
                <span className="text-slate-400 font-mono text-[11px]">
                  ({formatarDocumento(item.doc_sacado)})
                </span>
              </div>

              <div className="text-[11px] font-mono text-slate-400">
                Hash: {item.hash_titulo.substring(0, 16)}...
              </div>
            </div>

            {isAprovada ? (
              <div className="rounded-xl border border-emerald-200 bg-emerald-50/50 p-4 text-emerald-950 flex items-start gap-3">
                <CheckCircle2 className="h-5 w-5 text-emerald-600 shrink-0 mt-0.5" />
                <div className="space-y-1">
                  <p className="font-semibold text-xs">
                    Título elegível para antecipação imediata!
                  </p>
                  <p className="text-xs text-emerald-800 leading-relaxed">
                    Esta nota passou com sucesso em todos os validadores de risco do ANTECIPE FIDC.
                    O valor nominal de {formatarMoeda(item.valor_nominal)} terá deságio de{" "}
                    {formatarMoeda(item.desagio_reais)} proporcional a {item.prazo_dias} dias até o
                    vencimento ({item.data_vencimento}).
                  </p>
                  {item.salva_pelo_otimizador && (
                    <p className="text-xs text-teal-800 font-medium pt-1">
                      💡 Esta nota teria estourado o limite de crédito na ordem original do arquivo,
                      mas foi estrategicamente priorizada pelo Smart Batch Optimizer!
                    </p>
                  )}
                </div>
              </div>
            ) : (
              <div className="space-y-3">
                <p className="text-xs font-semibold text-slate-700">
                  Por que esta nota foi recusada ({item.erros.length}{" "}
                  {item.erros.length === 1 ? "motivo detectado" : "motivos detectados"}):
                </p>

                {item.erros.map((erro, idx) => (
                  <div
                    key={erro.codigo + "_" + idx}
                    className="rounded-xl border border-slate-200 bg-white p-4 space-y-3 shadow-2xs"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="h-2 w-2 rounded-full bg-amber-500" />
                        <h4 className="text-xs font-bold text-slate-800">
                          {erro.titulo_amigavel}
                        </h4>
                      </div>
                      <span className="text-[10px] font-mono text-slate-400 bg-slate-100 px-2 py-0.5 rounded">
                        {erro.codigo}
                      </span>
                    </div>

                    {/* O que aconteceu */}
                    <div className="space-y-1">
                      <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                        O que aconteceu:
                      </span>
                      <p className="text-xs text-slate-700 leading-relaxed">
                        {erro.mensagem_empresa}
                      </p>
                    </div>

                    {/* Como resolver (Ação Recomendada) */}
                    <div className="rounded-lg bg-emerald-50/60 border border-emerald-200/60 p-3 flex items-start gap-2.5">
                      <Lightbulb className="h-4 w-4 text-emerald-700 shrink-0 mt-0.5" />
                      <div>
                        <span className="text-[11px] font-bold text-emerald-900 block mb-0.5">
                          Como resolver:
                        </span>
                        <p className="text-xs text-emerald-800 leading-relaxed">
                          {erro.acao_recomendada}
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
