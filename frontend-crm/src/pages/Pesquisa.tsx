import { useState } from "react"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Search } from "lucide-react"
import { toast } from "@/hooks/use-toast"

// 👉 usa o wrapper da API
import { api, type SearchPayload, type Manifest } from "@/services/api"

// (mantido; não é usado diretamente aqui)
const API_BASE =
  (import.meta as any)?.env?.VITE_API_BASE_URL ?? "http://127.0.0.1:8000"

const pesquisaSchema = z.object({
  proposta: z.string({ required_error: "Selecione uma proposta" }),
  pais: z.string().min(2, "País deve ter pelo menos 2 caracteres"),
  provincia: z.string().min(2, "Província/Estado deve ter pelo menos 2 caracteres"),
  cidade: z.string().min(2, "Cidade deve ter pelo menos 2 caracteres"),
  bairro: z.string().optional(),
  setor: z.string().min(2, "Setor deve ter pelo menos 2 caracteres"),
  quantidade: z.string({ required_error: "Selecione a quantidade" }),
})

type PesquisaFormData = z.infer<typeof pesquisaSchema>

const propostas = ["Site", "Automações", "Tráfego Pago", "Produção de Conteúdo"]
const quantidades = Array.from({ length: 21 }, (_, i) => i + 5) // 5 a 25

// helper: “Site” -> "site" (suportado agora)
function propostaToKey(p?: string): "site" | null {
  if (!p) return null
  const low = p.trim().toLowerCase()
  return low.includes("site") ? "site" : null
}

export default function Pesquisa() {
  const [isLoading, setIsLoading] = useState(false)
  const [manifest, setManifest] = useState<Manifest | null>(null)

  const form = useForm<PesquisaFormData>({
    resolver: zodResolver(pesquisaSchema),
    defaultValues: { bairro: "" },
  })

  const onSubmit = async (data: PesquisaFormData) => {
    setIsLoading(true)
    setManifest(null)

    try {
      const proposal = propostaToKey(data.proposta)
      if (proposal !== "site") {
        toast({
          title: "Proposta não suportada",
          description: "Por enquanto, selecione a proposta “Site”.",
          variant: "destructive",
        })
        return
      }

      const payload: SearchPayload = {
        proposal, // <- literal "site"
        country: data.pais.trim(),
        state: data.provincia.trim(),
        city: data.cidade.trim(),
        neighborhood: (data.bairro || "").trim(),
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
      toast({
        title: "Erro",
        description: error?.message || "Ocorreu um erro ao processar sua solicitação.",
        variant: "destructive",
      })
    } finally {
      setIsLoading(false)
    }
  }

  const downloadUrl = (kind: "xlsx_validado" | "xlsx" | "csv") =>
    manifest ? api.pesquisa.downloadUrl(manifest.run_id, kind) : "#"

  return (
    <div className="container mx-auto p-6 max-w-2xl">
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
                    <Select onValueChange={field.onChange} defaultValue={field.value}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="Selecione o tipo de proposta" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {propostas.map((proposta) => (
                          <SelectItem key={proposta} value={proposta}>
                            {proposta}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
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
    </div>
  )
}
