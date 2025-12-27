// src/pages/AssistenteIA.tsx
import React, { useState, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useToast } from '@/hooks/use-toast';
import { Upload, FileText, Bot, Download, X, Sparkles, ArrowRight } from 'lucide-react';
import { CrmHeader } from '@/components/CrmHeader';
import { useNavigate } from 'react-router-dom';
import { api } from '@/services/api';
import { useApiErrorHandler } from '@/hooks/useApiErrorHandler';

const AssistenteIA = () => {
  // ======= estados existentes =======
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [isProcessing, setIsProcessing] = useState(false);

  // processedData: reutilizado para exibir a PRÉVIA (linhas anotadas)
  const [processedData, setProcessedData] = useState<any[]>([]);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const { toast } = useToast();
  const navigate = useNavigate();
  const { handleError } = useApiErrorHandler();

  // ======= estados novos (upload/preview/options/result) =======
  const [uploadId, setUploadId] = useState<string | null>(null);
  const [uploadInfo, setUploadInfo] = useState<{ filename?: string; ext?: string } | null>(null);

  const [isPreviewing, setIsPreviewing] = useState(false);
  const [previewStats, setPreviewStats] = useState<any | null>(null);

  const [createCards, setCreateCards] = useState(true);
  const [generateCopys, setGenerateCopys] = useState(true);
  const [channels, setChannels] = useState({ email: true, whatsapp: true, instagram: false, call: false });

  const [overwrite, setOverwrite] = useState<'skip' | 'update' | 'duplicate'>('update');
  const [tone, setTone] = useState('profissional e próximo');
  const [language, setLanguage] = useState('pt-PT');

  const [processResult, setProcessResult] = useState<any | null>(null);

  // ======= helpers =======
  const allowedTypes = [
    'text/csv',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
  ];

  const selectedChannels = () => {
    const arr: string[] = [];
    if (channels.email) arr.push('email');
    if (channels.whatsapp) arr.push('whatsapp');
    if (channels.instagram) arr.push('instagram');
    if (channels.call) arr.push('call');
    return arr;
  };

  // ======= upload =======
  const handleFileUpload = async (file: File) => {
    if (!allowedTypes.includes(file.type)) {
      toast({
        title: "Formato não suportado",
        description: "Selecione um CSV ou XLSX (planilha de pesquisa).",
        variant: "destructive",
      });
      return;
    }
    setUploadedFile(file);
    setProcessResult(null); // reset de execução anterior
    try {
      // envia ao backend e obtém upload_id + sample (20 linhas)
      const r = await api.uploads.enviar(file);
      setUploadId(r.upload_id);
      setUploadInfo({ filename: r.filename, ext: r.ext });

      // amostra crua (sem dedupe) para mostrar na prévia básica
      setProcessedData(Array.isArray(r.sample) ? r.sample : []);
      setPreviewStats(null);

      toast({
        title: "Planilha carregada",
        description: `${file.name} foi recebida. Agora, gere a PRÉVIA para analisar duplicados.`,
      });
    } catch (err: any) {
      console.error(err);
      toast({
        title: "Falha no upload",
        description: err?.message || "Não foi possível ler o arquivo.",
        variant: "destructive",
      });
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      handleFileUpload(files[0]);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      handleFileUpload(files[0]);
    }
  };

  const removeFile = () => {
    setUploadedFile(null);
    setUploadId(null);
    setUploadInfo(null);
    setProcessedData([]);
    setPreviewStats(null);
    setProcessResult(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  // ======= PRÉVIA / dedupe =======
  const handlePreview = async () => {
    if (!uploadId) {
      toast({
        title: "Arquivo não enviado",
        description: "Envie a planilha primeiro.",
        variant: "destructive",
      });
      return;
    }
    setIsPreviewing(true);
    try {
      const p = await api.assistenteIA.preview({ upload_id: uploadId, overwrite });
      // rows anotadas (dup_phone/dup_email/dup_name + pred_action)
      setProcessedData(Array.isArray(p.rows) ? p.rows : []);
      setPreviewStats(p.stats || null);
      toast({ title: "Prévia pronta", description: "Duplicados e ações previstas calculados." });
    } catch (err: any) {
      console.error(err);
      toast({
        title: "Erro ao gerar prévia",
        description: err?.message || "Não foi possível analisar duplicados.",
        variant: "destructive",
      });
    } finally {
      setIsPreviewing(false);
    }
  };

  // ======= PROCESSAMENTO REAL =======
  const handleProcessWithAI = async () => {
    if (!uploadId) {
      toast({
        title: "Arquivo necessário",
        description: "Faça upload da planilha e gere a prévia antes de processar.",
        variant: "destructive",
      });
      return;
    }

    setIsProcessing(true);
    setProcessResult(null);

    try {
      const payload = {
        upload_id: uploadId,
        create_cards: createCards,
        generate_copys: generateCopys,
        channels: selectedChannels(),
        overwrite,
        limit: undefined,
        tone,
        language,
      };

      const r = await api.assistenteIA.processar(payload);
      setProcessResult(r);

      toast({
        title: "Processamento concluído",
        description: `Criados: ${r.stats?.created ?? 0}, Atualizados: ${r.stats?.updated ?? 0}, Pulados: ${r.stats?.skipped ?? 0}, Mensagens: ${r.stats?.messages ?? 0}`,
      });
    } catch (error: any) {
      console.error(error);
      handleError(error, { fallbackMessage: "Ocorreu um erro ao processar com a IA." });
    } finally {
      setIsProcessing(false);
    }
  };

  // ======= ações antigas (mantidas) =======
  const handleCreateCRMCards = () => {
    if (!processResult) {
      toast({
        title: "Nenhum resultado de processamento",
        description: "Execute o processamento para criar/atualizar cards.",
        variant: "destructive",
      });
      return;
    }
    toast({
      title: "Cartões criados/atualizados!",
      description: `Criados: ${processResult.stats?.created ?? 0}, Atualizados: ${processResult.stats?.updated ?? 0}`,
    });
    navigate('/');
  };

  const handleDownloadProspectionSheet = () => {
    if (processedData.length === 0) {
      toast({
        title: "Nenhum dado para baixar",
        description: "Gere a prévia ou processe antes de baixar.",
        variant: "destructive",
      });
      return;
    }
    toast({
      title: "Planilha baixada (simulada)",
      description: "No novo fluxo, a planilha é opcional.",
    });
  };

  return (
    <div className="min-h-screen bg-background">
      <CrmHeader
        onNewLead={() => navigate('/')}
        onDashboard={() => navigate('/dashboard')}
        searchTerm={searchTerm}
        onSearchChange={setSearchTerm}
        allColumns={[]}
        onLeadSelect={() => navigate('/')}
      />

      <main className="container mx-auto px-6 py-8">
        <div className="max-w-5xl mx-auto space-y-8">
          <div className="text-center space-y-2">
            <h1 className="text-3xl font-bold text-foreground flex items-center justify-center gap-2">
              <Bot className="h-8 w-8 text-primary" />
              Assistente IA
            </h1>
            <p className="text-muted-foreground">
              Importe sua planilha, gere a prévia e processe para criar cards e (opcional) gerar copys.
            </p>
          </div>

          {/* 1. Upload da Planilha */}
          <Card className="gradient-card border-lead-card-border">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Upload className="h-5 w-5" />
                1. Importar Planilha de Pesquisa
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              {!uploadedFile ? (
                <div
                  className={`border-2 border-dashed rounded-lg p-8 text-center transition-smooth ${
                    isDragging ? 'border-primary bg-primary/10' : 'border-border hover:border-primary/50'
                  }`}
                  onDrop={handleDrop}
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                >
                  <Upload className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
                  <div className="space-y-2">
                    <p className="text-lg font-medium">Arraste e solte sua planilha aqui</p>
                    <p className="text-sm text-muted-foreground">ou clique para selecionar um arquivo</p>
                    <p className="text-xs text-muted-foreground">Formatos: CSV, XLSX (aba "Leads")</p>
                  </div>
                  <Button variant="outline" className="mt-4" onClick={() => fileInputRef.current?.click()}>
                    Selecionar Arquivo
                  </Button>
                  <Input
                    ref={fileInputRef}
                    type="file"
                    accept=".csv,.xlsx,.xls"
                    onChange={handleFileSelect}
                    className="hidden"
                  />
                </div>
              ) : (
                <div className="border rounded-lg p-4 bg-card">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <FileText className="h-8 w-8 text-primary" />
                      <div>
                        <p className="font-medium">{uploadedFile.name}</p>
                        <p className="text-sm text-muted-foreground">
                          {(uploadedFile.size / 1024 / 1024).toFixed(2)} MB • {uploadInfo?.ext?.replace('.','').toUpperCase()}
                        </p>
                      </div>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={removeFile}
                      className="text-destructive hover:text-destructive-foreground hover:bg-destructive"
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* 2. Prévia e Opções */}
          <Card className="gradient-card border-lead-card-border">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Sparkles className="h-5 w-5" />
                2. Prévia e Opções
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="space-y-2">
                  <Label>Duplicados</Label>
                  <select
                    className="w-full border rounded px-3 py-2 bg-background"
                    value={overwrite}
                    onChange={(e) => setOverwrite(e.target.value as any)}
                    disabled={!uploadId || isPreviewing || isProcessing}
                  >
                    <option value="skip">Pular duplicados</option>
                    <option value="update">Atualizar existentes</option>
                    <option value="duplicate">Criar duplicados</option>
                  </select>
                </div>

                <div className="space-y-2">
                  <Label>Geração de Copys (IA)</Label>
                  <div className="flex items-center gap-3">
                    <input
                      id="gen-copys"
                      type="checkbox"
                      className="h-4 w-4"
                      checked={generateCopys}
                      onChange={(e) => setGenerateCopys(e.target.checked)}
                      disabled={!uploadId || isProcessing}
                    />
                    <Label htmlFor="gen-copys">Gerar copys com IA</Label>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label>Criar Cards</Label>
                  <div className="flex items-center gap-3">
                    <input
                      id="create-cards"
                      type="checkbox"
                      className="h-4 w-4"
                      checked={createCards}
                      onChange={(e) => setCreateCards(e.target.checked)}
                      disabled={!uploadId || isProcessing}
                    />
                    <Label htmlFor="create-cards">Criar/atualizar cards no CRM</Label>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="space-y-2">
                  <Label>Canais (quando IA ativa)</Label>
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <label className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={channels.email}
                        onChange={(e) => setChannels({ ...channels, email: e.target.checked })}
                        disabled={!generateCopys || isProcessing}
                      />
                      E-mail
                    </label>
                    <label className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={channels.whatsapp}
                        onChange={(e) => setChannels({ ...channels, whatsapp: e.target.checked })}
                        disabled={!generateCopys || isProcessing}
                      />
                      WhatsApp
                    </label>
                    <label className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={channels.instagram}
                        onChange={(e) => setChannels({ ...channels, instagram: e.target.checked })}
                        disabled={!generateCopys || isProcessing}
                      />
                      Instagram
                    </label>
                    <label className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={channels.call}
                        onChange={(e) => setChannels({ ...channels, call: e.target.checked })}
                        disabled={!generateCopys || isProcessing}
                      />
                      Ligação
                    </label>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label>Tom</Label>
                  <Input
                    value={tone}
                    onChange={(e) => setTone(e.target.value)}
                    placeholder="ex.: profissional e próximo"
                    disabled={isProcessing}
                  />
                </div>

                <div className="space-y-2">
                  <Label>Idioma</Label>
                  <Input
                    value={language}
                    onChange={(e) => setLanguage(e.target.value)}
                    placeholder="ex.: pt-PT"
                    disabled={isProcessing}
                  />
                </div>
              </div>

              <div className="flex flex-col md:flex-row gap-3">
                <Button
                  variant="outline"
                  onClick={handlePreview}
                  disabled={!uploadId || isPreviewing || isProcessing}
                  className="w-full md:w-auto"
                >
                  {isPreviewing ? 'Analisando...' : 'Gerar Prévia (duplicados)'}
                </Button>

                <Button
                  onClick={handleProcessWithAI}
                  disabled={!uploadId || isProcessing}
                  className="w-full md:w-auto gradient-primary text-primary-foreground font-medium"
                >
                  {isProcessing ? (
                    <>
                      <Bot className="h-4 w-4 mr-2 animate-spin" />
                      Processando...
                    </>
                  ) : (
                    <>
                      <Sparkles className="h-4 w-4 mr-2" />
                      Confirmar e Processar
                    </>
                  )}
                </Button>
              </div>

              {/* Resumo da prévia */}
              {previewStats && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                  <div className="p-3 rounded border bg-muted/30">
                    <strong>Total</strong>
                    <div>{previewStats.total}</div>
                  </div>
                  <div className="p-3 rounded border bg-muted/30">
                    <strong>Prev. Criar</strong>
                    <div>{previewStats.pred_create}</div>
                  </div>
                  <div className="p-3 rounded border bg-muted/30">
                    <strong>Prev. Atualizar</strong>
                    <div>{previewStats.pred_update}</div>
                  </div>
                  <div className="p-3 rounded border bg-muted/30">
                    <strong>Prev. Pular</strong>
                    <div>{previewStats.pred_skip}</div>
                  </div>
                </div>
              )}

              {/* Grid simples da prévia (nomes + contato) */}
              {processedData.length > 0 && (
                <div className="border rounded-lg p-4 bg-muted/30">
                  <h4 className="font-medium mb-3">Prévia (amostra/anotações):</h4>
                  <div className="space-y-2 text-sm">
                    {processedData.slice(0, 10).map((item, idx) => {
                      const empresa = item.empresa || item.company || item.companyname || item.name || '—';
                      const contatoNome = item.nome || item.contact || item.contactname || '';
                      const contatoTel = item.telefone || item.phone || '';
                      const contatoEmail = item.email || (Array.isArray?.(item.emails) ? item.emails[0] : item.emails) || '';
                      const contato = contatoNome
                        ? `${contatoNome}${contatoTel || contatoEmail ? ' - ' : ''}${contatoTel || contatoEmail || ''}`
                        : (contatoTel || contatoEmail || '—');

                      return (
                        <div key={idx} className="p-3 bg-background rounded border">
                          <p><strong>Empresa:</strong> {empresa}</p>
                          <p><strong>Contato:</strong> {contato}</p>

                          {(item.pred_action || item.dup_phone || item.dup_email || item.dup_name) && (
                            <p className="mt-1">
                              <strong>Ação:</strong> {item.pred_action || '—'} •
                              <span className={`ml-2 ${item.dup_phone ? 'text-red-600' : 'text-muted-foreground'}`}>tel dup: {String(!!item.dup_phone)}</span> •
                              <span className={`ml-2 ${item.dup_email ? 'text-red-600' : 'text-muted-foreground'}`}>email dup: {String(!!item.dup_email)}</span> •
                              <span className={`ml-2 ${item.dup_name ? 'text-red-600' : 'text-muted-foreground'}`}>nome dup: {String(!!item.dup_name)}</span>
                            </p>
                          )}
                        </div>
                      );
                    })}
                    {processedData.length > 10 && (
                      <p className="text-muted-foreground text-center">
                        E mais {processedData.length - 10} registros...
                      </p>
                    )}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* 3. Resultado do Processamento */}
          {processResult && (
            <Card className="gradient-card border-lead-card-border">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Bot className="h-5 w-5" />
                  3. Resultado do Processamento
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                  <div className="p-3 rounded border bg-muted/30">
                    <strong>Criados</strong>
                    <div>{processResult?.stats?.created ?? 0}</div>
                  </div>
                  <div className="p-3 rounded border bg-muted/30">
                    <strong>Atualizados</strong>
                    <div>{processResult?.stats?.updated ?? 0}</div>
                  </div>
                  <div className="p-3 rounded border bg-muted/30">
                    <strong>Pulados</strong>
                    <div>{processResult?.stats?.skipped ?? 0}</div>
                  </div>
                  <div className="p-3 rounded border bg-muted/30">
                    <strong>Mensagens</strong>
                    <div>{processResult?.stats?.messages ?? 0}</div>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <Button
                    onClick={handleCreateCRMCards}
                    className="gradient-primary text-primary-foreground font-medium"
                    size="lg"
                  >
                    <ArrowRight className="h-4 w-4 mr-2" />
                    Ver Leads no CRM
                  </Button>

                  <Button
                    onClick={handleDownloadProspectionSheet}
                    variant="outline"
                    size="lg"
                  >
                    <Download className="h-4 w-4 mr-2" />
                    Baixar Planilha (opcional)
                  </Button>
                </div>

                {processResult?.errors && processResult.errors.length > 0 && (
                  <div className="border rounded-lg p-4 bg-muted/30 text-sm">
                    <h4 className="font-medium mb-2">Ocorreram alguns erros:</h4>
                    <ul className="list-disc pl-5 space-y-1">
                      {processResult.errors.slice(0, 10).map((er: string, i: number) => (
                        <li key={i}>{er}</li>
                      ))}
                    </ul>
                    {processResult.errors.length > 10 && (
                      <p className="text-muted-foreground mt-2">
                        E mais {processResult.errors.length - 10} erros...
                      </p>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      </main>
    </div>
  );
};

export default AssistenteIA;
