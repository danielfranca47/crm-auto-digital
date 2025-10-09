import { useTranslation } from 'react-i18next';
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { MessageSquare, Bot, Zap, Clock, TrendingUp, Users } from 'lucide-react';
import AIWhatsAppDemo from "@/components/AIWhatsAppDemo";
import BusinessSegmentBenefits from "@/components/BusinessSegmentBenefits";
import ROICalculatorAI from "@/components/ROICalculatorAI";
import AIFeaturesShowcase from "@/components/AIFeaturesShowcase";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import WhatsAppMessage from "@/components/WhatsAppMessage";
import { useEffect } from 'react';

const AIWhatsAppAutomation = () => {
  const { t, i18n } = useTranslation();

  useEffect(() => {
    // Update meta tags for SEO
    document.title = t('aiWhatsappAutomation.meta.title');
    
    const metaDescription = document.querySelector('meta[name="description"]');
    if (metaDescription) {
      metaDescription.setAttribute('content', t('aiWhatsappAutomation.meta.description'));
    }

    // Open Graph tags
    const ogTitle = document.querySelector('meta[property="og:title"]');
    if (ogTitle) ogTitle.setAttribute('content', t('aiWhatsappAutomation.meta.title'));
    
    const ogDescription = document.querySelector('meta[property="og:description"]');
    if (ogDescription) ogDescription.setAttribute('content', t('aiWhatsappAutomation.meta.description'));

    // Canonical URL
    const currentPath = window.location.pathname;
    const canonical = document.querySelector('link[rel="canonical"]');
    if (canonical) {
      canonical.setAttribute('href', `${window.location.origin}${currentPath}`);
    }
  }, [t, i18n.language]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-background via-card to-background">
      <Header />
      <main>
        {/* Hero Section */}
        <section className="relative py-20 px-4 overflow-hidden">
          <div className="container mx-auto max-w-6xl text-center">
            <div className="animate-fade-in">
              <Badge variant="secondary" className="mb-6 px-4 py-2 text-sm font-semibold">
                <Bot className="w-4 h-4 mr-2" />
                {t('aiWhatsappAutomation.hero.badge')}
              </Badge>
              
              <h1 className="text-4xl md:text-6xl font-bold mb-6 bg-gradient-to-r from-foreground to-accent bg-clip-text text-transparent leading-tight">
                {t('aiWhatsappAutomation.hero.title')}
              </h1>
              
              <p className="text-xl text-muted-foreground mb-8 max-w-3xl mx-auto leading-relaxed">
                {t('aiWhatsappAutomation.hero.subtitle')}
              </p>
              
              <div className="flex flex-col sm:flex-row gap-4 justify-center items-center mb-12">
                <Button size="lg" className="px-8 py-3 text-lg hover-scale">
                  <MessageSquare className="w-5 h-5 mr-2" />
                  {t('aiWhatsappAutomation.hero.ctaPrimary')}
                </Button>
                <Button variant="outline" size="lg" className="px-8 py-3 text-lg hover-scale">
                  <Zap className="w-5 h-5 mr-2" />
                  {t('aiWhatsappAutomation.hero.ctaSecondary')}
                </Button>
              </div>
            </div>

            {/* Hero Stats */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-6 mt-16 animate-fade-in">
              {[
                { icon: Clock, value: "80%", label: t('aiWhatsappAutomation.hero.stats.timeReduction') },
                { icon: TrendingUp, value: "150%", label: t('aiWhatsappAutomation.hero.stats.salesIncrease') },
                { icon: Users, value: "24/7", label: t('aiWhatsappAutomation.hero.stats.availability') },
                { icon: Bot, value: "99%", label: t('aiWhatsappAutomation.hero.stats.accuracy') }
              ].map((stat, index) => (
                <Card key={index} className="bg-card/50 backdrop-blur-sm border-border/50 hover:bg-card/70 transition-all duration-300">
                  <CardContent className="p-6 text-center">
                    <stat.icon className="w-8 h-8 mx-auto mb-2 text-accent" />
                    <div className="text-2xl font-bold text-foreground">{stat.value}</div>
                    <div className="text-sm text-muted-foreground">{stat.label}</div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </section>

        {/* Business Segments */}
        <BusinessSegmentBenefits />

        {/* Interactive Demo */}
        <AIWhatsAppDemo />

        {/* AI Features */}
        <AIFeaturesShowcase />

        {/* ROI Calculator */}
        <ROICalculatorAI />

        {/* Success Stories */}
        <section className="py-20 px-4 bg-gradient-to-r from-card/30 to-background">
          <div className="container mx-auto max-w-6xl">
            <div className="text-center mb-16">
              <h2 className="text-3xl md:text-4xl font-bold mb-4">
                {t('aiWhatsappAutomation.successStories.title')}
              </h2>
              <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
                {t('aiWhatsappAutomation.successStories.subtitle')}
              </p>
            </div>

            <div className="grid md:grid-cols-3 gap-8">
              {['serviceCompany', 'healthcare', 'ecommerce'].map((segment, index) => (
                <Card key={segment} className="bg-card hover:bg-card/80 transition-all duration-300 hover-scale">
                  <CardHeader>
                    <CardTitle className="text-xl">
                      {t(`aiWhatsappAutomation.successStories.${segment}.company`)}
                    </CardTitle>
                    <CardDescription>
                      {t(`aiWhatsappAutomation.successStories.${segment}.industry`)}
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <blockquote className="text-muted-foreground mb-4">
                      "{t(`aiWhatsappAutomation.successStories.${segment}.testimonial`)}"
                    </blockquote>
                    <div className="grid grid-cols-2 gap-4 text-sm">
                      <div className="text-center">
                        <div className="text-2xl font-bold text-accent">
                          {t(`aiWhatsappAutomation.successStories.${segment}.metric1Value`)}
                        </div>
                        <div className="text-muted-foreground">
                          {t(`aiWhatsappAutomation.successStories.${segment}.metric1Label`)}
                        </div>
                      </div>
                      <div className="text-center">
                        <div className="text-2xl font-bold text-accent">
                          {t(`aiWhatsappAutomation.successStories.${segment}.metric2Value`)}
                        </div>
                        <div className="text-muted-foreground">
                          {t(`aiWhatsappAutomation.successStories.${segment}.metric2Label`)}
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </section>

        {/* Final CTA */}
        <section className="py-20 px-4 bg-gradient-to-r from-primary/10 to-accent/10">
          <div className="container mx-auto max-w-4xl text-center">
            <h2 className="text-3xl md:text-4xl font-bold mb-6">
              {t('aiWhatsappAutomation.finalCta.title')}
            </h2>
            <p className="text-xl text-muted-foreground mb-8 max-w-2xl mx-auto">
              {t('aiWhatsappAutomation.finalCta.subtitle')}
            </p>
            
            <div className="flex flex-col sm:flex-row gap-4 justify-center items-center mb-8">
              <Button size="lg" className="px-12 py-4 text-lg hover-scale">
                <Bot className="w-5 h-5 mr-2" />
                {t('aiWhatsappAutomation.finalCta.primaryButton')}
              </Button>
              <Button variant="outline" size="lg" className="px-8 py-4 text-lg hover-scale">
                {t('aiWhatsappAutomation.finalCta.secondaryButton')}
              </Button>
            </div>

            <div className="grid md:grid-cols-3 gap-6 mt-12 text-sm text-muted-foreground">
              <div className="flex items-center justify-center">
                <Clock className="w-4 h-4 mr-2" />
                {t('aiWhatsappAutomation.finalCta.guarantees.setup')}
              </div>
              <div className="flex items-center justify-center">
                <Users className="w-4 h-4 mr-2" />
                {t('aiWhatsappAutomation.finalCta.guarantees.support')}
              </div>
              <div className="flex items-center justify-center">
                <Zap className="w-4 h-4 mr-2" />
                {t('aiWhatsappAutomation.finalCta.guarantees.trial')}
              </div>
            </div>
          </div>
        </section>
      </main>
      
      <Footer />
      <WhatsAppMessage 
        show={false} 
        bookingData={null} 
        onReset={() => {}} 
      />
    </div>
  );
};

export default AIWhatsAppAutomation;