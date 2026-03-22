import { useMemo, useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { isSameDay } from "date-fns";
import { Dashboard as DashboardComponent } from "../components/Dashboard";
import { useAppointments } from "@/hooks/useAppointments";
import { useLeads } from "@/contexts/LeadsContext";
import { ScheduleAppointmentDialog } from "@/components/ScheduleAppointmentDialog";
import { api } from "@/services/api";
import type { AiProfile } from "@/services/api";

const Dashboard = () => {
  const navigate = useNavigate();
  const { columns, archivedColumns } = useLeads();
  const [profile, setProfile] = useState<AiProfile | null>(null);

  useEffect(() => {
    api.core.getAiProfileMe().then(setProfile).catch(() => {});
  }, []);

  const todayRange = useMemo(() => {
    const start = new Date();
    start.setHours(0, 0, 0, 0);
    const end = new Date();
    end.setHours(23, 59, 59, 999);
    return { start: start.toISOString(), end: end.toISOString() };
  }, []);
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
    const today = new Date();
    return appointments.filter((appointment) => {
      const start = new Date(appointment.startTime);
      const belongsToLead = !appointment.leadId || leadIds.has(String(appointment.leadId));
      return belongsToLead && isSameDay(start, today);
    });
  }, [appointments, leadIds]);

  const handleBack = () => {
    navigate("/");
  };

  return (
    <>
      <DashboardComponent
        profile={profile}
        onBack={handleBack}
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
