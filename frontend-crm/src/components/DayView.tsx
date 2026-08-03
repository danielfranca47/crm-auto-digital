import { useMemo, useState, useEffect } from "react";
import {
  format,
  isSameDay,
  addDays,
  subDays,
  getHours,
  getMinutes,
  startOfDay,
  addMinutes,
} from "date-fns";
import { ptBR } from "date-fns/locale";
import { ChevronLeft, ChevronRight, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useAppointments } from "@/hooks/useAppointments";
import { useBusinessTimezone } from "@/hooks/useBusinessTimezone";
import { toBusinessTimezoneDate } from "@/lib/timezone";
import { ScheduleAppointmentDialog } from "@/components/ScheduleAppointmentDialog";
import type { Appointment, AppointmentType } from "@/types/crm";

const START_HOUR = 7;
const END_HOUR = 21;
const SLOT_HEIGHT = 56; // px por slot de 30min (mais alto que WeekView para melhor legibilidade)
const HALF_HOURS = (END_HOUR - START_HOUR) * 2;
const TOTAL_HEIGHT = HALF_HOURS * SLOT_HEIGHT;

const EVENT_COLORS: Record<AppointmentType, string> = {
  meeting: "bg-primary/85 text-primary-foreground border-primary",
  call: "bg-green-600/85 text-white border-green-600",
  "follow-up": "bg-amber-500/85 text-white border-amber-500",
  presentation: "bg-blue-500/85 text-white border-blue-500",
};

const TYPE_LABELS: Record<AppointmentType, string> = {
  meeting: "Reunião",
  call: "Ligação",
  "follow-up": "Follow-up",
  presentation: "Apresentação",
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

export function DayView() {
  const [selectedDay, setSelectedDay] = useState(() => new Date());
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogInitialDate, setDialogInitialDate] = useState<Date>(new Date());
  const [editingAppointment, setEditingAppointment] = useState<Appointment | null>(null);
  const [nowTop, setNowTop] = useState<number | null>(null);

  const dayStart = startOfDay(selectedDay);
  const dayEnd = new Date(dayStart.getTime() + 24 * 60 * 60 * 1000 - 1);

  const { data: appointments = [], refetch } = useAppointments({
    start: dayStart.toISOString(),
    end: dayEnd.toISOString(),
  });
  const businessTimezone = useBusinessTimezone();

  // Indicador de hora actual (no fuso do negócio, mesmo fuso usado para posicionar os eventos)
  useEffect(() => {
    function updateNow() {
      if (!isSameDay(selectedDay, new Date())) {
        setNowTop(null);
        return;
      }
      const now = toBusinessTimezoneDate(new Date(), businessTimezone);
      const mins = (getHours(now) - START_HOUR) * 60 + getMinutes(now);
      setNowTop(mins >= 0 && mins <= HALF_HOURS * 30 ? (mins / 30) * SLOT_HEIGHT : null);
    }
    updateNow();
    const id = setInterval(updateNow, 60_000);
    return () => clearInterval(id);
  }, [selectedDay, businessTimezone]);

  const timeSlots = useMemo(() => {
    const base = startOfDay(new Date());
    return Array.from({ length: HALF_HOURS }, (_, i) =>
      addMinutes(base, START_HOUR * 60 + i * 30)
    );
  }, []);

  function openCreate(slotIndex: number) {
    const d = new Date(selectedDay);
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

  const isToday = isSameDay(selectedDay, new Date());

  return (
    <div className="flex flex-col h-full">
      {/* Barra de navegação */}
      <div className="flex items-center gap-2 mb-3 flex-shrink-0">
        <Button variant="outline" size="sm" onClick={() => setSelectedDay(subDays(selectedDay, 1))}>
          <ChevronLeft className="h-4 w-4" />
        </Button>
        <Button
          variant={isToday ? "default" : "outline"}
          size="sm"
          onClick={() => setSelectedDay(new Date())}
        >
          Hoje
        </Button>
        <Button variant="outline" size="sm" onClick={() => setSelectedDay(addDays(selectedDay, 1))}>
          <ChevronRight className="h-4 w-4" />
        </Button>
        <span className="text-sm font-semibold text-foreground ml-1 capitalize">
          {format(selectedDay, "EEEE, dd 'de' MMMM yyyy", { locale: ptBR })}
        </span>
        <Button
          size="sm"
          className="ml-auto h-8"
          onClick={() => {
            setEditingAppointment(null);
            setDialogInitialDate(selectedDay);
            setDialogOpen(true);
          }}
        >
          <Plus className="h-4 w-4 mr-1" />
          Novo
        </Button>
      </div>

      {/* Timeline */}
      <div className="flex-1 overflow-auto rounded-md border border-border">
        <div
          className="grid"
          style={{ gridTemplateColumns: "52px 1fr" }}
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

          {/* Coluna dos eventos */}
          <div
            className={`relative ${isToday ? "bg-primary/5" : ""}`}
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
                onClick={() => openCreate(i)}
              />
            ))}

            {/* Indicador de hora actual */}
            {isToday && nowTop !== null && (
              <div
                className="absolute left-0 right-0 z-10 pointer-events-none"
                style={{ top: nowTop }}
              >
                <div className="h-0.5 bg-red-500 w-full" />
                <div className="absolute -top-1 -left-0.5 h-2.5 w-2.5 rounded-full bg-red-500" />
              </div>
            )}

            {/* Eventos */}
            {appointments.map((event) => {
              const start = toBusinessTimezoneDate(event.startTime, businessTimezone);
              const top = slotTopPx(start);
              const height = durationPx(event.startTime, event.endTime);
              if (top >= TOTAL_HEIGHT || top < 0) return null;
              const isGoogle = event.source === "google";
              return (
                <div
                  key={event.id}
                  className={`absolute left-2 right-2 rounded border text-xs overflow-hidden z-10 px-2 py-1.5 ${EVENT_COLORS[event.type]} ${isGoogle ? "cursor-default opacity-80" : "cursor-pointer"}`}
                  style={{ top: top + 1, height: Math.max(height - 2, 28) }}
                  onClick={(e) => {
                    e.stopPropagation();
                    if (!isGoogle) openEdit(event);
                  }}
                >
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-semibold text-sm">
                      {format(start, "HH:mm")}
                      {event.endTime &&
                        ` – ${format(toBusinessTimezoneDate(event.endTime, businessTimezone), "HH:mm")}`}
                    </span>
                    <Badge
                      variant="outline"
                      className="text-[10px] px-1 py-0 h-4 border-white/40 text-inherit"
                    >
                      {TYPE_LABELS[event.type]}
                    </Badge>
                    {isGoogle && (
                      <Badge className="text-[10px] px-1 py-0 h-4 bg-white/20 text-inherit border-white/30">
                        Google
                      </Badge>
                    )}
                  </div>
                  {height > 38 && (
                    <div className="font-medium truncate mt-0.5">{event.title}</div>
                  )}
                  {height > 60 && event.leadName && (
                    <div className="opacity-80 truncate text-[11px]">{event.leadName}</div>
                  )}
                  {height > 80 && event.description && (
                    <div className="opacity-70 truncate text-[11px] mt-0.5">{event.description}</div>
                  )}
                </div>
              );
            })}

            {/* Mensagem vazia */}
            {appointments.length === 0 && (
              <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                <p className="text-sm text-muted-foreground">Nenhum compromisso para este dia</p>
              </div>
            )}
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
