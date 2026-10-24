import { useState, useEffect, useCallback } from "react";
import { MenuLateral, type Tela } from "./components/MenuLateral";
import { TelaEnvio } from "./components/telas/TelaEnvio";
import { TelaResumo, Cabecalho } from "./components/telas/TelaResumo";
import { TelaEstatistica } from "./components/telas/TelaEstatistica";
import { StatusApi } from "./components/StatusApi";
import { TabelaRecebiveis } from "./components/TabelaRecebiveis";
import { GavetaGestor } from "./components/GavetaGestor";
import { LoginScreen, type Persona } from "./components/LoginScreen";
import { validarLote, salvarValidadores, simularLoteLocal, obterHealth } from "./services/api";
import { formatarMoedaCompacta } from "./utils/formatters";
import type { BatchValidationResponse, ComparativoRegras, FonteDados, ModoValidacao, ValidadoresConfig } from "./types/api";

const TELAS: Tela[] = ["envio", "resumo", "estatistica", "notas"];
const telaDoEndereco = (): Tela => {
  const h = window.location.hash.slice(1) as Tela;
  return TELAS.includes(h) ? h : "envio";
};

const personaSalva = (): Persona | null => {
  try {
    return JSON.parse(localStorage.getItem("antecipe_persona") ?? "null");
  } catch {
    return null;
  }
};

export default function App() {
  // Perfil da demonstração (cedente ou gestor); sobrevive ao F5
  const [persona, setPersonaEstado] = useState<Persona | null>(personaSalva);
  const setPersona = (p: Persona | null) => {
    try {
      if (p) localStorage.setItem("antecipe_persona", JSON.stringify(p));
      else localStorage.removeItem("antecipe_persona");
    } catch { /* navegador sem storage: só não lembra o perfil */ }
    setPersonaEstado(p);
  };

  // Parâmetros da operação
  const [dataBase, setDataBase] = useState<string>("22/10/2026");
  const [taxaMensalPercentual, setTaxaMensalPercentual] = useState<number>(2.0);
  const [taxaAlteradaManualmente, setTaxaAlteradaManualmente] = useState<boolean>(false);
  const [otimizarLote, setOtimizarLote] = useState<boolean>(true);
  const [modo, setModo] = useState<ModoValidacao>("lote");

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

  // Tela atual vive no endereço (#resumo...), então voltar do navegador e links funcionam
  const [tela, setTelaEstado] = useState<Tela>(telaDoEndereco);
  useEffect(() => {
    const aoMudar = () => setTelaEstado(telaDoEndereco());
    window.addEventListener("hashchange", aoMudar);
    return () => window.removeEventListener("hashchange", aoMudar);
  }, []);
  const irPara = (t: Tela) => {
    if (window.location.hash.slice(1) !== t) window.location.hash = t;
    setTelaEstado(t);
    window.scrollTo({ top: 0 });
  };

  // A tela nunca começa vazia: lote de demonstração local até a pessoa enviar o dela
  useEffect(() => {
    setResultado(simularLoteLocal({ dataBase: "22/10/2026", taxaMensal: 0.02, otimizarLote: true }));
    setFonteDados("demo");
    obterHealth()
      .then((res) => {
        if (res.dados.taxa_mensal_padrao !== undefined) {
          setTaxaMensalPercentual(Number((res.dados.taxa_mensal_padrao * 100).toFixed(4)));
        }
        if (res.dados.data_base_padrao) {
          setDataBase(res.dados.data_base_padrao);
        }
      })
      .catch(() => {});
  }, []);

  const processarLote = useCallback(
    async (arquivo: File | null, override?: ValidadoresConfig, isWhatIfSimulacao = false, depois?: Tela) => {
      setCarregando(true);
      setErroGeral(null);
      const valorLiquidoAnterior = resultado?.resumo.valor_liquido_receber ?? 0;
      const aprovadasAnteriores = resultado?.resumo.qtd_aprovadas ?? 0;
      const totalNotas = resultado?.resumo.total_notas ?? 0;
      try {
        const res = await validarLote(arquivo, {
          dataBase,
          taxaMensal: taxaAlteradaManualmente ? taxaMensalPercentual / 100 : undefined,
          otimizarLote,
          validadoresOverride: override,
          modo,
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
        if (depois) irPara(depois);
      } catch (err: unknown) {
        setErroGeral(err instanceof Error ? err.message : "Erro inesperado ao validar o lote.");
      } finally {
        setCarregando(false);
      }
    },
    [dataBase, taxaMensalPercentual, taxaAlteradaManualmente, otimizarLote, modo, resultado]
  );

  const handleLote = (arquivo: File, qtdArquivos: number) => {
    setArquivoAtual(arquivo);
    setLoteAtual({ nome: arquivo.name, qtdArquivos });
    setComparativoRegras(null);
    setMotivoFiltroAtivo(null);
    processarLote(arquivo, undefined, false, "resumo");
  };

  const handleCarregarDemo = () => {
    setArquivoAtual(null);
    setLoteAtual(null);
    setComparativoRegras(null);
    setMotivoFiltroAtivo(null);
    processarLote(null, undefined, false, "resumo");
  };

  const verNotas = (codigo: string | null) => {
    setMotivoFiltroAtivo(codigo);
    irPara("notas");
  };

  const demo = fonteDados === "demo";
  const motorDesligado = !!arquivoAtual && demo; // enviou arquivo, mas a API não respondeu: números do lote de demonstração

  if (!persona) {
    return <LoginScreen onLogin={(p) => { setPersona(p); setDrawerGestorAberto(p.role === "GESTOR"); }} />;
  }
  const gestor = persona.role === "GESTOR";

  return (
    <div className="min-h-screen bg-creme font-sans">
      <MenuLateral
        tela={tela}
        onTela={irPara}
        onAbrirGestor={gestor ? () => setDrawerGestorAberto(true) : undefined}
        persona={persona}
        onSair={() => { setPersona(null); setDrawerGestorAberto(false); }}
        onCarregarDemo={handleCarregarDemo}
        carregando={carregando}
        temResultado={!!resultado}
        liquidoCompacto={resultado ? formatarMoedaCompacta(resultado.resumo.valor_liquido_receber) : null}
        qtdRecusadas={resultado?.resumo.qtd_recusadas ?? 0}
        fonte={fonteDados}
        nomeLote={loteAtual?.nome ?? null}
      />

      <main className="lg:pl-72">
        {tela === "envio" && (
          <TelaEnvio
            onLote={handleLote}
            onVerResumo={() => irPara("resumo")}
            carregando={carregando}
            loteAtual={loteAtual}
            motorDesligado={motorDesligado}
            erro={erroGeral}
            onErro={setErroGeral}
            modo={modo}
            onModo={setModo}
            dataBase={dataBase}
            onDataBaseChange={setDataBase}
            taxaMensalPercentual={taxaMensalPercentual}
            onTaxaMensalChange={(v) => {
              setTaxaMensalPercentual(v);
              setTaxaAlteradaManualmente(true);
            }}
            otimizarLote={otimizarLote}
            onOtimizarLoteChange={setOtimizarLote}
          />
        )}

        {resultado && tela === "resumo" && (
          <TelaResumo
            resumo={resultado.resumo}
            meta={resultado.meta}
            demo={demo}
            motorDesligado={motorDesligado}
            nomeLote={loteAtual?.nome ?? null}
            replayIdempotente={replayIdempotente}
            onIr={(destino, motivo) => (destino === "notas" ? verNotas(motivo ?? null) : irPara(destino))}
          />
        )}

        {resultado && tela === "estatistica" && (
          <TelaEstatistica resumo={resultado.resumo} itens={resultado.itens} analise={resultado.analise_recusas} onVerNotas={verNotas} />
        )}

        {resultado && tela === "notas" && (
          <div className="mx-auto flex max-w-6xl flex-col gap-6 px-5 py-10 sm:px-8 lg:py-14">
            <Cabecalho titulo="Nota por nota" sub="Busque pelo número da nota ou pelo cliente. Clique numa nota recusada para ver o problema e o que fazer." />
            <StatusApi tempoProcessamentoMs={resultado.meta.tempo_processamento_ms} dataBase={resultado.meta.data_base_utilizada || dataBase} />
            <TabelaRecebiveis itens={resultado.itens} motivoFiltroAtivo={motivoFiltroAtivo} onLimparMotivoFiltro={() => setMotivoFiltroAtivo(null)} />
          </div>
        )}
      </main>

      <GavetaGestor
        aberto={gestor && drawerGestorAberto}
        onFechar={() => setDrawerGestorAberto(false)}
        onAplicarRegras={async (config) => { await salvarValidadores(config); await processarLote(arquivoAtual, config, false); }}
        onSimularWhatIf={(config) => processarLote(arquivoAtual, config, true)}
        carregando={carregando}
        comparativo={comparativoRegras}
      />
    </div>
  );
}
