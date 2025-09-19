import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import Index from "./pages/Index";
import Dashboard from "./pages/Dashboard";
import Prospeccao from "./pages/Prospeccao";
import AssistenteIA from "./pages/AssistenteIA";
import Pesquisa from "./pages/Pesquisa";
import NotFound from "./pages/NotFound";
import { ThemeProvider } from "./contexts/ThemeContext";
import { LeadsProvider } from "./contexts/LeadsContext";
import { AppSidebar } from "./components/AppSidebar";
import TestContext from './tests/TestContext';

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <LeadsProvider>
      <ThemeProvider>
        <TooltipProvider>
        <Toaster />
        <Sonner />
        <BrowserRouter>
          <SidebarProvider>
            <div className="flex min-h-screen w-full">
              <AppSidebar />
              
              <div className="flex-1 flex flex-col">
                <header className="h-12 flex items-center border-b bg-background">
                  <SidebarTrigger className="ml-2" />
                </header>

                <main className="flex-1">
                  <Routes>
                    <Route path="/test" element={<TestContext />} />
                    <Route path="/" element={<Index />} />
                    <Route path="/dashboard" element={<Dashboard />} />
                    <Route path="/prospeccao" element={<Prospeccao />} />
                    <Route path="/assistente-ia" element={<AssistenteIA />} />
                    <Route path="/pesquisa" element={<Pesquisa />} />
                    {/* ADD ALL CUSTOM ROUTES ABOVE THE CATCH-ALL "*" ROUTE */}
                    <Route path="*" element={<NotFound />} />
                  </Routes>
                </main>
              </div>
            </div>
          </SidebarProvider>
        </BrowserRouter>
        </TooltipProvider>
      </ThemeProvider>
    </LeadsProvider>
  </QueryClientProvider>
);

export default App;
