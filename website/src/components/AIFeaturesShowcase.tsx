import React from 'react';
import { useTranslation } from 'react-i18next';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { 
  Brain, 
  MessageSquare, 
  Globe, 
  Zap, 
  BarChart3, 
  Shield,
  Bot,
  Cpu,
  Database,
  Cloud,
  Smartphone,
  Settings
} from 'lucide-react';

interface Feature {
  icon: React.ElementType;
  title: string;
  description: string;
  details: string[];
  color: string;
}

const AIFeaturesShowcase = () => {
  const { t } = useTranslation();

  const features: Feature[] = [
    {
      icon: Brain,
      title: t('aiWhatsappAutomation.features.nlp.title'),
      description: t('aiWhatsappAutomation.features.nlp.description'),
      details: [
        t('aiWhatsappAutomation.features.nlp.details.intent'),
        t('aiWhatsappAutomation.features.nlp.details.sentiment'),
        t('aiWhatsappAutomation.features.nlp.details.context')
      ],
      color: 'from-purple-500 to-pink-500'
    },
    {
      icon: MessageSquare,
      title: t('aiWhatsappAutomation.features.whatsapp.title'),
      description: t('aiWhatsappAutomation.features.whatsapp.description'),
      details: [
        t('aiWhatsappAutomation.features.whatsapp.details.api'),
        t('aiWhatsappAutomation.features.whatsapp.details.multimedia'),
        t('aiWhatsappAutomation.features.whatsapp.details.templates')
      ],
      color: 'from-green-500 to-emerald-500'
    },
    {
      icon: Database,
      title: t('aiWhatsappAutomation.features.catalog.title'),
      description: t('aiWhatsappAutomation.features.catalog.description'),
      details: [
        t('aiWhatsappAutomation.features.catalog.details.sync'),
        t('aiWhatsappAutomation.features.catalog.details.search'),
        t('aiWhatsappAutomation.features.catalog.details.recommendations')
      ],
      color: 'from-blue-500 to-cyan-500'
    },
    {
      icon: Zap,
      title: t('aiWhatsappAutomation.features.automation.title'),
      description: t('aiWhatsappAutomation.features.automation.description'),
      details: [
        t('aiWhatsappAutomation.features.automation.details.workflows'),
        t('aiWhatsappAutomation.features.automation.details.triggers'),
        t('aiWhatsappAutomation.features.automation.details.actions')
      ],
      color: 'from-orange-500 to-red-500'
    },
    {
      icon: BarChart3,
      title: t('aiWhatsappAutomation.features.analytics.title'),
      description: t('aiWhatsappAutomation.features.analytics.description'),
      details: [
        t('aiWhatsappAutomation.features.analytics.details.metrics'),
        t('aiWhatsappAutomation.features.analytics.details.insights'),
        t('aiWhatsappAutomation.features.analytics.details.reports')
      ],
      color: 'from-indigo-500 to-purple-500'
    },
    {
      icon: Cloud,
      title: t('aiWhatsappAutomation.features.scalability.title'),
      description: t('aiWhatsappAutomation.features.scalability.description'),
      details: [
        t('aiWhatsappAutomation.features.scalability.details.infrastructure'),
        t('aiWhatsappAutomation.features.scalability.details.performance'),
        t('aiWhatsappAutomation.features.scalability.details.reliability')
      ],
      color: 'from-teal-500 to-blue-500'
    }
  ];

  const techSpecs = [
    {
      icon: Cpu,
      title: t('aiWhatsappAutomation.features.tech.processing.title'),
      value: t('aiWhatsappAutomation.features.tech.processing.value')
    },
    {
      icon: Globe,
      title: t('aiWhatsappAutomation.features.tech.languages.title'),
      value: t('aiWhatsappAutomation.features.tech.languages.value')
    },
    {
      icon: Shield,
      title: t('aiWhatsappAutomation.features.tech.security.title'),
      value: t('aiWhatsappAutomation.features.tech.security.value')
    },
    {
      icon: Smartphone,
      title: t('aiWhatsappAutomation.features.tech.integration.title'),
      value: t('aiWhatsappAutomation.features.tech.integration.value')
    }
  ];

  return (
    <section className="py-20 px-4 bg-gradient-to-b from-card/30 to-background">
      <div className="container mx-auto max-w-7xl">
        <div className="text-center mb-16">
          <Badge variant="secondary" className="mb-4 px-4 py-2">
            <Bot className="w-4 h-4 mr-2" />
            {t('aiWhatsappAutomation.features.badge')}
          </Badge>
          <h2 className="text-3xl md:text-4xl font-bold mb-4">
            {t('aiWhatsappAutomation.features.title')}
          </h2>
          <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
            {t('aiWhatsappAutomation.features.subtitle')}
          </p>
        </div>

        {/* Features Grid */}
        <div className="grid lg:grid-cols-3 gap-8 mb-16">
          {features.map((feature, index) => (
            <Card 
              key={index} 
              className="bg-card hover:bg-card/80 transition-all duration-300 hover-scale overflow-hidden group"
            >
              <CardHeader className="relative">
                <div className={`absolute inset-0 bg-gradient-to-br ${feature.color} opacity-5 group-hover:opacity-10 transition-opacity duration-300`} />
                <div className={`w-12 h-12 rounded-lg bg-gradient-to-br ${feature.color} flex items-center justify-center mb-4 relative z-10`}>
                  <feature.icon className="w-6 h-6 text-white" />
                </div>
                <CardTitle className="text-xl relative z-10">{feature.title}</CardTitle>
                <CardDescription className="relative z-10">{feature.description}</CardDescription>
              </CardHeader>
              <CardContent className="relative">
                <ul className="space-y-2">
                  {feature.details.map((detail, detailIndex) => (
                    <li key={detailIndex} className="flex items-start text-sm">
                      <div className={`w-1.5 h-1.5 rounded-full bg-gradient-to-r ${feature.color} mt-2 mr-3 flex-shrink-0`} />
                      <span className="text-muted-foreground">{detail}</span>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Technical Specifications */}
        <div className="grid md:grid-cols-2 gap-8 mb-16">
          <Card className="bg-gradient-to-br from-card to-card/50">
            <CardHeader>
              <CardTitle className="flex items-center">
                <Settings className="w-5 h-5 mr-2 text-accent" />
                {t('aiWhatsappAutomation.features.techSpecs.title')}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid sm:grid-cols-2 gap-6">
                {techSpecs.map((spec, index) => (
                  <div key={index} className="text-center">
                    <div className="w-12 h-12 bg-accent/10 rounded-lg flex items-center justify-center mx-auto mb-3">
                      <spec.icon className="w-6 h-6 text-accent" />
                    </div>
                    <h4 className="font-semibold mb-1">{spec.title}</h4>
                    <p className="text-sm text-muted-foreground">{spec.value}</p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card className="bg-gradient-to-br from-primary/10 to-accent/10 border-accent/20">
            <CardHeader>
              <CardTitle className="text-accent">
                {t('aiWhatsappAutomation.features.comparison.title')}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {[
                  {
                    feature: t('aiWhatsappAutomation.features.comparison.responseTime'),
                    traditional: t('aiWhatsappAutomation.features.comparison.traditional.responseTime'),
                    ai: t('aiWhatsappAutomation.features.comparison.ai.responseTime')
                  },
                  {
                    feature: t('aiWhatsappAutomation.features.comparison.availability'),
                    traditional: t('aiWhatsappAutomation.features.comparison.traditional.availability'),
                    ai: t('aiWhatsappAutomation.features.comparison.ai.availability')
                  },
                  {
                    feature: t('aiWhatsappAutomation.features.comparison.accuracy'),
                    traditional: t('aiWhatsappAutomation.features.comparison.traditional.accuracy'),
                    ai: t('aiWhatsappAutomation.features.comparison.ai.accuracy')
                  },
                  {
                    feature: t('aiWhatsappAutomation.features.comparison.scalability'),
                    traditional: t('aiWhatsappAutomation.features.comparison.traditional.scalability'),
                    ai: t('aiWhatsappAutomation.features.comparison.ai.scalability')
                  }
                ].map((item, index) => (
                  <div key={index} className="border-l-2 border-accent/30 pl-4">
                    <h5 className="font-medium mb-2">{item.feature}</h5>
                    <div className="grid grid-cols-2 gap-4 text-sm">
                      <div>
                        <span className="text-muted-foreground">Traditional:</span>
                        <p className="text-red-500">{item.traditional}</p>
                      </div>
                      <div>
                        <span className="text-muted-foreground">AI:</span>
                        <p className="text-green-500">{item.ai}</p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Integration Preview */}
        <Card className="bg-gradient-to-r from-card to-accent/5 border-accent/20">
          <CardContent className="p-8 text-center">
            <Bot className="w-16 h-16 mx-auto mb-4 text-accent" />
            <h3 className="text-2xl font-bold mb-4">
              {t('aiWhatsappAutomation.features.integration.title')}
            </h3>
            <p className="text-muted-foreground mb-6 max-w-2xl mx-auto">
              {t('aiWhatsappAutomation.features.integration.description')}
            </p>
            <div className="flex flex-wrap justify-center gap-4 mb-6">
              {[
                'WhatsApp Business',
                'CRM Systems',
                'E-commerce',
                'Calendars',
                'Payment Gateways',
                'Analytics Tools'
              ].map((integration, index) => (
                <Badge key={index} variant="secondary" className="px-3 py-1">
                  {integration}
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </section>
  );
};

export default AIFeaturesShowcase;