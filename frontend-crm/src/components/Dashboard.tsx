import { Appointment } from "../types/crm";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Button } from "./ui/button";
import { Calendar } from "./ui/calendar";
import { useTheme } from "../contexts/ThemeContext";
import {
  ArrowLeft,
  Sun,
  Moon,
  Clock,
  Plus,
  RefreshCw,
  Sparkles,
} from "lucide-react";
import { format } from "date-fns";
import { ptBR } from "date-fns/locale";
import { useMemo } from "react";
import { useLeads } from "@/contexts/LeadsContext";
import { Badge } from "./ui/badge";
import { Skeleton } from "./ui/skeleton";
import { Link } from "react-router-dom";
import { FunilAgente } from "@/components/agente/FunilAgente";
import { LeadsQuentes } from "@/components/agente/LeadsQuentes";
import type { AiProfile } from "@/services/api";
import type { FunilItem, LeadQuente } from "@/types/agente";

// ─── Helpers ──────────────────────────────────────────────────

function initials(name: string): string {
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map((s) => s[0]?.toUpperCase() ?? "")
    .join("");
}

function computeFunil(leads: any[]): FunilItem[] {
  const active = leads.filter((l) => l.category !== "archived");
  const total = active.length || 1;

  const f1 = active.filter((l) => ["to-prospect", "prospecting"].includes(l.category)).length;
  const f2 = active.filter((l) => ["qualified"].includes(l.category)).length;
  const f3 = active.filter((l) => ["closing"].includes(l.category)).length;
  const ag = active.filter((l) => ["scheduled", "meeting"].includes(l.category)).length;

  const pct = (n: number) => Math.round((n / total) * 100);

  return [
    { stage: "entrada", label: "Ent", count: active.length, pct: 100, color: "var(--o-sub)" },
    { stage: "f1", label: "F1", count: f1 + f2 + f3 + ag, pct: pct(f1 + f2 + f3 + ag), color: "var(--o-cold)" },
    { stage: "f2", label: "F2", count: f2 + f3 + ag, pct: pct(f2 + f3 + ag), color: "var(--o-warn)" },
    { stage: "f3", label: "F3", count: f3 + ag, pct: pct(f3 + ag), color: "var(--o-purple)" },
    { stage: "ag", label: "Ag", count: ag, pct: pct(ag), color: "var(--o-active)" },
  ];
}

function computeLeadsQuentes(leads: any[]): LeadQuente[] {
  const active = leads.filter((l) => l.category !== "archived").slice(0, 5);

  return active.map((l) => {
    const name = l.contactName || l.companyName || "Lead";
    const cat = l.category ?? "";
    const stageMap: Record<string, string> = {
      "to-prospect": "F1 · Entrada",
      prospecting: "F1 · Perfil",
      qualified: "F2 · Dor",
      closing: "F3 · 4Ps",
      scheduled: "Agendamento",
    };
    const stage = stageMap[cat] ?? cat;
    const scoreMap: Record<string, number> = {
      scheduled: 90, closing: 75, qualified: 55, prospecting: 35, "to-prospect": 20,
    };
    const score = scoreMap[cat] ?? 30;
    const temp: "hot" | "warm" | "cold" = score >= 70 ? "hot" : score >= 45 ? "warm" : "cold";
    return { id: l.id, name, initials: initials(name), stage, score, temp };
  });
}

// ─── Props ────────────────────────────────────────────────────

interface DashboardProps {
  profile: AiProfile | null;
  onBack: () => void;
  todayAppointments: Appointment[];
  appointmentsLoading?: boolean;
  appointmentsError?: string | null;
  onRetryAppointments?: () => void;
  onNewAppointment?: () => void;
}

const appointmentTypeColors: Record<Appointment["type"], string> = {
  meeting: "bg-primary text-primary-foreground",
  call: "bg-success text-success-foreground",
  "follow-up": "bg-warning text-warning-foreground",
  presentation: "bg-info text-info-foreground",
};

const appointmentTypeLabels: Record<Appointment["type"], string> = {
  meeting: "Reunião",
  call: "Ligação",
  "follow-up": "Follow-up",
  presentation: "Apresentação",
};

// ─── Component ────────────────────────────────────────────────

export function Dashboard({
  profile,
  onBack,
  todayAppointments,
  appointmentsLoading,
  appointmentsError,
  onRetryAppointments,
  onNewAppointment,
}: DashboardProps) {
  const { theme, toggleTheme } = useTheme();
  const { columns } = useLeads();

  const allLeads = useMemo(() => {
    const leadMap = new Map<string, any>();
    columns.forEach((column) => {
      column.leads.forEach((lead) => leadMap.set(lead.id, lead));
    });
    return Array.from(leadMap.values());
  }, [columns]);

  const activeLeads = useMemo(() => allLeads.filter((l) => l.category !== "archived"), [allLeads]);
  const qualificados = useMemo(
    () => allLeads.filter((l) => ["closing", "qualified", "scheduled"].includes(l.category)).length,
    [allLeads]
  );
  const funil = useMemo(() => computeFunil(allLeads), [allLeads]);
  const leadsQuentes = useMemo(() => computeLeadsQuentes(allLeads), [allLeads]);

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="bg-card border-b border-border p-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <Button onClick={onBack} variant="ghost" size="sm" className="hover:bg-muted">
              <ArrowLeft className="w-4 h-4 mr-2" />
              Voltar ao Kanban
            </Button>
            <h1 className="text-2xl font-bold text-foreground">Dashboard</h1>
          </div>
          <Button
            onClick={toggleTheme}
            variant="ghost"
            size="sm"
            className="border border-border hover:bg-muted"
            title={theme === "dark" ? "Mudar para tema claro" : "Mudar para tema escuro"}
          >
            {theme === "dark" ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
          </Button>
        </div>
      </div>

      <div className="p-6 space-y-6">
        {/* Identidade do Agente */}
        {profile && (
          <Card className="bg-card border-border">
            <CardContent className="pt-5">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Sparkles className="w-5 h-5 text-primary flex-shrink-0" />
                  <div>
                    <p className="font-semibold text-foreground">{profile.name || "Agente"}</p>
                    <p className="text-sm text-muted-foreground">{profile.brand_name || "—"}</p>
                  </div>
                  {profile.agent_mode && (
                    <Badge variant="outline" className="ml-2">{profile.agent_mode}</Badge>
                  )}
                  {profile.tone_of_voice && (
                    <Badge variant="outline">Tom: {profile.tone_of_voice}</Badge>
                  )}
                </div>
                <Link to="/ai-profile">
                  <Button variant="outline" size="sm">Configurar agente →</Button>
                </Link>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Stat cards (dados reais) */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card className="bg-card border-border">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Leads ativos</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-foreground">{activeLeads.length}</div>
              <p className="text-xs text-muted-foreground">total no pipeline</p>
            </CardContent>
          </Card>

          <Card className="bg-card border-border">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Qualificados</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-foreground">{qualificados}</div>
              <p className="text-xs text-muted-foreground">
                {activeLeads.length > 0
                  ? `${Math.round((qualificados / activeLeads.length) * 100)}% do total`
                  : "—"}
              </p>
            </CardContent>
          </Card>

          <Card className="bg-card border-border">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Agendamentos hoje</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-foreground">{todayAppointments.length}</div>
              <p className="text-xs text-muted-foreground">compromissos no dia</p>
            </CardContent>
          </Card>

          <Card className="bg-card border-border">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Taxa de resposta</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-foreground">—</div>
              <p className="text-xs text-muted-foreground">dados em breve</p>
            </CardContent>
          </Card>
        </div>

        {/* Funil + Agenda */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Funil */}
          <FunilAgente items={funil} />

          {/* Agenda do Dia */}
          <Card className="bg-card border-border">
            <CardHeader>
              <CardTitle className="text-foreground flex items-center justify-between">
                <span>📅 Agenda do Dia</span>
                <div className="flex items-center gap-2">
                  {appointmentsError && onRetryAppointments && (
                    <Button size="sm" variant="outline" className="text-xs" onClick={onRetryAppointments}>
                      <RefreshCw className="w-3 h-3 mr-1" />
                      Recarregar
                    </Button>
                  )}
                  <Button size="sm" className="text-xs" onClick={onNewAppointment}>
                    <Plus className="w-3 h-3 mr-1" />
                    Nova Reunião
                  </Button>
                </div>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <Calendar
                  mode="single"
                  className="rounded-md border border-border pointer-events-none opacity-70"
                  disabled
                />
                <div className="space-y-3">
                  <h4 className="font-medium text-foreground flex items-center justify-between">
                    <span>Reuniões de Hoje</span>
                    <span className="text-xs text-muted-foreground">
                      {format(new Date(), "dd 'de' MMMM", { locale: ptBR })}
                    </span>
                  </h4>

                  {appointmentsLoading ? (
                    <div className="space-y-2">
                      <Skeleton className="h-16 w-full" />
                      <Skeleton className="h-16 w-full" />
                    </div>
                  ) : appointmentsError ? (
                    <p className="text-sm text-destructive">Não foi possível carregar as reuniões de hoje.</p>
                  ) : todayAppointments.length === 0 ? (
                    <p className="text-sm text-muted-foreground">Nenhum compromisso agendado para hoje.</p>
                  ) : (
                    <div className="space-y-2">
                      {todayAppointments.map((appointment) => {
                        const start = new Date(appointment.startTime);
                        const time = format(start, "HH:mm");
                        const leadLabel = appointment.leadName || appointment.leadCompany || "Lead sem nome";
                        return (
                          <div
                            key={appointment.id}
                            className="flex items-start space-x-3 p-3 rounded-lg border border-border bg-muted/40"
                          >
                            <Badge className={appointmentTypeColors[appointment.type]}>
                              {appointmentTypeLabels[appointment.type]}
                            </Badge>
                            <div className="flex-1 space-y-1">
                              <p className="font-medium text-sm text-foreground">
                                {time} - {leadLabel}
                              </p>
                              <p className="text-xs text-muted-foreground">{appointment.title}</p>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Leads quentes */}
        <LeadsQuentes leads={leadsQuentes} />
      </div>
    </div>
  );
}
