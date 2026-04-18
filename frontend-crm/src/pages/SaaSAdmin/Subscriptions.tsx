import { useState, useEffect, useCallback } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { api } from "@/services/api"
import { useToast } from "@/hooks/use-toast"

const AVAILABLE_EXTENSIONS = [
  { id: "website_audit", label: "Auditoria de Site" },
  { id: "instagram_profile", label: "Perfil Instagram" },
  { id: "linkedin_company", label: "LinkedIn Empresa" },
  { id: "google_reviews", label: "Avaliações Google" },
]

const TOKEN_KEY = "saas_admin_service_token"

type UserRow = {
  id: number
  email: string
  name?: string
  enabled_extensions?: string[]
}

export default function Subscriptions() {
  const { toast } = useToast()
  const [serviceToken, setServiceToken] = useState(() => localStorage.getItem(TOKEN_KEY) || "")
  const [tokenInput, setTokenInput] = useState("")
  const [users, setUsers] = useState<UserRow[]>([])
  const [search, setSearch] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [modalUser, setModalUser] = useState<UserRow | null>(null)
  const [editExtensions, setEditExtensions] = useState<string[]>([])
  const [isSaving, setIsSaving] = useState(false)

  const saveToken = () => {
    const t = tokenInput.trim()
    if (!t) return
    localStorage.setItem(TOKEN_KEY, t)
    setServiceToken(t)
    setTokenInput("")
    toast({ title: "Token salvo", description: "Sessão admin iniciada." })
  }

  const loadUsers = useCallback(async () => {
    if (!serviceToken) return
    setIsLoading(true)
    try {
      const data = await api.admin.listUsers(serviceToken, search || undefined)
      setUsers(data)
    } catch (err: any) {
      toast({ title: "Erro ao listar usuários", description: err?.message || "Verifique o service token.", variant: "destructive" })
    } finally {
      setIsLoading(false)
    }
  }, [serviceToken, search, toast])

  useEffect(() => {
    if (serviceToken) loadUsers()
  }, [serviceToken, loadUsers])

  const openModal = (user: UserRow) => {
    setModalUser(user)
    setEditExtensions(user.enabled_extensions || [])
  }

  const toggleExtension = (id: string) => {
    setEditExtensions((prev) =>
      prev.includes(id) ? prev.filter((e) => e !== id) : [...prev, id]
    )
  }

  const saveExtensions = async () => {
    if (!modalUser) return
    setIsSaving(true)
    try {
      await api.admin.setExtensions(serviceToken, modalUser.id, editExtensions)
      setUsers((prev) =>
        prev.map((u) => u.id === modalUser.id ? { ...u, enabled_extensions: editExtensions } : u)
      )
      toast({ title: "Extensões salvas", description: `Atualizado para ${modalUser.email}.` })
      setModalUser(null)
    } catch (err: any) {
      toast({ title: "Erro ao salvar", description: err?.message, variant: "destructive" })
    } finally {
      setIsSaving(false)
    }
  }

  if (!serviceToken) {
    return (
      <div className="container mx-auto p-6 max-w-md">
        <h1 className="text-2xl font-bold mb-6">SaaS Admin — Subscriptions</h1>
        <Card>
          <CardContent className="pt-6 space-y-4">
            <Label>Service Token</Label>
            <Input
              type="password"
              placeholder="Cole o CORE_SERVICE_TOKEN aqui"
              value={tokenInput}
              onChange={(e) => setTokenInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && saveToken()}
            />
            <Button className="w-full" onClick={saveToken} disabled={!tokenInput.trim()}>
              Entrar
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="container mx-auto p-6 max-w-4xl">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">SaaS Admin — Extensões por Usuário</h1>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => { localStorage.removeItem(TOKEN_KEY); setServiceToken("") }}
        >
          Sair
        </Button>
      </div>

      <div className="flex gap-3 mb-4">
        <Input
          placeholder="Buscar por email…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && loadUsers()}
          className="max-w-sm"
        />
        <Button variant="outline" onClick={loadUsers} disabled={isLoading}>
          {isLoading ? "Carregando…" : "Buscar"}
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Usuários ({users.length})</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <div className="divide-y">
            {users.map((user) => (
              <div key={user.id} className="flex items-center justify-between px-4 py-3">
                <div>
                  <p className="text-sm font-medium">{user.email}</p>
                  <p className="text-xs text-muted-foreground">
                    {user.enabled_extensions?.length
                      ? `Extensões: ${user.enabled_extensions.join(", ")}`
                      : "Sem extensões ativas"}
                  </p>
                </div>
                <Button size="sm" variant="outline" onClick={() => openModal(user)}>
                  Gerenciar
                </Button>
              </div>
            ))}
            {users.length === 0 && !isLoading && (
              <p className="px-4 py-8 text-center text-sm text-muted-foreground">
                Nenhum usuário encontrado.
              </p>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Modal de extensões */}
      {modalUser && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
          onClick={() => setModalUser(null)}
        >
          <div
            className="bg-card rounded-xl shadow-xl p-6 max-w-sm mx-4 space-y-4 w-full"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="font-semibold">Extensões — {modalUser.email}</h3>
            <div className="space-y-2">
              {AVAILABLE_EXTENSIONS.map((ext) => (
                <label key={ext.id} className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    className="h-4 w-4"
                    checked={editExtensions.includes(ext.id)}
                    onChange={() => toggleExtension(ext.id)}
                  />
                  <span className="text-sm">{ext.label}</span>
                </label>
              ))}
            </div>
            <div className="flex gap-2">
              <Button className="flex-1" onClick={saveExtensions} disabled={isSaving}>
                {isSaving ? "Salvando…" : "Salvar"}
              </Button>
              <Button variant="outline" onClick={() => setModalUser(null)}>
                Cancelar
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
