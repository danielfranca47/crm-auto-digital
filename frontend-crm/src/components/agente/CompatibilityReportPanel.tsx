import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Download, Mail, CheckCircle2, XCircle, AlertCircle } from "lucide-react";
import type { CompatibilityReport } from "@/services/api";

interface CompatibilityReportPanelProps {
  report: CompatibilityReport;
  runId: number;
}

export function CompatibilityReportPanel({ report, runId }: CompatibilityReportPanelProps) {
  const handleExport = () => {
    const blob = new Blob(
      [JSON.stringify({ run_id: runId, generated_at: new Date().toISOString(), ...report }, null, 2)],
      { type: "application/json" }
    );
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `spy-agent-report-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleSendToSupport = () => {
    const subject = encodeURIComponent(`[Agente Espião] Relatório de compatibilidade — run_id=${runId}`);
    const gaps = report.features_unsupported
      .map((f) => `- ${f.feature}: ${f.reason}`)
      .join("\n");
    const body = encodeURIComponent(
      `Olá,\n\nO Agente Espião identificou as seguintes funcionalidades não suportadas no meu pipeline:\n\n${gaps}\n\nRun ID: ${runId}\n\nPor favor, avaliem a possibilidade de adicionar suporte a estas funcionalidades.\n\nObrigado!`
    );
    window.location.href = `mailto:suporte@orionai.io?subject=${subject}&body=${body}`;
  };

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-semibold">Relatório de Compatibilidade</CardTitle>
          <div className="flex gap-1.5">
            <Button variant="outline" size="sm" className="h-7 text-xs gap-1" onClick={handleExport}>
              <Download className="h-3.5 w-3.5" /> Exportar
            </Button>
            {report.features_unsupported.length > 0 && (
              <Button variant="outline" size="sm" className="h-7 text-xs gap-1" onClick={handleSendToSupport}>
                <Mail className="h-3.5 w-3.5" /> Suporte
              </Button>
            )}
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Estágios do pipeline */}
        {report.pipeline_stages_detected.length > 0 && (
          <div>
            <p className="text-xs font-medium text-muted-foreground mb-2">Estágios detectados no pipeline</p>
            <div className="flex flex-wrap gap-1.5">
              {report.pipeline_stages_detected.map((s) => (
                <Badge key={s} variant="secondary" className="text-xs capitalize">
                  {s}
                </Badge>
              ))}
            </div>
          </div>
        )}

        {/* Modo de agente recomendado */}
        {report.recommended_agent_mode && (
          <div className="flex items-center gap-2 py-2 px-3 rounded-lg bg-primary/5 border border-primary/20">
            <AlertCircle className="h-4 w-4 text-primary shrink-0" />
            <p className="text-xs">
              <span className="font-medium">Modo recomendado:</span>{" "}
              <code className="bg-muted px-1 rounded text-xs">{report.recommended_agent_mode}</code>
            </p>
          </div>
        )}

        {/* Funcionalidades suportadas */}
        {report.features_supported.length > 0 && (
          <div>
            <p className="text-xs font-medium text-muted-foreground mb-2">Pode configurar no agente</p>
            <div className="space-y-1.5">
              {report.features_supported.map((f) => (
                <div key={f.feature} className="flex items-start gap-2">
                  <CheckCircle2 className="h-4 w-4 text-green-500 shrink-0 mt-0.5" />
                  <div>
                    <p className="text-xs font-medium">{f.feature}</p>
                    {f.notes && <p className="text-xs text-muted-foreground">{f.notes}</p>}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Funcionalidades não suportadas */}
        {report.features_unsupported.length > 0 && (
          <div>
            <p className="text-xs font-medium text-muted-foreground mb-2">Não suportado atualmente</p>
            <div className="space-y-2">
              {report.features_unsupported.map((f) => (
                <div key={f.feature} className="rounded-lg border border-destructive/30 bg-destructive/5 p-3">
                  <div className="flex items-start gap-2">
                    <XCircle className="h-4 w-4 text-destructive shrink-0 mt-0.5" />
                    <div>
                      <p className="text-xs font-medium">{f.feature}</p>
                      <p className="text-xs text-muted-foreground mt-0.5">{f.reason}</p>
                      {f.workaround && (
                        <p className="text-xs text-amber-700 dark:text-amber-400 mt-1">
                          💡 {f.workaround}
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {report.features_unsupported.length === 0 && (
          <div className="flex items-center gap-2 py-2 px-3 rounded-lg bg-green-500/10 border border-green-500/20">
            <CheckCircle2 className="h-4 w-4 text-green-500 shrink-0" />
            <p className="text-xs text-green-700 dark:text-green-400">
              Todas as funcionalidades detectadas no seu pipeline são suportadas pelo agente.
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
