import { useState, useEffect, useCallback } from "react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { RefreshCw, Bot, Lock, Globe, Linkedin, Instagram, Star, ExternalLink } from "lucide-react"
import { api } from "@/services/api"

// ── Tipos ──────────────────────────────────────────────────────────────────

type HistoryEntry = {
  id: number
  lead_id: number
  lead_name: string
  phone: string
  action: string
  notes: string
  created_at: string
}

const ACTION_LABELS: Record<string, string> = {
  manual_outbound: "Enviado (manual)",
  sent: "Enviado",
  failed: "Falhou",
  queued: "Enfileirado",
  copied: "Copy copiado",
  updated_message: "Mensagem guardada",
}

const ACTION_COLORS: Record<string, string> = {
  manual_outbound: "default",
  sent: "default",
  failed: "destructive",
  queued: "secondary",
}

// ── Extensões (upsell) ─────────────────────────────────────────────────────

type Extension = {
  id: string
  name: string
  description: string
  icon: React.ReactNode
  whatsappText: string
}

const AVAILABLE_EXTENSIONS: Extension[] = [
  {
    id: "website_audit",
    name: "Auditoria de Site",
    description: "Verifica se a empresa tem site, faz webscraping e gera relatório de melhorias automaticamente.",
    icon: <Globe className="h-6 w-6" />,
    whatsappText: "Olá! Tenho interesse na extensão de Auditoria de Site para minha conta.",
  },
  {
    id: "instagram_profile",
    name: "Perfil Instagram",
    description: "Coleta seguidores, bio e posts recentes das empresas encontradas via agente local.",
    icon: <Instagram className="h-6 w-6" />,
    whatsappText: "Olá! Tenho interesse na extensão de Pesquisa no Instagram para minha conta.",
  },
  {
    id: "linkedin_company",
    name: "LinkedIn Empresa",
    description: "Coleta tamanho, setor e vagas abertas das empresas via agente local.",
    icon: <Linkedin className="h-6 w-6" />,
    whatsappText: "Olá! Tenho interesse na extensão de Pesquisa no LinkedIn para minha conta.",
  },
  {
    id: "google_reviews",
    name: "Avaliações Google",
    description: "Coleta avaliações e comentários do Google Maps para análise de reputação.",
    icon: <Star className="h-6 w-6" />,
    whatsappText: "Olá! Tenho interesse na extensão de Avaliações Google para minha conta.",
  },
]

const OWNER_WHATSAPP = "+351912345678"

// ── Componente ──────────────────────────────────────────────────────────────

export default function Pesquisa() {
  const [entries, setEntries] = useState<HistoryEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState<string>("all")
  const [enabledExtensions, setEnabledExtensions] = useState<string[]>([])
  const [upsellModal, setUpsellModal] = useState<Extension | null>(null)

  // Extensões habilitadas
  useEffect(() => {
    api.core.getAiProfileMe().then((profile: any) => {
      setEnabledExtensions(Array.isArray(profile?.enabled_extensions) ? profile.enabled_extensions : [])
    }).catch(() => {})
  }, [])

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await (api.prospeccao as any).history(200, 0)
      setEntries(Array.isArray(data) ? data : [])
    } catch (err: any) {
      setError("Não foi possível carregar o histórico.")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const filtered = filter === "all"
    ? entries
    : entries.filter(e => {
        if (filter === "sent") return e.action === "sent" || e.action === "manual_outbound"
        if (filter === "failed") return e.action === "failed"
        return true
      })

  const formatDate = (iso: string) =>
    iso ? iso.replace("T", " ").slice(0, 16) : "—"

  return (
    <div className="container mx-auto p-6 max-w-4xl space-y-8">

      {/* Cabeçalho */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
          <Bot className="h-7 w-7 text-primary" />
          Leads do Agente Local
        </h1>
        <p className="text-muted-foreground mt-2">
          Os leads prospectados via agent-local aparecem aqui automaticamente.
          Use o app desktop para pesquisar no Google Maps e enviar mensagens de prospecção.
        </p>
      </div>

      {/* Histórico de prospecções */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">Histórico de Prospecções</CardTitle>
            <div className="flex items-center gap-2">
              <Select value={filter} onValueChange={setFilter}>
                <SelectTrigger className="w-36 h-8 text-sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Todos</SelectItem>
                  <SelectItem value="sent">Enviados</SelectItem>
                  <SelectItem value="failed">Falhados</SelectItem>
                </SelectContent>
              </Select>
              <Button size="sm" variant="outline" onClick={load} disabled={loading}>
                <RefreshCw className={`h-4 w-4 mr-1 ${loading ? "animate-spin" : ""}`} />
                Actualizar
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {loading && (
            <p className="text-sm text-muted-foreground text-center py-8">A carregar…</p>
          )}
          {!loading && error && (
            <p className="text-sm text-destructive text-center py-8">{error}</p>
          )}
          {!loading && !error && filtered.length === 0 && (
            <div className="text-center py-12 space-y-2">
              <Bot className="h-10 w-10 mx-auto text-muted-foreground/40" />
              <p className="text-sm text-muted-foreground">
                Sem prospecções registadas ainda.
              </p>
              <p className="text-xs text-muted-foreground">
                Abre o app Gerador de Leads, pesquisa empresas e usa o botão 📱 para prospectar.
              </p>
            </div>
          )}
          {!loading && !error && filtered.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-muted-foreground text-xs uppercase tracking-wide">
                    <th className="text-left py-2 pr-4 font-medium">Data/Hora</th>
                    <th className="text-left py-2 pr-4 font-medium">Lead</th>
                    <th className="text-left py-2 pr-4 font-medium">Telefone</th>
                    <th className="text-left py-2 pr-4 font-medium">Estado</th>
                    <th className="text-left py-2 font-medium">Notas</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((entry) => (
                    <tr key={entry.id} className="border-b last:border-0 hover:bg-muted/30 transition-colors">
                      <td className="py-2 pr-4 text-muted-foreground whitespace-nowrap">
                        {formatDate(entry.created_at)}
                      </td>
                      <td className="py-2 pr-4 font-medium max-w-[160px] truncate">
                        {entry.lead_name || "—"}
                      </td>
                      <td className="py-2 pr-4 text-muted-foreground font-mono text-xs">
                        {entry.phone || "—"}
                      </td>
                      <td className="py-2 pr-4">
                        <Badge
                          variant={
                            (ACTION_COLORS[entry.action] as any) ?? "secondary"
                          }
                          className="text-xs"
                        >
                          {ACTION_LABELS[entry.action] ?? entry.action}
                        </Badge>
                      </td>
                      <td className="py-2 text-muted-foreground text-xs max-w-[200px] truncate">
                        {entry.notes || "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="text-xs text-muted-foreground mt-3">
                {filtered.length} registo{filtered.length !== 1 ? "s" : ""}
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Extensões de Pesquisa (upsell) */}
      <div>
        <h2 className="text-xl font-semibold mb-1">Extensões de Pesquisa</h2>
        <p className="text-sm text-muted-foreground mb-4">
          Enriquecimentos avançados para o agente local. Extensões desbloqueadas ficam disponíveis automaticamente.
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {AVAILABLE_EXTENSIONS.map((ext) => {
            const unlocked = enabledExtensions.includes(ext.id)
            return (
              <div
                key={ext.id}
                onClick={() => { if (!unlocked) setUpsellModal(ext) }}
                className={`relative border rounded-lg p-4 flex gap-3 transition-colors ${
                  unlocked
                    ? "bg-card border-primary/30 cursor-default"
                    : "bg-muted/30 border-border cursor-pointer hover:border-primary/50 hover:bg-muted/50"
                }`}
              >
                <div className={`shrink-0 mt-0.5 ${unlocked ? "text-primary" : "text-muted-foreground"}`}>
                  {ext.icon}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-sm">{ext.name}</p>
                  <p className="text-xs text-muted-foreground mt-0.5 leading-relaxed">{ext.description}</p>
                </div>
                {!unlocked && (
                  <div className="absolute top-3 right-3 text-muted-foreground">
                    <Lock className="h-4 w-4" />
                  </div>
                )}
                {unlocked && (
                  <div className="absolute top-3 right-3">
                    <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full">Ativo</span>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>

      {/* Modal Upsell */}
      {upsellModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
          onClick={() => setUpsellModal(null)}
        >
          <div
            className="bg-card rounded-xl shadow-xl p-6 max-w-sm mx-4 space-y-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-3">
              <div className="text-primary">{upsellModal.icon}</div>
              <h3 className="text-lg font-semibold">{upsellModal.name}</h3>
            </div>
            <p className="text-sm text-muted-foreground">{upsellModal.description}</p>
            <p className="text-sm">
              Esta extensão requer contratação adicional. Entre em contacto para activar na sua conta.
            </p>
            <div className="flex gap-2">
              <Button
                className="flex-1"
                onClick={() => {
                  const url = `https://wa.me/${OWNER_WHATSAPP.replace(/\D/g, "")}?text=${encodeURIComponent(upsellModal.whatsappText)}`
                  window.open(url, "_blank")
                }}
              >
                <ExternalLink className="h-4 w-4 mr-2" />
                Quero contratar
              </Button>
              <Button variant="outline" onClick={() => setUpsellModal(null)}>
                Fechar
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
