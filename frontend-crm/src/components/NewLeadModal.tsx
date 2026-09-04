import { useState } from "react";
import { NewLeadForm, LeadStatus } from "../types/crm";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Textarea } from "./ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetClose } from "./ui/sheet";
import { X } from "lucide-react";
import { api } from "@/services/api";
import { useApiErrorHandler } from "@/hooks/useApiErrorHandler";
import { LEAD_DIRECTION_OPTIONS } from "@/lib/lead-origin";

interface NewLeadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave?: (lead: NewLeadForm) => void | Promise<void>;
}

const LEAD_CATEGORIES: { value: LeadStatus; label: string }[] = [
  { value: "to-prospect", label: "À Prospectar" },
  { value: "in-progress", label: "Em Andamento" },
  { value: "qualification", label: "Qualificação" },
  { value: "apresentation", label: "Apresentação" },
  { value: "follow-up", label: "Follow-up" },
  { value: "closing", label: "Fechamento" },
  { value: "client-list", label: "Lista de Clientes" },
  { value: "prospect-refused", label: "Prospecção Recusada" },
  { value: "disqualified", label: "Desqualificados" },
];

const COUNTRY_OPTIONS = [
  { code: "BR", label: "🇧🇷 Brasil (+55)" },
  { code: "PT", label: "🇵🇹 Portugal (+351)" },
  { code: "US", label: "🇺🇸 Estados Unidos (+1)" },
  { code: "ES", label: "🇪🇸 Espanha (+34)" },
  { code: "FR", label: "🇫🇷 França (+33)" },
  { code: "IT", label: "🇮🇹 Itália (+39)" },
  { code: "DE", label: "🇩🇪 Alemanha (+49)" },
  { code: "GB", label: "🇬🇧 Reino Unido (+44)" },
  { code: "NL", label: "🇳🇱 Holanda (+31)" },
  { code: "IE", label: "🇮🇪 Irlanda (+353)" },
];

const DEFAULT_COUNTRY_CODE = "BR";
const sanitizeLocalPhone = (raw: string) => (raw ?? "").replace(/[^\d\s]/g, "").trim();

export function NewLeadModal({ isOpen, onClose, onSave }: NewLeadModalProps) {
  const [formData, setFormData] = useState<NewLeadForm>({
    contactName: "",
    companyName: "",
    phone: "",
    country_code: DEFAULT_COUNTRY_CODE,
    origin: "Manual",
    acquisition_channel: "",
    category: "to-prospect",
    observations: "",
  });
  const [loading, setLoading] = useState(false);
  const { handleError } = useApiErrorHandler();

  const hasContactName = Boolean(formData.contactName.trim());
  const hasCompanyName = Boolean(formData.companyName.trim());
  const requiresDirection = formData.category !== "to-prospect";
  const canSubmit =
    Boolean(formData.phone) &&
    (hasContactName || hasCompanyName) &&
    (!requiresDirection || Boolean(formData.origin));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!canSubmit) return;

    try {
      setLoading(true);

      const payload = {
        ...formData,
        phone: sanitizeLocalPhone(formData.phone),
        country_code: (formData.country_code || DEFAULT_COUNTRY_CODE).toUpperCase(),
      };

      if (typeof onSave === "function") {
        await onSave(payload);
      } else {
        await api.createLead({
          companyName: payload.companyName.trim() || null,
          contactName: payload.contactName.trim() || null,
          phone: payload.phone || null,
          country_code: payload.country_code,
          email: null,
          origin: payload.origin || "Manual",
          acquisition_channel: payload.acquisition_channel || null,
          category: payload.category,
          customMessage: null,
          observations: payload.observations || null,
          priority: 1,
        });
      }

      setFormData({
        companyName: "",
        contactName: "",
        phone: "",
        country_code: DEFAULT_COUNTRY_CODE,
        origin: "Manual",
        acquisition_channel: "",
        category: "to-prospect",
        observations: "",
      });
      onClose();
    } catch (err) {
      handleError(err, { fallbackMessage: "Não foi possível criar o lead." });
    } finally {
      setLoading(false);
    }
  };

  return (
    <Sheet
      open={isOpen}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <SheetContent side="right" className="w-[400px] sm:w-[500px] bg-card border-border">
        <SheetHeader className="pb-6">
          <div className="flex items-center justify-between">
            <SheetTitle className="text-xl font-bold text-foreground">Novo Lead</SheetTitle>
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
              Nome
            </Label>
            <Input
              id="name"
              value={formData.contactName}
              onChange={(e) => setFormData((prev) => ({ ...prev, contactName: e.target.value }))}
              placeholder="Nome do contato"
              className="bg-input border-border"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="company" className="text-sm font-medium">
              Empresa
            </Label>
            <Input
              id="company"
              value={formData.companyName}
              onChange={(e) => setFormData((prev) => ({ ...prev, companyName: e.target.value }))}
              placeholder="Nome da Empresa"
              className="bg-input border-border"
            />
            {!hasContactName && !hasCompanyName && (
              <p className="text-xs text-muted-foreground">Preencha ao menos o Nome ou a Empresa.</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="country" className="text-sm font-medium">
              País *
            </Label>
            <Select
              value={formData.country_code || DEFAULT_COUNTRY_CODE}
              onValueChange={(value) => setFormData((prev) => ({ ...prev, country_code: value }))}
            >
              <SelectTrigger id="country" className="bg-input border-border">
                <SelectValue placeholder="Selecione o país" />
              </SelectTrigger>
              <SelectContent className="bg-popover border-border">
                {COUNTRY_OPTIONS.map((country) => (
                  <SelectItem key={country.code} value={country.code}>
                    {country.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="phone" className="text-sm font-medium">
              Número local *
            </Label>
            <Input
              id="phone"
              value={formData.phone}
              onChange={(e) =>
                setFormData((prev) => ({
                  ...prev,
                  phone: sanitizeLocalPhone(e.target.value),
                }))
              }
              placeholder="11999999999"
              required
              className="bg-input border-border font-mono"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="category" className="text-sm font-medium">
              Categoria
            </Label>
            <Select
              value={formData.category}
              onValueChange={(value: LeadStatus) =>
                setFormData((prev) => ({
                  ...prev,
                  category: value,
                  // "À Prospectar" ainda não teve contacto — a direção fica em aberto até o
                  // ProspectConfirmModal perguntar, no drag do Kanban. Fora disso, é obrigatório
                  // escolher agora.
                  origin: value === "to-prospect" ? "Manual" : "",
                }))
              }
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

          {requiresDirection && (
            <div className="space-y-2">
              <Label htmlFor="origin" className="text-sm font-medium">
                Direção *
              </Label>
              <Select
                value={formData.origin}
                onValueChange={(value) => setFormData((prev) => ({ ...prev, origin: value }))}
              >
                <SelectTrigger id="origin" className="bg-input border-border">
                  <SelectValue placeholder="Quem procurou primeiro?" />
                </SelectTrigger>
                <SelectContent className="bg-popover border-border">
                  {LEAD_DIRECTION_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          <div className="space-y-2">
            <Label htmlFor="acquisition_channel" className="text-sm font-medium">
              Canal de aquisição
            </Label>
            <Input
              id="acquisition_channel"
              value={formData.acquisition_channel}
              onChange={(e) => setFormData((prev) => ({ ...prev, acquisition_channel: e.target.value }))}
              placeholder="Facebook Ads, Google Ads, Indicação, Website..."
              className="bg-input border-border"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="observations" className="text-sm font-medium">
              Observações
            </Label>
            <Textarea
              id="observations"
              value={formData.observations}
              onChange={(e) => setFormData((prev) => ({ ...prev, observations: e.target.value }))}
              placeholder="Informações adicionais sobre o lead..."
              rows={4}
              className="bg-input border-border resize-none"
            />
          </div>

          <div className="flex gap-3 pt-4">
            <Button
              type="submit"
              className="gradient-primary text-white flex-1 hover:shadow-glow transition-smooth"
              disabled={loading || !canSubmit}
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
