import { useState, useEffect, useCallback } from "react";
import { AlertOctagon } from "lucide-react";
import { Header } from "./components/Header";
import { StatusApi } from "./components/StatusApi";
import { CheckoutLiquidez } from "./components/CheckoutLiquidez";
import { RaioXRecusas } from "./components/RaioXRecusas";
import { TabelaRecebiveis } from "./components/TabelaRecebiveis";
import { GavetaGestor } from "./components/GavetaGestor";
import {
  validarLote,
  salvarValidadores,
  simularLoteLocal,
} from "./services/api";
import type {
  BatchValidationResponse,
  ComparativoRegras,
  FonteDados,
  ValidadoresConfig,
} from "./types/api";

export default function App() {
  // Parâmetros da Operação
  const [dataBase, setDataBase] = useState<string>("22/10/2026");
  const [taxaMensalPercentual, setTaxaMensalPercentual] = useState<number>(2.0);
  const [otimizarLote, setOtimizarLote] = useState<boolean>(true);

  // Estados de dados e execução
  const [resultado, setResultado] = useState<BatchValidationResponse | null>(null);
  const [arquivoAtual, setArquivoAtual] = useState<File | null>(null);
  const [fonteDados, setFonteDados] = useState<FonteDados>("demo");
  const [replayIdempotente, setReplayIdempotente] = useState<boolean>(false);
  const [carregando, setCarregando] = useState<boolean>(false);
  const [erroGeral, setErroGeral] = useState<string | null>(null);

  // Filtro ativo do Raio-X
  const [motivoFiltroAtivo, setMotivoFiltroAtivo] = useState<string | null>(null);

  // Drawer do Gestor e Comparativo What-If
  const [drawerGestorAberto, setDrawerGestorAberto] = useState<boolean>(false);
  const [comparativoRegras, setComparativoRegras] = useState<ComparativoRegras | null>(null);

  // Carrega simulação inicial para a tela nunca começar vazia
  useEffect(() => {
    const mockInicial = simularLoteLocal({
      dataBase: "22/10/2026",
      taxaMensal: 0.02,
      otimizarLote: true,
    });
    setResultado(mockInicial);
    setFonteDados("demo");
  }, []);

  // Executa validação de lote
  const processarLote = useCallback(
    async (
      arquivo: File | null,
      override?: ValidadoresConfig,
      isWhatIfSimulacao = false
    ) => {
      setCarregando(true);
      setErroGeral(null);

      const valorLiquidoAnterior = resultado?.resumo.valor_liquido_receber ?? 0;
      const aprovadasAnteriores = resultado?.resumo.qtd_aprovadas ?? 0;
      const totalNotas = resultado?.resumo.total_notas ?? 0;

      try {
        const taxaFracao = taxaMensalPercentual / 100;
        const res = await validarLote(arquivo, {
          dataBase,
          taxaMensal: taxaFracao,
          otimizarLote,
          validadoresOverride: override,
        });

        setResultado(res.dados);
        setFonteDados(res.fonte);
        setReplayIdempotente(res.replayIdempotente);

        if (override) {
          setComparativoRegras({
            tipo: isWhatIfSimulacao ? "simulado" : "aplicado",
            liquidoAntes: valorLiquidoAnterior,
            liquidoDepois: res.dados.resumo.valor_liquido_receber,
            aprovadasAntes: aprovadasAnteriores,
            aprovadasDepois: res.dados.resumo.qtd_aprovadas,
            totalNotas: totalNotas || res.dados.resumo.total_notas,
          });
        }
      } catch (err: unknown) {
        setErroGeral(err instanceof Error ? err.message : "Erro inesperado ao validar o lote.");
      } finally {
        setCarregando(false);
      }
    },
    [dataBase, taxaMensalPercentual, otimizarLote, resultado]
  );

  // Handlers
  const handleUploadArquivo = (arquivo: File) => {
    setArquivoAtual(arquivo);
    setComparativoRegras(null);
    setMotivoFiltroAtivo(null);
    processarLote(arquivo);
  };

  const handleCarregarDemo = () => {
    setArquivoAtual(null);
    setComparativoRegras(null);
    setMotivoFiltroAtivo(null);
    processarLote(null);
  };

  const handleAplicarRegrasGestor = async (config: ValidadoresConfig) => {
    await salvarValidadores(config);
    await processarLote(arquivoAtual, config, false);
  };

  const handleSimularWhatIfGestor = async (config: ValidadoresConfig) => {
    await processarLote(arquivoAtual, config, true);
  };

  // Revalida quando os parâmetros globais da barra mudam
  const handleDataBaseChange = (novaData: string) => {
    setDataBase(novaData);
  };

  const handleTaxaMensalChange = (novaTaxa: number) => {
    setTaxaMensalPercentual(novaTaxa);
  };

  const handleOtimizarLoteChange = (otimizar: boolean) => {
    setOtimizarLote(otimizar);
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col font-sans">
      {/* Header Executivo & Controles da Operação */}
      <Header
        dataBase={dataBase}
        onDataBaseChange={handleDataBaseChange}
        taxaMensalPercentual={taxaMensalPercentual}
        onTaxaMensalChange={handleTaxaMensalChange}
        otimizarLote={otimizarLote}
        onOtimizarLoteChange={handleOtimizarLoteChange}
        onCarregarDemo={handleCarregarDemo}
        onAbrirGestor={() => setDrawerGestorAberto(true)}
        carregando={carregando}
      />

      {/* Alerta de Fraude Crítica no Topo se houver */}
      {resultado && resultado.resumo.qtd_alertas_fraude > 0 && (
        <div className="bg-rose-600 text-white px-4 py-2.5 shadow-md">
          <div className="mx-auto max-w-7xl flex items-center justify-between gap-3 text-xs sm:text-sm font-semibold">
            <div className="flex items-center gap-2">
              <span className="relative flex h-3 w-3">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-white opacity-75" />
                <span className="relative inline-flex rounded-full h-3 w-3 bg-white" />
              </span>
              <AlertOctagon className="h-5 w-5 shrink-0" />
              <span>
                ALERTA CRÍTICO DE RISCO: {resultado.resumo.qtd_alertas_fraude} título(s) deste lote já
                constam na carteira de outros fundos do mercado (Triplo Radar Anti-Fraude)!
              </span>
            </div>
            <button
              type="button"
              onClick={() => setMotivoFiltroAtivo("FRAUDE_OUTRO_FUNDO")}
              className="text-xs bg-white text-rose-700 px-3 py-1 rounded-md font-bold hover:bg-rose-50 transition-colors whitespace-nowrap"
            >
              Ver Títulos com Suspeita
            </button>
          </div>
        </div>
      )}

      {/* Conteúdo Principal */}
      <main className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-6 space-y-6 flex-1 w-full">
        {/* Barra de Status e Telemetria do Motor */}
        <StatusApi
          tempoProcessamentoMs={resultado?.meta.tempo_processamento_ms}
          dataBase={resultado?.meta.data_base_utilizada || dataBase}
        />

        {/* Erro Geral se houver */}
        {erroGeral && (
          <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center justify-between">
            <span>{erroGeral}</span>
            <button
              type="button"
              onClick={() => setErroGeral(null)}
              className="text-rose-900 font-bold ml-2"
            >
              ✕
            </button>
          </div>
        )}

        {/* Zona de Upload & Checkout de Liquidez */}
        <CheckoutLiquidez
          resumo={resultado?.resumo ?? null}
          meta={resultado?.meta ?? null}
          carregando={carregando}
          arquivoSelecionado={arquivoAtual}
          onArquivoUpload={handleUploadArquivo}
          replayIdempotente={replayIdempotente}
        />

        {/* Raio-X das Recusas & Motivos de Inelegibilidade */}
        {resultado && resultado.resumo.contagem_por_motivo.length > 0 && (
          <RaioXRecusas
            motivos={resultado.resumo.contagem_por_motivo}
            motivoSelecionado={motivoFiltroAtivo}
            onSelecionarMotivo={setMotivoFiltroAtivo}
          />
        )}

        {/* Tabela Inteligente de Recebíveis com Expansor Explicativo */}
        {resultado && (
          <TabelaRecebiveis
            itens={resultado.itens}
            motivoFiltroAtivo={motivoFiltroAtivo}
            onLimparMotivoFiltro={() => setMotivoFiltroAtivo(null)}
          />
        )}
      </main>

      {/* Gaveta Lateral (Drawer) do Gestor com Motor Zero-Deploy */}
      <GavetaGestor
        aberto={drawerGestorAberto}
        onFechar={() => setDrawerGestorAberto(false)}
        onAplicarRegras={handleAplicarRegrasGestor}
        onSimularWhatIf={handleSimularWhatIfGestor}
        carregando={carregando}
        comparativo={comparativoRegras}
      />

      {/* Rodapé Institucional */}
      <footer className="border-t border-slate-200 bg-white py-4 text-center text-xs text-slate-500">
        <div className="mx-auto max-w-7xl px-4 flex flex-col sm:flex-row items-center justify-between gap-2">
          <span>ANTECIPE PRO · Hackathon Antecipe 2026</span>
          <span className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full bg-slate-100 text-slate-600">
              Fonte: {fonteDados === "api" ? "Motor Real (FastAPI)" : "Modo Contingência (Demo)"}
            </span>
            <span>Arquitetura de Sistemas Financeiros para FIDCs · Zero-Deploy Engine</span>
          </span>
        </div>
      </footer>
    </div>
  );
}
