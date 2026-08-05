import { useMemo, useState, useEffect } from "react";
import {
  startOfWeek,
  endOfWeek,
  eachDayOfInterval,
  format,
  isSameDay,
  addWeeks,
  subWeeks,
  getHours,
  getMinutes,
  startOfDay,
  addMinutes,
} from "date-fns";
import { ptBR } from "date-fns/locale";
import { ChevronLeft, ChevronRight, Plus, Globe } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useAppointments } from "@/hooks/useAppointments";
import { useAgendaTimezoneMode } from "@/hooks/useAgendaTimezoneMode";
import { toBusinessTimezoneDate, getBusinessRangeBounds, getTimezoneCityLabel } from "@/lib/timezone";
import { ScheduleAppointmentDialog } from "@/components/ScheduleAppointmentDialog";
import type { Appointment, AppointmentType } from "@/types/crm";

const START_HOUR = 7;
const END_HOUR = 21;
const SLOT_HEIGHT = 44; // px por slot de 30min
const HALF_HOURS = (END_HOUR - START_HOUR) * 2;
const TOTAL_HEIGHT = HALF_HOURS * SLOT_HEIGHT;

const EVENT_COLORS: Record<AppointmentType, string> = {
  meeting: "bg-primary/85 text-primary-foreground border-primary",
  call: "bg-green-600/85 text-white border-green-600",
  "follow-up": "bg-amber-500/85 text-white border-amber-500",
  presentation: "bg-blue-500/85 text-white border-blue-500",
};

function slotTopPx(date: Date): number {
  const mins = (getHours(date) - START_HOUR) * 60 + getMinutes(date);
  return (mins / 30) * SLOT_HEIGHT;
}

function durationPx(startTime: string, endTime: string | null | undefined): number {
  const start = new Date(startTime);
  const end = endTime ? new Date(endTime) : addMinutes(start, 60);
  const durationMins = Math.max(30, (end.getTime() - start.getTime()) / 60000);
  return (durationMins / 30) * SLOT_HEIGHT;
}

export function WeekView() {
  const [weekStart, setWeekStart] = useState(() =>
    startOfWeek(new Date(), { weekStartsOn: 1 })
  );
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogInitialDate, setDialogInitialDate] = useState<Date>(new Date());
  const [editingAppointment, setEditingAppointment] = useState<Appointment | null>(null);
  const [nowTop, setNowTop] = useState<number | null>(null);

  const weekEnd = endOfWeek(weekStart, { weekStartsOn: 1 });
  const days = useMemo(
    () => eachDayOfInterval({ start: weekStart, end: weekEnd }),
    [weekStart, weekEnd]
  );

  const { mode, toggle, mismatched, activeTimezone, businessTimezone, browserTimezone } =
    useAgendaTimezoneMode();

  const queryBounds = useMemo(
    () => getBusinessRangeBounds(weekStart, weekEnd, businessTimezone),
    [weekStart, weekEnd, businessTimezone]
  );

  const { data: appointments = [], refetch } = useAppointments({
    start: queryBounds.start.toISOString(),
    end: queryBounds.end.toISOString(),
  });

  // Indicador de hora actual (no fuso activo — navegador por defeito, ou negócio se alternado)
  useEffect(() => {
    function updateNow() {
      const now = toBusinessTimezoneDate(new Date(), activeTimezone);
      const mins = (getHours(now) - START_HOUR) * 60 + getMinutes(now);
      setNowTop(mins >= 0 && mins <= HALF_HOURS * 30 ? (mins / 30) * SLOT_HEIGHT : null);
    }
    updateNow();
    const id = setInterval(updateNow, 60_000);
    return () => clearInterval(id);
  }, [activeTimezone]);

  // Slots de 30 min para referência de tempo
  const timeSlots = useMemo(() => {
    const base = startOfDay(new Date());
    return Array.from({ length: HALF_HOURS }, (_, i) =>
      addMinutes(base, START_HOUR * 60 + i * 30)
    );
  }, []);

  function openCreate(day: Date, slotIndex: number) {
    const d = new Date(day);
    d.setHours(START_HOUR + Math.floor((slotIndex * 30) / 60), (slotIndex * 30) % 60, 0, 0);
    setEditingAppointment(null);
    setDialogInitialDate(d);
    setDialogOpen(true);
  }

  function openEdit(appointment: Appointment) {
    setEditingAppointment(appointment);
    setDialogInitialDate(new Date(appointment.startTime));
    setDialogOpen(true);
  }

  const isCurrentWeek = isSameDay(startOfWeek(new Date(), { weekStartsOn: 1 }), weekStart);

  return (
    <div className="flex flex-col h-full">
      {/* Barra de navegação */}
      <div className="flex items-center gap-2 mb-3 flex-shrink-0">
        <Button variant="outline" size="sm" onClick={() => setWeekStart(subWeeks(weekStart, 1))}>
          <ChevronLeft className="h-4 w-4" />
        </Button>
        <Button
          variant={isCurrentWeek ? "default" : "outline"}
          size="sm"
          onClick={() => setWeekStart(startOfWeek(new Date(), { weekStartsOn: 1 }))}
        >
          Hoje
        </Button>
        <Button variant="outline" size="sm" onClick={() => setWeekStart(addWeeks(weekStart, 1))}>
          <ChevronRight className="h-4 w-4" />
        </Button>
        <span className="text-sm font-medium text-muted-foreground ml-1">
          {format(weekStart, "dd MMM", { locale: ptBR })} –{" "}
          {format(weekEnd, "dd MMM yyyy", { locale: ptBR })}
        </span>
        {mismatched && (
          <Button variant="outline" size="sm" className="h-8 ml-2" onClick={toggle}>
            <Globe className="h-4 w-4 mr-1" />
            {mode === "browser"
              ? `Ver: ${getTimezoneCityLabel(browserTimezone)}`
              : `Ver: ${getTimezoneCityLabel(businessTimezone)}`}
          </Button>
        )}
        <Button
          size="sm"
          className="ml-auto h-8"
          onClick={() => {
            setEditingAppointment(null);
            setDialogInitialDate(new Date());
            setDialogOpen(true);
          }}
        >
          <Plus className="h-4 w-4 mr-1" />
          Novo
        </Button>
      </div>

      {/* Grade da semana */}
      <div className="flex-1 overflow-auto rounded-md border border-border">
        <div className="min-w-[640px]">
          {/* Cabeçalho com os dias */}
          <div
            className="grid sticky top-0 bg-background z-20 border-b border-border"
            style={{ gridTemplateColumns: "52px repeat(7, 1fr)" }}
          >
            <div className="border-r border-border" />
            {days.map((day) => {
              const isToday = isSameDay(day, new Date());
              return (
                <div
                  key={day.toISOString()}
                  className={`text-center py-2 border-r border-border last:border-r-0 ${isToday ? "bg-primary/5" : ""}`}
                >
                  <div className="text-xs uppercase text-muted-foreground font-medium">
                    {format(day, "EEE", { locale: ptBR })}
                  </div>
                  <div
                    className={`text-base font-bold ${isToday ? "text-primary" : "text-foreground"}`}
                  >
                    {format(day, "dd")}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Corpo com slots e eventos */}
          <div
            className="grid"
            style={{ gridTemplateColumns: "52px repeat(7, 1fr)" }}
          >
            {/* Coluna de horas */}
            <div className="relative border-r border-border" style={{ height: TOTAL_HEIGHT }}>
              {timeSlots.map((slot, i) => (
                <div
                  key={i}
                  className="absolute right-2 text-[10px] text-muted-foreground leading-none select-none"
                  style={{ top: i * SLOT_HEIGHT - 5 }}
                >
                  {i % 2 === 0 ? format(slot, "HH:mm") : ""}
                </div>
              ))}
            </div>

            {/* Colunas dos dias */}
            {days.map((day) => {
              const dayEvents = appointments.filter((a) =>
                isSameDay(toBusinessTimezoneDate(a.startTime, activeTimezone), day)
              );
              const isToday = isSameDay(day, new Date());

              return (
                <div
                  key={day.toISOString()}
                  className={`relative border-r border-border last:border-r-0 ${isToday ? "bg-primary/5" : ""}`}
                  style={{ height: TOTAL_HEIGHT }}
                >
                  {/* Slots de fundo (clicáveis) */}
                  {timeSlots.map((_, i) => (
                    <div
                      key={i}
                      className={`absolute w-full cursor-pointer hover:bg-primary/8 transition-colors ${
                        i % 2 === 0
                          ? "border-t border-border/40"
                          : "border-t border-dashed border-border/20"
                      }`}
                      style={{ top: i * SLOT_HEIGHT, height: SLOT_HEIGHT }}
                      onClick={() => openCreate(day, i)}
                    />
                  ))}

                  {/* Indicador de hora actual */}
                  {isToday && nowTop !== null && (
                    <div
                      className="absolute left-0 right-0 z-10 pointer-events-none"
                      style={{ top: nowTop }}
                    >
                      <div className="h-px bg-red-500 w-full" />
                      <div className="absolute -top-1 -left-0.5 h-2 w-2 rounded-full bg-red-500" />
                    </div>
                  )}

                  {/* Eventos */}
                  {dayEvents.map((event) => {
                    const start = toBusinessTimezoneDate(event.startTime, activeTimezone);
                    const top = slotTopPx(start);
                    const height = durationPx(event.startTime, event.endTime);
                    if (top >= TOTAL_HEIGHT || top < 0) return null;
                    const isGoogle = event.source === "google";
                    return (
                      <div
                        key={event.id}
                        className={`absolute left-0.5 right-0.5 rounded border text-xs overflow-hidden z-10 px-1 py-0.5 ${EVENT_COLORS[event.type]} ${isGoogle ? "cursor-default opacity-80" : "cursor-pointer"}`}
                        style={{ top: top + 1, height: Math.max(height - 2, 22) }}
                        onClick={(e) => {
                          e.stopPropagation();
                          if (!isGoogle) openEdit(event);
                        }}
                      >
                        <div className="font-semibold truncate leading-tight flex items-center gap-1">
                          {format(start, "HH:mm")} {event.title}
                          {isGoogle && (
                            <Badge className="text-[8px] px-1 py-0 h-3 bg-white/20 text-inherit border-white/30 shrink-0">
                              Google
                            </Badge>
                          )}
                        </div>
                        {height > 40 && event.leadName && (
                          <div className="truncate opacity-80 leading-tight">{event.leadName}</div>
                        )}
                      </div>
                    );
                  })}
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <ScheduleAppointmentDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        initialDate={dialogInitialDate}
        appointmentToEdit={editingAppointment}
        onSuccess={() => refetch()}
      />
    </div>
  );
}
