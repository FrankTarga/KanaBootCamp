import { useState, useEffect, useCallback } from "react";
import { Navegacao, Marca } from "./components/Navegacao";
import { Hero } from "./components/Hero";
import { NumerosLote } from "./components/NumerosLote";
import { GraficosLote } from "./components/GraficosLote";
import { StatusApi } from "./components/StatusApi";
import { TabelaRecebiveis } from "./components/TabelaRecebiveis";
import { GavetaGestor } from "./components/GavetaGestor";
import { validarLote, salvarValidadores, simularLoteLocal } from "./services/api";
import type { BatchValidationResponse, ComparativoRegras, FonteDados, ValidadoresConfig } from "./types/api";

const rolarPara = (id: string) => document.getElementById(id)?.scrollIntoView({ block: "start" });

export default function App() {
  // Parâmetros da operação
  const [dataBase, setDataBase] = useState<string>("22/10/2026");
  const [taxaMensalPercentual, setTaxaMensalPercentual] = useState<number>(2.0);
  const [otimizarLote, setOtimizarLote] = useState<boolean>(true);

  // Dados e execução
  const [resultado, setResultado] = useState<BatchValidationResponse | null>(null);
  const [arquivoAtual, setArquivoAtual] = useState<File | null>(null);
  const [loteAtual, setLoteAtual] = useState<{ nome: string; qtdArquivos: number } | null>(null);
  const [fonteDados, setFonteDados] = useState<FonteDados>("demo");
  const [replayIdempotente, setReplayIdempotente] = useState<boolean>(false);
  const [carregando, setCarregando] = useState<boolean>(false);
  const [erroGeral, setErroGeral] = useState<string | null>(null);
  const [motivoFiltroAtivo, setMotivoFiltroAtivo] = useState<string | null>(null);

  // Gaveta do gestor e comparativo what-if
  const [drawerGestorAberto, setDrawerGestorAberto] = useState<boolean>(false);
  const [comparativoRegras, setComparativoRegras] = useState<ComparativoRegras | null>(null);

  // A tela nunca começa vazia: lote de demonstração local até a pessoa enviar o dela
  useEffect(() => {
    setResultado(simularLoteLocal({ dataBase: "22/10/2026", taxaMensal: 0.02, otimizarLote: true }));
    setFonteDados("demo");
  }, []);

  const processarLote = useCallback(
    async (arquivo: File | null, override?: ValidadoresConfig, isWhatIfSimulacao = false, rolar = false) => {
      setCarregando(true);
      setErroGeral(null);
      const valorLiquidoAnterior = resultado?.resumo.valor_liquido_receber ?? 0;
      const aprovadasAnteriores = resultado?.resumo.qtd_aprovadas ?? 0;
      const totalNotas = resultado?.resumo.total_notas ?? 0;
      try {
        const res = await validarLote(arquivo, {
          dataBase,
          taxaMensal: taxaMensalPercentual / 100,
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
        if (rolar) requestAnimationFrame(() => rolarPara("resultado"));
      } catch (err: unknown) {
        setErroGeral(err instanceof Error ? err.message : "Erro inesperado ao validar o lote.");
      } finally {
        setCarregando(false);
      }
    },
    [dataBase, taxaMensalPercentual, otimizarLote, resultado]
  );

  const handleLote = (arquivo: File, qtdArquivos: number) => {
    setArquivoAtual(arquivo);
    setLoteAtual({ nome: arquivo.name, qtdArquivos });
    setComparativoRegras(null);
    setMotivoFiltroAtivo(null);
    processarLote(arquivo, undefined, false, true);
  };

  const handleCarregarDemo = () => {
    setArquivoAtual(null);
    setLoteAtual(null);
    setComparativoRegras(null);
    setMotivoFiltroAtivo(null);
    processarLote(null, undefined, false, true);
  };

  const verNotas = (codigo: string | null) => {
    setMotivoFiltroAtivo(codigo);
    rolarPara("notas");
  };

  return (
    <div className="flex min-h-screen flex-col bg-creme font-sans">
      <a href="#resultado" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-creme focus:px-3 focus:py-2">
        Pular para o resultado
      </a>
      <Navegacao onCarregarDemo={handleCarregarDemo} onAbrirGestor={() => setDrawerGestorAberto(true)} carregando={carregando} />

      <main className="flex-1">
        <Hero
          onLote={handleLote}
          carregando={carregando}
          loteAtual={loteAtual}
          erro={erroGeral}
          onErro={setErroGeral}
          dataBase={dataBase}
          onDataBaseChange={setDataBase}
          taxaMensalPercentual={taxaMensalPercentual}
          onTaxaMensalChange={setTaxaMensalPercentual}
          otimizarLote={otimizarLote}
          onOtimizarLoteChange={setOtimizarLote}
        />

        {resultado && (
          <>
            <NumerosLote
              resumo={resultado.resumo}
              meta={resultado.meta}
              demo={!arquivoAtual}
              replayIdempotente={replayIdempotente}
              onVerFraudes={() => verNotas("FRAUDE_OUTRO_FUNDO")}
            />
            <GraficosLote resumo={resultado.resumo} itens={resultado.itens} onVerMotivo={verNotas} />

            <section id="notas" className="scroll-mt-24 bg-creme px-5 py-24 sm:py-28">
              <div className="mx-auto max-w-6xl space-y-8">
                <div className="text-center">
                  <p className="eyebrow text-emerald-700">Nota por nota</p>
                  <h2 className="titulo-secao mt-4 text-slate-900">Encontre qualquer nota</h2>
                  <p className="mx-auto mt-4 max-w-2xl text-slate-600">
                    Busque pelo número da nota ou pelo cliente. Clique numa nota recusada para ver o problema e o que fazer.
                  </p>
                </div>
                <StatusApi tempoProcessamentoMs={resultado.meta.tempo_processamento_ms} dataBase={resultado.meta.data_base_utilizada || dataBase} />
                <TabelaRecebiveis
                  itens={resultado.itens}
                  motivoFiltroAtivo={motivoFiltroAtivo}
                  onLimparMotivoFiltro={() => setMotivoFiltroAtivo(null)}
                />
              </div>
            </section>
          </>
        )}
      </main>

      <GavetaGestor
        aberto={drawerGestorAberto}
        onFechar={() => setDrawerGestorAberto(false)}
        onAplicarRegras={async (config) => { await salvarValidadores(config); await processarLote(arquivoAtual, config, false); }}
        onSimularWhatIf={(config) => processarLote(arquivoAtual, config, true)}
        carregando={carregando}
        comparativo={comparativoRegras}
      />

      <footer className="bg-floresta-escura px-5 py-10 text-creme/70">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 text-sm sm:flex-row">
          <Marca clara />
          <span>Hackathon Antecipe 2026 · análise de recebíveis para o ANTECIPE FIDC</span>
          <span className="rounded-full border border-creme/20 px-3 py-1 text-xs">
            {fonteDados === "api" ? "Dados do motor real" : "Modo demonstração"}
          </span>
        </div>
      </footer>
    </div>
  );
}
