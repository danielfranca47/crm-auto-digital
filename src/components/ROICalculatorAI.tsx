import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { 
  Calculator, 
  TrendingUp, 
  Clock, 
  Users, 
  DollarSign, 
  MessageSquare,
  Zap,
  BarChart3
} from 'lucide-react';

interface ROIInputs {
  businessType: string;
  messagesPerDay: number;
  avgResponseTime: number;
  hourlyRate: number;
  employees: number;
  conversionRate: number;
}

interface ROIResults {
  timesSaved: number;
  moneySaved: number;
  capacityIncrease: number;
  roiPercentage: number;
  messagesHandled: number;
  satisfactionImprovement: number;
}

const ROICalculatorAI = () => {
  const { t } = useTranslation();
  const [inputs, setInputs] = useState<ROIInputs>({
    businessType: '',
    messagesPerDay: 50,
    avgResponseTime: 5,
    hourlyRate: 25,
    employees: 2,
    conversionRate: 15
  });
  const [showResults, setShowResults] = useState(false);

  const calculateROI = (): ROIResults => {
    const messagesPerMonth = inputs.messagesPerDay * 30;
    const currentTimeSpent = (messagesPerMonth * inputs.avgResponseTime) / 60; // hours
    const currentCost = currentTimeSpent * inputs.hourlyRate;
    
    // AI efficiency improvements based on business type
    const efficiencyMultipliers = {
      'service': { time: 0.75, conversion: 1.3, satisfaction: 1.25 },
      'healthcare': { time: 0.70, conversion: 1.25, satisfaction: 1.30 },
      'ecommerce': { time: 0.80, conversion: 1.35, satisfaction: 1.20 },
      'default': { time: 0.75, conversion: 1.25, satisfaction: 1.25 }
    };
    
    const multiplier = efficiencyMultipliers[inputs.businessType as keyof typeof efficiencyMultipliers] || efficiencyMultipliers.default;
    
    const newTimeSpent = currentTimeSpent * multiplier.time;
    const timesSaved = currentTimeSpent - newTimeSpent;
    const moneySaved = timesSaved * inputs.hourlyRate;
    const capacityIncrease = ((currentTimeSpent - newTimeSpent) / currentTimeSpent) * 100;
    const roiPercentage = (moneySaved / (moneySaved * 0.3)) * 100; // Assuming 30% cost of AI solution
    const messagesHandled = messagesPerMonth * (1 / multiplier.time);
    const satisfactionImprovement = (multiplier.satisfaction - 1) * 100;

    return {
      timesSaved,
      moneySaved,
      capacityIncrease,
      roiPercentage,
      messagesHandled,
      satisfactionImprovement
    };
  };

  const results = calculateROI();

  const handleCalculate = () => {
    setShowResults(true);
  };

  const businessTypes = [
    { value: 'service', label: t('aiWhatsappAutomation.roiCalculator.businessTypes.service') },
    { value: 'healthcare', label: t('aiWhatsappAutomation.roiCalculator.businessTypes.healthcare') },
    { value: 'ecommerce', label: t('aiWhatsappAutomation.roiCalculator.businessTypes.ecommerce') }
  ];

  const resultsData = [
    {
      icon: Clock,
      title: t('aiWhatsappAutomation.roiCalculator.results.timeSaved.title'),
      value: `${results.timesSaved.toFixed(1)}h`,
      description: t('aiWhatsappAutomation.roiCalculator.results.timeSaved.description'),
      color: 'text-blue-500'
    },
    {
      icon: DollarSign,
      title: t('aiWhatsappAutomation.roiCalculator.results.moneySaved.title'),
      value: `$${results.moneySaved.toFixed(0)}`,
      description: t('aiWhatsappAutomation.roiCalculator.results.moneySaved.description'),
      color: 'text-green-500'
    },
    {
      icon: TrendingUp,
      title: t('aiWhatsappAutomation.roiCalculator.results.capacityIncrease.title'),
      value: `${results.capacityIncrease.toFixed(0)}%`,
      description: t('aiWhatsappAutomation.roiCalculator.results.capacityIncrease.description'),
      color: 'text-purple-500'
    },
    {
      icon: BarChart3,
      title: t('aiWhatsappAutomation.roiCalculator.results.roi.title'),
      value: `${results.roiPercentage.toFixed(0)}%`,
      description: t('aiWhatsappAutomation.roiCalculator.results.roi.description'),
      color: 'text-orange-500'
    },
    {
      icon: MessageSquare,
      title: t('aiWhatsappAutomation.roiCalculator.results.messagesHandled.title'),
      value: `${results.messagesHandled.toFixed(0)}`,
      description: t('aiWhatsappAutomation.roiCalculator.results.messagesHandled.description'),
      color: 'text-cyan-500'
    },
    {
      icon: Users,
      title: t('aiWhatsappAutomation.roiCalculator.results.satisfaction.title'),
      value: `+${results.satisfactionImprovement.toFixed(0)}%`,
      description: t('aiWhatsappAutomation.roiCalculator.results.satisfaction.description'),
      color: 'text-pink-500'
    }
  ];

  return (
    <section className="py-20 px-4 bg-gradient-to-r from-background to-accent/5">
      <div className="container mx-auto max-w-6xl">
        <div className="text-center mb-16">
          <Badge variant="secondary" className="mb-4 px-4 py-2">
            <Calculator className="w-4 h-4 mr-2" />
            {t('aiWhatsappAutomation.roiCalculator.badge')}
          </Badge>
          <h2 className="text-3xl md:text-4xl font-bold mb-4">
            {t('aiWhatsappAutomation.roiCalculator.title')}
          </h2>
          <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
            {t('aiWhatsappAutomation.roiCalculator.subtitle')}
          </p>
        </div>

        <div className="grid lg:grid-cols-2 gap-8">
          {/* Calculator Inputs */}
          <Card className="bg-card">
            <CardHeader>
              <CardTitle className="flex items-center">
                <Calculator className="w-5 h-5 mr-2 text-accent" />
                {t('aiWhatsappAutomation.roiCalculator.inputsTitle')}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-2">
                <Label htmlFor="businessType">
                  {t('aiWhatsappAutomation.roiCalculator.inputs.businessType')}
                </Label>
                <Select
                  value={inputs.businessType}
                  onValueChange={(value) => setInputs({ ...inputs, businessType: value })}
                >
                  <SelectTrigger>
                    <SelectValue placeholder={t('aiWhatsappAutomation.roiCalculator.inputs.selectBusiness')} />
                  </SelectTrigger>
                  <SelectContent>
                    {businessTypes.map((type) => (
                      <SelectItem key={type.value} value={type.value}>
                        {type.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="grid sm:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="messagesPerDay">
                    {t('aiWhatsappAutomation.roiCalculator.inputs.messagesPerDay')}
                  </Label>
                  <Input
                    id="messagesPerDay"
                    type="number"
                    value={inputs.messagesPerDay}
                    onChange={(e) => setInputs({ ...inputs, messagesPerDay: parseInt(e.target.value) || 0 })}
                    className="text-center"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="avgResponseTime">
                    {t('aiWhatsappAutomation.roiCalculator.inputs.avgResponseTime')}
                  </Label>
                  <Input
                    id="avgResponseTime"
                    type="number"
                    value={inputs.avgResponseTime}
                    onChange={(e) => setInputs({ ...inputs, avgResponseTime: parseFloat(e.target.value) || 0 })}
                    className="text-center"
                  />
                </div>
              </div>

              <div className="grid sm:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="hourlyRate">
                    {t('aiWhatsappAutomation.roiCalculator.inputs.hourlyRate')}
                  </Label>
                  <Input
                    id="hourlyRate"
                    type="number"
                    value={inputs.hourlyRate}
                    onChange={(e) => setInputs({ ...inputs, hourlyRate: parseFloat(e.target.value) || 0 })}
                    className="text-center"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="employees">
                    {t('aiWhatsappAutomation.roiCalculator.inputs.employees')}
                  </Label>
                  <Input
                    id="employees"
                    type="number"
                    value={inputs.employees}
                    onChange={(e) => setInputs({ ...inputs, employees: parseInt(e.target.value) || 0 })}
                    className="text-center"
                  />
                </div>
              </div>

              <Button 
                onClick={handleCalculate} 
                className="w-full hover-scale"
                size="lg"
              >
                <Zap className="w-5 h-5 mr-2" />
                {t('aiWhatsappAutomation.roiCalculator.calculateButton')}
              </Button>
            </CardContent>
          </Card>

          {/* Results */}
          <div className="space-y-6">
            {!showResults ? (
              <Card className="bg-gradient-to-br from-accent/10 to-primary/10 border-accent/20 h-full flex items-center justify-center">
                <CardContent className="text-center p-8">
                  <Calculator className="w-16 h-16 mx-auto mb-4 text-accent" />
                  <h3 className="text-xl font-semibold mb-2">
                    {t('aiWhatsappAutomation.roiCalculator.placeholder.title')}
                  </h3>
                  <p className="text-muted-foreground">
                    {t('aiWhatsappAutomation.roiCalculator.placeholder.description')}
                  </p>
                </CardContent>
              </Card>
            ) : (
              <div className="space-y-4">
                <Card className="bg-gradient-to-r from-green-500/10 to-blue-500/10 border-green-500/20">
                  <CardHeader>
                    <CardTitle className="text-green-600 dark:text-green-400">
                      {t('aiWhatsappAutomation.roiCalculator.resultsTitle')}
                    </CardTitle>
                  </CardHeader>
                </Card>

                <div className="grid sm:grid-cols-2 gap-4">
                  {resultsData.map((result, index) => (
                    <Card key={index} className="bg-card hover:bg-card/80 transition-all duration-300 hover-scale">
                      <CardContent className="p-6">
                        <div className="flex items-center mb-3">
                          <result.icon className={`w-6 h-6 mr-3 ${result.color}`} />
                          <h4 className="font-semibold">{result.title}</h4>
                        </div>
                        <div className={`text-2xl font-bold mb-2 ${result.color}`}>
                          {result.value}
                        </div>
                        <p className="text-sm text-muted-foreground">
                          {result.description}
                        </p>
                      </CardContent>
                    </Card>
                  ))}
                </div>

                <Card className="bg-gradient-to-r from-accent/10 to-primary/10 border-accent/20">
                  <CardContent className="p-6 text-center">
                    <h4 className="text-lg font-semibold mb-2">
                      {t('aiWhatsappAutomation.roiCalculator.summary.title')}
                    </h4>
                    <p className="text-muted-foreground mb-4">
                      {t('aiWhatsappAutomation.roiCalculator.summary.description', {
                        monthlySavings: results.moneySaved.toFixed(0),
                        yearlyROI: (results.roiPercentage * 12).toFixed(0)
                      })}
                    </p>
                    <Button className="hover-scale">
                      {t('aiWhatsappAutomation.roiCalculator.summary.cta')}
                    </Button>
                  </CardContent>
                </Card>
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
};

export default ROICalculatorAI;