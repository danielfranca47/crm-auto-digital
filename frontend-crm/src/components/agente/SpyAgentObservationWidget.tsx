import { useNavigate } from "react-router-dom";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Eye, Sparkles, ArrowRight } from "lucide-react";
import type { SpyAgentSession } from "@/services/api";

interface SpyAgentObservationWidgetProps {
  session: SpyAgentSession;
}

export function SpyAgentObservationWidget({ session }: SpyAgentObservationWidgetProps) {
  const navigate = useNavigate();

  if (session.status === "completed") {
    return (
      <Card className="border-primary/40 bg-primary/5">
        <CardContent className="p-4 flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <Sparkles className="h-5 w-5 text-primary shrink-0" />
            <div>
              <p className="text-sm font-semibold">Análise concluída!</p>
              <p className="text-xs text-muted-foreground">
                O Agente Espião aprendeu com suas conversas. Revise as sugestões.
              </p>
            </div>
          </div>
          <Button size="sm" className="shrink-0" onClick={() => navigate("/spy-agent")}>
            Revisar <ArrowRight className="h-3.5 w-3.5 ml-1" />
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (session.status === "observing") {
    return (
      <Card className="border-border">
        <CardContent className="p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Eye className="h-4 w-4 text-muted-foreground shrink-0" />
              <p className="text-sm font-medium">Agente Espião em observação</p>
            </div>
            <Button
              variant="ghost"
              size="sm"
              className="text-xs h-7"
              onClick={() => navigate("/spy-agent")}
            >
              Gerenciar
            </Button>
          </div>
          <Progress value={session.progress_pct} className="h-1.5 mb-2" />
          <p className="text-xs text-muted-foreground">
            {session.days_remaining > 0
              ? `${session.days_remaining} dia${session.days_remaining !== 1 ? "s" : ""} restante${session.days_remaining !== 1 ? "s" : ""} — coletando dados das suas conversas`
              : "Análise será iniciada em breve..."}
          </p>
        </CardContent>
      </Card>
    );
  }

  if (session.status === "analyzing") {
    return (
      <Card className="border-primary/30">
        <CardContent className="p-4 flex items-center gap-3">
          <Sparkles className="h-4 w-4 text-primary shrink-0 animate-pulse" />
          <div>
            <p className="text-sm font-medium">Analisando suas conversas...</p>
            <p className="text-xs text-muted-foreground">
              O Agente Espião está processando os dados coletados.
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return null;
}
