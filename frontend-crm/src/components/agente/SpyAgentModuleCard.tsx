import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Check, X, ChevronDown, ChevronUp } from "lucide-react";
import type { SpyAgentModuleResult, SpyAgentSuggestion } from "@/services/api";

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
  acceptedFields: Set<string>;
  onToggle: (field: string, value: unknown) => void;
}

export function SpyAgentModuleCard({ result, acceptedFields, onToggle }: SpyAgentModuleCardProps) {
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
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-semibold">
            {MODULE_LABELS[result.module] ?? result.module}
          </CardTitle>
          <div className="flex items-center gap-2">
            <span className={`text-xs font-medium ${confidenceColor}`}>
              {confidencePct}% confiança
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
            const accepted = acceptedFields.has(s.field);
            return (
              <div
                key={s.field}
                className={`rounded-lg border p-3 transition-colors ${
                  accepted ? "border-primary/60 bg-primary/5" : "border-border"
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
                      <p className="text-xs text-muted-foreground line-through mb-0.5">
                        Atual: {JSON.stringify(s.current_value)}
                      </p>
                    )}
                    <p className="text-xs font-medium text-foreground">
                      Sugerido: {JSON.stringify(s.suggested_value)}
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">{s.rationale}</p>
                  </div>
                  <Button
                    variant={accepted ? "default" : "outline"}
                    size="icon"
                    className="h-7 w-7 shrink-0"
                    onClick={() => onToggle(s.field, s.suggested_value)}
                    title={accepted ? "Remover seleção" : "Aceitar sugestão"}
                  >
                    {accepted ? <Check className="h-3.5 w-3.5" /> : <X className="h-3.5 w-3.5 opacity-40" />}
                  </Button>
                </div>
              </div>
            );
          })}
        </CardContent>
      )}
    </Card>
  );
}
