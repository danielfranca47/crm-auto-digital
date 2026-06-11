import { useState } from "react";
import { CalendarDays, Calendar, Clock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScheduleView } from "@/components/ScheduleView";
import { WeekView } from "@/components/WeekView";
import { DayView } from "@/components/DayView";

type ViewMode = "monthly" | "weekly" | "daily";

const viewOptions: { mode: ViewMode; label: string; icon: React.ElementType }[] = [
  { mode: "monthly", label: "Mensal", icon: CalendarDays },
  { mode: "weekly", label: "Semanal", icon: Calendar },
  { mode: "daily", label: "Diária", icon: Clock },
];

const Agenda = () => {
  const [viewMode, setViewMode] = useState<ViewMode>("monthly");

  return (
    <div className="flex flex-col h-[calc(100vh-3rem)] p-4 gap-4">
      {/* Header */}
      <div className="flex items-center justify-between flex-shrink-0">
        <h1 className="text-xl font-semibold text-foreground">Agenda</h1>
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
