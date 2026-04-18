import { useState, useEffect } from “react”
import { useForm } from “react-hook-form”
import { zodResolver } from “@hookform/resolvers/zod”
import { z } from “zod”
import { Button } from “@/components/ui/button”
import { Input } from “@/components/ui/input”
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from “@/components/ui/select”
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from “@/components/ui/form”
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from “@/components/ui/card”
import { Search, Lock, Globe, Linkedin, Instagram, Star, ExternalLink } from “lucide-react”
import { toast } from “@/hooks/use-toast”
import { useApiErrorHandler } from “@/hooks/useApiErrorHandler”

import { api, type SearchPayload, type Manifest } from “@/services/api”

type Extension = {
  id: string
  name: string
  description: string
  icon: React.ReactNode
  whatsappText: string
}

const AVAILABLE_EXTENSIONS: Extension[] = [
  {
    id: “website_audit”,
    name: “Auditoria de Site”,
    description: “Verifica se a empresa tem site, faz webscraping e gera relatório de melhorias automaticamente.”,
    icon: <Globe className=”h-6 w-6” />,
    whatsappText: “Olá! Tenho interesse na extensão de Auditoria de Site para minha conta.”,
  },
  {
    id: “instagram_profile”,
    name: “Perfil Instagram”,
    description: “Coleta seguidores, bio e posts recentes das empresas encontradas via agente local.”,
    icon: <Instagram className=”h-6 w-6” />,
    whatsappText: “Olá! Tenho interesse na extensão de Pesquisa no Instagram para minha conta.”,
  },
  {
    id: “linkedin_company”,
    name: “LinkedIn Empresa”,
    description: “Coleta tamanho, setor e vagas abertas das empresas via agente local.”,
    icon: <Linkedin className=”h-6 w-6” />,
    whatsappText: “Olá! Tenho interesse na extensão de Pesquisa no LinkedIn para minha conta.”,
  },
  {
    id: “google_reviews”,
    name: “Avaliações Google”,
    description: “Coleta avaliações e comentários do Google Maps para análise de reputação.”,
    icon: <Star className=”h-6 w-6” />,
    whatsappText: “Olá! Tenho interesse na extensão de Avaliações Google para minha conta.”,
  },
]

const OWNER_WHATSAPP = “+351912345678” // substituir pelo WhatsApp real do dono

const API_BASE =
  (import.meta as any)?.env?.VITE_API_BASE_URL ?? “http://127.0.0.1:8000”

const pesquisaSchema = z.object({
  proposta: z.string().min(2, “Descreva a sua proposta”),
  pais: z.string().min(2, “País deve ter pelo menos 2 caracteres”),
  provincia: z.string().min(2, “Província/Estado deve ter pelo menos 2 caracteres”),
  cidade: z.string().min(2, “Cidade deve ter pelo menos 2 caracteres”),
  bairro: z.string().optional(),
  setor: z.string().min(2, “Setor deve ter pelo menos 2 caracteres”),
  quantidade: z.string({ required_error: “Selecione a quantidade” }),
})

type PesquisaFormData = z.infer<typeof pesquisaSchema>

const propostaSugestoes = [“Site”, “Automações”, “Tráfego Pago”, “Produção de Conteúdo”]
const quantidades = Array.from({ length: 21 }, (_, i) => i + 5) // 5 a 25

export default function Pesquisa() {
  const [isLoading, setIsLoading] = useState(false)
  const [manifest, setManifest] = useState<Manifest | null>(null)
  const { handleError } = useApiErrorHandler()

  const [enabledExtensions, setEnabledExtensions] = useState<string[]>([])
  const [upsellModal, setUpsellModal] = useState<Extension | null>(null)

  useEffect(() => {
    api.core.getAiProfileMe().then((profile: any) => {
      setEnabledExtensions(Array.isArray(profile?.enabled_extensions) ? profile.enabled_extensions : [])
    }).catch(() => {})
  }, [])

  const form = useForm<PesquisaFormData>({
    resolver: zodResolver(pesquisaSchema),
    defaultValues: { bairro: “” },
  })

  const onSubmit = async (data: PesquisaFormData) => {
    setIsLoading(true)
    setManifest(null)

    try {
      const payload: SearchPayload = {
        proposal: data.proposta.trim(),
        country: data.pais.trim(),
        state: data.provincia.trim(),
        city: data.cidade.trim(),
        neighborhood: (data.bairro || “”).trim(),
        sector: data.setor.trim(),
        quantity: Math.max(5, Math.min(50, parseInt(data.quantidade, 10) || 20)),
      }

      const res = await api.pesquisa.executar(payload)
      const man = res?.manifest as Manifest | undefined
      if (!man) {
        throw new Error("Resposta sem manifest.")
      }
      setManifest(man)

      toast({
        title: "Pesquisa solicitada!",
        description: "Sua automação foi iniciada e já gerou o run_id. Você pode baixar a planilha.",
      })
    } catch (error: any) {
      handleError(error, { fallbackMessage: "Não foi possível executar a pesquisa." })
    } finally {
      setIsLoading(false)
    }
  }

  const downloadUrl = (kind: "xlsx_validado" | "xlsx" | "csv") =>
    manifest ? api.pesquisa.downloadUrl(manifest.run_id, kind) : "#"

  return (
    <div className="container mx-auto p-6 max-w-3xl">
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight">Pesquisa de Empresas</h1>
        <p className="text-muted-foreground mt-2">
          Configure os parâmetros para encontrar empresas potenciais através da automação
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Search className="h-5 w-5" />
            Configurar Pesquisa
          </CardTitle>
          <CardDescription>
            Preencha os campos abaixo para personalizar sua busca automática
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
              <FormField
                control={form.control}
                name="proposta"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Proposta *</FormLabel>
                    <FormControl>
                      <>
                        <Input
                          placeholder="Ex: Site, Automações, Consultoria Jurídica…"
                          list="proposta-sugestoes"
                          {...field}
                        />
                        <datalist id="proposta-sugestoes">
                          {propostaSugestoes.map((s) => (
                            <option key={s} value={s} />
                          ))}
                        </datalist>
                      </>
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <FormField
                  control={form.control}
                  name="pais"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>País *</FormLabel>
                      <FormControl>
                        <Input placeholder="Ex: Brasil" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="provincia"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Província/Estado *</FormLabel>
                      <FormControl>
                        <Input placeholder="Ex: São Paulo" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <FormField
                  control={form.control}
                  name="cidade"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Cidade *</FormLabel>
                      <FormControl>
                        <Input placeholder="Ex: São Paulo" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="bairro"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Bairro (Opcional)</FormLabel>
                      <FormControl>
                        <Input placeholder="Ex: Vila Madalena" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              <FormField
                control={form.control}
                name="setor"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Setor / Empresas *</FormLabel>
                    <FormControl>
                      <Input placeholder="Ex: Restaurantes, Tecnologia, Saúde" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="quantidade"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Quantidade de Empresas *</FormLabel>
                    <Select onValueChange={field.onChange} defaultValue={field.value}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="Selecione a quantidade (5-25)" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {quantidades.map((quantidade) => (
                          <SelectItem key={quantidade} value={quantidade.toString()}>
                            {quantidade} empresas
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <Button type="submit" className="w-full" size="lg" disabled={isLoading}>
                {isLoading ? "Processando..." : "Pesquisar por Empresas"}
              </Button>
            </form>
          </Form>

          {manifest && (
            <div className="mt-6 space-y-3 border-t pt-4">
              <div className="text-sm text-muted-foreground">
                <span className="font-medium">Execução concluída.</span>{" "}
                run_id: <span className="font-mono">{manifest.run_id}</span>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button asChild>
                  <a href={downloadUrl("xlsx_validado")} target="_blank" rel="noopener noreferrer">
                    Baixar planilha validada (.xlsx)
                  </a>
                </Button>
                <Button asChild variant="outline">
                  <a href={downloadUrl("xlsx")} target="_blank" rel="noopener noreferrer">
                    Baixar XLSX
                  </a>
                </Button>
                <Button asChild variant="outline">
                  <a href={downloadUrl("csv")} target="_blank" rel="noopener noreferrer">
                    Baixar CSV
                  </a>
                </Button>
              </div>
              {manifest.counts && (
                <div className="text-xs text-muted-foreground">
                  <div>Encontrados: {manifest.counts.found ?? "-"}</div>
                  <div>Finais: {manifest.counts.final ?? "-"}</div>
                  <div>Issues: {manifest.counts.issues ?? "-"}</div>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Seção de Extensões */}
      <div className="mt-8">
        <h2 className="text-xl font-semibold mb-1">Extensões de Pesquisa</h2>
        <p className="text-sm text-muted-foreground mb-4">
          Enriquecimentos avançados para sua pesquisa. Extensões desbloqueadas ficam disponíveis automaticamente.
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
              Esta extensão requer contratação adicional. Entre em contato para ativar na sua conta.
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
