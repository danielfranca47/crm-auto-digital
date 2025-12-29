import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { useApiErrorHandler } from "@/hooks/useApiErrorHandler";
import { useToast } from "@/hooks/use-toast";
import { api, AiProfilePayload, AiTemplate, KnowledgeItem } from "@/services/api";
import { useUsage } from "@/hooks/useUsage";
import { AlertCircle, Brain, FileEdit, FilePlus, RefreshCw, Sparkles, Upload, Wand2 } from "lucide-react";

const fallbackTemplates: Record<
  string,
  { name: string; description: string; tone: string; goals: string[] }
> = {
  sdr_padrao: {
    name: "SDR Padrão",
    description: "Abordagem consultiva para prospecção e qualificação inicial.",
    tone: "profissional e próximo",
    goals: ["Gerar interesse", "Agendar reuniões", "Nutrir leads frios"],
  },
  consultor_especialista: {
    name: "Consultor Especialista",
    description: "Consultor para vendas high-ticket com foco em discovery profundo.",
    tone: "consultivo e estratégico",
    goals: ["Conduzir discovery", "Mapear dores", "Elevar autoridade"],
  },
  closer_agressivo: {
    name: "Closer Agressivo",
    description: "Closer para low-ticket com senso de urgência controlado.",
    tone: "direto e objetivo",
    goals: ["Gerar urgência", "Objeções rápidas", "Fechar no primeiro contato"],
  },
};

const initialProfileState: AiProfilePayload = {
  template_key: "",
  name: "",
  brand_name: "",
  tone_of_voice: "",
  niche: "",
  target_audience: "",
  offer_description: "",
  goals: "",
  custom_instructions: "",
};

const goalSuggestions = [
  "Agendar demos qualificadas",
  "Reduzir churn nos primeiros 90 dias",
  "Aumentar taxa de resposta em campanhas frias",
  "Priorizar leads com maior fit",
];

const allowedExtensions = [".txt", ".csv", ".xlsx"];

function summarizeProfile(profile: AiProfilePayload) {
  const missing: string[] = [];
  ("template_key name brand_name tone_of_voice niche target_audience offer_description goals".split(
    " "
  ) as (keyof AiProfilePayload)[]).forEach((field) => {
    if (!profile[field]?.trim()) missing.push(field);
  });
  return { missing, complete: missing.length === 0 };
}

function toBulletList(goals: string[]) {
  return goals.map((g) => `- ${g}`).join("\n");
}

function formatDate(value?: string | null) {
  if (!value) return "";
  try {
    return new Date(value).toLocaleString("pt-BR");
  } catch {
    return value;
  }
}

function KnowledgeLevel({ count }: { count: number }) {
  const label = count === 0 ? "Vazio" : count <= 3 ? "Básico" : "Enriquecido";
  const variant: "secondary" | "outline" | "default" =
    count === 0 ? "secondary" : count <= 3 ? "outline" : "default";
  return <Badge variant={variant}>{label}</Badge>;
}

export default function AiProfilePage() {
  const { toast } = useToast();
  const { handleError } = useApiErrorHandler();
  const { data: usageData } = useUsage();

  const [templates, setTemplates] = useState<AiTemplate[]>([]);
  const [loadingTemplates, setLoadingTemplates] = useState(false);
  const [profile, setProfile] = useState<AiProfilePayload>(initialProfileState);
  const [profileExists, setProfileExists] = useState(false);
  const [loadingProfile, setLoadingProfile] = useState(false);
  const [saving, setSaving] = useState(false);

  const [knowledgeItems, setKnowledgeItems] = useState<KnowledgeItem[]>([]);
  const [loadingKnowledge, setLoadingKnowledge] = useState(false);
  const [knowledgeModalOpen, setKnowledgeModalOpen] = useState(false);
  const [knowledgeTab, setKnowledgeTab] = useState("manual");
  const [manualTitle, setManualTitle] = useState("");
  const [manualContent, setManualContent] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [editingItem, setEditingItem] = useState<KnowledgeItem | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editContent, setEditContent] = useState("");
  const [viewItem, setViewItem] = useState<KnowledgeItem | null>(null);

  const entitlements = usageData?.entitlements;
  const limits = entitlements?.limits ?? {};
  const maxIa = limits?.max_ia_conversas_monthly;
  const iaProductActive = entitlements?.products?.some(
    (p) => p?.product_code === "agent_ia" && (p.status ?? "") === "active"
  );
  const iaUnavailable = !iaProductActive || maxIa === 0 || maxIa === null;

  const status = useMemo(() => summarizeProfile(profile), [profile]);
  const previewText = useMemo(() => {
    if (!profile.name && !profile.brand_name) return "Preencha os campos para ver o preview.";
    const intro = `Olá! Eu sou ${profile.name || "seu agente"} da ${profile.brand_name || "sua marca"}.`;
    const tone = profile.tone_of_voice ? `Vou manter um tom ${profile.tone_of_voice}.` : "";
    const offer = profile.offer_description
      ? `Posso te ajudar com ${profile.offer_description.toLowerCase()}.`
      : "";
    const target = profile.target_audience ? `Atendo principalmente ${profile.target_audience}.` : "";
    return `${intro} ${tone} ${offer} ${target}`.trim();
  }, [profile]);

  const exampleReply = useMemo(() => {
    if (!profile.tone_of_voice) return "Defina o tom de voz para gerar uma resposta exemplo.";
    return `Exemplo (${profile.tone_of_voice}): Obrigado pelo interesse! ${
      profile.offer_description
        ? `Temos uma oferta focada em ${profile.offer_description.toLowerCase()}.`
        : "Posso explicar melhor nossa solução."
    }`;
  }, [profile]);

  const mappedTemplates = useMemo(() => {
    if (!templates.length) return Object.entries(fallbackTemplates).map(([key, meta]) => ({
      key,
      name: meta.name,
      description: meta.description,
    }));
    return templates.map((tpl) => ({
      ...tpl,
      name: tpl.name || fallbackTemplates[tpl.key]?.name || tpl.key,
      description: tpl.description ?? fallbackTemplates[tpl.key]?.description,
    }));
  }, [templates]);

  async function loadTemplates() {
    setLoadingTemplates(true);
    try {
      const data = await api.core.getAiTemplates();
      setTemplates(data);
    } catch (err) {
      handleError(err, { fallbackMessage: "Falha ao carregar templates." });
    } finally {
      setLoadingTemplates(false);
    }
  }

  async function loadProfile() {
    setLoadingProfile(true);
    try {
      const data = await api.core.getAiProfileMe();
      setProfile({
        ...initialProfileState,
        ...data,
      });
      setProfileExists(true);
    } catch (err: any) {
      handleError(err, {
        fallbackMessage: "Falha ao carregar perfil de IA.",
        silent: err?.status === 404,
      });
      if ((err as any)?.status === 404) {
        setProfile(initialProfileState);
        setProfileExists(false);
      }
    } finally {
      setLoadingProfile(false);
    }
  }

  async function loadKnowledge() {
    setLoadingKnowledge(true);
    try {
      const data = await api.crm.getKnowledgeList();
      setKnowledgeItems(data);
    } catch (err) {
      handleError(err, { fallbackMessage: "Falha ao carregar conhecimento." });
    } finally {
      setLoadingKnowledge(false);
    }
  }

  useEffect(() => {
    loadTemplates();
    loadProfile();
    loadKnowledge();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleTemplateSelect = (tpl: AiTemplate) => {
    const preset = fallbackTemplates[tpl.key] || fallbackTemplates.sdr_padrao;
    setProfile((prev) => ({
      ...prev,
      template_key: tpl.key,
      tone_of_voice: prev.tone_of_voice || preset.tone,
      goals: prev.goals || toBulletList(preset.goals),
    }));
  };

  async function handleSave() {
    if (saving) return;
    if (!profileExists) {
      const essentials = summarizeProfile(profile);
      if (!essentials.complete) {
        toast({
          title: "Campos obrigatórios",
          description: "Preencha os campos essenciais para criar o perfil.",
          variant: "destructive",
        });
        return;
      }
    }
    setSaving(true);
    try {
      const payload: AiProfilePayload = {
        ...profile,
        custom_instructions: profile.custom_instructions?.trim() || null,
      };
      const fn = profileExists ? api.core.updateAiProfileMe : api.core.createAiProfile;
      const saved = await fn(payload);
      setProfile({ ...initialProfileState, ...saved });
      setProfileExists(true);
      toast({ title: "Perfil salvo", description: "Identidade do agente atualizada." });
    } catch (err) {
      handleError(err, { fallbackMessage: "Falha ao salvar perfil." });
    } finally {
      setSaving(false);
    }
  }

  async function handleCreateManual() {
    if (!manualTitle.trim() || manualContent.trim().length < 20) {
      toast({
        title: "Conteúdo insuficiente",
        description: "Informe um título e pelo menos 20 caracteres de conteúdo.",
        variant: "destructive",
      });
      return;
    }
    setUploading(true);
    try {
      const created = await api.crm.createKnowledgeManual({
        title: manualTitle.trim(),
        content_text: manualContent.trim(),
      });
      setKnowledgeItems((items) => [created, ...items]);
      setManualTitle("");
      setManualContent("");
      setKnowledgeModalOpen(false);
      toast({ title: "Conhecimento adicionado", description: "Conteúdo manual salvo." });
    } catch (err) {
      handleError(err, { fallbackMessage: "Falha ao salvar conhecimento." });
    } finally {
      setUploading(false);
    }
  }

  const validateFile = (file: File) => {
    const ext = file.name.toLowerCase().slice(file.name.lastIndexOf("."));
    return allowedExtensions.includes(ext);
  };

  async function handleUploadFile() {
    if (!selectedFile) {
      toast({ title: "Selecione um arquivo", variant: "destructive" });
      return;
    }
    if (!validateFile(selectedFile)) {
      toast({
        title: "Formato não suportado",
        description: "Use apenas .txt, .csv ou .xlsx (sem PDF).",
        variant: "destructive",
      });
      return;
    }
    setUploading(true);
    try {
      const created = await api.crm.uploadKnowledgeFile(selectedFile);
      setKnowledgeItems((items) => [created, ...items]);
      setSelectedFile(null);
      setKnowledgeModalOpen(false);
      toast({ title: "Arquivo processado", description: "Conhecimento criado a partir do arquivo." });
    } catch (err) {
      handleError(err, { fallbackMessage: "Falha no upload." });
    } finally {
      setUploading(false);
    }
  }

  async function handleDeleteItem(item: KnowledgeItem) {
    const confirmed = window.confirm(`Remover '${item.title}'?`);
    if (!confirmed) return;
    try {
      await api.crm.deleteKnowledge(item.id);
      setKnowledgeItems((items) => items.filter((k) => k.id !== item.id));
      toast({ title: "Removido", description: "Item excluído com sucesso." });
    } catch (err) {
      handleError(err, { fallbackMessage: "Não foi possível remover o item." });
    }
  }

  function openEdit(item: KnowledgeItem) {
    setEditingItem(item);
    setEditTitle(item.title);
    setEditContent(item.content_text);
  }

  async function handleEditSave() {
    if (!editingItem) return;
    try {
      const updated = await api.crm.updateKnowledge(editingItem.id, {
        title: editTitle,
        content_text: editContent,
      });
      setKnowledgeItems((items) =>
        items.map((k) => (k.id === editingItem.id ? updated : k))
      );
      setEditingItem(null);
      toast({ title: "Item atualizado", description: "Alterações salvas." });
    } catch (err) {
      handleError(err, { fallbackMessage: "Não foi possível atualizar." });
    }
  }

  const knowledgeStatus = <KnowledgeLevel count={knowledgeItems.length} />;

  return (
    <div className="p-6 space-y-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-primary" />
            <h1 className="text-3xl font-bold tracking-tight">Identidade do Agente</h1>
          </div>
          <p className="text-muted-foreground">
            Configure o comportamento do agente e organize o conhecimento do negócio.
          </p>
          {iaUnavailable && (
            <Alert className="mt-3 border-orange-400/60 bg-orange-50/40 dark:bg-orange-950/20">
              <AlertCircle className="h-4 w-4" />
              <AlertTitle>IA conversacional indisponível</AlertTitle>
              <AlertDescription>
                Seu plano atual não inclui o agente conversacional. Ainda assim, você pode
                configurar o perfil e o conhecimento. <a className="underline" href="/assinatura">Ver planos</a>.
              </AlertDescription>
            </Alert>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Badge variant={status.complete ? "default" : "secondary"}>
            {status.complete ? "Perfil completo" : "Perfil incompleto"}
          </Badge>
          <Button
            variant="outline"
            size="sm"
            onClick={loadProfile}
            disabled={loadingProfile || loadingTemplates}
          >
            <RefreshCw className={`mr-2 h-4 w-4 ${loadingProfile ? "animate-spin" : ""}`} />
            Restaurar
          </Button>
          <Button onClick={handleSave} disabled={saving || loadingTemplates}>
            {saving ? "Salvando..." : "Salvar"}
          </Button>
        </div>
      </div>

      <Tabs defaultValue="profile">
        <TabsList>
          <TabsTrigger value="profile">Identidade do agente</TabsTrigger>
          <TabsTrigger value="knowledge">Conhecimento do negócio</TabsTrigger>
        </TabsList>

        <TabsContent value="profile" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Wand2 className="h-5 w-5 text-primary" /> Template / Estilo do agente
              </CardTitle>
              <CardDescription>Selecione um template e adapte o tom.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-3">
              {loadingTemplates && <p>Carregando templates...</p>}
              {!loadingTemplates &&
                mappedTemplates.map((tpl) => (
                  <button
                    key={tpl.key}
                    className={`rounded-lg border p-4 text-left transition hover:border-primary/60 hover:shadow-sm ${
                      profile.template_key === tpl.key ? "border-primary bg-primary/5" : ""
                    }`}
                    onClick={() => handleTemplateSelect(tpl)}
                    type="button"
                  >
                    <div className="flex items-center justify-between">
                      <div className="font-semibold">{tpl.name || tpl.key}</div>
                      {profile.template_key === tpl.key && (
                        <Badge variant="default" className="text-xs">Selecionado</Badge>
                      )}
                    </div>
                    <p className="mt-2 text-sm text-muted-foreground line-clamp-3">
                      {tpl.description || fallbackTemplates[tpl.key]?.description}
                    </p>
                  </button>
                ))}
            </CardContent>
          </Card>

          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Identidade e marca</CardTitle>
                <CardDescription>Como o agente se apresenta.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="space-y-2">
                  <Label>Nome do agente</Label>
                  <Input
                    value={profile.name}
                    placeholder="Ex.: Ana, seu copilot de vendas"
                    onChange={(e) => setProfile((p) => ({ ...p, name: e.target.value }))}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Marca</Label>
                  <Input
                    value={profile.brand_name}
                    placeholder="Ex.: Auto Digital"
                    onChange={(e) => setProfile((p) => ({ ...p, brand_name: e.target.value }))}
                  />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Nicho e público</CardTitle>
                <CardDescription>Quem você atende.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="space-y-2">
                  <Label>Nicho</Label>
                  <Input
                    value={profile.niche}
                    placeholder="Ex.: Software B2B para marketing"
                    onChange={(e) => setProfile((p) => ({ ...p, niche: e.target.value }))}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Público-alvo</Label>
                  <Input
                    value={profile.target_audience}
                    placeholder="Ex.: PMEs de e-commerce"
                    onChange={(e) => setProfile((p) => ({ ...p, target_audience: e.target.value }))}
                  />
                </div>
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Oferta</CardTitle>
                <CardDescription>Explique o que você vende.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2">
                <Textarea
                  value={profile.offer_description}
                  placeholder="Ex.: Implementação completa do CRM com onboarding em 14 dias."
                  onChange={(e) =>
                    setProfile((p) => ({ ...p, offer_description: e.target.value }))
                  }
                  rows={4}
                />
                <div className="text-xs text-muted-foreground text-right">
                  {profile.offer_description.length} caracteres
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Objetivos</CardTitle>
                <CardDescription>Selecione objetivos e personalize.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <Textarea
                  value={profile.goals}
                  placeholder="Use bullets. Ex.:\n- Agendar 10 demos/semana\n- Reduzir ciclo de vendas"
                  onChange={(e) => setProfile((p) => ({ ...p, goals: e.target.value }))}
                  rows={4}
                />
                <div className="flex flex-wrap gap-2">
                  {goalSuggestions.map((goal) => (
                    <Button
                      key={goal}
                      variant="secondary"
                      size="sm"
                      type="button"
                      onClick={() =>
                        setProfile((p) => ({
                          ...p,
                          goals: p.goals.includes(goal)
                            ? p.goals
                            : `${p.goals ? `${p.goals}\n` : ""}${`- ${goal}`}`,
                        }))
                      }
                    >
                      {goal}
                    </Button>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Tom de voz</CardTitle>
                <CardDescription>Como o agente fala.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2">
                <Select
                  value={profile.tone_of_voice}
                  onValueChange={(value) => setProfile((p) => ({ ...p, tone_of_voice: value }))}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Selecione um tom" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="consultivo">Consultivo</SelectItem>
                    <SelectItem value="direto">Direto</SelectItem>
                    <SelectItem value="acolhedor">Acolhedor</SelectItem>
                    <SelectItem value="entusiasmado">Entusiasmado</SelectItem>
                    <SelectItem value="profissional e próximo">Profissional e próximo</SelectItem>
                  </SelectContent>
                </Select>
                <Input
                  value={profile.tone_of_voice}
                  onChange={(e) => setProfile((p) => ({ ...p, tone_of_voice: e.target.value }))}
                  placeholder="Ou personalize o tom"
                />
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Instruções extras</CardTitle>
                <CardDescription>Diretrizes adicionais para o agente.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2">
                <Textarea
                  value={profile.custom_instructions || ""}
                  placeholder="Ex.: Sempre responder em português do Brasil e sugerir próximos passos claros."
                  onChange={(e) =>
                    setProfile((p) => ({ ...p, custom_instructions: e.target.value }))
                  }
                  rows={4}
                />
                <div className="text-xs text-muted-foreground text-right">
                  {(profile.custom_instructions || "").length} caracteres
                </div>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Preview</CardTitle>
              <CardDescription>Simulação local de apresentação e resposta.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4 md:grid-cols-2">
              <div className="rounded-lg border bg-muted/30 p-4 space-y-2">
                <div className="text-sm font-semibold text-muted-foreground">Apresentação</div>
                <p className="leading-relaxed">{previewText}</p>
              </div>
              <div className="rounded-lg border bg-muted/30 p-4 space-y-2">
                <div className="text-sm font-semibold text-muted-foreground">Resposta exemplo</div>
                <p className="leading-relaxed">{exampleReply}</p>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="knowledge" className="space-y-4">
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <div className="flex items-center gap-2">
                <Brain className="h-5 w-5 text-primary" />
                <h2 className="text-2xl font-semibold">Conhecimento do negócio</h2>
              </div>
              <p className="text-muted-foreground text-sm">
                Base privada do usuário para alimentar o agente.
              </p>
              <div className="mt-2 flex items-center gap-2">
                <span className="text-sm text-muted-foreground">Status:</span>
                {knowledgeStatus}
              </div>
            </div>
            <Button onClick={() => setKnowledgeModalOpen(true)}>
              <FilePlus className="mr-2 h-4 w-4" /> Adicionar conhecimento
            </Button>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Itens cadastrados</CardTitle>
              <CardDescription>CRUD completo e upload dedicado (sem PDFs).</CardDescription>
            </CardHeader>
            <CardContent>
              {loadingKnowledge ? (
                <p>Carregando conhecimento...</p>
              ) : knowledgeItems.length === 0 ? (
                <div className="flex flex-col items-start gap-2 rounded-md border border-dashed p-4 text-sm text-muted-foreground">
                  <p>Nenhum conhecimento cadastrado ainda.</p>
                  <Button variant="outline" size="sm" onClick={() => setKnowledgeModalOpen(true)}>
                    <FilePlus className="mr-2 h-4 w-4" /> Adicionar
                  </Button>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Título</TableHead>
                        <TableHead>Tipo</TableHead>
                        <TableHead>Atualizado em</TableHead>
                        <TableHead className="text-right">Ações</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {knowledgeItems.map((item) => (
                        <TableRow key={item.id}>
                          <TableCell className="font-medium">{item.title}</TableCell>
                          <TableCell>
                            <Badge variant={item.source_type === "file" ? "outline" : "secondary"}>
                              {item.source_type}
                            </Badge>
                          </TableCell>
                          <TableCell>{formatDate(item.updated_at)}</TableCell>
                          <TableCell className="flex justify-end gap-2">
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => setViewItem(item)}
                            >
                              Ver
                            </Button>
                            <Button size="sm" variant="outline" onClick={() => openEdit(item)}>
                              <FileEdit className="mr-1 h-4 w-4" /> Editar
                            </Button>
                            <Button
                              size="sm"
                              variant="destructive"
                              onClick={() => handleDeleteItem(item)}
                            >
                              Remover
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <Dialog open={knowledgeModalOpen} onOpenChange={setKnowledgeModalOpen}>
        <DialogContent className="sm:max-w-xl">
          <DialogHeader>
            <DialogTitle>Adicionar conhecimento</DialogTitle>
          </DialogHeader>
          <Tabs value={knowledgeTab} onValueChange={setKnowledgeTab}>
            <TabsList>
              <TabsTrigger value="manual">Texto livre</TabsTrigger>
              <TabsTrigger value="upload">Upload (.txt/.csv/.xlsx)</TabsTrigger>
            </TabsList>
            <TabsContent value="manual" className="space-y-3">
              <div className="space-y-2">
                <Label>Título</Label>
                <Input
                  value={manualTitle}
                  onChange={(e) => setManualTitle(e.target.value)}
                  placeholder="Ex.: Tabela de preços"
                />
              </div>
              <div className="space-y-2">
                <Label>Conteúdo</Label>
                <Textarea
                  value={manualContent}
                  onChange={(e) => setManualContent(e.target.value)}
                  placeholder="Inclua regras, objeções, horários, etc."
                  rows={5}
                />
                <div className="text-xs text-muted-foreground text-right">
                  {manualContent.length} caracteres
                </div>
              </div>
              <DialogFooter>
                <Button onClick={handleCreateManual} disabled={uploading}>
                  {uploading ? "Salvando..." : "Salvar"}
                </Button>
              </DialogFooter>
            </TabsContent>
            <TabsContent value="upload" className="space-y-3">
              <div className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">
                <p>Envie .txt, .csv ou .xlsx. PDF não é suportado no MVP.</p>
              </div>
              <Input
                type="file"
                accept={allowedExtensions.join(",")}
                onChange={(e) => setSelectedFile(e.target.files?.[0] ?? null)}
              />
              {selectedFile && (
                <div className="text-sm text-muted-foreground">
                  Arquivo: {selectedFile.name}
                </div>
              )}
              <DialogFooter>
                <Button onClick={handleUploadFile} disabled={uploading}>
                  <Upload className="mr-2 h-4 w-4" />
                  {uploading ? "Enviando..." : "Enviar"}
                </Button>
              </DialogFooter>
            </TabsContent>
          </Tabs>
        </DialogContent>
      </Dialog>

      <Dialog open={!!editingItem} onOpenChange={(open) => !open && setEditingItem(null)}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Editar item</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-2">
              <Label>Título</Label>
              <Input value={editTitle} onChange={(e) => setEditTitle(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label>Conteúdo</Label>
              <Textarea
                value={editContent}
                onChange={(e) => setEditContent(e.target.value)}
                rows={6}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditingItem(null)}>
              Cancelar
            </Button>
            <Button onClick={handleEditSave}>Salvar alterações</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!viewItem} onOpenChange={(open) => !open && setViewItem(null)}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>{viewItem?.title}</DialogTitle>
            <p className="text-sm text-muted-foreground">
              {viewItem?.source_type === "file" ? "Arquivo" : "Manual"} · Atualizado em {formatDate(viewItem?.updated_at)}
            </p>
          </DialogHeader>
          <div className="rounded-md border bg-muted/40 p-3 text-sm whitespace-pre-wrap">
            {viewItem?.content_text}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setViewItem(null)}>
              Fechar
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
