import { useState } from "react";
import { NewLeadForm, LeadStatus } from "../types/crm";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Textarea } from "./ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetClose } from "./ui/sheet";
import { X } from "lucide-react";
import { api } from "@/services/api"; // ✅ ajuste o caminho conforme seu projeto

interface NewLeadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave?: (lead: NewLeadForm) => void | Promise<void>; // ✅ opcional
}

const LEAD_CATEGORIES: { value: LeadStatus; label: string }[] = [
  { value: 'to-prospect', label: 'À Prospectar' },
  { value: 'in-progress', label: 'Em Andamento' },
  { value: 'qualification', label: 'Qualificação' },
  { value: 'apresentation', label: 'Apresentação' },
  { value: 'follow-up', label: 'Follow-up' },
  { value: 'closing', label: 'Fechamento' },
  { value: 'client-list', label: 'Lista de Clientes' },
  { value: 'prospect-refused', label: 'Prospecção Recusada' },
  { value: 'disqualified', label: 'Desqualificados' },
];

export function NewLeadModal({ isOpen, onClose, onSave }: NewLeadModalProps) {
  const [formData, setFormData] = useState<NewLeadForm>({
    contactName: '',
    companyName: '',
    phone: '',
    origin: 'Manual',          // ✅ default ajuda o backend
    category: 'to-prospect',
    observations: '',
  });
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // ✅ inclua companyName para evitar 422 no backend
    if (!formData.contactName || !formData.phone || !formData.companyName) return;

    try {
      setLoading(true);

      if (typeof onSave === "function") {
        // pai controla a chamada à API
        await onSave(formData);
      } else {
        // ✅ fallback: chama a API direto daqui
        await api.createLead({
          companyName: formData.companyName,
          contactName: formData.contactName || null,
          phone: formData.phone || null,
          email: null,
          origin: formData.origin || "Manual",
          category: formData.category,
          customMessage: null,
          observations: formData.observations || null,
          priority: 1,
        });
      }

      // reset e fechar
      setFormData({
        companyName: '',
        contactName: '',
        phone: '',
        origin: 'Manual',
        category: 'to-prospect',
        observations: ''
      });
      onClose();
    } catch (err) {
      console.error("Erro ao salvar lead:", err);
    } finally {
      setLoading(false);
    }
  };

  const normalizePhoneOnBlur = (raw: string) => {
    const trimmed = (raw ?? "").trim();
    const digits = trimmed.replace(/\D/g, "");
    if (trimmed.startsWith("+")) {
      const pretty = `+${digits}`;
      if (digits.startsWith("351") && digits.length >= 12) {
        const local = digits.slice(3, 12);
        return `+351 ${local.slice(0,3)} ${local.slice(3,6)} ${local.slice(6,9)}`.trim();
      }
      return pretty;
    }
    if (digits.length === 9) {
      return `+351 ${digits.slice(0,3)} ${digits.slice(3,6)} ${digits.slice(6,9)}`.trim();
    }
    if (digits.length >= 12 && digits.startsWith("351")) {
      const local = digits.slice(3, 12);
      return `+351 ${local.slice(0,3)} ${local.slice(3,6)} ${local.slice(6,9)}`.trim();
    }
    return digits ? digits : "";
  };

  return (
    // ✅ fecha apenas quando o usuário fechar (não ao abrir)
    <Sheet open={isOpen} onOpenChange={(open) => { if (!open) onClose(); }}>
      <SheetContent side="right" className="w-[400px] sm:w-[500px] bg-card border-border">
        <SheetHeader className="pb-6">
          <div className="flex items-center justify-between">
            <SheetTitle className="text-xl font-bold text-foreground">
              Novo Lead
            </SheetTitle>
            <SheetClose asChild>
              <Button variant="ghost" size="sm" onClick={onClose}>
                <X className="w-4 h-4" />
              </Button>
            </SheetClose>
          </div>
        </SheetHeader>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="space-y-2">
            <Label htmlFor="name" className="text-sm font-medium">
              Nome *
            </Label>
            <Input
              id="name"
              value={formData.contactName}
              onChange={(e) => setFormData(prev => ({ ...prev, contactName: e.target.value }))}
              placeholder="Nome do contato"
              required
              className="bg-input border-border"
            />
          </div>

          {/* ✅ bloco correto da empresa (remove o <div /> solto) */}
          <div className="space-y-2">
            <Label htmlFor="company" className="text-sm font-medium">
              Empresa *
            </Label>
            <Input
              id="company"
              value={formData.companyName}
              onChange={(e) => setFormData(prev => ({ ...prev, companyName: e.target.value }))}
              placeholder="Nome da Empresa"
              required
              className="bg-input border-border"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="phone" className="text-sm font-medium">
              Telefone *
            </Label>
            <Input
              id="phone"
              value={formData.phone}
              onChange={(e) => setFormData(prev => ({ ...prev, phone: e.target.value }))}
              onBlur={(e) => setFormData(prev => ({ ...prev, phone: normalizePhoneOnBlur(e.target.value) }))}
              placeholder="+351 912 345 678"
              required
              className="bg-input border-border font-mono"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="origin" className="text-sm font-medium">
              Origem
            </Label>
            <Input
              id="origin"
              value={formData.origin}
              onChange={(e) => setFormData(prev => ({ ...prev, origin: e.target.value }))}
              placeholder="Website, LinkedIn, Indicação..."
              className="bg-input border-border"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="category" className="text-sm font-medium">
              Categoria
            </Label>
            <Select
              value={formData.category}
              onValueChange={(value: LeadStatus) => setFormData(prev => ({ ...prev, category: value }))}
            >
              <SelectTrigger className="bg-input border-border">
                <SelectValue placeholder="Selecione..." />
              </SelectTrigger>
              <SelectContent className="bg-popover border-border">
                {LEAD_CATEGORIES.map((category) => (
                  <SelectItem key={category.value} value={category.value}>
                    {category.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="observations" className="text-sm font-medium">
              Observações
            </Label>
            <Textarea
              id="observations"
              value={formData.observations}
              onChange={(e) => setFormData(prev => ({ ...prev, observations: e.target.value }))}
              placeholder="Informações adicionais sobre o lead..."
              rows={4}
              className="bg-input border-border resize-none"
            />
          </div>

          <div className="flex gap-3 pt-4">
            <Button
              type="submit"
              className="gradient-primary text-white flex-1 hover:shadow-glow transition-smooth"
              disabled={loading || !formData.contactName || !formData.phone || !formData.companyName}
            >
              {loading ? "Salvando..." : "Salvar Lead"}
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={onClose}
              className="border-border hover:bg-muted"
            >
              Cancelar
            </Button>
          </div>
        </form>
      </SheetContent>
    </Sheet>
  );
}