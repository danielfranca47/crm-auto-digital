import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { 
  Calculator, 
  Clock, 
  DollarSign, 
  TrendingUp, 
  Users,
  CheckCircle2,
  Calendar
} from 'lucide-react';

const ROICalculator = () => {
  const { t } = useTranslation();
  const [inputs, setInputs] = useState({
    employees: 2,
    dailyBookings: 15,
    timePerBooking: 5,
    hourlyRate: 50
  });
  const [showResults, setShowResults] = useState(false);

  const calculateROI = () => {
    setShowResults(true);
  };

  // Calculations
  const monthlyTimeSpent = inputs.employees * inputs.dailyBookings * inputs.timePerBooking * 22; // 22 working days
  const timeSavedPercentage = 80; // 80% time saved with automation
  const timeSavedMonthly = (monthlyTimeSpent * timeSavedPercentage) / 100;
  const moneySavedMonthly = (timeSavedMonthly / 60) * inputs.hourlyRate;
  const capacityIncrease = Math.round((timeSavedMonthly / 60) / 8); // Additional days of work
  const noShowReduction = 60; // 60% reduction in no-shows

  const results = [
    {
      icon: Clock,
      title: t('schedulingDemo.roi.results.timesSaved'),
      value: `${Math.round(timeSavedMonthly / 60)}h`,
      description: 'Horas economizadas por mês'
    },
    {
      icon: DollarSign,
      title: t('schedulingDemo.roi.results.moneySaved'),
      value: `R$ ${moneySavedMonthly.toLocaleString('pt-BR')}`,
      description: 'Economia mensal em custos operacionais'
    },
    {
      icon: TrendingUp,
      title: t('schedulingDemo.roi.results.increaseCapacity'),
      value: `+${capacityIncrease} dias`,
      description: 'Equivalente de dias de trabalho extras'
    },
    {
      icon: CheckCircle2,
      title: t('schedulingDemo.roi.results.noShowReduction'),
      value: `${noShowReduction}%`,
      description: 'Redução média de no-shows'
    }
  ];

  return (
    <section className="py-20 lg:py-32">
      <div className="container mx-auto px-4 lg:px-8">
        <div className="text-center mb-16">
          <h2 className="text-heading text-foreground mb-6">
            {t('schedulingDemo.roi.title')}
          </h2>
          <p className="text-lg text-muted-foreground max-w-3xl mx-auto">
            {t('schedulingDemo.roi.subtitle')}
          </p>
        </div>

        <div className="max-w-6xl mx-auto">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-start">
            
            {/* Calculator Inputs */}
            <Card className="p-8">
              <div className="flex items-center mb-6">
                <div className="w-12 h-12 rounded-xl accent-gradient flex items-center justify-center mr-4">
                  <Calculator className="w-6 h-6 text-accent-foreground" />
                </div>
                <div>
                  <h3 className="text-xl font-bold text-foreground">
                    Calculadora de ROI
                  </h3>
                  <p className="text-muted-foreground">
                    Insira os dados do seu negócio
                  </p>
                </div>
              </div>

              <div className="space-y-6">
                <div>
                  <Label className="flex items-center mb-2">
                    <Users className="w-4 h-4 mr-2" />
                    {t('schedulingDemo.roi.inputs.employees')}
                  </Label>
                  <Input
                    type="number"
                    value={inputs.employees}
                    onChange={(e) => setInputs(prev => ({ ...prev, employees: parseInt(e.target.value) || 0 }))}
                    min="1"
                    max="50"
                  />
                </div>

                <div>
                  <Label className="flex items-center mb-2">
                    <Calendar className="w-4 h-4 mr-2" />
                    {t('schedulingDemo.roi.inputs.dailyBookings')}
                  </Label>
                  <Input
                    type="number"
                    value={inputs.dailyBookings}
                    onChange={(e) => setInputs(prev => ({ ...prev, dailyBookings: parseInt(e.target.value) || 0 }))}
                    min="1"
                    max="100"
                  />
                </div>

                <div>
                  <Label className="flex items-center mb-2">
                    <Clock className="w-4 h-4 mr-2" />
                    {t('schedulingDemo.roi.inputs.timePerBooking')}
                  </Label>
                  <Input
                    type="number"
                    value={inputs.timePerBooking}
                    onChange={(e) => setInputs(prev => ({ ...prev, timePerBooking: parseInt(e.target.value) || 0 }))}
                    min="1"
                    max="30"
                  />
                </div>

                <div>
                  <Label className="flex items-center mb-2">
                    <DollarSign className="w-4 h-4 mr-2" />
                    {t('schedulingDemo.roi.inputs.hourlyRate')}
                  </Label>
                  <Input
                    type="number"
                    value={inputs.hourlyRate}
                    onChange={(e) => setInputs(prev => ({ ...prev, hourlyRate: parseInt(e.target.value) || 0 }))}
                    min="10"
                    max="500"
                  />
                </div>

                <Button 
                  onClick={calculateROI}
                  className="w-full h-12 text-lg"
                >
                  <Calculator className="w-5 h-5 mr-2" />
                  {t('schedulingDemo.roi.calculate')}
                </Button>
              </div>
            </Card>

            {/* Results */}
            <div className="space-y-6">
              {showResults ? (
                <div className="space-y-4">
                  {results.map((result, index) => (
                    <Card 
                      key={result.title}
                      className="p-6 animate-fade-in"
                      style={{ animationDelay: `${index * 100}ms` }}
                    >
                      <div className="flex items-center space-x-4">
                        <div className="w-12 h-12 rounded-xl accent-gradient flex items-center justify-center">
                          <result.icon className="w-6 h-6 text-accent-foreground" />
                        </div>
                        <div className="flex-1">
                          <h4 className="font-semibold text-foreground mb-1">
                            {result.title}
                          </h4>
                          <div className="flex items-baseline space-x-2">
                            <span className="text-2xl font-bold text-accent">
                              {result.value}
                            </span>
                          </div>
                          <p className="text-sm text-muted-foreground mt-1">
                            {result.description}
                          </p>
                        </div>
                      </div>
                    </Card>
                  ))}

                  <Card className="p-6 bg-gradient-to-br from-accent/10 via-transparent to-primary/10 border-accent/20">
                    <div className="text-center">
                      <h4 className="text-xl font-bold text-foreground mb-2">
                        Economia Anual Estimada
                      </h4>
                      <div className="text-3xl font-bold text-accent mb-2">
                        R$ {(moneySavedMonthly * 12).toLocaleString('pt-BR')}
                      </div>
                      <p className="text-muted-foreground">
                        Baseado nos dados informados
                      </p>
                    </div>
                  </Card>
                </div>
              ) : (
                <Card className="p-8 text-center">
                  <div className="w-20 h-20 rounded-full bg-accent/20 flex items-center justify-center mx-auto mb-6">
                    <Calculator className="w-10 h-10 text-accent" />
                  </div>
                  <h3 className="text-xl font-semibold text-foreground mb-3">
                    Calcule Seu ROI
                  </h3>
                  <p className="text-muted-foreground">
                    Preencha os campos ao lado para ver quanto você pode economizar
                  </p>
                </Card>
              )}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};

export default ROICalculator;