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
import { ThemeProvider } from "./contexts/ThemeContext";
import { LeadsProvider } from "./contexts/LeadsContext";
import { AppSidebar } from "./components/AppSidebar";
import TestContext from "./tests/TestContext";
import Login from "./pages/Login"; // tem que estar exatamente assim
import { useEffect, useState } from "react";
import { api } from "./services/api";

const queryClient = new QueryClient();

/** Wrapper que valida a sessão e redireciona para /login caso não autenticado */
function Protected({ children }: { children: React.ReactNode }) {
  const [ok, setOk] = useState<null | boolean>(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        await api.auth.me();
        if (alive) setOk(true);
      } catch {
        if (alive) window.location.href = "/login";
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

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
    <LeadsProvider>
      <ThemeProvider>
        <TooltipProvider>
          <Toaster />
          <Sonner />

          <BrowserRouter>
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
                <Route path="/minha-conta" element={<MinhaConta />} />
                <Route path="/assinatura" element={<Assinatura />} />
                <Route path="/uso-do-plano" element={<UsoDoPlano />} />
              </Route>

              {/* catch-all */}
              <Route path="*" element={<NotFound />} />
            </Routes>
          </BrowserRouter>
        </TooltipProvider>
      </ThemeProvider>
    </LeadsProvider>
  </QueryClientProvider>
);

export default App;
