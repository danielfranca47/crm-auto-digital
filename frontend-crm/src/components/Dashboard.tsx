import { Appointment } from "../types/crm";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Button } from "./ui/button";
import { Calendar } from "./ui/calendar";
import { useTheme } from "../contexts/ThemeContext";
import { ArrowLeft, Sun, Moon, Clock, Plus, RefreshCw, Sparkles, AlertTriangle, ExternalLink } from "lucide-react";
import { format } from "date-fns";
import { ptBR } from "date-fns/locale";
import { useMemo } from "react";
import { AppointmentTimeLabel } from "./AppointmentTimeLabel";
import { useLeads } from "@/contexts/LeadsContext";
import { Badge } from "./ui/badge";
import { Skeleton } from "./ui/skeleton";
import { Link } from "react-router-dom";
import { FunilAgente } from "@/components/agente/FunilAgente";
import { LeadsQuentes } from "@/components/agente/LeadsQuentes";
import type { AiProfile } from "@/services/api";
import type { AgentConfig, FunilItem, LeadQuente } from "@/types/agente";
import { AGENT_MODE_LABELS, IDENTITY_MODE_LABELS } from "@/types/agente";

// ─── Helpers ──────────────────────────────────────────────────

function initials(name: string): string {
  return name.split(/\s+/).slice(0, 2).map((s) => s[0]?.toUpperCase() ?? "").join("");
}

function computeFunil(leads: any[]): FunilItem[] {
  const active = leads.filter((l) => l.category !== "archived");
  const total = active.length || 1;
  const f1 = active.filter((l) => ["to-prospect", "prospecting"].includes(l.category)).length;
  const f2 = active.filter((l) => l.category === "qualified").length;
  const f3 = active.filter((l) => l.category === "closing").length;
  const ag = active.filter((l) => ["scheduled", "meeting"].includes(l.category)).length;
  const pct = (n: number) => Math.round((n / total) * 100);
  return [
    { stage: "entrada", label: "Ent", count: active.length, pct: 100,                    color: "var(--o-sub)" },
    { stage: "f1",      label: "F1",  count: f1+f2+f3+ag,  pct: pct(f1+f2+f3+ag),       color: "var(--o-cold)" },
    { stage: "f2",      label: "F2",  count: f2+f3+ag,     pct: pct(f2+f3+ag),           color: "var(--o-warn)" },
    { stage: "f3",      label: "F3",  count: f3+ag,        pct: pct(f3+ag),              color: "var(--o-purple)" },
    { stage: "ag",      label: "Ag",  count: ag,           pct: pct(ag),                 color: "var(--o-active)" },
  ];
}

function computeLeadsQuentes(leads: any[]): LeadQuente[] {
  return leads
    .filter((l) => l.category !== "archived")
    .slice(0, 5)
    .map((l) => {
      const name = l.contactName || l.companyName || "Lead";
      const cat = l.category ?? "";
      const stageMap: Record<string, string> = {
        "to-prospect": "F1 · Entrada", prospecting: "F1 · Perfil",
        qualified: "F2 · Dor", closing: "F3 · 4Ps", scheduled: "Agendamento",
      };
      const scoreMap: Record<string, number> = {
        scheduled: 90, closing: 75, qualified: 55, prospecting: 35, "to-prospect": 20,
      };
      const score = scoreMap[cat] ?? 30;
      return {
        id: l.id, name, initials: initials(name), stage: stageMap[cat] ?? cat,
        score, temp: score >= 70 ? "hot" : score >= 45 ? "warm" : "cold",
      } as LeadQuente;
    });
}

// ─── Layer config helpers ──────────────────────────────────────

function layerProgress(profile: AiProfile | null, agentConfig: AgentConfig | null) {
  const c1Fields = [profile?.name, profile?.brand_name, profile?.agent_mode, profile?.identity_mode, profile?.tone_of_voice];
  const c1Done = c1Fields.filter(Boolean).length;
  const c1Total = c1Fields.length;

  const c2Fields = [
    agentConfig?.niche, agentConfig?.target_audience, agentConfig?.offer_description,
    agentConfig?.f1_questions?.length, agentConfig?.f2_questions?.length, agentConfig?.f3_questions?.length,
  ];
  const c2Done = c2Fields.filter(Boolean).length;
  const c2Total = c2Fields.length;

  const c3Checks = {
    optOut:        (agentConfig?.opt_out_keywords?.length ?? 0) > 0,
    lgpd:          !!agentConfig?.lgpd_mode,
    reactivation:  !!agentConfig?.reactivation_mode,
    mediaFallback: !!agentConfig?.media_fallback,
  };
  const c3Done = Object.values(c3Checks).filter(Boolean).length;
  const c3Total = Object.keys(c3Checks).length;
  const criticals = [!c3Checks.optOut, !c3Checks.lgpd, !c3Checks.reactivation].filter(Boolean).length;

  return { c1Done, c1Total, c2Done, c2Total, c3Done, c3Total, criticals, c3Checks };
}

// ─── Props ────────────────────────────────────────────────────

interface DashboardProps {
  profile: AiProfile | null;
  agentConfig: AgentConfig | null;
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
  meeting: "Reunião", call: "Ligação", "follow-up": "Follow-up", presentation: "Apresentação",
};

// ─── Component ────────────────────────────────────────────────

export function Dashboard({
  profile, agentConfig, onBack,
  todayAppointments, appointmentsLoading, appointmentsError,
  onRetryAppointments, onNewAppointment,
}: DashboardProps) {
  const { theme, toggleTheme } = useTheme();
  const { columns } = useLeads();

  const allLeads = useMemo(() => {
    const map = new Map<string, any>();
    columns.forEach((col) => col.leads.forEach((l) => map.set(l.id, l)));
    return Array.from(map.values());
  }, [columns]);

  const activeLeads = useMemo(() => allLeads.filter((l) => l.category !== "archived"), [allLeads]);
  const qualificados = useMemo(
    () => allLeads.filter((l) => ["closing", "qualified", "scheduled"].includes(l.category)).length,
    [allLeads]
  );

  // Pipeline conversion counts
  const f1count = useMemo(() => activeLeads.filter((l) => ["to-prospect", "prospecting"].includes(l.category)).length, [activeLeads]);
  const f2count = useMemo(() => activeLeads.filter((l) => l.category === "qualified").length, [activeLeads]);
  const f3count = useMemo(() => activeLeads.filter((l) => l.category === "closing").length, [activeLeads]);
  const agcount = useMemo(() => activeLeads.filter((l) => ["scheduled", "meeting"].includes(l.category)).length, [activeLeads]);

  const conv = (a: number, b: number) => b > 0 ? Math.round((a / b) * 100) : 0;

  const funil        = useMemo(() => computeFunil(allLeads), [allLeads]);
  const leadsQuentes = useMemo(() => computeLeadsQuentes(allLeads), [allLeads]);
  const layers       = useMemo(() => layerProgress(profile, agentConfig), [profile, agentConfig]);

  // Agent hero description line
  const heroDesc = useMemo(() => {
    const parts: string[] = [];
    if (profile?.agent_mode) parts.push(AGENT_MODE_LABELS[profile.agent_mode] ?? profile.agent_mode);
    if (agentConfig?.niche)  parts.push(agentConfig.niche);
    if (profile?.brand_name) parts.push(profile.brand_name);
    return parts.join(" · ");
  }, [profile, agentConfig]);

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
          <Button onClick={toggleTheme} variant="ghost" size="sm" className="border border-border hover:bg-muted"
            title={theme === "dark" ? "Mudar para tema claro" : "Mudar para tema escuro"}>
            {theme === "dark" ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
          </Button>
        </div>
      </div>

      <div className="p-6 space-y-6">

        {/* ── 1. Alert strip crítico ── */}
        {layers.criticals > 0 && (
          <div className="flex items-start gap-3 p-4 rounded-md bg-destructive/10 border border-destructive/30 text-destructive text-sm">
            <AlertTriangle className="w-4 h-4 mt-0.5 flex-shrink-0" />
            <span className="flex-1">
              <strong>{layers.criticals} {layers.criticals === 1 ? "item crítico" : "itens críticos"}</strong> na
              configuração do agente sem definição — opt-out, LGPD ou reativação. O agente está ativo e exposto.
            </span>
            <Link to="/ai-profile">
              <Button variant="destructive" size="sm" className="text-xs h-7">Resolver →</Button>
            </Link>
          </div>
        )}

        {/* ── 2. Agent hero melhorado ── */}
        {profile && (
          <Card className="bg-card border-border">
            <CardContent className="pt-5">
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-start gap-3">
                  <Sparkles className="w-5 h-5 text-primary mt-0.5 flex-shrink-0" />
                  <div>
                    <p className="font-semibold text-foreground text-base">{profile.name || "Agente"}</p>
                    {heroDesc && <p className="text-sm text-muted-foreground mt-0.5">{heroDesc}</p>}
                    <div className="flex flex-wrap gap-2 mt-2">
                      <Badge variant="secondary" className="text-xs">✓ Ativo</Badge>
                      {profile.agent_mode && (
                        <Badge variant="outline" className="text-xs">{AGENT_MODE_LABELS[profile.agent_mode] ?? profile.agent_mode}</Badge>
                      )}
                      {profile.identity_mode && (
                        <Badge variant="outline" className="text-xs">{IDENTITY_MODE_LABELS[profile.identity_mode] ?? profile.identity_mode}</Badge>
                      )}
                      {profile.tone_of_voice && (
                        <Badge variant="outline" className="text-xs">Tom: {profile.tone_of_voice}</Badge>
                      )}
                      {profile.timezone && (
                        <Badge variant="outline" className="text-xs">{profile.timezone}</Badge>
                      )}
                      {profile.created_at && (
                        <Badge variant="outline" className="text-xs">
                          Desde {format(new Date(profile.created_at), "dd MMM yyyy", { locale: ptBR })}
                        </Badge>
                      )}
                    </div>
                  </div>
                </div>
                <div className="flex gap-2 flex-shrink-0">
                  <Link to="/ai-profile">
                    <Button variant="outline" size="sm" className="text-xs gap-1">
                      <ExternalLink className="w-3 h-3" />
                      Configurar
                    </Button>
                  </Link>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* ── 3. Stat cards com dados reais ── */}
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
                {activeLeads.length > 0 ? `${Math.round((qualificados / activeLeads.length) * 100)}% do total` : "—"}
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

        {/* ── 4. Pipeline de conversão ── */}
        <Card className="bg-card border-border">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-foreground">Conversão do pipeline</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {[
                { label: "F1 → F2", value: conv(f2count + f3count + agcount, f1count + f2count + f3count + agcount), a: f2count + f3count + agcount, b: f1count + f2count + f3count + agcount, color: "text-blue-400" },
                { label: "F2 → F3", value: conv(f3count + agcount, f2count + f3count + agcount), a: f3count + agcount, b: f2count + f3count + agcount, color: "text-yellow-400" },
                { label: "F3 → Ag.", value: conv(agcount, f3count + agcount), a: agcount, b: f3count + agcount, color: "text-emerald-400" },
                { label: "Total ativo", value: null, a: activeLeads.length, b: null, color: "text-foreground" },
              ].map((item) => (
                <div key={item.label} className="text-center p-3 rounded-md bg-muted/40">
                  <p className="text-xs text-muted-foreground mb-1">{item.label}</p>
                  <p className={`text-2xl font-bold ${item.color}`}>
                    {item.value !== null ? `${item.value}%` : item.a}
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">
                    {item.b !== null ? `${item.a} de ${item.b}` : "leads no pipeline"}
                  </p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* ── Funil + Agenda ── */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <FunilAgente items={funil} />

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
                <Calendar mode="single" className="rounded-md border border-border pointer-events-none opacity-70" disabled />
                <div className="space-y-3">
                  <h4 className="font-medium text-foreground flex items-center justify-between">
                    <span>Reuniões de Hoje</span>
                    <span className="text-xs text-muted-foreground">
                      {format(new Date(), "dd 'de' MMMM", { locale: ptBR })}
                    </span>
                  </h4>
                  {appointmentsLoading ? (
                    <div className="space-y-2"><Skeleton className="h-16 w-full" /><Skeleton className="h-16 w-full" /></div>
                  ) : appointmentsError ? (
                    <p className="text-sm text-destructive">Não foi possível carregar as reuniões de hoje.</p>
                  ) : todayAppointments.length === 0 ? (
                    <p className="text-sm text-muted-foreground">Nenhum compromisso agendado para hoje.</p>
                  ) : (
                    <div className="space-y-2">
                      {todayAppointments.map((appt) => {
                        const label = appt.leadName || appt.leadCompany || "Lead sem nome";
                        return (
                          <div key={appt.id} className="flex items-start space-x-3 p-3 rounded-lg border border-border bg-muted/40">
                            <Badge className={appointmentTypeColors[appt.type]}>{appointmentTypeLabels[appt.type]}</Badge>
                            <div className="flex-1 space-y-1">
                              <p className="font-medium text-sm text-foreground">
                                <AppointmentTimeLabel startTime={appt.startTime} /> - {label}
                              </p>
                              <p className="text-xs text-muted-foreground">{appt.title}</p>
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

        {/* ── Leads quentes ── */}
        <LeadsQuentes leads={leadsQuentes} />

        {/* ── 5. Layer status cards ── */}
        {(profile || agentConfig) && (
          <div>
            <p className="text-xs font-mono uppercase tracking-widest text-muted-foreground mb-3">
              Estado da configuração por camada
            </p>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {/* Camada 1 */}
              <Link to="/ai-profile" className="block">
                <Card className="bg-card border-border hover:border-emerald-500/40 transition-colors cursor-pointer h-full">
                  <CardContent className="pt-5">
                    <p className="text-xs font-mono uppercase tracking-widest text-muted-foreground mb-1">Camada 1</p>
                    <p className="font-semibold text-foreground mb-1">Identidade e estratégia</p>
                    <p className="text-xs text-muted-foreground mb-3">Quem é o agente, como fala e como vende.</p>
                    <div className="h-1.5 bg-muted rounded-full mb-2">
                      <div className="h-full rounded-full bg-emerald-500 transition-all"
                        style={{ width: `${Math.round((layers.c1Done / layers.c1Total) * 100)}%` }} />
                    </div>
                    <div className="flex justify-between text-xs font-mono text-muted-foreground">
                      <span>{layers.c1Done === layers.c1Total ? "Completa" : "Incompleta"}</span>
                      <span>{layers.c1Done} / {layers.c1Total}</span>
                    </div>
                    <div className="flex flex-wrap gap-1 mt-3">
                      {[
                        { label: "Identidade", ok: !!profile?.name },
                        { label: "Empresa",    ok: !!profile?.brand_name },
                        { label: "Tipo",       ok: !!profile?.agent_mode },
                        { label: "Modo",       ok: !!profile?.identity_mode },
                        { label: "Tom",        ok: !!profile?.tone_of_voice },
                      ].map((t) => (
                        <span key={t.label} className={`text-[10px] font-mono px-1.5 py-0.5 rounded border ${
                          t.ok ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                               : "bg-destructive/10 text-destructive border-destructive/30"
                        }`}>{t.label}</span>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              </Link>

              {/* Camada 2 */}
              <Link to="/ai-profile" className="block">
                <Card className="bg-card border-border hover:border-yellow-500/40 transition-colors cursor-pointer h-full">
                  <CardContent className="pt-5">
                    <p className="text-xs font-mono uppercase tracking-widest text-muted-foreground mb-1">Camada 2</p>
                    <p className="font-semibold text-foreground mb-1">Qualificação</p>
                    <p className="text-xs text-muted-foreground mb-3">Filtros F1, F2, F3 e perguntas do agente.</p>
                    <div className="h-1.5 bg-muted rounded-full mb-2">
                      <div className="h-full rounded-full bg-yellow-500 transition-all"
                        style={{ width: `${Math.round((layers.c2Done / layers.c2Total) * 100)}%` }} />
                    </div>
                    <div className="flex justify-between text-xs font-mono text-muted-foreground">
                      <span>{Math.round((layers.c2Done / layers.c2Total) * 100)}%</span>
                      <span>{layers.c2Done} / {layers.c2Total}</span>
                    </div>
                    <div className="flex flex-wrap gap-1 mt-3">
                      {[
                        { label: "Nicho",     ok: !!agentConfig?.niche },
                        { label: "Público",   ok: !!agentConfig?.target_audience },
                        { label: "Oferta",    ok: !!agentConfig?.offer_description },
                        { label: `F1 · ${agentConfig?.f1_questions?.length ?? 0}p`, ok: (agentConfig?.f1_questions?.length ?? 0) > 0 },
                        { label: `F2 · ${agentConfig?.f2_questions?.length ?? 0}p`, ok: (agentConfig?.f2_questions?.length ?? 0) > 0 },
                        { label: `F3 · ${agentConfig?.f3_questions?.length ?? 0}p`, ok: (agentConfig?.f3_questions?.length ?? 0) > 0 },
                      ].map((t) => (
                        <span key={t.label} className={`text-[10px] font-mono px-1.5 py-0.5 rounded border ${
                          t.ok ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                               : "bg-yellow-500/10 text-yellow-400 border-yellow-500/30"
                        }`}>{t.label}</span>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              </Link>

              {/* Camada 3 */}
              <Link to="/ai-profile" className="block">
                <Card className={`bg-card border-border hover:border-purple-500/40 transition-colors cursor-pointer h-full ${
                  layers.criticals > 0 ? "border-destructive/40" : ""
                }`}>
                  <CardContent className="pt-5">
                    <p className="text-xs font-mono uppercase tracking-widest text-muted-foreground mb-1">Camada 3</p>
                    <p className="font-semibold text-foreground mb-1">Pipeline e comportamento</p>
                    <p className="text-xs text-muted-foreground mb-3">Reativação, mídia e proteção do número.</p>
                    <div className="h-1.5 bg-muted rounded-full mb-2">
                      <div className={`h-full rounded-full transition-all ${layers.criticals > 0 ? "bg-destructive" : "bg-purple-500"}`}
                        style={{ width: `${Math.round((layers.c3Done / layers.c3Total) * 100)}%` }} />
                    </div>
                    <div className={`flex justify-between text-xs font-mono ${layers.criticals > 0 ? "text-destructive" : "text-muted-foreground"}`}>
                      <span>{layers.criticals > 0 ? `${layers.criticals} críticos` : "OK"}</span>
                      <span>{layers.c3Done} / {layers.c3Total}</span>
                    </div>
                    <div className="flex flex-wrap gap-1 mt-3">
                      {[
                        { label: "Opt-out",    ok: layers.c3Checks.optOut,       critical: true },
                        { label: "LGPD",       ok: layers.c3Checks.lgpd,         critical: true },
                        { label: "Reativação", ok: layers.c3Checks.reactivation, critical: true },
                        { label: "Mídia",      ok: layers.c3Checks.mediaFallback, critical: false },
                      ].map((t) => (
                        <span key={t.label} className={`text-[10px] font-mono px-1.5 py-0.5 rounded border ${
                          t.ok
                            ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                            : t.critical
                              ? "bg-destructive/10 text-destructive border-destructive/30"
                              : "bg-yellow-500/10 text-yellow-400 border-yellow-500/30"
                        }`}>{t.label}</span>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              </Link>
            </div>
          </div>
        )}

      </div>
    </div>
  );
}
