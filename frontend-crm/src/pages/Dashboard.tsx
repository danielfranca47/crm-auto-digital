import { useMemo, useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { isSameDay } from "date-fns";
import { Dashboard as DashboardComponent } from "../components/Dashboard";
import { useAppointments } from "@/hooks/useAppointments";
import { useBusinessTimezone } from "@/hooks/useBusinessTimezone";
import { getBusinessDayBounds, toBusinessTimezoneDate } from "@/lib/timezone";
import { useLeads } from "@/contexts/LeadsContext";
import { ScheduleAppointmentDialog } from "@/components/ScheduleAppointmentDialog";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/services/api";
import type { AiProfile } from "@/services/api";
import type { AgentConfig } from "@/types/agente";
import { SpyAgentObservationWidget } from "@/components/agente/SpyAgentObservationWidget";

const Dashboard = () => {
  const navigate = useNavigate();
  const { columns, archivedColumns } = useLeads();
  const [profile, setProfile] = useState<AiProfile | null>(null);
  const [agentConfig, setAgentConfig] = useState<AgentConfig | null>(null);

  useEffect(() => {
    api.core.getAiProfileMe().then(setProfile).catch(() => {});
    api.agente.getConfig().then(setAgentConfig).catch(() => {});
  }, []);

  const { data: spySession } = useQuery({
    queryKey: ["spy-agent-session"],
    queryFn: () => api.spyAgent.getSession(),
    staleTime: 60_000,
    refetchInterval: (query) => {
      const s = (query.state.data as any)?.status;
      return s === "observing" || s === "analyzing" ? 30_000 : false;
    },
  });

  const spyStatus = (spySession as any)?.status;
  const showSpyWidget = spyStatus === "observing" || spyStatus === "analyzing" || spyStatus === "completed";

  const businessTimezone = useBusinessTimezone();

  const todayRange = useMemo(() => {
    const { start, end } = getBusinessDayBounds(
      toBusinessTimezoneDate(new Date(), businessTimezone),
      businessTimezone
    );
    return { start: start.toISOString(), end: end.toISOString() };
  }, [businessTimezone]);
  const { data: appointments = [], isLoading, isError, error, refetch } = useAppointments(todayRange);
  const [isDialogOpen, setIsDialogOpen] = useState(false);

  const leadIds = useMemo(() => {
    const ids = new Set<string>();
    const inject = (list: typeof columns[number]["leads"]) => {
      list.forEach((lead) => ids.add(lead.id));
    };
    columns.forEach((column) => inject(column.leads));
    archivedColumns.forEach((column) => inject(column.leads));
    return ids;
  }, [columns, archivedColumns]);

  const todayAppointments = useMemo(() => {
    const today = toBusinessTimezoneDate(new Date(), businessTimezone);
    return appointments.filter((appointment) => {
      const start = toBusinessTimezoneDate(appointment.startTime, businessTimezone);
      const belongsToLead = !appointment.leadId || leadIds.has(String(appointment.leadId));
      return belongsToLead && isSameDay(start, today);
    });
  }, [appointments, leadIds, businessTimezone]);

  return (
    <>
      {showSpyWidget && spySession && (
        <div className="px-4 pt-4 max-w-5xl mx-auto">
          <SpyAgentObservationWidget session={spySession as any} />
        </div>
      )}
      <DashboardComponent
        profile={profile}
        agentConfig={agentConfig}
        onBack={() => navigate("/")}
        todayAppointments={todayAppointments}
        appointmentsLoading={isLoading}
        appointmentsError={isError ? (error instanceof Error ? error.message : "Erro ao carregar") : null}
        onRetryAppointments={() => refetch()}
        onNewAppointment={() => setIsDialogOpen(true)}
      />

      <ScheduleAppointmentDialog
        open={isDialogOpen}
        onOpenChange={setIsDialogOpen}
        initialDate={new Date()}
        onSuccess={() => refetch()}
      />
    </>
  );
};

export default Dashboard;
