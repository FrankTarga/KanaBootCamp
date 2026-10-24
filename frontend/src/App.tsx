import { useState, useEffect, useCallback, useRef } from "react";
import { MenuLateral, type Tela } from "./components/MenuLateral";
import { PaginaInicial } from "./components/PaginaInicial";
import { TelaEnvio } from "./components/telas/TelaEnvio";
import { TelaResumo, Cabecalho } from "./components/telas/TelaResumo";
import { TelaEstatistica } from "./components/telas/TelaEstatistica";
import { TelaHistorico } from "./components/telas/TelaHistorico";
import { TelaPerda } from "./components/telas/TelaPerda";
import { StatusApi } from "./components/StatusApi";
import { TabelaRecebiveis } from "./components/TabelaRecebiveis";
import { GavetaGestor } from "./components/GavetaGestor";
import { LoginScreen, type Persona } from "./components/LoginScreen";
import { validarLote, salvarValidadores, simularLoteLocal, obterHealth, sessaoAtual } from "./services/api";
import { formatarMoedaCompacta } from "./utils/formatters";
import type { BatchValidationResponse, ComparativoRegras, FonteDados, ModoValidacao, ValidadoresConfig } from "./types/api";

const TELAS: Tela[] = ["envio", "resumo", "estatistica", "perda", "notas", "historico"];
const telaDoEndereco = (): Tela => {
  const h = window.location.hash.slice(1) as Tela;
  return TELAS.includes(h) ? h : "envio";
};

const CHAVE_TOKEN = "antecipe_token";
const tokenSalvo = (): string | null => {
  try {
    return localStorage.getItem(CHAVE_TOKEN);
  } catch {
    return null;
  }
};

export default function App() {
  // Sessão do portal: só o token fica no navegador; o perfil sempre vem do servidor (GET /auth/me)
  const [persona, setPersonaEstado] = useState<Persona | null>(null);
  const [conferindoSessao, setConferindoSessao] = useState<boolean>(() => !!tokenSalvo());
  const setPersona = (p: Persona | null) => {
    try {
      if (p) localStorage.setItem(CHAVE_TOKEN, p.token);
      else localStorage.removeItem(CHAVE_TOKEN);
    } catch { /* navegador sem storage: só não lembra a sessão no F5 */ }
    setPersonaEstado(p);
  };
  useEffect(() => {
    const token = tokenSalvo();
    if (!token) return;
    sessaoAtual(token)
      .then(setPersonaEstado)
      .catch(() => setPersona(null)) // token forjado, vencido ou de outro segredo: volta pro login
      .finally(() => setConferindoSessao(false));
  }, []);

  // Parâmetros da operação
  const [dataBase, setDataBase] = useState<string>("22/10/2026");
  const [taxaMensalPercentual, setTaxaMensalPercentual] = useState<number>(2.0);
  // sem mexer na taxa, o servidor usa a do fundo (JSON); só envia se a pessoa alterar
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
  const navInterna = useRef(false); // true quando o próprio site trocou o endereço
  // o painel fica logo abaixo da página inicial; trocar de tela leva ao topo do painel
  const painelRef = useRef<HTMLDivElement>(null);
  const conteudoRef = useRef<HTMLElement>(null); // área que rola dentro do painel
  const raizRef = useRef<HTMLDivElement>(null);
  // dentro do painel, a roda do mouse para baixo nunca mexe a página: ou rola uma área do painel, ou não faz nada
  // (assim o menu lateral não "sobe" quando o conteúdo acaba ou quando o mouse está em cima dele)
  useEffect(() => {
    const el = painelRef.current;
    if (!el) return;
    const podeRolar = (alvo: EventTarget | null, dy: number) => {
      for (let n = alvo as HTMLElement | null; n && n !== el; n = n.parentElement) {
        const st = getComputedStyle(n);
        if (!/(auto|scroll)/.test(st.overflowY) || n.scrollHeight <= n.clientHeight + 1) continue;
        if (dy > 0 ? n.scrollTop + n.clientHeight < n.scrollHeight - 1 : n.scrollTop > 0) return true;
      }
      return false;
    };
    const roda = (e: WheelEvent) => {
      if (e.ctrlKey || Math.abs(e.deltaY) < Math.abs(e.deltaX)) return;
      const chegou = el.getBoundingClientRect().top <= 1;
      if (chegou && e.deltaY > 0 && !podeRolar(e.target, e.deltaY)) e.preventDefault();
    };
    el.addEventListener("wheel", roda, { passive: false });
    return () => el.removeEventListener("wheel", roda);
  }, [persona]);

  // transição da página inicial para o painel: 0 = só a página inicial, 1 = painel ocupando a tela
  useEffect(() => {
    let quadro = 0;
    const atualizar = () => {
      quadro = 0;
      const el = painelRef.current;
      if (!el) return;
      const p = Math.min(Math.max(1 - el.getBoundingClientRect().top / window.innerHeight, 0), 1);
      raizRef.current?.style.setProperty("--entrada", p.toFixed(3));
    };
    const pedir = () => { if (!quadro) quadro = requestAnimationFrame(atualizar); };
    atualizar();
    window.addEventListener("scroll", pedir, { passive: true });
    window.addEventListener("resize", pedir);
    return () => { window.removeEventListener("scroll", pedir); window.removeEventListener("resize", pedir); cancelAnimationFrame(quadro); };
  }, []);
  useEffect(() => {
    // endereço mudou por fora (voltar do navegador, link colado): troca a tela e desce até o painel
    const aoMudar = () => {
      if (navInterna.current) { navInterna.current = false; return; } // a rolagem já foi tratada por quem navegou
      setTelaEstado(telaDoEndereco());
      if (TELAS.includes(window.location.hash.slice(1) as Tela)) requestAnimationFrame(() => topoDoPainel(false));
      else window.scrollTo({ top: 0 });
    };
    window.addEventListener("hashchange", aoMudar);
    return () => window.removeEventListener("hashchange", aoMudar);
  }, []);
  const topoDoPainel = (suave: boolean) => {
    const el = painelRef.current;
    if (el) window.scrollTo({ top: el.getBoundingClientRect().top + window.scrollY, behavior: suave ? "smooth" : "instant" });
  };
  const irPara = (t: Tela, suave = false) => {
    if (window.location.hash.slice(1) !== t) { navInterna.current = true; window.location.hash = t; }
    setTelaEstado(t);
    topoDoPainel(suave);
    conteudoRef.current?.scrollTo({ top: 0, behavior: "instant" });
  };
  const entrarNoPainel = useCallback((t?: Tela) => {
    if (t) {
      if (window.location.hash.slice(1) !== t) { navInterna.current = true; window.location.hash = t; }
      setTelaEstado(t);
    }
    topoDoPainel(true);
  }, []);
  // link direto para uma tela (#resumo...) abre já no painel, sem passar pela página inicial
  useEffect(() => {
    if (TELAS.includes(window.location.hash.slice(1) as Tela)) requestAnimationFrame(() => topoDoPainel(false));
  }, []);

  // A tela nunca começa vazia: lote de demonstração local até a pessoa enviar o dela
  useEffect(() => {
    setResultado(simularLoteLocal({ dataBase: "22/10/2026", taxaMensal: 0.02, otimizarLote: true }));
    setFonteDados("demo");
    obterHealth()
      .then((res) => {
        if (res.dados.taxa_mensal_padrao !== undefined) setTaxaMensalPercentual(Number((res.dados.taxa_mensal_padrao * 100).toFixed(4)));
        if (res.dados.data_base_padrao) setDataBase(res.dados.data_base_padrao);
      })
      .catch(() => {});
  }, []);

  const processarLote = useCallback(
    async (arquivo: File | null, override?: ValidadoresConfig, isWhatIfSimulacao = false, depois?: Tela, regrasJaNoServidor = false) => {
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
          // regras recém-salvas no servidor: valida com elas direto, sem override (senão o histórico registra como simulação)
          validadoresOverride: regrasJaNoServidor ? undefined : override,
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

  const gestor = persona?.role === "GESTOR";

  // sair limpa o que a pessoa enviou e os parâmetros dela: quem entrar depois não vê o lote de outra conta
  const sair = () => {
    setPersona(null);
    setDrawerGestorAberto(false);
    setResultado(simularLoteLocal({ dataBase: "22/10/2026", taxaMensal: 0.02, otimizarLote: true }));
    setFonteDados("demo");
    setArquivoAtual(null);
    setLoteAtual(null);
    setReplayIdempotente(false);
    setComparativoRegras(null);
    setMotivoFiltroAtivo(null);
    setErroGeral(null);
    setModo("lote");
    setOtimizarLote(true);
    setTaxaAlteradaManualmente(false);
    obterHealth()
      .then((res) => {
        setTaxaMensalPercentual(res.dados.taxa_mensal_padrao !== undefined ? Number((res.dados.taxa_mensal_padrao * 100).toFixed(4)) : 2);
        if (res.dados.data_base_padrao) setDataBase(res.dados.data_base_padrao);
      })
      .catch(() => setTaxaMensalPercentual(2));
    irPara("envio");
  };

  return (
    <div ref={raizRef} className="min-h-screen bg-creme font-sans">
      <PaginaInicial onEntrar={entrarNoPainel} />

      {/* abaixo da página inicial: login (se ainda não entrou) ou o painel */}
      <div ref={painelRef} id="painel" className="sticky top-0 h-screen snap-start overflow-hidden supports-[height:100dvh]:h-[100dvh]">
      {conferindoSessao ? (
        <div className="h-full" aria-busy="true" />
      ) : !persona ? (
        <div className="entrada-conteudo h-full overflow-y-auto">
        <LoginScreen onLogin={(p) => { setPersona(p); setDrawerGestorAberto(p.role === "GESTOR"); requestAnimationFrame(() => topoDoPainel(false)); }} />
        </div>
      ) : (
      <div className="flex h-full flex-col lg:flex-row">
      <MenuLateral
        tela={tela}
        onTela={irPara}
        onAbrirGestor={gestor ? () => setDrawerGestorAberto(true) : undefined}
        persona={persona}
        onSair={sair}
        onCarregarDemo={handleCarregarDemo}
        carregando={carregando}
        temResultado={!!resultado}
        liquidoCompacto={resultado ? formatarMoedaCompacta(resultado.resumo.valor_liquido_receber) : null}
        qtdRecusadas={resultado?.resumo.qtd_recusadas ?? 0}
        fonte={fonteDados}
        nomeLote={loteAtual?.nome ?? null}
      />

      <main ref={conteudoRef} className="entrada-conteudo min-h-0 min-w-0 flex-1 overflow-y-auto">
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
            onTaxaMensalChange={(v) => { setTaxaMensalPercentual(v); setTaxaAlteradaManualmente(true); }}
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

        {resultado && tela === "perda" && <TelaPerda resumo={resultado.resumo} meta={resultado.meta} itens={resultado.itens} />}

        {resultado && tela === "notas" && (
          <div className="mx-auto flex max-w-6xl flex-col gap-6 px-5 py-10 sm:px-8 lg:py-14">
            <Cabecalho titulo="Nota por nota" sub="Busque pelo número da nota ou pelo cliente. Clique numa nota recusada para ver o problema e o que fazer." />
            <StatusApi tempoProcessamentoMs={resultado.meta.tempo_processamento_ms} dataBase={resultado.meta.data_base_utilizada || dataBase} />
            <TabelaRecebiveis itens={resultado.itens} motivoFiltroAtivo={motivoFiltroAtivo} onLimparMotivoFiltro={() => setMotivoFiltroAtivo(null)} />
          </div>
        )}
        {tela === "historico" && (
          // só marca "aberto agora" quando o lote veio do servidor (o demo local não está no banco)
          <TelaHistorico
            batchHashAtual={fonteDados === "api" ? resultado?.meta.batch_hash_idempotencia ?? null : null}
            ehGestor={gestor}
          />
        )}
      </main>
      </div>
      )}
      </div>

      <GavetaGestor
        aberto={gestor && drawerGestorAberto}
        onFechar={() => setDrawerGestorAberto(false)}
        onAplicarRegras={async (config, chave) => {
          const salvo = await salvarValidadores(config, chave);
          await processarLote(arquivoAtual, config, false, undefined, salvo.fonte === "api");
        }}
        onSimularWhatIf={(config) => processarLote(arquivoAtual, config, true)}
        carregando={carregando}
        comparativo={comparativoRegras}
      />
    </div>
  );
}
