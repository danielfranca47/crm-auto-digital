import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api } from "@/services/api";
import type { PedidoCorrecao, PedidoCorrecaoEstado } from "@/services/api";
import { useToast } from "@/hooks/use-toast";
import { Copy, RefreshCw } from "lucide-react";

const ESTADOS: { value: PedidoCorrecaoEstado; label: string; cls: string }[] = [
  { value: "novo", label: "Novo", cls: "bg-indigo-900/50 text-indigo-300 border-indigo-700/50" },
  { value: "em_curso", label: "Em curso", cls: "bg-amber-900/50 text-amber-300 border-amber-700/50" },
  { value: "feito", label: "Feito", cls: "bg-emerald-900/50 text-emerald-300 border-emerald-700/50" },
  { value: "descartado", label: "Descartado", cls: "bg-slate-800 text-slate-400 border-slate-600" },
];

function formatDate(iso: string) {
  try {
    return new Date(iso.replace(" ", "T") + (iso.endsWith("Z") ? "" : "Z")).toLocaleString("pt-BR", {
      day: "2-digit",
      month: "2-digit",
      year: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

// Prompt pronto a colar numa conversa do Claude Code na pasta do projeto (lado do dono).
function promptDoPedido(p: PedidoCorrecao) {
  return [
    `Pedido de correção #${p.id} da skill configuracao-personalizada (de ${p.user_email ?? `user ${p.user_id}`}).`,
    `Ler CLAUDE.md e docs/implementations/_guia-documentar-implementacao.md; criar o ficheiro de implementação`,
    `a partir deste pedido e seguir o fluxo normal (Plan Mode → aprovação → worktree → fases → testes).`,
    `Ao terminar, marcar o pedido como "feito" no frontend-admin (Pedidos de correção).`,
    "",
    `Título: ${p.titulo}`,
    `Sintoma: ${p.sintoma}`,
    p.evidencia ? `Evidência:\n${p.evidencia}` : "",
    p.cenarios_json ? `Cenários da bancada (cenarios.json):\n${p.cenarios_json}` : "",
  ]
    .filter(Boolean)
    .join("\n");
}

export default function AdminPedidos() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [filtro, setFiltro] = useState<PedidoCorrecaoEstado | undefined>("novo");
  const [aberto, setAberto] = useState<number | null>(null);

  const { data: pedidos = [], isLoading, refetch } = useQuery({
    queryKey: ["admin", "pedidos-correcao", filtro ?? "todos"],
    queryFn: () => api.listPedidosCorrecao(filtro),
    staleTime: 30_000,
  });

  const mudarEstado = async (p: PedidoCorrecao, estado: PedidoCorrecaoEstado) => {
    try {
      await api.updatePedidoCorrecao(p.id, { estado });
      await queryClient.invalidateQueries({ queryKey: ["admin", "pedidos-correcao"] });
      toast({ title: `Pedido #${p.id}: ${ESTADOS.find((e) => e.value === estado)?.label}` });
    } catch (err) {
      toast({ title: "Não foi possível mudar o estado", description: String(err), variant: "destructive" });
    }
  };

  const copiar = async (p: PedidoCorrecao) => {
    try {
      await navigator.clipboard.writeText(promptDoPedido(p));
      toast({ title: "Prompt copiado" });
    } catch {
      toast({ title: "Não foi possível copiar", variant: "destructive" });
    }
  };

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-xl font-semibold">Pedidos de correção</h1>
          <p className="text-sm text-slate-400">
            Problemas que a skill de configuração de agentes não resolveu com configuração e enviou para correção no sistema.
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {[undefined, ...ESTADOS.map((e) => e.value)].map((v) => (
            <Button
              key={v ?? "todos"}
              size="sm"
              variant={filtro === v ? "default" : "outline"}
              onClick={() => setFiltro(v)}
            >
              {v ? ESTADOS.find((e) => e.value === v)?.label : "Todos"}
            </Button>
          ))}
          <Button size="sm" variant="outline" onClick={() => refetch()}>
            <RefreshCw size={14} />
          </Button>
        </div>
      </div>

      {isLoading && <p className="text-sm text-slate-400">A carregar…</p>}
      {!isLoading && pedidos.length === 0 && <p className="text-sm text-slate-400">Sem pedidos.</p>}

      {pedidos.map((p) => {
        const est = ESTADOS.find((e) => e.value === p.estado);
        return (
          <Card key={p.id} className="bg-slate-800/50 border-slate-700">
            <CardHeader className="pb-2">
              <div className="flex items-start justify-between gap-3">
                <button className="text-left" onClick={() => setAberto(aberto === p.id ? null : p.id)}>
                  <CardTitle className="text-base text-slate-100">
                    #{p.id} — {p.titulo}
                  </CardTitle>
                  <p className="text-xs text-slate-400 mt-1">
                    {p.user_email ?? `user ${p.user_id}`} · {formatDate(p.created_at)}
                    {p.bancada ? ` · bancada ${p.bancada}` : ""}
                  </p>
                </button>
                <Badge className={`${est?.cls ?? ""} text-xs`}>{est?.label ?? p.estado}</Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="text-sm text-slate-200 whitespace-pre-wrap">{p.sintoma}</p>
              {aberto === p.id && p.evidencia && (
                <pre className="text-xs text-slate-300 bg-slate-900 rounded p-3 whitespace-pre-wrap max-h-80 overflow-auto">
                  {p.evidencia}
                </pre>
              )}
              <div className="flex gap-2 flex-wrap">
                <Button size="sm" variant="outline" onClick={() => copiar(p)}>
                  <Copy size={14} className="mr-1" /> Copiar prompt
                </Button>
                {ESTADOS.filter((e) => e.value !== p.estado).map((e) => (
                  <Button key={e.value} size="sm" variant="ghost" onClick={() => mudarEstado(p, e.value)}>
                    {e.label}
                  </Button>
                ))}
              </div>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
