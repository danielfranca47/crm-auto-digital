import { useState } from "react";
import { Outlet, useNavigate } from "react-router-dom";
import { LogOut } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/services/api";

/**
 * Layout da app para conta sem plano activo: sem sidebar nem banners (todos dependem do
 * backend-crm, que responde 403) — só a página de assinatura e a saída.
 */
export default function LockedShell() {
  const navigate = useNavigate();
  const [loggingOut, setLoggingOut] = useState(false);

  async function onLogout() {
    if (loggingOut) return;
    setLoggingOut(true);
    try {
      await api.auth.logout();
    } catch {
      // mesmo se falhar, seguimos para tela de login
    } finally {
      navigate("/login", { replace: true });
      setLoggingOut(false);
    }
  }

  return (
    <div className="flex min-h-screen w-full flex-col">
      <header className="h-12 flex items-center justify-between border-b bg-background px-4">
        <span className="text-sm font-semibold">CRM AutoDigital</span>
        <Button variant="ghost" size="sm" onClick={onLogout} disabled={loggingOut}>
          <LogOut className="mr-2 h-4 w-4" />
          Sair
        </Button>
      </header>
      <main className="flex-1">
        <Outlet />
      </main>
    </div>
  );
}
