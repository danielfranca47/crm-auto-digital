import { useMemo, useState } from "react";
import { Calendar } from "./ui/calendar";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Button } from "./ui/button";
import { CalendarDays, List, Plus, RefreshCw } from "lucide-react";
import { Badge } from "./ui/badge";
import { format, isSameDay } from "date-fns";
import { ptBR } from "date-fns/locale";
import { useAppointments } from "@/hooks/useAppointments";
import { Appointment } from "@/types/crm";
import { Skeleton } from "./ui/skeleton";
import { ScheduleAppointmentDialog } from "./ScheduleAppointmentDialog";

const eventTypeColors: Record<Appointment["type"], string> = {
  meeting: "bg-primary text-primary-foreground",
  call: "bg-success text-success-foreground",
  "follow-up": "bg-warning text-warning-foreground",
  presentation: "bg-info text-info-foreground",
};

const eventTypeLabels: Record<Appointment["type"], string> = {
  meeting: "Reunião",
  call: "Ligação",
  "follow-up": "Follow-up",
  presentation: "Apresentação",
};

function monthRange(date: Date) {
  const start = new Date(date.getFullYear(), date.getMonth(), 1, 0, 0, 0, 0);
  const end = new Date(date.getFullYear(), date.getMonth() + 1, 0, 23, 59, 59, 999);
  return { start: start.toISOString(), end: end.toISOString() };
}

export function ScheduleView() {
  const [viewMode, setViewMode] = useState<"calendar" | "list">("calendar");
  const [selectedDate, setSelectedDate] = useState<Date>(new Date());
  const [isDialogOpen, setIsDialogOpen] = useState(false);

  // 🔧 Passa SEMPRE um intervalo (o mês do dia selecionado)
  const { start, end } = monthRange(selectedDate);
  const {
    data: appointments = [],
    isLoading,
    isError,
    refetch,
  } = useAppointments({ start, end });

  const normalized = useMemo(() => {
    return appointments.map((appointment) => {
      const date = new Date(appointment.startTime);
      return {
        ...appointment,
        date,
        time: format(date, "HH:mm"),
        label: appointment.title || eventTypeLabels[appointment.type],
        leadName:
          appointment.leadName || appointment.leadCompany || "Lead sem nome",
      };
    });
  }, [appointments]);

  const filteredEvents = useMemo(() => {
    if (viewMode === "calendar") {
      return normalized.filter((event) => isSameDay(event.date, selectedDate));
    }
    return [...normalized].sort((a, b) => a.date.getTime() - b.date.getTime());
  }, [normalized, viewMode, selectedDate]);

  const hasEventsOnDate = (date: Date) => {
    return normalized.some((event) => isSameDay(event.date, date));
  };

  return (
    <Card className="bg-card border-border h-full">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-foreground">Agenda</CardTitle>
          <div className="flex items-center gap-2">
            {isError && (
              <Button
                variant="outline"
                size="sm"
                className="h-8"
                onClick={() => refetch()}
              >
                <RefreshCw className="w-4 h-4 mr-2" />
                Tentar novamente
              </Button>
            )}
            <Button
              variant={viewMode === "calendar" ? "default" : "outline"}
              size="sm"
              onClick={() => setViewMode("calendar")}
              className="h-8"
            >
              <CalendarDays className="w-4 h-4" />
            </Button>
            <Button
              variant={viewMode === "list" ? "default" : "outline"}
              size="sm"
              onClick={() => setViewMode("list")}
              className="h-8"
            >
              <List className="w-4 h-4" />
            </Button>
            <Button size="sm" className="h-8" onClick={() => setIsDialogOpen(true)}>
              <Plus className="w-4 h-4 mr-1" />
              Novo
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="space-y-4">
            <Skeleton className="h-72 w-full" />
            <Skeleton className="h-24 w-full" />
          </div>
        ) : isError ? (
          <p className="text-sm text-destructive text-center py-4">
            Não foi possível carregar os compromissos.
          </p>
        ) : viewMode === "calendar" ? (
          <div className="space-y-4">
            <Calendar
              mode="single"
              selected={selectedDate}
              onSelect={(date) => date && setSelectedDate(date)}
              className="rounded-md border border-border pointer-events-auto"
              modifiers={{
                hasEvents: (date) => hasEventsOnDate(date),
              }}
              modifiersStyles={{
                hasEvents: {
                  fontWeight: "bold",
                  backgroundColor: "hsl(var(--primary) / 0.1)",
                },
              }}
            />
            <div className="space-y-2">
              <h4 className="font-medium text-foreground">
                {format(selectedDate, "dd 'de' MMMM", { locale: ptBR })}
              </h4>
              {filteredEvents.length > 0 ? (
                <div className="space-y-2">
                  {filteredEvents.map((event) => (
                    <div
                      key={event.id}
                      className="p-3 rounded-lg border border-border bg-muted/30 hover:bg-muted/50 transition-smooth"
                    >
                      <div className="flex items-start justify-between">
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            <Badge className={eventTypeColors[event.type]}>
                              {eventTypeLabels[event.type]}
                            </Badge>
                            <span className="text-sm font-medium text-foreground">
                              {event.time}
                            </span>
                          </div>
                          <p className="text-sm text-foreground font-medium">
                            {event.label}
                          </p>
                          <p className="text-xs text-muted-foreground">
                            Lead: {event.leadName}
                          </p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground text-center py-4">
                  Nenhum evento agendado para esta data
                </p>
              )}
            </div>
          </div>
        ) : (
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {filteredEvents.map((event) => (
              <div
                key={event.id}
                className="p-3 rounded-lg border border-border bg-muted/30 hover:bg-muted/50 transition-smooth"
              >
                <div className="flex items-start justify-between">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <Badge className={eventTypeColors[event.type]}>
                        {eventTypeLabels[event.type]}
                      </Badge>
                      <span className="text-sm text-muted-foreground">
                        {format(event.date, "dd/MM")} às {event.time}
                      </span>
                    </div>
                    <p className="text-sm text-foreground font-medium">
                      {event.label}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      Lead: {event.leadName}
                    </p>
                  </div>
                </div>
              </div>
            ))}
            {filteredEvents.length === 0 && (
              <p className="text-sm text-muted-foreground text-center py-8">
                Nenhum evento agendado
              </p>
            )}
          </div>
        )}
      </CardContent>
      <ScheduleAppointmentDialog
        open={isDialogOpen}
        onOpenChange={setIsDialogOpen}
        initialDate={selectedDate}
        onSuccess={(appointment) => {
          setSelectedDate(new Date(appointment.startTime));
        }}
      />
    </Card>
  );
}
