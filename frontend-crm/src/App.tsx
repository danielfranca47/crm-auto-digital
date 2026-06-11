import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, Outlet } from "react-router-dom";
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
import TiposAgentes from "./pages/TiposAgentes";
import FollowUpCenter from "./pages/FollowUpCenter";
import FollowUpEdit from "./pages/FollowUpEdit";
import DebugAiProfile from "./pages/DebugAiProfile";
import Playground from "./pages/Playground";
import Onboarding from "./pages/Onboarding";
import SpyAgent from "./pages/SpyAgent";
import Agenda from "./pages/Agenda";
import { ThemeProvider } from "./contexts/ThemeContext";
import { LeadsProvider } from "./contexts/LeadsContext";
import { RateLimitModalProvider } from "./contexts/RateLimitModalContext";
import { AppSidebar } from "./components/AppSidebar";
import AdminGuard from "./components/AdminGuard";
import AdminLayout from "./pages/SaaSAdmin/AdminLayout";
import AdminLogin from "./pages/SaaSAdmin/AdminLogin";
import AdminDashboard from "./pages/SaaSAdmin/AdminDashboard";
import AdminInstances from "./pages/SaaSAdmin/AdminInstances";
import AdminUsers from "./pages/SaaSAdmin/AdminUsers";
import AdminAgents from "./pages/SaaSAdmin/AdminAgents";
import AdminGrowth from "./pages/SaaSAdmin/AdminGrowth";
import AdminFinancial from "./pages/SaaSAdmin/AdminFinancial";
import AdminSettings from "./pages/SaaSAdmin/AdminSettings";
import TestContext from "./tests/TestContext";
import Login from "./pages/Login"; // tem que estar exatamente assim
import ForgotPassword from "./pages/ForgotPassword";
import ResetPassword from "./pages/ResetPassword";
import Register from "./pages/Register";
import { useEffect, useState } from "react";
import { api } from "./services/api";
import { useApiErrorHandler } from "./hooks/useApiErrorHandler";
import UsageAlertBanner from "./components/UsageAlertBanner";

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

          <UsageAlertBanner />
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
                {/* Rotas públicas */}
                <Route path="/login" element={<Login />} />
                <Route path="/register" element={<Register />} />
                <Route path="/forgot-password" element={<ForgotPassword />} />
                <Route path="/reset-password" element={<ResetPassword />} />

                {/* Rotas privadas com layout do app (sidebar) */}
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
                  <Route path="/minha-conta" element={<MinhaConta />} />
                  <Route path="/assinatura" element={<Assinatura />} />
                  <Route path="/uso-do-plano" element={<UsoDoPlano />} />
                  <Route path="/follow-ups" element={<FollowUpCenter />} />
                  <Route path="/playground" element={<Playground />} />
                  <Route path="/agenda" element={<Agenda />} />
                </Route>

                {/* Rotas do Agente Orion — layout próprio (sem sidebar) */}
                <Route
                  element={
                    <Protected>
                      <Outlet />
                    </Protected>
                  }
                >
                  <Route path="/onboarding" element={<Onboarding />} />
                  <Route path="/spy-agent" element={<SpyAgent />} />
                  <Route path="/ai-profile" element={<AiProfile />} />
                  <Route path="/agentes-info" element={<TiposAgentes />} />
                  <Route path="/follow-ups/:leadId/edit" element={<FollowUpEdit />} />
                  <Route path="/debug-ai-profile" element={<DebugAiProfile />} />
                </Route>

                {/* Rotas do painel admin — guard próprio, sem sidebar do app */}
                <Route path="/saas-admin/login" element={<AdminLogin />} />
                <Route
                  path="/saas-admin"
                  element={
                    <AdminGuard>
                      <AdminLayout />
                    </AdminGuard>
                  }
                >
                  <Route index element={<AdminDashboard />} />
                  <Route path="instancias" element={<AdminInstances />} />
                  <Route path="usuarios" element={<AdminUsers />} />
                  <Route path="agentes" element={<AdminAgents />} />
                  <Route path="crescimento" element={<AdminGrowth />} />
                  <Route path="financeiro" element={<AdminFinancial />} />
                  <Route path="configuracoes" element={<AdminSettings />} />
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
