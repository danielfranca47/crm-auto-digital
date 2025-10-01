import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { isSameDay } from "date-fns";
import { Dashboard as DashboardComponent } from "../components/Dashboard";
import { MOCK_DASHBOARD_METRICS } from "../data/mockData";
import { useAppointments } from "@/hooks/useAppointments";
import { useLeads } from "@/contexts/LeadsContext";
import { ScheduleAppointmentDialog } from "@/components/ScheduleAppointmentDialog";

const Dashboard = () => {
  const navigate = useNavigate();
  const { columns, archivedColumns } = useLeads();
  const { data: appointments = [], isLoading, isError, error, refetch } = useAppointments();
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
        metrics={MOCK_DASHBOARD_METRICS}
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