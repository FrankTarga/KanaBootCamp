import { useEffect, useState, type ComponentType } from "react";
import { BarChart3, FolderUp, History, ListChecks, LogOut, Menu, Receipt, SlidersHorizontal, TrendingDown, Wand2, X } from "lucide-react";
import type { Persona } from "./LoginScreen";

export type Tela = "envio" | "resumo" | "estatistica" | "perda" | "notas" | "historico";

interface MenuLateralProps {
  tela: Tela;
  onTela: (t: Tela) => void;
  onAbrirGestor?: () => void; // ausente = perfil sem permissão para editar regras
  onCarregarDemo: () => void;
  persona: Persona;
  onSair: () => void;
  carregando: boolean;
  temResultado: boolean;
  liquidoCompacto: string | null;
  qtdRecusadas: number;
  fonte: "api" | "demo";
  nomeLote: string | null;
}

export function Marca({ clara = true }: { clara?: boolean }) {
  return (
    <span className="flex items-center gap-2.5">
      {/* duas setas para a frente: o recebível que chega antes */}
      <svg viewBox="0 0 28 28" className="h-7 w-7" aria-hidden="true">
        <path d="M5 7l8 7-8 7" fill="none" stroke="currentColor" strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round" className={clara ? "text-creme" : "text-floresta"} />
        <path d="M14 7l8 7-8 7" fill="none" stroke="currentColor" strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round" className="text-broto" />
      </svg>
      <span className={`font-display text-2xl font-semibold tracking-tight ${clara ? "text-creme" : "text-floresta"}`}>antecipe</span>
    </span>
  );
}

const ITENS: { id: Tela; rotulo: string; dica: string; Icone: ComponentType<{ className?: string }> }[] = [
  { id: "envio", rotulo: "Enviar notas", dica: "Arraste a pasta", Icone: FolderUp },
  { id: "resumo", rotulo: "Resumo", dica: "Quanto você recebe", Icone: Receipt },
  { id: "estatistica", rotulo: "Estatística", dica: "Recusas e prazos", Icone: BarChart3 },
  { id: "perda", rotulo: "Análise de perda", dica: "Quanto custa esperar", Icone: TrendingDown },
  { id: "notas", rotulo: "Notas", dica: "Nota por nota", Icone: ListChecks },
  { id: "historico", rotulo: "Histórico", dica: "Lotes já validados", Icone: History },
];

export function MenuLateral(props: MenuLateralProps) {
  const [aberto, setAberto] = useState(false);
  const { tela, onTela, onAbrirGestor, onCarregarDemo, carregando, temResultado, liquidoCompacto, qtdRecusadas, fonte, nomeLote, persona, onSair } = props;
  const ir = (t: Tela) => { onTela(t); setAberto(false); };
  // menu do celular aberto: a página de trás não rola
  useEffect(() => {
    if (!aberto) return;
    const anterior = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = anterior; };
  }, [aberto]);

  const conteudo = (
    <div className="flex min-h-full flex-col gap-8 px-4 py-6">
      <div className="px-2"><Marca /></div>

      <nav aria-label="Telas" className="flex flex-col gap-1">
        {ITENS.map(({ id, rotulo, dica, Icone }) => {
          const ativo = tela === id;
          const bloqueado = id !== "envio" && id !== "historico" && !temResultado;
          return (
            <button key={id} type="button" disabled={bloqueado} onClick={() => ir(id)} aria-current={ativo ? "page" : undefined}
              className={`group flex items-center gap-3 rounded-xl px-3 py-2.5 text-left transition-colors disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-broto ${
                ativo ? "bg-creme text-floresta" : "text-creme/80 hover:bg-white/[0.06] hover:text-creme"
              }`}>
              <Icone className={`h-5 w-5 shrink-0 ${ativo ? "text-emerald-700" : "text-creme/60 group-hover:text-broto"}`} />
              <span className="min-w-0 flex-1">
                <span className="block text-sm font-semibold">{rotulo}</span>
                <span className={`block truncate text-xs ${ativo ? "text-emerald-800/70" : "text-creme/50"}`}>
                  {id === "resumo" && liquidoCompacto ? `${liquidoCompacto} hoje` : dica}
                </span>
              </span>
              {id === "notas" && qtdRecusadas > 0 && (
                <span className="rounded-full bg-rose-500/90 px-2 py-0.5 text-[11px] font-bold tabular-nums text-white" title="notas recusadas">
                  {qtdRecusadas.toLocaleString("pt-BR")}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      <div className="flex flex-col gap-1 border-t border-white/10 pt-6">
        <p className="eyebrow px-3 pb-1 text-creme/40">{onAbrirGestor ? "Gestor do fundo" : "Atalhos"}</p>
        {onAbrirGestor && (
          <button type="button" onClick={() => { onAbrirGestor(); setAberto(false); }}
            className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-semibold text-creme/80 hover:bg-white/[0.06] hover:text-creme focus-visible:outline focus-visible:outline-2 focus-visible:outline-broto">
            <SlidersHorizontal className="h-5 w-5 text-creme/60" /> Regras do fundo
          </button>
        )}
        <button type="button" onClick={() => { onCarregarDemo(); setAberto(false); }} disabled={carregando}
          className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-semibold text-creme/80 hover:bg-white/[0.06] hover:text-creme disabled:opacity-40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-broto">
          <Wand2 className="h-5 w-5 text-creme/60" /> Carregar lote demo
        </button>
      </div>

      <div className="mt-auto rounded-2xl border border-white/10 bg-white/[0.04] p-4 text-xs text-creme/70">
        <p className="flex items-center gap-2 font-semibold text-creme">
          <span className={`h-2 w-2 rounded-full ${fonte === "api" ? "bg-broto" : "bg-amber-400"}`} />
          {fonte === "api" ? "Análise ligada" : "Modo demonstração"}
        </p>
        <p className="mt-1 truncate">{nomeLote ? `Lote: ${nomeLote}` : "Nenhum arquivo enviado ainda"}</p>
      </div>

      <div className="-mt-4 flex items-center gap-3 rounded-2xl border border-white/10 px-4 py-3 text-xs">
        <span className="min-w-0 flex-1">
          <span className="block truncate font-semibold text-creme">{persona.nome}</span>
          <span className="block truncate text-creme/50">{persona.cargo}</span>
        </span>
        <button type="button" onClick={() => { onSair(); setAberto(false); }} title="Sair / trocar perfil" aria-label="Sair / trocar perfil"
          className="rounded-lg p-2 text-creme/70 hover:bg-white/10 hover:text-creme focus-visible:outline focus-visible:outline-2 focus-visible:outline-broto">
          <LogOut className="h-4 w-4" />
        </button>
      </div>
    </div>
  );

  return (
    <>
      {/* celular: barra no topo + gaveta */}
      <div className="entrada-barra z-30 flex shrink-0 items-center justify-between bg-floresta-escura px-4 py-3 lg:hidden">
        <Marca />
        <button type="button" onClick={() => setAberto(true)} aria-label="Abrir menu" aria-expanded={aberto}
          className="rounded-lg p-2 text-creme hover:bg-white/10"><Menu className="h-6 w-6" /></button>
      </div>
      {aberto && (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label="Menu">
          <button type="button" className="absolute inset-0 bg-black/50" aria-label="Fechar menu" onClick={() => setAberto(false)} />
          <aside className="absolute inset-y-0 left-0 w-72 max-w-[85vw] overflow-y-auto overscroll-contain bg-floresta-escura">
            <button type="button" onClick={() => setAberto(false)} aria-label="Fechar menu" className="absolute right-3 top-5 rounded-lg p-2 text-creme hover:bg-white/10">
              <X className="h-5 w-5" />
            </button>
            {conteudo}
          </aside>
        </div>
      )}
      {/* computador: ocupa a altura do painel e não se mexe; só o conteúdo à direita rola */}
      <aside className="entrada-menu z-30 hidden h-full w-72 shrink-0 overflow-y-auto overscroll-contain bg-floresta-escura lg:block">{conteudo}</aside>
    </>
  );
}
