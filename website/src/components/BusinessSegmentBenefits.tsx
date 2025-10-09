import React from 'react';
import { useTranslation } from 'react-i18next';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { 
  Calendar, 
  DollarSign, 
  MessageSquare, 
  Headphones,
  Stethoscope,
  Bell,
  FileText,
  Shield,
  Package,
  Search,
  CreditCard,
  RotateCcw,
  ArrowRight
} from 'lucide-react';

interface Segment {
  id: string;
  title: string;
  description: string;
  icon: React.ElementType;
  color: string;
  benefits: {
    icon: React.ElementType;
    title: string;
    description: string;
  }[];
}

const BusinessSegmentBenefits = () => {
  const { t } = useTranslation();

  const segments: Segment[] = [
    {
      id: 'serviceCompanies',
      title: t('aiWhatsappAutomation.segments.serviceCompanies.title'),
      description: t('aiWhatsappAutomation.segments.serviceCompanies.description'),
      icon: Calendar,
      color: 'from-blue-500 to-blue-600',
      benefits: [
        {
          icon: Calendar,
          title: t('aiWhatsappAutomation.segments.serviceCompanies.benefits.scheduling.title'),
          description: t('aiWhatsappAutomation.segments.serviceCompanies.benefits.scheduling.description')
        },
        {
          icon: DollarSign,
          title: t('aiWhatsappAutomation.segments.serviceCompanies.benefits.quotes.title'),
          description: t('aiWhatsappAutomation.segments.serviceCompanies.benefits.quotes.description')
        },
        {
          icon: MessageSquare,
          title: t('aiWhatsappAutomation.segments.serviceCompanies.benefits.info.title'),
          description: t('aiWhatsappAutomation.segments.serviceCompanies.benefits.info.description')
        },
        {
          icon: Headphones,
          title: t('aiWhatsappAutomation.segments.serviceCompanies.benefits.support.title'),
          description: t('aiWhatsappAutomation.segments.serviceCompanies.benefits.support.description')
        }
      ]
    },
    {
      id: 'healthcare',
      title: t('aiWhatsappAutomation.segments.healthcare.title'),
      description: t('aiWhatsappAutomation.segments.healthcare.description'),
      icon: Stethoscope,
      color: 'from-green-500 to-green-600',
      benefits: [
        {
          icon: Calendar,
          title: t('aiWhatsappAutomation.segments.healthcare.benefits.appointments.title'),
          description: t('aiWhatsappAutomation.segments.healthcare.benefits.appointments.description')
        },
        {
          icon: Bell,
          title: t('aiWhatsappAutomation.segments.healthcare.benefits.reminders.title'),
          description: t('aiWhatsappAutomation.segments.healthcare.benefits.reminders.description')
        },
        {
          icon: FileText,
          title: t('aiWhatsappAutomation.segments.healthcare.benefits.healthInfo.title'),
          description: t('aiWhatsappAutomation.segments.healthcare.benefits.healthInfo.description')
        },
        {
          icon: Shield,
          title: t('aiWhatsappAutomation.segments.healthcare.benefits.insurance.title'),
          description: t('aiWhatsappAutomation.segments.healthcare.benefits.insurance.description')
        }
      ]
    },
    {
      id: 'ecommerce',
      title: t('aiWhatsappAutomation.segments.ecommerce.title'),
      description: t('aiWhatsappAutomation.segments.ecommerce.description'),
      icon: Package,
      color: 'from-purple-500 to-purple-600',
      benefits: [
        {
          icon: Search,
          title: t('aiWhatsappAutomation.segments.ecommerce.benefits.catalog.title'),
          description: t('aiWhatsappAutomation.segments.ecommerce.benefits.catalog.description')
        },
        {
          icon: Package,
          title: t('aiWhatsappAutomation.segments.ecommerce.benefits.tracking.title'),
          description: t('aiWhatsappAutomation.segments.ecommerce.benefits.tracking.description')
        },
        {
          icon: CreditCard,
          title: t('aiWhatsappAutomation.segments.ecommerce.benefits.payment.title'),
          description: t('aiWhatsappAutomation.segments.ecommerce.benefits.payment.description')
        },
        {
          icon: RotateCcw,
          title: t('aiWhatsappAutomation.segments.ecommerce.benefits.recovery.title'),
          description: t('aiWhatsappAutomation.segments.ecommerce.benefits.recovery.description')
        }
      ]
    }
  ];

  return (
    <section className="py-20 px-4 bg-gradient-to-b from-background to-card/30">
      <div className="container mx-auto max-w-7xl">
        <div className="text-center mb-16">
          <Badge variant="secondary" className="mb-4 px-4 py-2">
            {t('aiWhatsappAutomation.segments.badge')}
          </Badge>
          <h2 className="text-3xl md:text-4xl font-bold mb-4">
            {t('aiWhatsappAutomation.segments.title')}
          </h2>
          <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
            {t('aiWhatsappAutomation.segments.subtitle')}
          </p>
        </div>

        <div className="space-y-12">
          {segments.map((segment, index) => (
            <Card 
              key={segment.id} 
              className="overflow-hidden bg-card hover:bg-card/80 transition-all duration-300 hover-scale"
            >
              <div className="grid lg:grid-cols-2 gap-0">
                {/* Segment Header */}
                <div className={`bg-gradient-to-br ${segment.color} p-8 text-white`}>
                  <div className="flex items-center mb-4">
                    <div className="w-12 h-12 bg-white/20 rounded-lg flex items-center justify-center mr-4">
                      <segment.icon className="w-6 h-6" />
                    </div>
                    <div>
                      <h3 className="text-2xl font-bold">{segment.title}</h3>
                      <p className="text-white/80">{segment.description}</p>
                    </div>
                  </div>
                  
                  <div className="space-y-4 mb-6">
                    <h4 className="text-lg font-semibold text-white/90">
                      {t('aiWhatsappAutomation.segments.keyBenefits')}
                    </h4>
                    {segment.benefits.map((benefit, benefitIndex) => (
                      <div key={benefitIndex} className="flex items-start">
                        <benefit.icon className="w-5 h-5 mr-3 mt-0.5 text-white/80" />
                        <div>
                          <h5 className="font-medium text-white">{benefit.title}</h5>
                          <p className="text-sm text-white/80">{benefit.description}</p>
                        </div>
                      </div>
                    ))}
                  </div>

                  <Button 
                    variant="secondary" 
                    className="bg-white/20 hover:bg-white/30 text-white border-white/30 hover:border-white/50"
                  >
                    {t('aiWhatsappAutomation.segments.viewDemo')}
                    <ArrowRight className="w-4 h-4 ml-2" />
                  </Button>
                </div>

                {/* Benefits Grid */}
                <div className="p-8">
                  <h4 className="text-xl font-semibold mb-6">
                    {t('aiWhatsappAutomation.segments.detailedFeatures')}
                  </h4>
                  <div className="grid sm:grid-cols-2 gap-4">
                    {segment.benefits.map((benefit, benefitIndex) => (
                      <div 
                        key={benefitIndex}
                        className="p-4 rounded-lg bg-gradient-to-br from-card to-card/50 border border-border/50 hover:border-accent/50 transition-all duration-300"
                      >
                        <div className="flex items-center mb-3">
                          <div className={`w-8 h-8 rounded-lg bg-gradient-to-br ${segment.color} flex items-center justify-center mr-3`}>
                            <benefit.icon className="w-4 h-4 text-white" />
                          </div>
                          <h5 className="font-medium">{benefit.title}</h5>
                        </div>
                        <p className="text-sm text-muted-foreground leading-relaxed">
                          {benefit.description}
                        </p>
                      </div>
                    ))}
                  </div>

                  {/* Use Case Examples */}
                  <div className="mt-6 p-4 bg-accent/10 rounded-lg border border-accent/20">
                    <h5 className="font-medium text-accent mb-2">
                      {t('aiWhatsappAutomation.segments.useCase')}
                    </h5>
                    <p className="text-sm text-muted-foreground">
                      {t(`aiWhatsappAutomation.segments.${segment.id}.useCase`)}
                    </p>
                  </div>
                </div>
              </div>
            </Card>
          ))}
        </div>

        {/* Call to Action */}
        <div className="text-center mt-16">
          <Card className="bg-gradient-to-r from-accent/10 to-primary/10 p-8 border-accent/20">
            <h3 className="text-2xl font-bold mb-4">
              {t('aiWhatsappAutomation.segments.cta.title')}
            </h3>
            <p className="text-muted-foreground mb-6 max-w-2xl mx-auto">
              {t('aiWhatsappAutomation.segments.cta.description')}
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <Button size="lg" className="hover-scale">
                {t('aiWhatsappAutomation.segments.cta.primary')}
              </Button>
              <Button variant="outline" size="lg" className="hover-scale">
                {t('aiWhatsappAutomation.segments.cta.secondary')}
              </Button>
            </div>
          </Card>
        </div>
      </div>
    </section>
  );
};

export default BusinessSegmentBenefits;