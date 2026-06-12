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
  FlaskConical,
  Eye,
  CalendarDays,
} from "lucide-react";
import { NavLink, useNavigate } from "react-router-dom";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
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
  { title: "Agenda", url: "/agenda", icon: CalendarDays },
  { title: "Follow-ups", url: "/follow-ups", icon: MessageSquareDot },
  { title: "Prospecção", url: "/prospeccao", icon: Search },
  { title: "Assistente IA", url: "/assistente-ia", icon: Bot },
  { title: "Pesquisa", url: "/pesquisa", icon: FileSearch },
  { title: "Playground IA", url: "/playground", icon: FlaskConical },
];

const accountItems = [
  { title: "Identidade do Agente", url: "/ai-profile", icon: Sparkles },
  { title: "Minha conta", url: "/minha-conta", icon: UserCircle },
  { title: "Uso do plano", url: "/uso-do-plano", icon: Gauge },
  { title: "Assinatura", url: "/assinatura", icon: CreditCard },
];

export function AppSidebar() {
  const navigate = useNavigate();
  const [loggingOut, setLoggingOut] = useState(false);

  const { data: spySession } = useQuery({
    queryKey: ["spy-agent-session"],
    queryFn: () => api.spyAgent.getSession(),
    refetchInterval: 60_000,
    staleTime: 30_000,
  });

  const spyStatus = (spySession as any)?.status;
  const spyDaysRemaining = (spySession as any)?.days_remaining;

  const spyBadge =
    spyStatus === "completed"
      ? { label: "Novo", className: "bg-green-500 text-white" }
      : spyStatus === "observing" && spyDaysRemaining != null
      ? { label: `${spyDaysRemaining}d`, className: "bg-blue-500 text-white" }
      : spyStatus === "analyzing"
      ? { label: "...", className: "bg-primary text-primary-foreground" }
      : null;

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
          <SidebarGroupLabel>Automação</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton asChild>
                  <NavLink to="/spy-agent" end className={getNavCls}>
                    <Eye className="mr-2 h-4 w-4" />
                    <span className="flex-1">Agente Espião</span>
                    {spyBadge && (
                      <span className={`ml-1 rounded-full px-1.5 py-0.5 text-[10px] font-semibold leading-none ${spyBadge.className}`}>
                        {spyBadge.label}
                      </span>
                    )}
                  </NavLink>
                </SidebarMenuButton>
              </SidebarMenuItem>
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
