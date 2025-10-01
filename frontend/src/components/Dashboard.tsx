import { DashboardMetrics, Appointment } from "../types/crm";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { Button } from "./ui/button";
import { Calendar } from "./ui/calendar";
import { useTheme } from "../contexts/ThemeContext";
import {
  ArrowLeft,
  TrendingUp,
  Target,
  DollarSign,
  Sun,
  Moon,
  Clock,
  AlertTriangle,
  Plus,
  RefreshCw,
} from "lucide-react";
import { format } from "date-fns";
import { ptBR } from "date-fns/locale";
import { Badge } from "./ui/badge";
import { Skeleton } from "./ui/skeleton";

interface DashboardProps {
  metrics: DashboardMetrics;
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

export function Dashboard({
  metrics,
  onBack,
  todayAppointments,
  appointmentsLoading,
  appointmentsError,
  onRetryAppointments,
  onNewAppointment,
}: DashboardProps) {
  const { theme, toggleTheme } = useTheme();
  const totalLeads = metrics?.totalLeads ?? 0;
  const conversionRate = metrics?.conversionRate ?? 0;
  const salesClosed = metrics?.salesClosed ?? 0;

  return (
    <div className="min-h-screen bg-background">
      <div className="bg-card border-b border-border p-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <Button onClick={onBack} variant="ghost" size="sm" className="hover:bg-muted">
              <ArrowLeft className="w-4 h-4 mr-2" />
              Voltar ao Kanban
            </Button>
            <h1 className="text-2xl font-bold text-foreground">Dashboard de Métricas</h1>
          </div>

          <div className="flex items-center space-x-3">
            <Button
              onClick={toggleTheme}
              variant="ghost"
              size="sm"
              className="border border-border hover:bg-muted transition-smooth"
              title={theme === "dark" ? "Mudar para tema claro" : "Mudar para tema escuro"}
            >
              {theme === "dark" ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
            </Button>

            <Select defaultValue="current-month">
              <SelectTrigger className="w-48 bg-input border-border">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-popover border-border">
                <SelectItem value="last-7-days">Últimos 7 dias</SelectItem>
                <SelectItem value="current-month">Mês atual</SelectItem>
                <SelectItem value="current-quarter">Trimestre atual</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
      </div>

      <div className="p-6 space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card className="bg-card border-border">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">💰 Vendas no Mês</CardTitle>
              <DollarSign className="h-4 w-4 text-success" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-foreground">{salesClosed} vendas</div>
              <p className="text-xs text-warning">Meta de 10 vendas/mês</p>
            </CardContent>
          </Card>

          <Card className="bg-card border-border">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">📈 Progresso Meta</CardTitle>
              <Target className="h-4 w-4 text-primary" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-foreground">{conversionRate}%</div>
              <div className="w-full bg-muted rounded-full h-2 mt-2">
                <div className="bg-primary h-2 rounded-full" style={{ width: "30%" }} />
              </div>
            </CardContent>
          </Card>

          <Card className="bg-card border-border">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">📊 Ticket Médio Real</CardTitle>
              <DollarSign className="h-4 w-4 text-info" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-foreground">{totalLeads}</div>
              <p className="text-xs text-muted-foreground">Leads criados no mês</p>
            </CardContent>
          </Card>

          <Card className="bg-card border-border">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">⏱️ Dias Restantes</CardTitle>
              <Clock className="h-4 w-4 text-warning" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-foreground">12 dias</div>
              <p className="text-xs text-warning">Para bater a meta</p>
            </CardContent>
          </Card>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card className="bg-card border-border border-l-4 border-l-warning">
            <CardHeader>
              <CardTitle className="text-foreground flex items-center">
                <AlertTriangle className="w-5 h-5 mr-2 text-warning" />
                Avisos
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center space-x-3 p-3 bg-muted/50 rounded-lg">
                <Clock className="w-4 h-4 text-info" />
                <span>⏰ 2 reuniões confirmadas (14h, 16h)</span>
              </div>
              <div className="flex items-center space-x-3 p-3 bg-muted/50 rounded-lg">
                <AlertTriangle className="w-4 h-4 text-warning" />
                <span>📞 4 follow-ups críticos (&gt; 5 dias sem contato)</span>
              </div>
              <div className="flex items-center space-x-3 p-3 bg-muted/50 rounded-lg">
                <TrendingUp className="w-4 h-4 text-primary" />
                <span>🎯 Faltam 6 prospecções para meta diária (20/dia)</span>
              </div>
              <div className="flex items-center space-x-3 p-3 bg-success/10 rounded-lg border border-success/20">
                <DollarSign className="w-4 h-4 text-success" />
                <span>💡 João Silva (site 500€) - pronto para fechar!</span>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-card border-border">
            <CardHeader>
              <CardTitle className="text-foreground flex items-center justify-between">
                <span>📅 Agenda do Dia</span>
                <div className="flex items-center gap-2">
                  {appointmentsError && onRetryAppointments && (
                    <Button
                      size="sm"
                      variant="outline"
                      className="text-xs"
                      onClick={onRetryAppointments}
                    >
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
                    <div className="space-y-2">
                      <Skeleton className="h-16 w-full" />
                      <Skeleton className="h-16 w-full" />
                    </div>
                  ) : appointmentsError ? (
                    <p className="text-sm text-destructive">
                      Não foi possível carregar as reuniões de hoje.
                    </p>
                  ) : todayAppointments.length === 0 ? (
                    <p className="text-sm text-muted-foreground">
                      Nenhum compromisso agendado para hoje.
                    </p>
                  ) : (
                    <div className="space-y-2">
                      {todayAppointments.map((appointment) => {
                        const start = new Date(appointment.startTime);
                        const time = format(start, "HH:mm");
                        const leadLabel =
                          appointment.leadName || appointment.leadCompany || "Lead sem nome";

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

        <Card className="bg-card border-border">
          <CardHeader>
            <CardTitle className="text-foreground">🔥 Funil Simplificado</CardTitle>
          </CardHeader>
          <CardContent className="py-8">
            <div className="flex flex-col items-center space-y-1">
              <div className="relative w-full max-w-md">
                <div
                  className="bg-primary/90 text-primary-foreground flex items-center justify-between px-6 py-4 text-sm font-medium"
                  style={{ clipPath: "polygon(0% 0%, 100% 0%, 95% 100%, 5% 100%)", width: "100%" }}
                >
                  <div className="flex items-center space-x-2">
                    <span>🔍</span>
                    <span>Prospectados</span>
                  </div>
                  <span className="font-bold">18 leads</span>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
