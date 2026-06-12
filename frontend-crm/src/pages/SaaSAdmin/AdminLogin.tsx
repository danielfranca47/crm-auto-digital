import { useState } from "react";
import { CORE_BASE } from "@/lib/api-client";
import { persistAdminToken } from "@/lib/admin-token";

export default function AdminLogin() {
  const [secret, setSecret] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setLoading(true);
    try {
      const res = await fetch(`${CORE_BASE}/admin/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ secret }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data?.detail ?? "Credenciais inválidas");
      }
      const data = await res.json();
      persistAdminToken(data.access_token);
      window.location.href = "/saas-admin";
    } catch (e: any) {
      setErr(e?.message ?? "Falha ao entrar");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-900 to-slate-800 flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-6">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-indigo-600 text-white font-bold text-xl shadow-sm">
            SA
          </div>
          <h1 className="mt-3 text-2xl font-semibold text-white">Admin</h1>
          <p className="text-slate-400 text-sm">Painel de operação SaaS</p>
        </div>

        <form
          onSubmit={onSubmit}
          className="bg-slate-800/80 backdrop-blur border border-slate-700 rounded-2xl shadow-md p-6"
        >
          <label className="block text-sm font-medium text-slate-300 mb-1">
            Segredo de acesso
          </label>
          <input
            type="password"
            placeholder="••••••••"
            value={secret}
            onChange={(e) => {
              setSecret(e.target.value);
              if (err) setErr(null);
            }}
            autoComplete="current-password"
            autoFocus
            required
            className="w-full rounded-lg border border-slate-600 bg-slate-900 text-white focus:border-indigo-500 focus:ring focus:ring-indigo-900 px-3 py-2 outline-none transition mb-4"
          />

          {err && (
            <p className="text-red-400 text-sm mb-3">{err}</p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-medium rounded-lg py-2 transition"
          >
            {loading ? "Entrando…" : "Entrar"}
          </button>
        </form>
      </div>
    </div>
  );
}
