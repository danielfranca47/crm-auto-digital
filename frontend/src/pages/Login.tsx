import { useEffect, useState } from "react";
import { api } from "../services/api";

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setLoading(true);
    try {
      await api.auth.login(email, password);
      await api.auth.me();
      window.location.href = "/";
    } catch (e: any) {
      setErr(e?.message ?? "Falha ao entrar");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-sky-50 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Marca / título */}
        <div className="text-center mb-6">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-sky-100 text-sky-600 font-bold text-xl shadow-sm">
            AD
          </div>
          <h1 className="mt-3 text-2xl font-semibold text-slate-800">Entrar</h1>
          <p className="text-slate-500 text-sm">Acesse o CRM AutoDigital</p>
        </div>

        {/* Card */}
        <form
          onSubmit={onSubmit}
          className="bg-white/90 backdrop-blur border border-slate-200 rounded-2xl shadow-md p-6"
        >
          <label className="block text-sm font-medium text-slate-700 mb-1">
            Email
          </label>
          <input
            type="email"
            placeholder="seu@email.com"
            value={email}
            onChange={(e) => {
              setEmail(e.target.value);
              if (err) setErr(null);
            }}
            autoComplete="username"
            autoFocus
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
            onChange={(e) => {
              setPassword(e.target.value);
              if (err) setErr(null);
            }}
            autoComplete="current-password"
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
            {loading ? "Entrando..." : "Entrar"}
          </button>
        </form>

        {/* Rodapé */}
        <p className="text-center text-slate-400 text-xs mt-4">
          © {new Date().getFullYear()} AutoDigital
        </p>
      </div>
    </div>
  );
}
