import { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api } from "@/services/api";
import { useToast } from "@/hooks/use-toast";
import { Search, X } from "lucide-react";
import type { AdminUser } from "@/services/api";

const AVAILABLE_EXTENSIONS = [
  { id: "website_audit", label: "Auditoria de Site" },
  { id: "instagram_profile", label: "Perfil Instagram" },
  { id: "linkedin_company", label: "LinkedIn Empresa" },
  { id: "google_reviews", label: "Avaliações Google" },
];

export default function AdminUsers() {
  const { toast } = useToast();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [search, setSearch] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [modalUser, setModalUser] = useState<AdminUser | null>(null);
  const [editExtensions, setEditExtensions] = useState<string[]>([]);
  const [isSaving, setIsSaving] = useState(false);

  const loadUsers = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await api.listUsers(search || undefined);
      setUsers(data);
    } catch (err: unknown) {
      toast({
        title: "Erro ao listar usuários",
        description: err instanceof Error ? err.message : "Verifique o token admin.",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  }, [search, toast]);

  useEffect(() => {
    loadUsers();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const openModal = (user: AdminUser) => {
    setModalUser(user);
    setEditExtensions(user.enabled_extensions ?? []);
  };

  const toggleExtension = (id: string) => {
    setEditExtensions((prev) =>
      prev.includes(id) ? prev.filter((e) => e !== id) : [...prev, id]
    );
  };

  const saveExtensions = async () => {
    if (!modalUser) return;
    setIsSaving(true);
    try {
      await api.setExtensions(modalUser.id, editExtensions);
      setUsers((prev) =>
        prev.map((u) =>
          u.id === modalUser.id ? { ...u, enabled_extensions: editExtensions } : u
        )
      );
      toast({ title: "Extensões salvas", description: `Atualizado para ${modalUser.email}.` });
      setModalUser(null);
    } catch (err: unknown) {
      toast({
        title: "Erro ao salvar",
        description: err instanceof Error ? err.message : "Erro desconhecido",
        variant: "destructive",
      });
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="p-6 max-w-4xl">
      <h1 className="text-xl font-semibold text-slate-200 mb-1">Usuários</h1>
      <p className="text-slate-500 text-sm mb-5">Gestão de clientes e extensões ativas.</p>

      <div className="flex gap-3 mb-5">
        <div className="relative flex-1 max-w-sm">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <Input
            placeholder="Buscar por email…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && loadUsers()}
            className="pl-8 bg-slate-800 border-slate-700 text-slate-200 placeholder:text-slate-500"
          />
        </div>
        <Button
          variant="outline"
          onClick={loadUsers}
          disabled={isLoading}
          className="border-slate-700 text-slate-300 hover:bg-slate-800"
        >
          {isLoading ? "Buscando…" : "Buscar"}
        </Button>
      </div>

      <Card className="bg-slate-800/60 border-slate-700">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium text-slate-400">
            {isLoading ? "Carregando…" : `${users.length} usuário${users.length !== 1 ? "s" : ""}`}
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <div className="divide-y divide-slate-700/60">
            {users.map((user) => (
              <div key={user.id} className="flex items-center justify-between px-5 py-3">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-slate-200 truncate">{user.email}</p>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {user.enabled_extensions?.length ? (
                      user.enabled_extensions.map((ext) => (
                        <Badge
                          key={ext}
                          variant="secondary"
                          className="text-xs bg-indigo-900/50 text-indigo-300 border-indigo-700/50"
                        >
                          {AVAILABLE_EXTENSIONS.find((e) => e.id === ext)?.label ?? ext}
                        </Badge>
                      ))
                    ) : (
                      <span className="text-xs text-slate-600">Sem extensões ativas</span>
                    )}
                  </div>
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => openModal(user)}
                  className="ml-3 shrink-0 border-slate-600 text-slate-300 hover:bg-slate-700"
                >
                  Gerenciar
                </Button>
              </div>
            ))}
            {users.length === 0 && !isLoading && (
              <p className="px-5 py-10 text-center text-sm text-slate-500">
                Nenhum usuário encontrado.
              </p>
            )}
          </div>
        </CardContent>
      </Card>

      {modalUser && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
          onClick={() => setModalUser(null)}
        >
          <div
            className="bg-slate-800 border border-slate-700 rounded-xl shadow-xl p-6 max-w-sm mx-4 w-full"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between mb-4">
              <div>
                <h3 className="font-semibold text-slate-200">Extensões</h3>
                <p className="text-xs text-slate-400 mt-0.5 truncate max-w-[220px]">{modalUser.email}</p>
              </div>
              <button onClick={() => setModalUser(null)} className="text-slate-500 hover:text-slate-300">
                <X size={16} />
              </button>
            </div>

            <div className="space-y-2 mb-5">
              {AVAILABLE_EXTENSIONS.map((ext) => (
                <label key={ext.id} className="flex items-center gap-3 cursor-pointer group">
                  <input
                    type="checkbox"
                    className="h-4 w-4 rounded border-slate-600 accent-indigo-500"
                    checked={editExtensions.includes(ext.id)}
                    onChange={() => toggleExtension(ext.id)}
                  />
                  <span className="text-sm text-slate-300 group-hover:text-slate-100 transition-colors">
                    {ext.label}
                  </span>
                </label>
              ))}
            </div>

            <div className="flex gap-2">
              <Button
                className="flex-1 bg-indigo-600 hover:bg-indigo-500 text-white"
                onClick={saveExtensions}
                disabled={isSaving}
              >
                {isSaving ? "Salvando…" : "Salvar"}
              </Button>
              <Button
                variant="outline"
                onClick={() => setModalUser(null)}
                className="border-slate-600 text-slate-300 hover:bg-slate-700"
              >
                Cancelar
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
