import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../services/api";

export default function Register() {
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    if (password !== confirm) {
      setErr("As senhas não coincidem.");
      return;
    }
    if (password.length < 6) {
      setErr("A senha deve ter pelo menos 6 caracteres.");
      return;
    }
    setLoading(true);
    try {
      await api.auth.register(email, password, name || undefined);
      navigate("/login?registered=1");
    } catch (e: any) {
      setErr(e?.message ?? "Erro ao criar conta. Verifique os dados.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-sky-50 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-6">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-sky-100 text-sky-600 font-bold text-xl shadow-sm">
            AD
          </div>
          <h1 className="mt-3 text-2xl font-semibold text-slate-800">Criar conta</h1>
          <p className="text-slate-500 text-sm">CRM AutoDigital — comece agora</p>
        </div>

        <form
          onSubmit={onSubmit}
          className="bg-white/90 backdrop-blur border border-slate-200 rounded-2xl shadow-md p-6"
        >
          <label className="block text-sm font-medium text-slate-700 mb-1">
            Nome <span className="text-slate-400 font-normal">(opcional)</span>
          </label>
          <input
            type="text"
            placeholder="Seu nome"
            value={name}
            onChange={(e) => setName(e.target.value)}
            autoFocus
            className="w-full rounded-lg border border-slate-300 focus:border-sky-400 focus:ring focus:ring-sky-100 px-3 py-2 outline-none transition mb-4"
          />

          <label className="block text-sm font-medium text-slate-700 mb-1">
            Email
          </label>
          <input
            type="email"
            placeholder="seu@email.com"
            value={email}
            onChange={(e) => { setEmail(e.target.value); if (err) setErr(null); }}
            autoComplete="username"
            required
            className="w-full rounded-lg border border-slate-300 focus:border-sky-400 focus:ring focus:ring-sky-100 px-3 py-2 outline-none transition mb-4"
          />

          <label className="block text-sm font-medium text-slate-700 mb-1">
            Senha
          </label>
          <input
            type="password"
            placeholder="••••••••"
            value={password}
            onChange={(e) => { setPassword(e.target.value); if (err) setErr(null); }}
            autoComplete="new-password"
            required
            className="w-full rounded-lg border border-slate-300 focus:border-sky-400 focus:ring focus:ring-sky-100 px-3 py-2 outline-none transition mb-4"
          />

          <label className="block text-sm font-medium text-slate-700 mb-1">
            Confirmar senha
          </label>
          <input
            type="password"
            placeholder="••••••••"
            value={confirm}
            onChange={(e) => { setConfirm(e.target.value); if (err) setErr(null); }}
            autoComplete="new-password"
            required
            className="w-full rounded-lg border border-slate-300 focus:border-sky-400 focus:ring focus:ring-sky-100 px-3 py-2 outline-none transition mb-2"
          />

          {err && (
            <div className="mt-2 mb-2 rounded-lg border border-red-200 bg-red-50 text-red-700 text-sm px-3 py-2">
              {err}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="mt-3 w-full inline-flex items-center justify-center rounded-lg bg-sky-600 text-white font-medium py-2.5 hover:bg-sky-700 disabled:opacity-60 disabled:cursor-not-allowed shadow-sm transition"
          >
            {loading ? "Criando conta…" : "Criar conta"}
          </button>

          <div className="mt-4 text-center">
            <span className="text-sm text-slate-500">
              Já tem conta?{" "}
              <Link to="/login" className="text-sky-600 hover:underline">
                Entrar
              </Link>
            </span>
          </div>
        </form>

        <p className="text-center text-slate-400 text-xs mt-4">
          © {new Date().getFullYear()} AutoDigital
        </p>
      </div>
    </div>
  );
}
