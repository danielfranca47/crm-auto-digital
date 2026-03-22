import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, Outlet, useNavigate } from "react-router-dom";
import Index from "./pages/Index";
import Dashboard from "./pages/Dashboard";
import Prospeccao from "./pages/Prospeccao";
import AssistenteIA from "./pages/AssistenteIA";
import Pesquisa from "./pages/Pesquisa";
import NotFound from "./pages/NotFound";
import MinhaConta from "./pages/MinhaConta";
import Assinatura from "./pages/Assinatura";
import UsoDoPlano from "./pages/UsoDoPlano";
import AiProfile from "./pages/AiProfile";
import AgenteDashboard from "./pages/AgenteDashboard";
import AgenteConfiguracao from "./pages/AgenteConfiguracao";
import { ThemeProvider } from "./contexts/ThemeContext";
import { LeadsProvider } from "./contexts/LeadsContext";
import { RateLimitModalProvider } from "./contexts/RateLimitModalContext";
import { AppSidebar } from "./components/AppSidebar";
import TestContext from "./tests/TestContext";
import Login from "./pages/Login"; // tem que estar exatamente assim
import { useEffect, useState } from "react";
import { api } from "./services/api";
import { useApiErrorHandler } from "./hooks/useApiErrorHandler";

const queryClient = new QueryClient();

/** Wrapper que valida a sessão e redireciona para /login caso não autenticado */
function Protected({ children }: { children: React.ReactNode }) {
  const [ok, setOk] = useState<null | boolean>(null);
  const { handleError } = useApiErrorHandler();

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        await api.auth.me();
        if (alive) setOk(true);
      } catch (err) {
        handleError(err, { fallbackMessage: "Sessão expirada" });
        if (alive) setOk(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, [handleError]);

  if (ok === null) {
    return <div style={{ padding: 24 }}>Carregando…</div>;
  }
  return <>{children}</>;
}

/** Resolve /agentes/dashboard → /agentes/:agentId/dashboard */
function AgenteResolver() {
  const navigate = useNavigate();
  const { handleError } = useApiErrorHandler();

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const agents = await api.agents.list();
        if (!alive) return;
        if (agents.length === 0) {
          navigate('/agentes/sem-agente', { replace: true });
        } else {
          navigate(`/agentes/${agents[0].id}/dashboard`, { replace: true });
        }
      } catch (err) {
        handleError(err, { fallbackMessage: 'Erro ao carregar agente' });
      }
    })();
    return () => { alive = false; };
  }, [navigate, handleError]);

  return <div style={{ padding: 24 }}>Carregando agente…</div>;
}

/** Tela exibida quando o usuário não tem nenhum runner provisionado */
function AgenteSemRunner() {
  const navigate = useNavigate();
  return (
    <div style={{ minHeight: '100vh', background: '#0d0f14', display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: 'system-ui, sans-serif' }}>
      <div style={{ maxWidth: 480, padding: 40, textAlign: 'center' }}>
        <div style={{ fontSize: 40, marginBottom: 16 }}>🤖</div>
        <div style={{ fontSize: 22, fontWeight: 500, color: '#e8e4d9', marginBottom: 8 }}>Nenhum agente provisionado</div>
        <div style={{ fontSize: 14, color: '#8a8070', marginBottom: 32, lineHeight: 1.6 }}>
          Você ainda não tem um agente local registrado. Provisione um agente para começar a usar o painel Orion.
        </div>
        <button
          onClick={() => navigate('/')}
          style={{ padding: '10px 24px', background: '#c9a84c', color: '#0d0f14', border: 'none', borderRadius: 4, fontSize: 13, fontWeight: 600, cursor: 'pointer' }}
        >
          Voltar ao CRM
        </button>
      </div>
    </div>
  );
}

/** Layout do app autenticado (Sidebar + Header + Outlet) */
function AppShell() {
  return (
    <SidebarProvider>
      <div className="flex min-h-screen w-full">
        <AppSidebar />

        <div className="flex-1 flex flex-col">
          <header className="h-12 flex items-center border-b bg-background">
            <SidebarTrigger className="ml-2" />
          </header>

          <main className="flex-1">
            <Outlet />
          </main>
        </div>
      </div>
    </SidebarProvider>
  );
}

const App = () => (
  <QueryClientProvider client={queryClient}>
    <BrowserRouter>
      <RateLimitModalProvider>
        <LeadsProvider>
          <ThemeProvider>
            <TooltipProvider>
              <Toaster />
              <Sonner />

              <Routes>
                {/* Rota pública */}
                <Route path="/login" element={<Login />} />

                {/* Rotas privadas com layout do app */}
                <Route
                  element={
                    <Protected>
                      <AppShell />
                    </Protected>
                  }
                >
                  <Route path="/test" element={<TestContext />} />
                  <Route path="/" element={<Index />} />
                  <Route path="/dashboard" element={<Dashboard />} />
                  <Route path="/prospeccao" element={<Prospeccao />} />
                  <Route path="/assistente-ia" element={<AssistenteIA />} />
                  <Route path="/pesquisa" element={<Pesquisa />} />
                  <Route path="/ai-profile" element={<AiProfile />} />
                  <Route path="/minha-conta" element={<MinhaConta />} />
                  <Route path="/assinatura" element={<Assinatura />} />
                  <Route path="/uso-do-plano" element={<UsoDoPlano />} />
                </Route>

                {/* Rotas do Agente Orion (sem AppShell — layout próprio) */}
                <Route
                  element={
                    <Protected>
                      <Outlet />
                    </Protected>
                  }
                >
                  <Route path="/agentes/dashboard" element={<AgenteResolver />} />
                  <Route path="/agentes/sem-agente" element={<AgenteSemRunner />} />
                  <Route path="/agentes/:agentId/dashboard" element={<AgenteDashboard />} />
                  <Route path="/agentes/:agentId/configuracao" element={<AgenteConfiguracao />} />
                </Route>

                {/* catch-all */}
                <Route path="*" element={<NotFound />} />
              </Routes>
            </TooltipProvider>
          </ThemeProvider>
        </LeadsProvider>
      </RateLimitModalProvider>
    </BrowserRouter>
  </QueryClientProvider>
);

export default App;
