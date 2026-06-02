import { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api } from "@/services/api";
import { useToast } from "@/hooks/use-toast";
import { Search, X, User, UserPlus } from "lucide-react";
import type { AdminUser, CrmPlan } from "@/services/api";

const AVAILABLE_EXTENSIONS = [
  { id: "website_audit", label: "Auditoria de Site" },
  { id: "instagram_profile", label: "Perfil Instagram" },
  { id: "linkedin_company", label: "LinkedIn Empresa" },
  { id: "google_reviews", label: "Avaliações Google" },
];

const PLAN_BADGE_CLASSES: Record<string, string> = {
  start: "bg-slate-700/60 text-slate-300 border-slate-600",
  growth: "bg-indigo-900/50 text-indigo-300 border-indigo-700/50",
  scale: "bg-violet-900/50 text-violet-300 border-violet-700/50",
  enterprise: "bg-amber-900/50 text-amber-300 border-amber-700/50",
};

function planBadgeClass(code?: string): string {
  if (!code) return "bg-slate-700/40 text-slate-500 border-slate-700";
  return PLAN_BADGE_CLASSES[code.toLowerCase()] ?? "bg-slate-700/60 text-slate-300 border-slate-600";
}

function fmtDate(iso?: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("pt-PT", { day: "2-digit", month: "short", year: "numeric" });
}

export default function AdminUsers() {
  const { toast } = useToast();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [search, setSearch] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [modalUser, setModalUser] = useState<AdminUser | null>(null);
  const [editExtensions, setEditExtensions] = useState<string[]>([]);
  const [isSaving, setIsSaving] = useState(false);

  const [createModal, setCreateModal] = useState(false);
  const [newEmail, setNewEmail] = useState("");
  const [newName, setNewName] = useState("");
  const [isCreating, setIsCreating] = useState(false);

  const [planModal, setPlanModal] = useState<AdminUser | null>(null);
  const [plans, setPlans] = useState<CrmPlan[]>([]);
  const [selectedPlan, setSelectedPlan] = useState("");
  const [planMonths, setPlanMonths] = useState(1);
  const [isTrial, setIsTrial] = useState(false);
  const [isAssigning, setIsAssigning] = useState(false);

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

  const openPlanModal = async (user: AdminUser) => {
    setPlanModal(user);
    setSelectedPlan(user.plan_code ?? "");
    setPlanMonths(1);
    setIsTrial(false);
    if (plans.length === 0) {
      try {
        const data = await api.listCrmPlans();
        setPlans(data);
        if (!user.plan_code && data.length > 0) setSelectedPlan(data[0].code);
      } catch {
        toast({ title: "Erro ao carregar planos", variant: "destructive" });
      }
    }
  };

  const handleAssignPlan = async () => {
    if (!planModal || !selectedPlan) return;
    setIsAssigning(true);
    try {
      const res = await api.assignPlan(planModal.id, selectedPlan, planMonths, isTrial);
      toast({
        title: "Plano atribuído",
        description: `${planModal.email} → ${res.plan_name}${isTrial ? " (trial 7 dias)" : ""}`,
      });
      setPlanModal(null);
      loadUsers();
    } catch (err: unknown) {
      toast({
        title: "Erro ao atribuir plano",
        description: err instanceof Error ? err.message : "Erro desconhecido",
        variant: "destructive",
      });
    } finally {
      setIsAssigning(false);
    }
  };

  const handleCreateUser = async () => {
    if (!newEmail) return;
    setIsCreating(true);
    try {
      const res = await api.createUser(newEmail, newName || undefined);
      toast({
        title: "Conta criada",
        description: res.email_sent
          ? `Email de boas-vindas enviado para ${res.email}.`
          : `Conta criada para ${res.email}. Email não enviado (SMTP não configurado).`,
      });
      setCreateModal(false);
      setNewEmail("");
      setNewName("");
      loadUsers();
    } catch (err: unknown) {
      toast({
        title: "Erro ao criar conta",
        description: err instanceof Error ? err.message : "Erro desconhecido",
        variant: "destructive",
      });
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <div className="p-6 max-w-5xl">
      <div className="flex items-center justify-between mb-1">
        <h1 className="text-xl font-semibold text-slate-200">Usuários</h1>
        <Button
          size="sm"
          onClick={() => setCreateModal(true)}
          className="bg-indigo-600 hover:bg-indigo-500 text-white flex items-center gap-1.5"
        >
          <UserPlus size={14} />
          Criar conta
        </Button>
      </div>
      <p className="text-slate-500 text-sm mb-5">Gestão de clientes, planos e extensões ativas.</p>

      <div className="flex gap-3 mb-5">
        <div className="relative flex-1 max-w-sm">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <Input
            placeholder="Buscar por email ou nome…"
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
          {/* Table header */}
          <div className="hidden md:grid grid-cols-[minmax(0,1fr)_105px_75px_95px_95px_110px] gap-x-3 px-5 py-2 border-b border-slate-700/60 text-xs font-medium text-slate-500 uppercase tracking-wide">
            <span>Usuário</span>
            <span>Plano</span>
            <span>Status</span>
            <span title="Início da assinatura">Início sub.</span>
            <span title="Data de expiração da assinatura">Expira</span>
            <span />
          </div>

          <div className="divide-y divide-slate-700/60">
            {users.map((user) => (
              <div
                key={user.id}
                className="grid grid-cols-1 md:grid-cols-[minmax(0,1fr)_105px_75px_95px_95px_110px] gap-x-3 gap-y-1 items-center px-5 py-3"
              >
                {/* Name / email */}
                <div className="min-w-0 flex items-center gap-2">
                  <div className="shrink-0 w-7 h-7 rounded-full bg-slate-700 flex items-center justify-center">
                    <User size={13} className="text-slate-400" />
                  </div>
                  <div className="min-w-0">
                    {user.name && (
                      <p className="text-sm font-medium text-slate-200 truncate">{user.name}</p>
                    )}
                    <p className={`text-xs truncate ${user.name ? "text-slate-500" : "text-sm font-medium text-slate-200"}`}>
                      {user.email}
                    </p>
                  </div>
                </div>

                {/* Plan */}
                <div className="flex items-center gap-1 flex-wrap">
                  <Badge
                    variant="outline"
                    className={`text-xs ${planBadgeClass(user.plan_code)}`}
                  >
                    {user.plan_name ?? "Sem plano"}
                  </Badge>
                  {user.subscription_is_trial && (
                    <Badge variant="outline" className="text-xs bg-amber-900/40 text-amber-400 border-amber-700/50">
                      Trial
                    </Badge>
                  )}
                </div>

                {/* Status */}
                <div className="flex items-center">
                  <Badge
                    variant="outline"
                    className={`text-xs ${
                      user.status === "active"
                        ? "bg-emerald-900/40 text-emerald-400 border-emerald-700/50"
                        : "bg-red-900/40 text-red-400 border-red-700/50"
                    }`}
                  >
                    {user.status === "active" ? "Ativo" : user.status}
                  </Badge>
                </div>

                {/* Subscription start */}
                <span className="text-xs text-slate-400" title={user.created_at ? `Conta criada: ${fmtDate(user.created_at)}` : ""}>
                  {user.subscription_period_start ? fmtDate(user.subscription_period_start) : "—"}
                </span>

                {/* Expiry */}
                <span className={`text-xs ${user.subscription_period_end ? "text-slate-400" : "text-slate-600"}`}>
                  {user.subscription_period_end ? fmtDate(user.subscription_period_end) : "—"}
                </span>

                {/* Actions */}
                <div className="flex items-center gap-1">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => openPlanModal(user)}
                    className="text-xs border-indigo-700/50 text-indigo-300 hover:bg-indigo-900/40"
                  >
                    Plano
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => openModal(user)}
                    className="text-xs border-slate-600 text-slate-300 hover:bg-slate-700"
                  >
                    Ext.
                  </Button>
                </div>
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

      {/* Assign plan modal */}
      {planModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={() => setPlanModal(null)}>
          <div className="bg-slate-800 border border-slate-700 rounded-xl shadow-xl p-6 max-w-sm mx-4 w-full" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-start justify-between mb-4">
              <div>
                <h3 className="font-semibold text-slate-200">Atribuir plano</h3>
                <p className="text-xs text-slate-400 mt-0.5 truncate max-w-[220px]">
                  {planModal.name ? `${planModal.name} · ` : ""}{planModal.email}
                </p>
              </div>
              <button onClick={() => setPlanModal(null)} className="text-slate-500 hover:text-slate-300"><X size={16} /></button>
            </div>

            <div className="space-y-3 mb-5">
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Plano</label>
                <select
                  value={selectedPlan}
                  onChange={(e) => setSelectedPlan(e.target.value)}
                  className="w-full rounded-lg bg-slate-700 border border-slate-600 text-slate-200 px-3 py-2 text-sm"
                >
                  {plans.map((p) => (
                    <option key={p.code} value={p.code}>{p.name}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Duração (meses)</label>
                <input
                  type="number"
                  min={1}
                  max={24}
                  value={planMonths}
                  onChange={(e) => setPlanMonths(Number(e.target.value))}
                  disabled={isTrial}
                  className="w-full rounded-lg bg-slate-700 border border-slate-600 text-slate-200 px-3 py-2 text-sm disabled:opacity-50"
                />
              </div>

              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded border-slate-600 accent-indigo-500"
                  checked={isTrial}
                  onChange={(e) => setIsTrial(e.target.checked)}
                />
                <span className="text-sm text-slate-300">Trial 7 dias</span>
              </label>
            </div>

            <div className="flex gap-2">
              <Button
                className="flex-1 bg-indigo-600 hover:bg-indigo-500 text-white"
                onClick={handleAssignPlan}
                disabled={isAssigning || !selectedPlan}
              >
                {isAssigning ? "Atribuindo…" : "Confirmar"}
              </Button>
              <Button variant="outline" onClick={() => setPlanModal(null)} className="border-slate-600 text-slate-300 hover:bg-slate-700">
                Cancelar
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Create user modal */}
      {createModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
          onClick={() => setCreateModal(false)}
        >
          <div
            className="bg-slate-800 border border-slate-700 rounded-xl shadow-xl p-6 max-w-sm mx-4 w-full"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between mb-4">
              <h3 className="font-semibold text-slate-200">Criar conta</h3>
              <button onClick={() => setCreateModal(false)} className="text-slate-500 hover:text-slate-300">
                <X size={16} />
              </button>
            </div>

            <div className="space-y-3 mb-5">
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Nome (opcional)</label>
                <Input
                  placeholder="Nome do cliente"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  className="bg-slate-700 border-slate-600 text-slate-200 placeholder:text-slate-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Email *</label>
                <Input
                  type="email"
                  placeholder="cliente@email.com"
                  value={newEmail}
                  onChange={(e) => setNewEmail(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleCreateUser()}
                  className="bg-slate-700 border-slate-600 text-slate-200 placeholder:text-slate-500"
                />
              </div>
            </div>

            <div className="flex gap-2">
              <Button
                className="flex-1 bg-indigo-600 hover:bg-indigo-500 text-white"
                onClick={handleCreateUser}
                disabled={isCreating || !newEmail}
              >
                {isCreating ? "Criando…" : "Criar e enviar email"}
              </Button>
              <Button
                variant="outline"
                onClick={() => setCreateModal(false)}
                className="border-slate-600 text-slate-300 hover:bg-slate-700"
              >
                Cancelar
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Extensions modal */}
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
                <p className="text-xs text-slate-400 mt-0.5 truncate max-w-[220px]">
                  {modalUser.name ? `${modalUser.name} · ` : ""}{modalUser.email}
                </p>
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
