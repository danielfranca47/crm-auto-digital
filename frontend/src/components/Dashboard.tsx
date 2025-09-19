import { DashboardMetrics } from "../types/crm";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { Button } from "./ui/button";
import { Calendar } from "./ui/calendar";
import { useTheme } from "../contexts/ThemeContext";
import { ArrowLeft, TrendingUp, Target, DollarSign, Sun, Moon, Clock, AlertTriangle, Search, CalendarIcon, MapPin, Smartphone, Plus } from "lucide-react";
interface DashboardProps {
  metrics: DashboardMetrics;
  onBack: () => void;
}
const COLORS = ['#3b82f6', '#22c55e', '#ef4444', '#64748b', '#f59e0b', '#8b5cf6'];
export function Dashboard({
  metrics,
  onBack
}: DashboardProps) {
  const {
    theme,
    toggleTheme
  } = useTheme();
  return <div className="min-h-screen bg-background">
      <div className="bg-card border-b border-border p-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <Button onClick={onBack} variant="ghost" size="sm" className="hover:bg-muted">
              <ArrowLeft className="w-4 h-4 mr-2" />
              Voltar ao Kanban
            </Button>
            <h1 className="text-2xl font-bold text-foreground">Dashboard de Métricas</h1>
          </div>
          
          <div className="flex items-center space-x-3">
            <Button onClick={toggleTheme} variant="ghost" size="sm" className="border border-border hover:bg-muted transition-smooth" title={theme === 'dark' ? 'Mudar para tema claro' : 'Mudar para tema escuro'}>
              {theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
            </Button>
            
            <Select defaultValue="current-month">
              <SelectTrigger className="w-48 bg-input border-border">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-popover border-border">
                <SelectItem value="last-7-days">Últimos 7 dias</SelectItem>
                <SelectItem value="current-month">Mês atual</SelectItem>
                <SelectItem value="current-quarter">Trimestre atual</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
      </div>

      <div className="p-6 space-y-6">
        {/* ZONA 1: TOPO - VISÃO GERAL CRÍTICA */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card className="bg-card border-border">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                💰 Vendas no Mês
              </CardTitle>
              <DollarSign className="h-4 w-4 text-success" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-foreground">3/10 vendas</div>
              <p className="text-xs text-warning">Meta de 10 vendas/mês</p>
            </CardContent>
          </Card>

          <Card className="bg-card border-border">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                📈 Progresso Meta
              </CardTitle>
              <Target className="h-4 w-4 text-primary" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-foreground">30%</div>
              <div className="w-full bg-muted rounded-full h-2 mt-2">
                <div className="bg-primary h-2 rounded-full" style={{
                width: '30%'
              }}></div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-card border-border">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                📊 Ticket Médio Real
              </CardTitle>
              <DollarSign className="h-4 w-4 text-info" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-foreground">280€</div>
              <p className="text-xs text-muted-foreground">Baseado em vendas fechadas</p>
            </CardContent>
          </Card>

          <Card className="bg-card border-border">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                ⏱️ Dias Restantes
              </CardTitle>
              <Clock className="h-4 w-4 text-warning" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-foreground">12 dias</div>
              <p className="text-xs text-warning">Para bater a meta</p>
            </CardContent>
          </Card>
        </div>

        {/* ZONA 2 e 3: CENTRO - PRIORIDADES E AGENDA */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* ZONA 2: CENTRO-ESQUERDA - AÇÃO IMEDIATA */}
          <Card className="bg-card border-border border-l-4 border-l-warning">
            <CardHeader>
              <CardTitle className="text-foreground flex items-center">
                <AlertTriangle className="w-5 h-5 mr-2 text-warning" />
                Avisos
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center space-x-3 p-3 bg-muted/50 rounded-lg">
                <Clock className="w-4 h-4 text-info" />
                <span>⏰ 2 reuniões confirmadas (14h, 16h)</span>
              </div>
              <div className="flex items-center space-x-3 p-3 bg-muted/50 rounded-lg">
                <AlertTriangle className="w-4 h-4 text-warning" />
                <span>📞 4 follow-ups críticos (&gt; 5 dias sem contato)</span>
              </div>
              <div className="flex items-center space-x-3 p-3 bg-muted/50 rounded-lg">
                <Target className="w-4 h-4 text-primary" />
                <span>🎯 Faltam 6 prospecções para meta diária (20/dia)</span>
              </div>
              <div className="flex items-center space-x-3 p-3 bg-success/10 rounded-lg border border-success/20">
                <DollarSign className="w-4 h-4 text-success" />
                <span>💡 João Silva (site 500€) - pronto para fechar!</span>
              </div>
            </CardContent>
          </Card>

          {/* ZONA 3: CENTRO-DIREITA - AGENDA */}
          <Card className="bg-card border-border">
            <CardHeader>
              <CardTitle className="text-foreground flex items-center justify-between">
                <span>📅 Calendário de Reuniões</span>
                <Button size="sm" className="text-xs">
                  <Plus className="w-3 h-3 mr-1" />
                  Nova Reunião
                </Button>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <Calendar mode="single" className="rounded-md border border-border pointer-events-auto" />
                
                {/* Eventos do Dia */}
                <div className="space-y-3">
                  <h4 className="font-medium text-foreground">Reuniões de Hoje</h4>
                  <div className="space-y-2">
                    <div className="flex items-center space-x-3 p-3 bg-primary/10 rounded-lg border border-primary/20">
                      <div className="w-2 h-2 bg-primary rounded-full"></div>
                      <div className="flex-1">
                        <p className="font-medium text-sm">14:00 - João Silva</p>
                        <p className="text-xs text-muted-foreground">Apresentação de proposta</p>
                      </div>
                    </div>
                    <div className="flex items-center space-x-3 p-3 bg-warning/10 rounded-lg border border-warning/20">
                      <div className="w-2 h-2 bg-warning rounded-full"></div>
                      <div className="flex-1">
                        <p className="font-medium text-sm">16:00 - Maria Santos</p>
                        <p className="text-xs text-muted-foreground">Follow-up negociação</p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* ZONA 4: LINHA COMPLETA - FUNIL VISUAL */}
        <Card className="bg-card border-border">
          <CardHeader>
            <CardTitle className="text-foreground">🔥 Funil Simplificado</CardTitle>
          </CardHeader>
          <CardContent className="py-8">
            <div className="flex flex-col items-center space-y-1">
              {/* Etapa 1: Prospectados */}
              <div className="relative w-full max-w-md">
                <div className="bg-primary/90 text-primary-foreground flex items-center justify-between px-6 py-4 text-sm font-medium" style={{
                clipPath: 'polygon(0% 0%, 100% 0%, 95% 100%, 5% 100%)',
                width: '100%'
              }}>
                  <div className="flex items-center space-x-2">
                    <span>🔍</span>
                    <span>Prospectados</span>
                  </div>
                  <span className="font-bold">18 leads</span>
                </div>
              </div>

              {/* Etapa 2: Contato Feito */}
              <div className="relative w-full max-w-md">
                <div className="bg-info/90 text-info-foreground flex items-center justify-between px-6 py-4 text-sm font-medium" style={{
                clipPath: 'polygon(5% 0%, 95% 0%, 90% 100%, 10% 100%)',
                width: '85%',
                margin: '0 auto'
              }}>
                  <div className="flex items-center space-x-2">
                    <span>📞</span>
                    <span>Contato Feito</span>
                  </div>
                  <span className="font-bold">12 leads</span>
                </div>
              </div>

              {/* Etapa 3: Reunião Agendada */}
              <div className="relative w-full max-w-md">
                <div className="bg-warning/90 text-warning-foreground flex items-center justify-between px-6 py-4 text-sm font-medium" style={{
                clipPath: 'polygon(10% 0%, 90% 0%, 85% 100%, 15% 100%)',
                width: '70%',
                margin: '0 auto'
              }}>
                  <div className="flex items-center space-x-2">
                    <span>📅</span>
                    <span>Reunião Agendada</span>
                  </div>
                  <span className="font-bold">6 leads</span>
                </div>
              </div>

              {/* Etapa 4: Em Negociação */}
              <div className="relative w-full max-w-md">
                <div className="bg-success/90 text-success-foreground flex items-center justify-between px-6 py-4 text-sm font-medium" style={{
                clipPath: 'polygon(15% 0%, 85% 0%, 80% 100%, 20% 100%)',
                width: '55%',
                margin: '0 auto'
              }}>
                  <div className="flex items-center space-x-2">
                    <span>💰</span>
                    <span>Em Negociação</span>
                  </div>
                  <span className="font-bold">3 leads</span>
                </div>
              </div>

              {/* Taxa de conversão */}
              <div className="mt-6 text-center">
                <p className="text-sm text-muted-foreground">Taxa de Conversão</p>
                <p className="text-lg font-bold text-foreground">16.7% (3/18)</p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* ZONA 5: DUPLA INFERIOR - PERFORMANCE */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Performance Semanal */}
          <Card className="bg-card border-border">
            <CardHeader>
              <CardTitle className="text-foreground">📊 Realizados vs Meta</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <span className="font-medium">Prospecções:</span>
                  <span className="font-bold">67/100 (67%)</span>
                </div>
                <div className="w-full bg-muted rounded-full h-3">
                  <div className="bg-info h-3 rounded-full" style={{
                  width: '67%'
                }}></div>
                </div>
              </div>

              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <span className="font-medium">Reuniões:</span>
                  <span className="font-bold">4/8 (50%)</span>
                </div>
                <div className="w-full bg-muted rounded-full h-3">
                  <div className="bg-warning h-3 rounded-full" style={{
                  width: '50%'
                }}></div>
                </div>
              </div>

              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <span className="font-medium">Vendas:</span>
                  <span className="font-bold">1/2.5 (40%)</span>
                </div>
                <div className="w-full bg-muted rounded-full h-3">
                  <div className="bg-destructive h-3 rounded-full" style={{
                  width: '40%'
                }}></div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Performance por Fonte */}
          <Card className="bg-card border-border">
            <CardHeader>
              <CardTitle className="text-foreground">📈 Performance por Fonte</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between p-4 bg-muted/50 rounded-lg">
                <div className="flex items-center space-x-3">
                  <MapPin className="w-5 h-5 text-primary" />
                  <div>
                    <p className="font-medium">🗺️ Google Maps</p>
                    <p className="text-sm text-muted-foreground">28 leads → 2 vendas</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="font-bold text-success">7% conversão</p>
                </div>
              </div>

              <div className="flex items-center justify-between p-4 bg-muted/50 rounded-lg">
                <div className="flex items-center space-x-3">
                  <Smartphone className="w-5 h-5 text-info" />
                  <div>
                    <p className="font-medium">📱 Redes Sociais</p>
                    <p className="text-sm text-muted-foreground">14 leads → 1 venda</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="font-bold text-success">7% conversão</p>
                </div>
              </div>

              <div className="mt-4 p-3 bg-info/10 rounded-lg border border-info/20">
                <p className="text-sm">💡 Ambas têm mesma eficiência - manter proporção</p>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* ZONA 6: RODAPÉ - AÇÕES RÁPIDAS */}
        <Card className="bg-card border-border">
          <CardHeader>
            <CardTitle className="text-foreground">⚡ Ações Rápidas</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <Button className="h-16 flex flex-col items-center justify-center space-y-2">
                <Search className="w-5 h-5" />
                <span className="text-sm">🔍 Nova Prospecção</span>
              </Button>
              
              <Button variant="outline" className="h-16 flex flex-col items-center justify-center space-y-2">
                <CalendarIcon className="w-5 h-5" />
                <span className="text-sm">📅 Agendar Reunião</span>
              </Button>
              
              <Button variant="outline" className="h-16 flex flex-col items-center justify-center space-y-2">
                <DollarSign className="w-5 h-5" />
                <span className="text-sm">💰 Registrar Venda</span>
              </Button>
              
              <Button variant="outline" className="h-16 flex flex-col items-center justify-center space-y-2">
                <Target className="w-5 h-5" />
                <span className="text-sm">📊 Meta do Mês</span>
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>;
}