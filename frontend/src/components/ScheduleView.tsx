import { useState } from "react";
import { Calendar } from "./ui/calendar";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Button } from "./ui/button";
import { CalendarDays, List, Plus } from "lucide-react";
import { Badge } from "./ui/badge";
import { format, isSameDay } from "date-fns";
import { ptBR } from "date-fns/locale";

interface ScheduleEvent {
  id: string;
  title: string;
  date: Date;
  time: string;
  type: 'meeting' | 'call' | 'follow-up' | 'presentation';
  leadName: string;
}

// Mock data para demonstração
const mockEvents: ScheduleEvent[] = [
  {
    id: '1',
    title: 'Reunião de apresentação',
    date: new Date(),
    time: '14:00',
    type: 'meeting',
    leadName: 'João Silva'
  },
  {
    id: '2',
    title: 'Follow-up ligação',
    date: new Date(Date.now() + 86400000), // Amanhã
    time: '10:30',
    type: 'follow-up',
    leadName: 'Maria Santos'
  },
  {
    id: '3',
    title: 'Ligação comercial',
    date: new Date(Date.now() + 172800000), // Depois de amanhã
    time: '16:00',
    type: 'call',
    leadName: 'Pedro Costa'
  }
];

const eventTypeColors = {
  meeting: 'bg-primary text-primary-foreground',
  call: 'bg-success text-success-foreground',
  'follow-up': 'bg-warning text-warning-foreground',
  presentation: 'bg-info text-info-foreground'
};

const eventTypeLabels = {
  meeting: 'Reunião',
  call: 'Ligação',
  'follow-up': 'Follow-up',
  presentation: 'Apresentação'
};

export function ScheduleView() {
  const [viewMode, setViewMode] = useState<'calendar' | 'list'>('calendar');
  const [selectedDate, setSelectedDate] = useState<Date>(new Date());
  const [events] = useState<ScheduleEvent[]>(mockEvents);

  const filteredEvents = viewMode === 'calendar' 
    ? events.filter(event => isSameDay(event.date, selectedDate))
    : events.sort((a, b) => a.date.getTime() - b.date.getTime());

  const hasEventsOnDate = (date: Date) => {
    return events.some(event => isSameDay(event.date, date));
  };

  return (
    <Card className="bg-card border-border h-full">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-foreground">Agenda</CardTitle>
          <div className="flex items-center gap-2">
            <Button
              variant={viewMode === 'calendar' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setViewMode('calendar')}
              className="h-8"
            >
              <CalendarDays className="w-4 h-4" />
            </Button>
            <Button
              variant={viewMode === 'list' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setViewMode('list')}
              className="h-8"
            >
              <List className="w-4 h-4" />
            </Button>
            <Button size="sm" className="h-8">
              <Plus className="w-4 h-4 mr-1" />
              Novo
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {viewMode === 'calendar' ? (
          <div className="space-y-4">
            <Calendar
              mode="single"
              selected={selectedDate}
              onSelect={(date) => date && setSelectedDate(date)}
              className="rounded-md border border-border pointer-events-auto"
              modifiers={{
                hasEvents: (date) => hasEventsOnDate(date)
              }}
              modifiersStyles={{
                hasEvents: {
                  fontWeight: 'bold',
                  backgroundColor: 'hsl(var(--primary) / 0.1)',
                }
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
                            {event.title}
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
                      {event.title}
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
    </Card>
  );
}