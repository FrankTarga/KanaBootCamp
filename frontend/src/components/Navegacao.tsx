import { useEffect, useState } from "react";
import { SlidersHorizontal, Wand2 } from "lucide-react";

interface NavegacaoProps {
  onCarregarDemo: () => void;
  onAbrirGestor: () => void;
  carregando: boolean;
}

const LINKS = [
  { href: "#resultado", rotulo: "Análise" },
  { href: "#graficos", rotulo: "Gráficos" },
  { href: "#notas", rotulo: "Notas" },
];

export function Marca({ clara }: { clara: boolean }) {
  return (
    <a href="#inicio" className="flex items-center gap-2.5" aria-label="Antecipe, voltar ao início">
      {/* duas setas para a frente: o recebível que chega antes */}
      <svg viewBox="0 0 28 28" className="h-7 w-7" aria-hidden="true">
        <path d="M5 7l8 7-8 7" fill="none" stroke="currentColor" strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round"
          className={clara ? "text-creme" : "text-floresta"} />
        <path d="M14 7l8 7-8 7" fill="none" stroke="currentColor" strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round"
          className="text-broto" />
      </svg>
      <span className={`font-display text-2xl font-semibold tracking-tight ${clara ? "text-creme" : "text-floresta"}`}>
        antecipe
      </span>
    </a>
  );
}

export function Navegacao({ onCarregarDemo, onAbrirGestor, carregando }: NavegacaoProps) {
  const [solido, setSolido] = useState(false);

  useEffect(() => {
    const atualizar = () => setSolido(window.scrollY > window.innerHeight * 0.6);
    atualizar();
    window.addEventListener("scroll", atualizar, { passive: true });
    return () => window.removeEventListener("scroll", atualizar);
  }, []);

  return (
    <header className="fixed inset-x-0 top-0 z-30 px-3 pt-3 sm:px-6 sm:pt-5">
      <nav
        aria-label="Principal"
        className={`mx-auto flex max-w-6xl items-center justify-between gap-4 rounded-2xl px-4 py-3 transition-all duration-300 sm:px-6 ${
          solido ? "border border-creme-linha bg-creme-claro/95 shadow-elevated backdrop-blur-md" : "border border-transparent"
        }`}
      >
        <Marca clara={!solido} />

        <ul className="hidden items-center gap-8 md:flex">
          {LINKS.map((l) => (
            <li key={l.href}>
              <a
                href={l.href}
                className={`text-sm font-semibold transition-colors ${
                  solido ? "text-slate-700 hover:text-floresta" : "text-creme/85 hover:text-creme"
                }`}
              >
                {l.rotulo}
              </a>
            </li>
          ))}
        </ul>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onCarregarDemo}
            disabled={carregando}
            title="Carrega um lote de demonstração com aprovações, recusas e limites"
            className={`btn text-sm ${
              solido
                ? "border border-creme-linha bg-creme text-slate-800 hover:bg-white"
                : "border border-creme/40 text-creme hover:bg-creme/10"
            }`}
          >
            <Wand2 className="h-4 w-4" />
            <span className="hidden sm:inline">Lote demo</span>
          </button>
          <button
            type="button"
            onClick={onAbrirGestor}
            className="btn bg-emerald-800 text-creme shadow-sm hover:bg-emerald-900 focus-visible:ring-emerald-500/30"
          >
            <SlidersHorizontal className="h-4 w-4" />
            <span className="hidden sm:inline">Regras do fundo</span>
          </button>
        </div>
      </nav>
    </header>
  );
}
