import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "@/components/ui/toaster";
import AdminGuard from "@/components/AdminGuard";
import AdminLayout from "@/components/AdminLayout";
import AdminLogin from "@/pages/AdminLogin";
import AdminDashboard from "@/pages/AdminDashboard";
import AdminUsers from "@/pages/AdminUsers";
import AdminInstances from "@/pages/AdminInstances";
import AdminAgents from "@/pages/AdminAgents";
import AdminGrowth from "@/pages/AdminGrowth";
import AdminFinancial from "@/pages/AdminFinancial";
import AdminSettings from "@/pages/AdminSettings";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1 },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<AdminLogin />} />
          <Route
            element={
              <AdminGuard>
                <AdminLayout />
              </AdminGuard>
            }
          >
            <Route index element={<AdminDashboard />} />
            <Route path="/instancias" element={<AdminInstances />} />
            <Route path="/usuarios" element={<AdminUsers />} />
            <Route path="/agentes" element={<AdminAgents />} />
            <Route path="/crescimento" element={<AdminGrowth />} />
            <Route path="/financeiro" element={<AdminFinancial />} />
            <Route path="/configuracoes" element={<AdminSettings />} />
          </Route>
          <Route path="*" element={<Navigate replace to="/" />} />
        </Routes>
      </BrowserRouter>
      <Toaster />
    </QueryClientProvider>
  );
}
