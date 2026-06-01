import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, Navigate, useParams, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useEffect } from "react";
import Index from "./pages/Index";
import NotFound from "./pages/NotFound";
import ProfessionalWebsites from "./pages/ProfessionalWebsites";
import SchedulingDemo from "./pages/SchedulingDemo";
import AIWhatsAppAutomation from "./pages/AIWhatsAppAutomation";
import ComingSoon from "./pages/ComingSoon";
import CRMLanding from "./pages/CRMLanding";
import SEOHead from "./components/SEOHead";

const queryClient = new QueryClient();

const LanguageRoute = ({ children }: { children: React.ReactNode }) => {
  const { lang } = useParams();
  const { i18n } = useTranslation();
  const navigate = useNavigate();

  useEffect(() => {
    const supportedLanguages = ['en', 'pt', 'es'];
    
    if (lang && supportedLanguages.includes(lang)) {
      if (i18n.language !== lang) {
        i18n.changeLanguage(lang);
      }
    } else if (lang) {
      // Invalid language, redirect to English
      navigate('/en' + window.location.pathname.replace(`/${lang}`, ''), { replace: true });
    }
  }, [lang, i18n, navigate]);

  return <>{children}</>;
};

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <SEOHead />
      <Toaster />
      <Sonner />
      <BrowserRouter>
        <Routes>
          {/* Redirect root to default language */}
          <Route path="/" element={<Navigate to="/en" replace />} />

          {/* Landing page do produto CRM — definida ANTES de /:lang para evitar conflito */}
          <Route path="/crm" element={<CRMLanding />} />

          {/* Language-specific routes */}
          <Route path="/:lang" element={
            <LanguageRoute>
              <Index />
            </LanguageRoute>
          } />
          
          <Route path="/:lang/professional-websites" element={
            <LanguageRoute>
              <ProfessionalWebsites />
            </LanguageRoute>
          } />
          
          <Route path="/:lang/scheduling-demo" element={
            <LanguageRoute>
              <SchedulingDemo />
            </LanguageRoute>
          } />
          
          <Route path="/:lang/ai-whatsapp-automation" element={
            <LanguageRoute>
              <AIWhatsAppAutomation />
            </LanguageRoute>
          } />

          <Route path="/:lang/coming-soon" element={
            <LanguageRoute>
              <ComingSoon />
            </LanguageRoute>
          } />
          
          {/* ADD ALL CUSTOM ROUTES ABOVE THE CATCH-ALL "*" ROUTE */}
          <Route path="*" element={<NotFound />} />
        </Routes>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
