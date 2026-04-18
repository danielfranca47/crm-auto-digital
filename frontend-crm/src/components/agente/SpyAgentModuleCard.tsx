import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Check, X, ChevronDown, ChevronUp } from "lucide-react";
import type { SpyAgentModuleResult, SpyAgentSuggestion } from "@/services/api";

export type Decision = "pending" | "accepted" | "rejected";

const MODULE_LABELS: Record<string, string> = {
  facts: "Complementação de Fatos",
  identity: "Identidade e Tom",
  strategy: "Estratégia de Vendas",
};

const MODULE_DESCRIPTIONS: Record<string, string> = {
  facts: "Informações objetivas sobre o negócio extraídas das conversas.",
  identity: "Estilo de comunicação e tom de voz do vendedor.",
  strategy: "Abordagem de vendas, qualificação e tipo de agente ideal.",
};

interface SpyAgentModuleCardProps {
  result: SpyAgentModuleResult;
  decisions: Record<string, Decision>;
  onDecide: (field: string, decision: Decision, value: unknown) => void;
  onAcceptAll: (moduleId: string) => void;
  onRejectAll: (moduleId: string) => void;
}

export function SpyAgentModuleCard({
  result,
  decisions,
  onDecide,
  onAcceptAll,
  onRejectAll,
}: SpyAgentModuleCardProps) {
  const [expanded, setExpanded] = useState(true);

  const confidencePct = Math.round(result.confidence * 100);
  const confidenceColor =
    result.confidence >= 0.7 ? "text-green-600" :
    result.confidence >= 0.4 ? "text-yellow-600" : "text-red-500";

  if (result.suggestions.length === 0) {
    return (
      <Card className="opacity-60">
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm font-semibold">
              {MODULE_LABELS[result.module] ?? result.module}
            </CardTitle>
            <Badge variant="outline" className="text-xs">Sem sugestões</Badge>
          </div>
          <p className="text-xs text-muted-foreground">{MODULE_DESCRIPTIONS[result.module]}</p>
        </CardHeader>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="text-sm font-semibold">
            {MODULE_LABELS[result.module] ?? result.module}
          </CardTitle>
          <div className="flex items-center gap-1.5 shrink-0">
            <button
              className="text-xs text-green-600 hover:text-green-700 font-medium px-1.5 py-0.5 rounded hover:bg-green-50 transition-colors"
              onClick={() => onAcceptAll(result.module)}
              title="Aceitar todas as sugestões deste módulo"
            >
              Aceitar todas
            </button>
            <span className="text-muted-foreground/40 text-xs">|</span>
            <button
              className="text-xs text-destructive/70 hover:text-destructive font-medium px-1.5 py-0.5 rounded hover:bg-destructive/5 transition-colors"
              onClick={() => onRejectAll(result.module)}
              title="Recusar todas as sugestões deste módulo"
            >
              Recusar todas
            </button>
            <span className={`text-xs font-medium ${confidenceColor}`}>
              {confidencePct}%
            </span>
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6"
              onClick={() => setExpanded((e) => !e)}
            >
              {expanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
            </Button>
          </div>
        </div>
        <p className="text-xs text-muted-foreground">{MODULE_DESCRIPTIONS[result.module]}</p>
      </CardHeader>

      {expanded && (
        <CardContent className="space-y-2 pt-0">
          {result.suggestions.map((s: SpyAgentSuggestion) => {
            const decision = decisions[s.field] ?? "pending";
            const isAccepted = decision === "accepted";
            const isRejected = decision === "rejected";

            return (
              <div
                key={s.field}
                className={`rounded-lg border p-3 transition-colors ${
                  isAccepted
                    ? "border-primary/60 bg-primary/5"
                    : isRejected
                    ? "border-destructive/30 bg-destructive/5 opacity-60"
                    : "border-border"
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5 mb-1">
                      <code className="text-xs bg-muted px-1.5 py-0.5 rounded font-mono">
                        {s.field}
                      </code>
                    </div>
                    {s.current_value !== null && s.current_value !== undefined && (
                      <p className={`text-xs text-muted-foreground mb-0.5 ${isRejected ? "" : "line-through"}`}>
                        Atual: {JSON.stringify(s.current_value)}
                      </p>
                    )}
                    <p className={`text-xs font-medium ${isRejected ? "text-muted-foreground line-through" : "text-foreground"}`}>
                      Sugerido: {JSON.stringify(s.suggested_value)}
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">{s.rationale}</p>
                  </div>

                  {/* Accept / Reject buttons */}
                  <div className="flex items-center gap-1 shrink-0">
                    <Button
                      variant={isAccepted ? "default" : "outline"}
                      size="icon"
                      className={`h-7 w-7 ${isAccepted ? "bg-primary text-primary-foreground" : "text-green-600 border-green-600/40 hover:bg-green-50 hover:border-green-600"}`}
                      onClick={() => onDecide(s.field, isAccepted ? "pending" : "accepted", s.suggested_value)}
                      title={isAccepted ? "Clique para desfazer aceitação" : "Aceitar sugestão"}
                    >
                      <Check className="h-3.5 w-3.5" />
                    </Button>
                    <Button
                      variant={isRejected ? "destructive" : "outline"}
                      size="icon"
                      className={`h-7 w-7 ${isRejected ? "" : "text-destructive/50 border-destructive/20 hover:bg-destructive/5 hover:border-destructive/50 hover:text-destructive"}`}
                      onClick={() => onDecide(s.field, isRejected ? "pending" : "rejected", s.suggested_value)}
                      title={isRejected ? "Clique para desfazer recusa" : "Recusar sugestão"}
                    >
                      <X className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </div>
              </div>
            );
          })}
        </CardContent>
      )}
    </Card>
  );
}
