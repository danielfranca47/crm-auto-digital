import { useState } from "react";
import { CalendarDays, Calendar, Clock, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScheduleView } from "@/components/ScheduleView";
import { WeekView } from "@/components/WeekView";
import { DayView } from "@/components/DayView";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/services/api";
import { appointmentsKeys } from "@/hooks/useAppointments";
import { useToast } from "@/hooks/use-toast";

type ViewMode = "monthly" | "weekly" | "daily";

const viewOptions: { mode: ViewMode; label: string; icon: React.ElementType }[] = [
  { mode: "monthly", label: "Mensal", icon: CalendarDays },
  { mode: "weekly", label: "Semanal", icon: Calendar },
  { mode: "daily", label: "Diária", icon: Clock },
];

const Agenda = () => {
  const [viewMode, setViewMode] = useState<ViewMode>("monthly");
  const [isSyncing, setIsSyncing] = useState(false);
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const { data: googleStatus } = useQuery({
    queryKey: ["googleCalendarStatus"],
    queryFn: () => api.googleCalendar.getStatus(),
    staleTime: 60_000,
  });

  const googleConnected = googleStatus?.connected === true;

  async function handleSync() {
    setIsSyncing(true);
    try {
      const now = new Date();
      const start = new Date(now.getFullYear(), now.getMonth(), 1).toISOString();
      const end = new Date(now.getFullYear(), now.getMonth() + 1, 0, 23, 59, 59).toISOString();
      await api.googleCalendar.sync(start, end);
      queryClient.invalidateQueries({ queryKey: appointmentsKeys.all });
      toast({ title: "Agenda sincronizada com Google Calendar" });
    } catch {
      toast({
        title: "Erro ao sincronizar",
        description: "Não foi possível importar eventos do Google Calendar.",
        variant: "destructive",
      });
    } finally {
      setIsSyncing(false);
    }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-3rem)] p-4 gap-4">
      {/* Header */}
      <div className="flex items-center justify-between flex-shrink-0">
        <h1 className="text-xl font-semibold text-foreground">Agenda</h1>
        <div className="flex items-center gap-2">
          {googleConnected && (
            <Button
              variant="outline"
              size="sm"
              className="h-8 gap-1.5"
              onClick={handleSync}
              disabled={isSyncing}
            >
              <RefreshCw className={`h-3.5 w-3.5 ${isSyncing ? "animate-spin" : ""}`} />
              <span className="hidden sm:inline">Sincronizar Google</span>
            </Button>
          )}
          <div className="flex rounded-md border border-border overflow-hidden">
            {viewOptions.map(({ mode, label, icon: Icon }) => (
              <Button
                key={mode}
                variant={viewMode === mode ? "default" : "ghost"}
                size="sm"
                className="rounded-none h-8 gap-1.5 px-3"
                onClick={() => setViewMode(mode)}
              >
                <Icon className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">{label}</span>
              </Button>
            ))}
          </div>
        </div>
      </div>

      {/* Vista actual */}
      <div className="flex-1 min-h-0">
        {viewMode === "monthly" && (
          <div className="h-full overflow-auto">
            <ScheduleView />
          </div>
        )}
        {viewMode === "weekly" && <WeekView />}
        {viewMode === "daily" && <DayView />}
      </div>
    </div>
  );
};

export default Agenda;
