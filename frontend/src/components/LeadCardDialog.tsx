import { Lead, LeadStatus } from "../types/crm";
import { Calendar, Building2, User, Phone, Mail, MessageSquare, Clock, Tag, FileText, Plus } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "./ui/dialog";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Textarea } from "./ui/textarea";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Separator } from "./ui/separator";
import { useState, useEffect } from "react";

interface LeadCardDialogProps {
  lead: Lead | null;
  isOpen: boolean;
  onClose: () => void;
  onUpdateLead?: (leadId: string, updates: Partial<Lead>) => void;
}

const statusColors: Record<LeadStatus, string> = {
  'to-prospect': 'bg-gray-500',
  'prospected': 'bg-blue-500',
  'prospect-refused': 'bg-red-500',
  'disqualified': 'bg-red-600',
  'follow-up': 'bg-yellow-500',
  'meeting-scheduled': 'bg-purple-500',
  'no-show': 'bg-orange-500',
  'in-negotiation': 'bg-indigo-500',
  'closed-sale': 'bg-green-500',
  'client-list': 'bg-emerald-600',
};

const statusLabels: Record<LeadStatus, string> = {
  'to-prospect': 'A Prospectar',
  'prospected': 'Prospectado',
  'prospect-refused': 'Recusou Prospecção',
  'disqualified': 'Desqualificado',
  'follow-up': 'Follow-up',
  'meeting-scheduled': 'Reunião Agendada',
  'no-show': 'Não Compareceu',
  'in-negotiation': 'Em Negociação',
  'closed-sale': 'Venda Fechada',
  'client-list': 'Lista de Clientes',
};

export function LeadCardDialog({ lead, isOpen, onClose, onUpdateLead }: LeadCardDialogProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editedLead, setEditedLead] = useState<Lead | null>(null);

  useEffect(() => {
    if (lead) {
      setEditedLead({ ...lead });
    }
  }, [lead]);

  if (!lead) return null;

  const formatDate = (date: Date) => {
    return new Intl.DateTimeFormat('pt-PT', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    }).format(date);
  };

  const formatDateOnly = (date: Date) => {
    return new Intl.DateTimeFormat('pt-PT', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric'
    }).format(date);
  };

  const handleSave = () => {
    if (editedLead && onUpdateLead) {
      onUpdateLead(lead.id, editedLead);
      setIsEditing(false);
    }
  };

  const handleCancel = () => {
    setEditedLead({ ...lead });
    setIsEditing(false);
  };

  const currentLead = isEditing ? editedLead! : lead;

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <div className="flex items-start justify-between">
            <div className="space-y-2">
              <DialogTitle className="text-xl font-semibold text-foreground">
                {currentLead.companyName || currentLead.contactName}
              </DialogTitle>
              <div className="flex items-center gap-2">
                <Badge 
                  className="text-white"
                  style={{ backgroundColor: statusColors[currentLead.category] }}
                >
                  {statusLabels[currentLead.category]}
                </Badge>
                <span className="text-xs text-muted-foreground">
                  ID: {currentLead.id}
                </span>
              </div>
            </div>
            <div className="flex gap-2">
              {!isEditing ? (
                <Button 
                  variant="outline" 
                  size="sm"
                  onClick={() => setIsEditing(true)}
                >
                  Editar
                </Button>
              ) : (
                <>
                  <Button 
                    variant="outline" 
                    size="sm"
                    onClick={handleCancel}
                  >
                    Cancelar
                  </Button>
                  <Button 
                    size="sm"
                    onClick={handleSave}
                  >
                    Salvar
                  </Button>
                </>
              )}
            </div>
          </div>
        </DialogHeader>

        <div className="space-y-6">
          {/* Informações Básicas */}
          <div className="space-y-4">
            <h3 className="text-lg font-medium text-foreground flex items-center gap-2">
              <Building2 className="h-5 w-5" />
              Informações Básicas
            </h3>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="companyName" className="text-sm font-medium">Nome da Empresa</Label>
                {isEditing ? (
                  <Input
                    id="companyName"
                    value={editedLead?.companyName || ''}
                    onChange={(e) => setEditedLead(prev => prev ? { ...prev, companyName: e.target.value } : null)}
                    placeholder="Nome da empresa"
                  />
                ) : (
                  <p className="text-sm text-foreground">{currentLead.companyName || 'Não informado'}</p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="contactName" className="text-sm font-medium">Nome do Contato</Label>
                {isEditing ? (
                  <Input
                    id="contactName"
                    value={editedLead?.contactName || ''}
                    onChange={(e) => setEditedLead(prev => prev ? { ...prev, contactName: e.target.value } : null)}
                    placeholder="Nome do contato"
                  />
                ) : (
                  <div className="flex items-center gap-2 text-sm text-foreground">
                    <User className="h-4 w-4" />
                    {currentLead.contactName}
                  </div>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="phone" className="text-sm font-medium">Telefone</Label>
                {isEditing ? (
                  <Input
                    id="phone"
                    value={editedLead?.phone || ''}
                    onChange={(e) => setEditedLead(prev => prev ? { ...prev, phone: e.target.value } : null)}
                    placeholder="Telefone"
                  />
                ) : (
                  <div className="flex items-center gap-2 text-sm text-foreground">
                    <Phone className="h-4 w-4" />
                    {currentLead.phone}
                  </div>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="email" className="text-sm font-medium">Email</Label>
                {isEditing ? (
                  <Input
                    id="email"
                    type="email"
                    value={editedLead?.email || ''}
                    onChange={(e) => setEditedLead(prev => prev ? { ...prev, email: e.target.value } : null)}
                    placeholder="Email"
                  />
                ) : (
                  <div className="flex items-center gap-2 text-sm text-foreground">
                    <Mail className="h-4 w-4" />
                    {currentLead.email || 'Não informado'}
                  </div>
                )}
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="origin" className="text-sm font-medium">Fonte do Lead</Label>
              {isEditing ? (
                <Input
                  id="origin"
                  value={editedLead?.origin || ''}
                  onChange={(e) => setEditedLead(prev => prev ? { ...prev, origin: e.target.value } : null)}
                  placeholder="Ex: Indicação, Website, Google Ads..."
                />
              ) : (
                <div className="flex items-center gap-2 text-sm text-foreground">
                  <Tag className="h-4 w-4" />
                  {currentLead.origin}
                </div>
              )}
            </div>
          </div>

          <Separator />

          {/* Mensagens e Notas */}
          <div className="space-y-4">
            <h3 className="text-lg font-medium text-foreground flex items-center gap-2">
              <MessageSquare className="h-5 w-5" />
              Mensagens e Notas
            </h3>

            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="customMessage" className="text-sm font-medium">Mensagem Personalizada</Label>
                {isEditing ? (
                  <Textarea
                    id="customMessage"
                    value={editedLead?.customMessage || ''}
                    onChange={(e) => setEditedLead(prev => prev ? { ...prev, customMessage: e.target.value } : null)}
                    placeholder="Mensagem personalizada para este lead..."
                    rows={3}
                  />
                ) : (
                  <p className="text-sm text-foreground bg-muted p-3 rounded-md">
                    {currentLead.customMessage || 'Nenhuma mensagem personalizada'}
                  </p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="observations" className="text-sm font-medium">Comentários/Notas</Label>
                {isEditing ? (
                  <Textarea
                    id="observations"
                    value={editedLead?.observations || ''}
                    onChange={(e) => setEditedLead(prev => prev ? { ...prev, observations: e.target.value } : null)}
                    placeholder="Comentários e observações internas..."
                    rows={3}
                  />
                ) : (
                  <p className="text-sm text-foreground bg-muted p-3 rounded-md">
                    {currentLead.observations || 'Nenhuma observação'}
                  </p>
                )}
              </div>
            </div>
          </div>

          <Separator />

          {/* Datas e Ações */}
          <div className="space-y-4">
            <h3 className="text-lg font-medium text-foreground flex items-center gap-2">
              <Clock className="h-5 w-5" />
              Cronologia e Ações
            </h3>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label className="text-sm font-medium">Data de Criação</Label>
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Calendar className="h-4 w-4" />
                  {formatDate(currentLead.createdAt)}
                </div>
              </div>

              <div className="space-y-2">
                <Label className="text-sm font-medium">Última Interação</Label>
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Calendar className="h-4 w-4" />
                  {formatDate(currentLead.lastMovement)}
                </div>
              </div>
            </div>

            <div className="space-y-2">
              <Label className="text-sm font-medium">Próxima Ação Agendada</Label>
              {isEditing ? (
                <div className="space-y-2">
                  <Input
                    type="datetime-local"
                    value={editedLead?.nextScheduledAction?.date ? 
                      new Date(editedLead.nextScheduledAction.date.getTime() - editedLead.nextScheduledAction.date.getTimezoneOffset() * 60000).toISOString().slice(0, 16) : ''
                    }
                    onChange={(e) => {
                      const date = e.target.value ? new Date(e.target.value) : null;
                      setEditedLead(prev => prev ? { 
                        ...prev, 
                        nextScheduledAction: date ? {
                          date,
                          description: prev.nextScheduledAction?.description || ''
                        } : undefined
                      } : null);
                    }}
                  />
                  <Input
                    placeholder="Descrição da ação..."
                    value={editedLead?.nextScheduledAction?.description || ''}
                    onChange={(e) => setEditedLead(prev => prev ? { 
                      ...prev, 
                      nextScheduledAction: prev.nextScheduledAction ? {
                        ...prev.nextScheduledAction,
                        description: e.target.value
                      } : { date: new Date(), description: e.target.value }
                    } : null)}
                  />
                </div>
              ) : (
                <div className="bg-muted p-3 rounded-md">
                  {currentLead.nextScheduledAction ? (
                    <div className="space-y-1">
                      <div className="flex items-center gap-2 text-sm font-medium text-foreground">
                        <Calendar className="h-4 w-4" />
                        {formatDate(currentLead.nextScheduledAction.date)}
                      </div>
                      <p className="text-sm text-muted-foreground">
                        {currentLead.nextScheduledAction.description}
                      </p>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      <Plus className="h-4 w-4" />
                      Nenhuma ação agendada
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}