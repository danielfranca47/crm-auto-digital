import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../services/api";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setLoading(true);
    try {
      await api.auth.forgotPassword(email);
      setSent(true);
    } catch (e: any) {
      setErr(e?.message ?? "Ocorreu um erro. Tente novamente.");
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
          <h1 className="mt-3 text-2xl font-semibold text-slate-800">Recuperar senha</h1>
          <p className="text-slate-500 text-sm">Enviamos um link para o seu email</p>
        </div>

        <div className="bg-white/90 backdrop-blur border border-slate-200 rounded-2xl shadow-md p-6">
          {sent ? (
            <div className="text-center py-2">
              <div className="w-12 h-12 rounded-full bg-emerald-100 flex items-center justify-center mx-auto mb-3">
                <svg className="w-6 h-6 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <p className="font-medium text-slate-800 mb-1">Verifique o seu email</p>
              <p className="text-sm text-slate-500">
                Se o email <strong>{email}</strong> estiver registado, receberá um link de recuperação em breve.
              </p>
              <Link
                to="/login"
                className="mt-4 inline-block text-sm text-sky-600 hover:underline"
              >
                Voltar ao login
              </Link>
            </div>
          ) : (
            <form onSubmit={onSubmit}>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Email
              </label>
              <input
                type="email"
                placeholder="seu@email.com"
                value={email}
                onChange={(e) => { setEmail(e.target.value); if (err) setErr(null); }}
                autoFocus
                required
                className="w-full rounded-lg border border-slate-300 focus:border-sky-400 focus:ring focus:ring-sky-100 px-3 py-2 outline-none transition mb-4"
              />

              {err && (
                <div className="mb-3 rounded-lg border border-red-200 bg-red-50 text-red-700 text-sm px-3 py-2">
                  {err}
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full inline-flex items-center justify-center rounded-lg bg-sky-600 text-white font-medium py-2.5 hover:bg-sky-700 disabled:opacity-60 disabled:cursor-not-allowed shadow-sm transition"
              >
                {loading ? "Enviando…" : "Enviar link de recuperação"}
              </button>

              <div className="mt-4 text-center">
                <Link to="/login" className="text-sm text-slate-500 hover:text-slate-700">
                  Voltar ao login
                </Link>
              </div>
            </form>
          )}
        </div>

        <p className="text-center text-slate-400 text-xs mt-4">
          © {new Date().getFullYear()} AutoDigital
        </p>
      </div>
    </div>
  );
}
