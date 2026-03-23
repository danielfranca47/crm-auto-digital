import {
  BarChart3,
  Users,
  Search,
  FileSearch,
  Bot,
  LogOut,
  UserCircle,
  CreditCard,
  Gauge,
  Sparkles,
  MessageSquareDot,
} from "lucide-react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { useState } from "react";
import { api } from "@/services/api";

import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";

const items = [
  { title: "Dashboard", url: "/dashboard", icon: BarChart3 },
  { title: "CRM Comercial", url: "/", icon: Users },
  { title: "Follow-ups", url: "/follow-ups", icon: MessageSquareDot },
  { title: "Prospecção", url: "/prospeccao", icon: Search },
  { title: "Assistente IA", url: "/assistente-ia", icon: Bot },
  { title: "Pesquisa", url: "/pesquisa", icon: FileSearch },
];

const accountItems = [
  { title: "Identidade do Agente", url: "/ai-profile", icon: Sparkles },
  { title: "Minha conta", url: "/minha-conta", icon: UserCircle },
  { title: "Uso do plano", url: "/uso-do-plano", icon: Gauge },
  { title: "Assinatura", url: "/assinatura", icon: CreditCard },
];

export function AppSidebar() {
  const location = useLocation();
  const navigate = useNavigate();
  const [loggingOut, setLoggingOut] = useState(false);

  const getNavCls = ({ isActive }: { isActive: boolean }) =>
    isActive ? "bg-muted text-primary font-medium" : "hover:bg-muted/50";

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
    <Sidebar collapsible="icon">
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Navegação</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {items.map((item) => (
                <SidebarMenuItem key={item.title}>
                  <SidebarMenuButton asChild>
                    <NavLink to={item.url} end className={getNavCls}>
                      <item.icon className="mr-2 h-4 w-4" />
                      <span>{item.title}</span>
                    </NavLink>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarGroup>
          <SidebarGroupLabel>Conta</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {accountItems.map((item) => (
                <SidebarMenuItem key={item.title}>
                  <SidebarMenuButton asChild>
                    <NavLink to={item.url} end className={getNavCls}>
                      <item.icon className="mr-2 h-4 w-4" />
                      <span>{item.title}</span>
                    </NavLink>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
              <SidebarMenuItem>
                <SidebarMenuButton onClick={onLogout} disabled={loggingOut}>
                  <LogOut className="mr-2 h-4 w-4" />
                  <span>{loggingOut ? "Saindo..." : "Sair"}</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
    </Sidebar>
  );
}
