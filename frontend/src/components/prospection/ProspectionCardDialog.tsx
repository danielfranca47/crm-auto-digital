// src/components/prospection/ProspectionCardDialog.tsx
import React, { useEffect, useRef, useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { ProspectionLead } from "@/types/prospection";
import { useLeads } from "@/contexts/LeadsContext";
import {
  Phone,
  Mail,
  MapPin,
  Calendar as CalendarIcon,
  MessageSquare,
  Edit3,
  Save,
  X,
  Clock,
  Building2,
  User,
  CheckCircle2,
  XCircle,
  RefreshCcw
} from "lucide-react";
import { format, formatDistanceToNow } from "date-fns";
import { ptBR } from "date-fns/locale";
import { cn } from "@/lib/utils";
import { api, type LeadMessage } from "@/services/api";

interface ProspectionCardDialogProps {
  lead: ProspectionLead | null;
  isOpen: boolean;
  onClose: () => void;
  onUpdateLead?: (leadId: string, updates: Partial<ProspectionLead>) => void;
}

const statusColors = {
  "to-prospect": "bg-blue-100 text-blue-800 border-blue-300",
  "in-progress": "bg-yellow-100 text-yellow-800 border-yellow-300",
  prospected: "bg-green-100 text-green-800 border-green-300",
  "prospect-refused": "bg-red-100 text-red-800 border-red-300",
  disqualified: "bg-gray-100 text-gray-800 border-gray-300",
  "follow-up": "bg-purple-100 text-purple-800 border-purple-300",
  "meeting-scheduled": "bg-indigo-100 text-indigo-800 border-indigo-300",
  "no-show": "bg-orange-100 text-orange-800 border-orange-300",
  "in-negotiation": "bg-cyan-100 text-cyan-800 border-cyan-300",
  "closed-sale": "bg-emerald-100 text-emerald-800 border-emerald-300",
  "client-list": "bg-teal-100 text-teal-800 border-teal-300",
} as const;

const statusLabels = {
  "to-prospect": "À Prospectar",
  "in-progress": "Em Andamento",
  prospected: "Prospectado",
  "prospect-refused": "Prospecto Recusado",
  disqualified: "Desqualificado",
  "follow-up": "Follow-up",
  "meeting-scheduled": "Reunião Agendada",
  "no-show": "Não Compareceu",
  "in-negotiation": "Em Negociação",
  "closed-sale": "Venda Fechada",
  "client-list": "Lista de Clientes",
} as const;

// helper: separa Subject e Body de um texto de e-mail no formato "Assunto\n\nCorpo"
function parseEmailText(raw: string): { subject?: string; body: string } {
  const txt = (raw || "").trim();
  if (!txt) return { body: "" };
  const parts = txt.split(/\n{2,}/); // separa por linha em branco
  if (parts.length > 1) {
    const subject = parts.shift()!.trim();
    const body = parts.join("\n\n").trim();
    return { subject: subject || undefined, body };
  }
  return { body: txt };
}

// tipos leves para último status WA (tolerante a campos snake/camel case)
type LastWaRow = {
  id?: number;
  lead_id?: number | string;
  status?: "pending" | "sent" | "failed";
  processedAt?: string | null;
  processed_at?: string | null;
  lastError?: string | null;
  last_error?: string | null;
  body?: string | null;
};

function parseWhen(row?: LastWaRow) {
  const ts = row?.processedAt ?? row?.processed_at;
  return ts ? new Date(ts) : null;
}
function parseError(row?: LastWaRow) {
  return (row?.lastError ?? row?.last_error ?? "") || "";
}

export function ProspectionCardDialog({
  lead,
  isOpen,
  onClose,
  onUpdateLead,
}: ProspectionCardDialogProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [editedLead, setEditedLead] = useState<ProspectionLead | null>(null);

  const [companyName, setCompanyName] = useState("");
  const [contactName, setContactName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");

  const [emailMessage, setEmailMessage] = useState("");
  const [whatsappMessage, setWhatsappMessage] = useState("");
  const [followUpDate, setFollowUpDate] = useState<Date | undefined>(undefined);
  const [comments, setComments] = useState("");

  // status WhatsApp (último envio)
  const [lastWa, setLastWa] = useState<LastWaRow | null>(null);
  const [loadingLast, setLoadingLast] = useState(false);

  const { updateProspectionLead } = useLeads();
  const saveLead =
    onUpdateLead ??
    (async (id: string, patch: Partial<ProspectionLead>) => {
      await updateProspectionLead(id, patch as any);
    });

  // Evita setState após desmontar
  const mountedRef = useRef(true);
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  // carrega os valores iniciais quando trocar o lead
  useEffect(() => {
    if (!lead) return;

    setIsEditing(false);
    setEditedLead(lead);
    setCompanyName(lead.companyName || "");
    setContactName(lead.contactName || "");
    setPhone(lead.phone || "");
    setEmail(lead.email || "");
    setComments(lead.observations || "");
    setFollowUpDate(lead.nextScheduledAction?.date);

    (async () => {
      try {
        const resp = await api.assistenteIA.mensagens(lead.id, true);
        if (!mountedRef.current) return;

        if (resp?.ok && Array.isArray(resp.messages)) {
          const msgs = resp.messages as LeadMessage[];
          const emailMsg = msgs.find((m) => m.channel === "email");
          const wppMsg = msgs.find((m) => m.channel === "whatsapp");

          const emailText = emailMsg
            ? emailMsg.subject
              ? `${emailMsg.subject}\n\n${emailMsg.body}`
              : emailMsg.body
            : "";

          // prioriza customMessage salvo no lead (edição anterior)
          const customMsg = (lead as any)?.customMessage
            ? String((lead as any).customMessage).trim()
            : "";

          const wppText = customMsg || (wppMsg ? wppMsg.body : "");

          setEmailMessage(emailText);
          setWhatsappMessage(wppText);
        } else {
          setEmailMessage("");
          setWhatsappMessage(((lead as any)?.customMessage as string) || "");
        }
      } catch {
        if (!mountedRef.current) return;
        setEmailMessage("");
        setWhatsappMessage(((lead as any)?.customMessage as string) || "");
      }
    })();

    // carrega último status WhatsApp do lead
    loadLastWhatsStatus(String(lead.id));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lead]);

  async function loadLastWhatsStatus(leadId: string) {
    if (!leadId) return;
    try {
      setLoadingLast(true);

      // evita erro de tipagem do TS (mantendo a metodologia do api.ts)
      const anyApi: any = api;

      // 1) tenta endpoint específico por lead, SE existir
      const lastByLead = anyApi?.prospeccao?.whatsapp?.lastForLead;
      if (typeof lastByLead === "function") {
        const r = (await lastByLead(parseInt(leadId, 10))) as LastWaRow | null;
        if (mountedRef.current) setLastWa(r || null);
        return;
      }

      // 2) fallback: usa recent() e filtra pelo lead
      const recent = anyApi?.prospeccao?.whatsapp?.recent;
      if (typeof recent === "function") {
        const rows = (await recent(2880)) as LastWaRow[]; // últimas 48h
        const mine = Array.isArray(rows)
          ? rows
              .filter((r) => String(r.lead_id) === String(leadId))
              .sort((a, b) => {
                const ta = parseWhen(a)?.getTime() ?? 0;
                const tb = parseWhen(b)?.getTime() ?? 0;
                return tb - ta;
              })[0]
          : null;
        if (mountedRef.current) setLastWa(mine || null);
        return;
      }

      if (mountedRef.current) setLastWa(null);
    } catch {
      if (mountedRef.current) setLastWa(null);
    } finally {
      if (mountedRef.current) setLoadingLast(false);
    }
  }

  if (!lead || !editedLead) return null;

  const handleCancel = () => {
    if (!lead) return;
    setIsEditing(false);
    setEditedLead(lead);
    setCompanyName(lead.companyName || "");
    setContactName(lead.contactName || "");
    setPhone(lead.phone || "");
    setEmail(lead.email || "");
    setComments(lead.observations || "");
    setFollowUpDate(lead.nextScheduledAction?.date);
  };

  const handleSave = async () => {
    if (!editedLead || isSaving) return;
    setIsSaving(true);

    const leadIdNum = Number(editedLead.id);

    try {
      // 1) Atualiza campos do lead
      const patch: Partial<ProspectionLead> = {
        companyName,
        contactName,
        phone,
        email,
        observations: comments,
        // mantém também uma cópia no lead (MVP) para exibir de imediato
        // @ts-ignore (campo existe no backend)
        customMessage: whatsappMessage,
      };
      await saveLead(editedLead.id, patch);

      // 2) Persiste WhatsApp na tabela `messages` e seleciona como ativa
      const wppBody = (whatsappMessage || "").trim();
      if (wppBody.length > 0) {
        await api.prospeccao.saveMessage({
          lead_id: leadIdNum,
          channel: "whatsapp",
          body: wppBody,
          select: true, // seleciona como ativa p/ automação
        });
      }

      // 3) Persiste E-mail na tabela `messages` (subject opcional)
      const rawEmail = (emailMessage || "").trim();
      if (rawEmail.length > 0) {
        const { subject, body } = parseEmailText(rawEmail);
        if ((body || "").trim().length > 0) {
          await api.prospeccao.saveMessage({
            lead_id: leadIdNum,
            channel: "email",
            subject,
            body,
            select: false, // não seleciona automaticamente o e-mail
          });
        }
      }

      // 4) Follow-up (log simples)
      if (followUpDate) {
        const iso = new Date(followUpDate).toISOString();
        try {
          await api.prospeccao.registrarLog({
            lead_id: leadIdNum,
            action: "scheduled_followup",
            notes: `FOLLOWUP: ${iso}`,
          });
        } catch {
          /* silencioso no MVP */
        }
      }

      setIsEditing(false);

      // 5) (Opcional) recarrega as mensagens mais recentes para refletir a seleção
      try {
        const refreshed = await api.assistenteIA.mensagens(editedLead.id, true);
        if (!mountedRef.current) return;
        if (refreshed?.ok) {
          const wpp = (refreshed.messages as LeadMessage[]).find((m) => m.channel === "whatsapp");
          if (wpp) setWhatsappMessage(wpp.body);
        }
      } catch {
        /* ok ignorar */
      }
    } catch (e) {
      console.error("Falha ao salvar lead/copys:", e);
    } finally {
      if (mountedRef.current) setIsSaving(false);
    }
  };

  // bloco visual do status WhatsApp (acima do texto)
  const when = parseWhen(lastWa);
  const lastIsSent = lastWa?.status === "sent";
  const lastIsFailed = lastWa?.status === "failed";
  const lastError = parseError(lastWa);

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
        <DialogHeader className="space-y-4">
          <div className="flex items-center justify-between">
            <DialogTitle className="text-2xl font-bold flex items-center gap-2">
              <Building2 className="h-6 w-6 text-primary" />
              {editedLead.companyName}
            </DialogTitle>
            <div className="flex items-center gap-2">
              {!isEditing ? (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setIsEditing(true)}
                  className="flex items-center gap-2"
                >
                  <Edit3 className="h-4 w-4" />
                  Editar
                </Button>
              ) : (
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleCancel}
                    disabled={isSaving}
                    className="flex items-center gap-2"
                  >
                    <X className="h-4 w-4" />
                    Cancelar
                  </Button>
                  <Button size="sm" onClick={handleSave} disabled={isSaving} className="flex items-center gap-2">
                    <Save className="h-4 w-4" />
                    {isSaving ? "Salvando..." : "Salvar"}
                  </Button>
                </div>
              )}
            </div>
          </div>

          <div className="flex items-center gap-3">
            <Badge variant="secondary" className={cn("px-3 py-1", statusColors[editedLead.category])}>
              {statusLabels[editedLead.category]}
            </Badge>
            <Badge variant="outline" className="flex items-center gap-1">
              <MapPin className="h-3 w-3" />
              {editedLead.origin}
            </Badge>
          </div>
        </DialogHeader>

        <div className="space-y-6">
          {/* Informações Básicas */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-4">
              <h3 className="text-lg font-semibold border-b pb-2">Informações do Contato</h3>

              <div className="space-y-3">
                <div className="flex items-center gap-3">
                  <User className="h-4 w-4 text-muted-foreground" />
                  <div>
                    <Label className="text-sm font-medium">ID do Lead</Label>
                    <p className="text-sm text-muted-foreground">{editedLead.id}</p>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <User className="h-4 w-4 text-muted-foreground" />
                  <div>
                    <Label className="text-sm font-medium">Nome do Contato</Label>
                    <Input
                      value={contactName}
                      onChange={(e) => setContactName(e.target.value)}
                      disabled={!isEditing || isSaving}
                    />
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <Building2 className="h-4 w-4 text-muted-foreground" />
                  <div>
                    <Label className="text-sm font-medium">Empresa</Label>
                    <Input
                      value={companyName}
                      onChange={(e) => setCompanyName(e.target.value)}
                      disabled={!isEditing || isSaving}
                    />
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <Phone className="h-4 w-4 text-muted-foreground" />
                  <div>
                    <Label className="text-sm font-medium">Telefone</Label>
                    <Input value={phone} onChange={(e) => setPhone(e.target.value)} disabled={!isEditing || isSaving} />
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <Mail className="h-4 w-4 text-muted-foreground" />
                  <div>
                    <Label className="text-sm font-medium">E-mail</Label>
                    <Input value={email} onChange={(e) => setEmail(e.target.value)} disabled={!isEditing || isSaving} />
                  </div>
                </div>
              </div>
            </div>

            <div className="space-y-4">
              <h3 className="text-lg font-semibold border-b pb-2">Informações Temporais</h3>

              <div className="space-y-3">
                <div className="flex items-center gap-3">
                  <Clock className="h-4 w-4 text-muted-foreground" />
                  <div>
                    <Label className="text-sm font-medium">Data de Criação</Label>
                    <p className="text-sm">
                      {format(editedLead.createdAt, "dd/MM/yyyy 'às' HH:mm", { locale: ptBR })}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <Clock className="h-4 w-4 text-muted-foreground" />
                  <div>
                    <Label className="text-sm font-medium">Última Interação</Label>
                    <p className="text-sm">
                      {formatDistanceToNow(editedLead.lastMovement, { addSuffix: true, locale: ptBR })}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <Separator />

          {/* Status WhatsApp (acima do texto) */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold flex items-center gap-2">
                <MessageSquare className="h-5 w-5" />
                Status do WhatsApp
              </h3>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => lead && loadLastWhatsStatus(String(lead.id))}
                disabled={loadingLast}
                className="flex items-center gap-1"
                title="Atualizar status"
              >
                <RefreshCcw className={cn("h-4 w-4", loadingLast && "animate-spin")} />
                Atualizar
              </Button>
            </div>

            {/* etiqueta + detalhes */}
            {lastIsSent && (
              <div className="flex items-start gap-2 rounded-lg border border-green-200 bg-green-50 p-3">
                <CheckCircle2 className="h-5 w-5 text-green-600 mt-0.5" />
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <Badge className="bg-green-600 text-white">WhatsApp</Badge>
                    <span className="text-sm text-green-700 font-medium">Enviado com sucesso</span>
                  </div>
                  {when && (
                    <p className="text-xs text-green-700">
                      Enviado em {format(when, "dd/MM/yyyy 'às' HH:mm", { locale: ptBR })}
                    </p>
                  )}
                </div>
              </div>
            )}

            {lastIsFailed && (
              <div className="flex items-start gap-2 rounded-lg border border-rose-200 bg-rose-50 p-3">
                <XCircle className="h-5 w-5 text-rose-600 mt-0.5" />
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <Badge className="bg-rose-600 text-white">WhatsApp</Badge>
                    <span className="text-sm text-rose-700 font-medium">Falha no envio</span>
                  </div>
                  {when && (
                    <p className="text-xs text-rose-700">
                      Ocorreu em {format(when, "dd/MM/yyyy 'às' HH:mm", { locale: ptBR })}
                    </p>
                  )}
                  {lastError && <p className="text-xs text-rose-700">Motivo: {lastError}</p>}
                </div>
              </div>
            )}

            {!lastIsSent && !lastIsFailed && (
              <p className="text-xs text-muted-foreground">
                Nenhum envio recente para este lead ou ainda não há dados.
              </p>
            )}
          </div>

          {/* Mensagens de Prospecção */}
          <div className="space-y-4">
            <h3 className="text-lg font-semibold">Mensagens de Prospecção</h3>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="email-message">E-mail a ser Enviado</Label>
                <Textarea
                  id="email-message"
                  value={emailMessage}
                  onChange={(e) => setEmailMessage(e.target.value)}
                  placeholder="Digite a mensagem do e-mail... (1ª linha = assunto, linha em branco, corpo)"
                  className="min-h-[120px]"
                  disabled={!isEditing || isSaving}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="whatsapp-message">WhatsApp a ser Enviado</Label>
                <Textarea
                  id="whatsapp-message"
                  value={whatsappMessage}
                  onChange={(e) => setWhatsappMessage(e.target.value)}
                  placeholder="Digite a mensagem do WhatsApp..."
                  className="min-h-[120px]"
                  disabled={!isEditing || isSaving}
                />
              </div>
            </div>
          </div>

          <Separator />

          {/* Agenda e Comentários */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-3">
              <Label>Data para Retornar Contato</Label>
              <Popover>
                <PopoverTrigger asChild>
                  <Button
                    variant="outline"
                    className={cn("w-full justify-start text-left font-normal", !followUpDate && "text-muted-foreground")}
                    disabled={!isEditing || isSaving}
                  >
                    <CalendarIcon className="mr-2 h-4 w-4" />
                    {followUpDate ? format(followUpDate, "dd/MM/yyyy", { locale: ptBR }) : "Selecionar data"}
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-auto p-0" align="start">
                  <Calendar mode="single" selected={followUpDate} onSelect={setFollowUpDate} initialFocus className="pointer-events-auto" />
                </PopoverContent>
              </Popover>
            </div>

            <div className="space-y-3">
              <Label htmlFor="comments">Comentários/Notas</Label>
              <Textarea
                id="comments"
                value={comments}
                onChange={(e) => setComments(e.target.value)}
                placeholder="Adicione comentários ou notas sobre o lead..."
                className="min-h-[120px]"
                disabled={!isEditing || isSaving}
              />
            </div>
          </div>

          {/* Tarefas de Prospecção */}
          {editedLead.prospectionTasks && editedLead.prospectionTasks.length > 0 && (
            <>
              <Separator />
              <div className="space-y-3">
                <h3 className="text-lg font-semibold flex items-center gap-2">
                  <MessageSquare className="h-5 w-5" />
                  Tarefas de Prospecção
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  {editedLead.prospectionTasks.map((task) => (
                    <div
                      key={task.id}
                      className={cn(
                        "p-3 rounded-lg border",
                        task.completed ? "bg-green-50 border-green-200" : "bg-gray-50 border-gray-200"
                      )}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-medium capitalize">{task.method}</span>
                        <Badge variant={task.completed ? "default" : "secondary"}>
                          {task.completed ? "Concluído" : "Pendente"}
                        </Badge>
                      </div>
                      {task.completedAt && (
                        <p className="text-xs text-muted-foreground mt-1">
                          Concluído {formatDistanceToNow(task.completedAt, { addSuffix: true, locale: ptBR })}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
