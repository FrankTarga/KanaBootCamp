import { useState, type FormEvent } from "react";
import { AlertCircle, Building2, Loader2, Lock, SlidersHorizontal } from "lucide-react";
import { Marca } from "./MenuLateral";
import { entrar, type Sessao } from "../services/api";

// Só entra com e-mail e senha validados no servidor (POST /auth/login); o perfil vem do banco, com token assinado.
// A proteção das regras continua sendo a X-API-Key do PUT /validators.
export type Persona = Sessao;

// E-mails padrão do backend (CEDENTE_EMAIL / BANCA_EMAIL); escolher o perfil só preenche o e-mail, a senha é sempre exigida
const PERFIS = {
  CEDENTE: { titulo: "Empresa (cedente)", dica: "Enviar notas e ver quanto recebe", email: "empresa@antecipe.com.br", Icone: Building2 },
  GESTOR: { titulo: "Gestor do fundo", dica: "Editar as regras e simular o impacto", email: "banca@antecipe.com.br", Icone: SlidersHorizontal },
} as const;

export function LoginScreen({ onLogin }: { onLogin: (p: Persona) => void }) {
  const [perfil, setPerfil] = useState<Persona["role"]>("CEDENTE");
  const [email, setEmail] = useState<string>(PERFIS.CEDENTE.email);
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(false);

  const escolher = (role: Persona["role"]) => {
    setPerfil(role);
    setEmail(PERFIS[role].email);
    setSenha("");
    setErro(null);
  };

  const enviar = async (e: FormEvent) => {
    e.preventDefault();
    setErro(null);
    setCarregando(true);
    try {
      const sessao = await entrar(email, senha);
      if (sessao.role !== perfil) {
        setErro(`Esta conta é de ${PERFIS[sessao.role].titulo.toLowerCase()}. Escolha esse perfil para entrar.`);
        return;
      }
      onLogin(sessao);
    } catch (err: unknown) {
      setErro(err instanceof Error ? err.message : "Não foi possível entrar.");
    } finally {
      setCarregando(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-creme p-4 font-sans">
      <div className="grid w-full max-w-4xl overflow-hidden rounded-2xl bg-white shadow-elevated md:grid-cols-2">
        <div className="flex flex-col justify-between gap-8 bg-floresta-escura p-8">
          <Marca />
          <div>
            <h1 className="font-display text-3xl font-semibold tracking-tight text-creme">Receba hoje o que você só receberia daqui a meses.</h1>
            <p className="mt-3 text-sm leading-relaxed text-creme/70">
              Antecipação de recebíveis com validação nota a nota, valor líquido na hora e regras do fundo editáveis sem deploy.
            </p>
          </div>
          <p className="text-xs text-creme/50">Ambiente de demonstração</p>
        </div>

        <div className="flex flex-col justify-center gap-5 p-8">
          <div>
            <h2 className="font-display text-xl font-semibold text-floresta">Acessar o portal</h2>
            <p className="mt-1 text-sm text-slate-500">Escolha como quer entrar e digite a senha.</p>
          </div>

          <fieldset className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <legend className="sr-only">Perfil de acesso</legend>
            {(Object.keys(PERFIS) as Persona["role"][]).map((role) => {
              const { titulo, dica, Icone } = PERFIS[role];
              const ativo = perfil === role;
              return (
                <label key={role}
                  className={`flex cursor-pointer items-start gap-3 rounded-xl border p-3 transition-colors has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-broto ${
                    ativo ? "border-emerald-500 bg-emerald-50" : "border-creme-linha bg-creme-claro hover:border-emerald-300"
                  }`}>
                  <input type="radio" name="perfil" value={role} checked={ativo} onChange={() => escolher(role)} className="sr-only" />
                  <span className={`rounded-lg p-2 ${ativo ? "bg-emerald-600 text-white" : "bg-emerald-100 text-emerald-700"}`}><Icone className="h-5 w-5" /></span>
                  <span className="min-w-0">
                    <span className="block text-sm font-semibold text-floresta">{titulo}</span>
                    <span className="block text-xs text-slate-500">{dica}</span>
                  </span>
                </label>
              );
            })}
          </fieldset>

          <form onSubmit={enviar} className="flex flex-col gap-3">
            {erro && (
              <p role="alert" className="flex items-center gap-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
                <AlertCircle className="h-4 w-4 shrink-0" /> {erro}
              </p>
            )}
            <label className="text-xs font-medium text-slate-600">
              E-mail corporativo
              <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
                className="mt-1 w-full rounded-lg border border-creme-linha bg-creme-claro px-3 py-2 text-sm text-floresta focus:border-emerald-500 focus:outline-none" />
            </label>
            <label className="text-xs font-medium text-slate-600">
              Senha
              <input type="password" required value={senha} onChange={(e) => setSenha(e.target.value)}
                className="mt-1 w-full rounded-lg border border-creme-linha bg-creme-claro px-3 py-2 text-sm text-floresta focus:border-emerald-500 focus:outline-none" />
            </label>
            <button type="submit" disabled={carregando}
              className="flex items-center justify-center gap-2 rounded-lg bg-emerald-600 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-emerald-500 disabled:opacity-60 focus-visible:outline focus-visible:outline-2 focus-visible:outline-broto">
              {carregando ? <Loader2 className="h-4 w-4 animate-spin" /> : <Lock className="h-4 w-4" />} {carregando ? "Entrando..." : `Entrar como ${PERFIS[perfil].titulo.toLowerCase()}`}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
