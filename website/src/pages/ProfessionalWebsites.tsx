import Header from '@/components/Header';
import Footer from '@/components/Footer';
import { useTranslation } from 'react-i18next';
import { useParams, useNavigate } from 'react-router-dom';
import { useEffect } from 'react';
import {
  ArrowRight, 
  CheckCircle2, 
  Code, 
  Smartphone, 
  Search, 
  Zap,
  Shield,
  BarChart3,
  Globe,
  Rocket,
  Calculator,
  Sparkles,
  Scissors,
  Ruler
} from 'lucide-react';

const ProfessionalWebsites = () => {
  const { t } = useTranslation();
  const { lang } = useParams();
  const navigate = useNavigate();

  useEffect(() => {
    document.title = t('professionalWebsites.meta.title');
    
    const metaDescription = document.querySelector('meta[name="description"]');
    if (metaDescription) {
      metaDescription.setAttribute('content', t('professionalWebsites.meta.description'));
    }
  }, [t]);

  const examples = [
    {
      title: t('professionalWebsites.examples.accounting.title'),
      category: t('professionalWebsites.examples.accounting.category'),
      description: t('professionalWebsites.examples.accounting.description'),
      features: t('professionalWebsites.examples.accounting.features', { returnObjects: true }) as string[],
      gradient: 'from-blue-600 to-indigo-600',
      icon: 'Calculator',
      available: true
    },
    {
      title: t('professionalWebsites.examples.spa.title'),
      category: t('professionalWebsites.examples.spa.category'),
      description: t('professionalWebsites.examples.spa.description'),
      features: t('professionalWebsites.examples.spa.features', { returnObjects: true }) as string[],
      gradient: 'from-pink-500 to-rose-500',
      icon: 'Sparkles',
      available: false
    },
    {
      title: t('professionalWebsites.examples.barbershop.title'),
      category: t('professionalWebsites.examples.barbershop.category'),
      description: t('professionalWebsites.examples.barbershop.description'),
      features: t('professionalWebsites.examples.barbershop.features', { returnObjects: true }) as string[],
      gradient: 'from-gray-600 to-gray-800',
      icon: 'Scissors',
      available: false
    },
    {
      title: t('professionalWebsites.examples.architecture.title'),
      category: t('professionalWebsites.examples.architecture.category'),
      description: t('professionalWebsites.examples.architecture.description'),
      features: t('professionalWebsites.examples.architecture.features', { returnObjects: true }) as string[],
      gradient: 'from-green-600 to-emerald-600',
      icon: 'Ruler',
      available: false
    }
  ];

  const features = [
    {
      icon: Smartphone,
      title: t('professionalWebsites.features.responsive.title'),
      description: t('professionalWebsites.features.responsive.description')
    },
    {
      icon: Search,
      title: t('professionalWebsites.features.seo.title'),
      description: t('professionalWebsites.features.seo.description')
    },
    {
      icon: Zap,
      title: t('professionalWebsites.features.performance.title'),
      description: t('professionalWebsites.features.performance.description')
    },
    {
      icon: Shield,
      title: t('professionalWebsites.features.security.title'),
      description: t('professionalWebsites.features.security.description')
    },
    {
      icon: BarChart3,
      title: t('professionalWebsites.features.analytics.title'),
      description: t('professionalWebsites.features.analytics.description')
    },
    {
      icon: Globe,
      title: t('professionalWebsites.features.multilingual.title'),
      description: t('professionalWebsites.features.multilingual.description')
    }
  ];

  const process = [
    {
      step: '01',
      title: t('professionalWebsites.process.briefing.title'),
      description: t('professionalWebsites.process.briefing.description')
    },
    {
      step: '02',
      title: t('professionalWebsites.process.design.title'),
      description: t('professionalWebsites.process.design.description')
    },
    {
      step: '03',
      title: t('professionalWebsites.process.development.title'),
      description: t('professionalWebsites.process.development.description')
    },
    {
      step: '04',
      title: t('professionalWebsites.process.launch.title'),
      description: t('professionalWebsites.process.launch.description')
    }
  ];

  return (
    <div className="min-h-screen bg-background">
        <Header />
        
        {/* Hero Section */}
        <section className="relative pt-32 pb-20 lg:pt-40 lg:pb-32 overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-br from-accent/5 via-transparent to-primary/5" />
          
          <div className="container mx-auto px-4 lg:px-8 relative">
            <div className="max-w-4xl mx-auto text-center">
              <div className="inline-flex items-center px-4 py-2 rounded-full bg-accent/10 text-accent border border-accent/20 mb-8 animate-fade-in">
                <Rocket className="w-4 h-4 mr-2" />
                <span className="text-sm font-medium">{t('professionalWebsites.hero.badge')}</span>
              </div>
              
              <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold text-foreground mb-6 animate-fade-in animation-delay-100">
                {t('professionalWebsites.hero.title')}
              </h1>
              
              <p className="text-xl text-muted-foreground mb-10 animate-fade-in animation-delay-200">
                {t('professionalWebsites.hero.subtitle')}
              </p>
              
              <div className="flex flex-col sm:flex-row gap-4 justify-center animate-fade-in animation-delay-300">
                <button 
                  onClick={() => navigate(`/${lang}#contato`)}
                  className="btn-primary group"
                >
                  <span>{t('professionalWebsites.hero.ctaPrimary')}</span>
                  <ArrowRight className="ml-2 w-4 h-4 transition-transform group-hover:translate-x-1" />
                </button>
                
                <button 
                  onClick={() => document.getElementById('examples')?.scrollIntoView({ behavior: 'smooth' })}
                  className="btn-outline"
                >
                  {t('professionalWebsites.hero.ctaSecondary')}
                </button>
              </div>
            </div>
          </div>
        </section>

        {/* Examples Section */}
        <section id="examples" className="py-20 lg:py-32 bg-secondary/30">
          <div className="container mx-auto px-4 lg:px-8">
            <div className="text-center mb-16">
              <h2 className="text-heading text-foreground mb-6">
                {t('professionalWebsites.examples.title')}
              </h2>
              <p className="text-lg text-muted-foreground max-w-3xl mx-auto mb-4">
                {t('professionalWebsites.examples.subtitle')}
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              {examples.map((example, index) => {
                const IconComponent = example.icon === 'Calculator' ? Calculator :
                                     example.icon === 'Sparkles' ? Sparkles :
                                     example.icon === 'Scissors' ? Scissors :
                                     example.icon === 'Ruler' ? Ruler : Globe;
                
                return (
                  <div 
                    key={example.title}
                    className="group card p-0 overflow-hidden animate-fade-in relative"
                    style={{ animationDelay: `${index * 100}ms` }}
                  >
                    {/* Coming Soon Badge */}
                    {!example.available && (
                      <div className="absolute top-4 right-4 z-10">
                        <span className="px-3 py-1 bg-accent/90 text-accent-foreground text-xs font-medium rounded-full backdrop-blur-sm">
                          {t('professionalWebsites.examples.comingSoon')}
                        </span>
                      </div>
                    )}

                    {/* Preview Area */}
                    <div className={`h-48 bg-gradient-to-br ${example.gradient} relative overflow-hidden ${!example.available ? 'opacity-70' : ''}`}>
                      <div className="absolute inset-0 bg-black/10" />
                      <div className="absolute inset-0 flex items-center justify-center">
                        <IconComponent className="w-16 h-16 text-white/30" />
                      </div>
                      {!example.available && (
                        <div className="absolute inset-0 bg-black/20" />
                      )}
                    </div>

                    {/* Content */}
                    <div className="p-6">
                      <div className="text-sm text-accent font-medium mb-2">
                        {example.category}
                      </div>
                      <h3 className="text-xl font-semibold text-foreground mb-3">
                        {example.title}
                      </h3>
                      <p className="text-muted-foreground mb-4">
                        {example.description}
                      </p>

                      {/* Features */}
                      <div className="space-y-2">
                        {example.features.map((feature) => (
                          <div key={feature} className="flex items-center text-sm text-muted-foreground">
                            <CheckCircle2 className="w-4 h-4 text-accent mr-2 flex-shrink-0" />
                            <span>{feature}</span>
                          </div>
                        ))}
                      </div>

                      {/* Action Button */}
                      {example.available && (
                        <div className="mt-6 pt-4 border-t border-border">
                          <button 
                            onClick={() => navigate(`/${lang}#contato`)}
                            className="btn-outline w-full group/btn"
                          >
                            <span className="flex items-center justify-center">
                              {t('professionalWebsites.hero.ctaPrimary')}
                              <ArrowRight className="ml-2 w-4 h-4 transition-transform group-hover/btn:translate-x-1" />
                            </span>
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        {/* Features Section */}
        <section className="py-20 lg:py-32">
          <div className="container mx-auto px-4 lg:px-8">
            <div className="text-center mb-16">
              <h2 className="text-heading text-foreground mb-6">
                {t('professionalWebsites.features.title')}
              </h2>
              <p className="text-lg text-muted-foreground max-w-3xl mx-auto">
                {t('professionalWebsites.features.subtitle')}
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
              {features.map((feature, index) => (
                <div 
                  key={feature.title}
                  className="group animate-fade-in"
                  style={{ animationDelay: `${index * 100}ms` }}
                >
                  <div className="flex items-start space-x-4">
                    <div className="w-12 h-12 rounded-xl accent-gradient flex items-center justify-center flex-shrink-0 group-hover:scale-110 transition-transform">
                      <feature.icon className="w-6 h-6 text-accent-foreground" />
                    </div>
                    <div>
                      <h3 className="text-lg font-semibold text-foreground mb-2">
                        {feature.title}
                      </h3>
                      <p className="text-muted-foreground">
                        {feature.description}
                      </p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Process Section */}
        <section className="py-20 lg:py-32 bg-secondary/30">
          <div className="container mx-auto px-4 lg:px-8">
            <div className="text-center mb-16">
              <h2 className="text-heading text-foreground mb-6">
                {t('professionalWebsites.process.title')}
              </h2>
              <p className="text-lg text-muted-foreground max-w-3xl mx-auto">
                {t('professionalWebsites.process.subtitle')}
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
              {process.map((item, index) => (
                <div 
                  key={item.step}
                  className="relative animate-fade-in"
                  style={{ animationDelay: `${index * 100}ms` }}
                >
                  {/* Connection Line */}
                  {index < process.length - 1 && (
                    <div className="hidden lg:block absolute top-8 left-full w-full h-0.5 bg-border -z-10" />
                  )}

                  <div className="text-center lg:text-left">
                    <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-accent/10 text-accent border-2 border-accent/20 mb-4">
                      <span className="text-2xl font-bold">{item.step}</span>
                    </div>
                    <h3 className="text-lg font-semibold text-foreground mb-2">
                      {item.title}
                    </h3>
                    <p className="text-muted-foreground">
                      {item.description}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* CTA Section */}
        <section className="py-20 lg:py-32">
          <div className="container mx-auto px-4 lg:px-8">
            <div className="card p-12 text-center bg-gradient-to-br from-accent/10 via-transparent to-primary/10 border-accent/20">
              <h2 className="text-3xl md:text-4xl font-bold text-foreground mb-6">
                {t('professionalWebsites.cta.title')}
              </h2>
              <p className="text-lg text-muted-foreground mb-8 max-w-2xl mx-auto">
                {t('professionalWebsites.cta.subtitle')}
              </p>
              
              <div className="flex flex-col sm:flex-row gap-4 justify-center">
                <button 
                  onClick={() => navigate(`/${lang}#contato`)}
                  className="btn-primary group"
                >
                  <span>{t('professionalWebsites.cta.button')}</span>
                  <ArrowRight className="ml-2 w-4 h-4 transition-transform group-hover:translate-x-1" />
                </button>
                
                <button 
                  onClick={() => navigate(`/${lang}`)}
                  className="btn-outline"
                >
                  {t('professionalWebsites.cta.backButton')}
                </button>
              </div>
            </div>
          </div>
        </section>

        <Footer />
      </div>
  );
};

export default ProfessionalWebsites;