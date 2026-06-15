import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, Navigate, useParams, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useEffect } from "react";
import Index from "./pages/Index";
import NotFound from "./pages/NotFound";
import CRMLanding from "./pages/CRMLanding";
import SEOHead from "./components/SEOHead";

const queryClient = new QueryClient();

// Slugs que não são códigos de idioma — não devem disparar redirect em LanguageRoute
const NON_LANG_SLUGS = new Set(['lara-ia', 'lara-ai', 'crm']);

const LanguageRoute = ({ children }: { children: React.ReactNode }) => {
  const { lang } = useParams();
  const { i18n } = useTranslation();
  const navigate = useNavigate();

  useEffect(() => {
    if (!lang || NON_LANG_SLUGS.has(lang)) return;

    const supportedLanguages = ['en', 'pt', 'es'];
    if (supportedLanguages.includes(lang)) {
      if (i18n.language !== lang) {
        i18n.changeLanguage(lang);
      }
    } else {
      navigate('/en', { replace: true });
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
          {/* Redirect root to PT landing */}
          <Route path="/" element={<Navigate to="/lara-ia" replace />} />

          {/* Landing pages da Lara — estáticas, fora do padrão /:lang */}
          <Route path="/lara-ia" element={<CRMLanding />} />
          <Route path="/lara-ai" element={<CRMLanding lang="en" />} />
          <Route path="/crm" element={<Navigate to="/lara-ia" replace />} />

          {/* Páginas com prefixo de idioma */}
          <Route path="/:lang" element={
            <LanguageRoute>
              <Index />
            </LanguageRoute>
          } />

          <Route path="*" element={<NotFound />} />
        </Routes>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
