import Header from '@/components/Header';
import Footer from '@/components/Footer';
import SchedulingSimulator from '@/components/SchedulingSimulator';
import ROICalculator from '@/components/ROICalculator';
import ComparisonTable from '@/components/ComparisonTable';
import { useTranslation } from 'react-i18next';
import { useParams, useNavigate } from 'react-router-dom';
import { useEffect } from 'react';
import {
  ArrowRight, 
  CheckCircle2, 
  Calendar, 
  Clock, 
  Bell,
  Users,
  BarChart3,
  MessageSquare,
  Star,
  ChevronRight
} from 'lucide-react';

const SchedulingDemo = () => {
  const { t } = useTranslation();
  const { lang } = useParams();
  const navigate = useNavigate();

  useEffect(() => {
    document.title = t('schedulingDemo.meta.title');
    
    const metaDescription = document.querySelector('meta[name="description"]');
    if (metaDescription) {
      metaDescription.setAttribute('content', t('schedulingDemo.meta.description'));
    }
  }, [t]);

  const benefits = [
    {
      icon: Calendar,
      title: t('schedulingDemo.benefits.availability.title'),
      description: t('schedulingDemo.benefits.availability.description')
    },
    {
      icon: Bell,
      title: t('schedulingDemo.benefits.reminders.title'),
      description: t('schedulingDemo.benefits.reminders.description')
    },
    {
      icon: BarChart3,
      title: t('schedulingDemo.benefits.analytics.title'),
      description: t('schedulingDemo.benefits.analytics.description')
    },
    {
      icon: Users,
      title: t('schedulingDemo.benefits.management.title'),
      description: t('schedulingDemo.benefits.management.description')
    }
  ];

  const features = [
    t('schedulingDemo.features.calendar'),
    t('schedulingDemo.features.whatsapp'),
    t('schedulingDemo.features.reminders'),
    t('schedulingDemo.features.analytics'),
    t('schedulingDemo.features.mobile'),
    t('schedulingDemo.features.integration')
  ];

  const testimonials = [
    {
      name: t('schedulingDemo.testimonials.barber.name'),
      business: t('schedulingDemo.testimonials.barber.business'),
      text: t('schedulingDemo.testimonials.barber.text'),
      rating: 5
    },
    {
      name: t('schedulingDemo.testimonials.dentist.name'),
      business: t('schedulingDemo.testimonials.dentist.business'),
      text: t('schedulingDemo.testimonials.dentist.text'),
      rating: 5
    },
    {
      name: t('schedulingDemo.testimonials.spa.name'),
      business: t('schedulingDemo.testimonials.spa.business'),
      text: t('schedulingDemo.testimonials.spa.text'),
      rating: 5
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
              <Calendar className="w-4 h-4 mr-2" />
              <span className="text-sm font-medium">{t('schedulingDemo.hero.badge')}</span>
            </div>
            
            <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold text-foreground mb-6 animate-fade-in animation-delay-100">
              {t('schedulingDemo.hero.title')}
            </h1>
            
            <p className="text-xl text-muted-foreground mb-10 animate-fade-in animation-delay-200">
              {t('schedulingDemo.hero.subtitle')}
            </p>
            
            <div className="flex flex-col sm:flex-row gap-4 justify-center animate-fade-in animation-delay-300">
              <button 
                onClick={() => document.getElementById('demo')?.scrollIntoView({ behavior: 'smooth' })}
                className="btn-primary group"
              >
                <span>{t('schedulingDemo.hero.ctaPrimary')}</span>
                <ArrowRight className="ml-2 w-4 h-4 transition-transform group-hover:translate-x-1" />
              </button>
              
              <button 
                onClick={() => navigate(`/${lang}#contato`)}
                className="btn-outline"
              >
                {t('schedulingDemo.hero.ctaSecondary')}
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* Benefits Section */}
      <section className="py-20 lg:py-32 bg-secondary/30">
        <div className="container mx-auto px-4 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-heading text-foreground mb-6">
              {t('schedulingDemo.benefits.title')}
            </h2>
            <p className="text-lg text-muted-foreground max-w-3xl mx-auto">
              {t('schedulingDemo.benefits.subtitle')}
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
            {benefits.map((benefit, index) => (
              <div 
                key={benefit.title}
                className="text-center animate-fade-in"
                style={{ animationDelay: `${index * 100}ms` }}
              >
                <div className="w-16 h-16 rounded-xl accent-gradient flex items-center justify-center mx-auto mb-6 hover:scale-110 transition-bounce">
                  <benefit.icon className="w-8 h-8 text-accent-foreground" />
                </div>
                <h3 className="text-lg font-semibold text-foreground mb-3">
                  {benefit.title}
                </h3>
                <p className="text-muted-foreground">
                  {benefit.description}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Interactive Demo Section */}
      <section id="demo" className="py-20 lg:py-32">
        <div className="container mx-auto px-4 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-heading text-foreground mb-6">
              {t('schedulingDemo.demo.title')}
            </h2>
            <p className="text-lg text-muted-foreground max-w-3xl mx-auto">
              {t('schedulingDemo.demo.subtitle')}
            </p>
          </div>

          <SchedulingSimulator />
        </div>
      </section>

      {/* ROI Calculator Section */}
      <ROICalculator />

      {/* Comparison Table Section */}
      <ComparisonTable />

      {/* Features Section */}
      <section className="py-20 lg:py-32 bg-secondary/30">
        <div className="container mx-auto px-4 lg:px-8">
          <div className="max-w-4xl mx-auto">
            <div className="text-center mb-16">
              <h2 className="text-heading text-foreground mb-6">
                {t('schedulingDemo.features.title')}
              </h2>
              <p className="text-lg text-muted-foreground">
                {t('schedulingDemo.features.subtitle')}
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {features.map((feature, index) => (
                <div 
                  key={feature}
                  className="flex items-center space-x-3 animate-fade-in"
                  style={{ animationDelay: `${index * 50}ms` }}
                >
                  <CheckCircle2 className="w-5 h-5 text-accent flex-shrink-0" />
                  <span className="text-foreground">{feature}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Testimonials Section */}
      <section className="py-20 lg:py-32">
        <div className="container mx-auto px-4 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-heading text-foreground mb-6">
              {t('schedulingDemo.testimonials.title')}
            </h2>
            <p className="text-lg text-muted-foreground max-w-3xl mx-auto">
              {t('schedulingDemo.testimonials.subtitle')}
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {testimonials.map((testimonial, index) => (
              <div 
                key={testimonial.name}
                className="card p-6 animate-fade-in"
                style={{ animationDelay: `${index * 100}ms` }}
              >
                <div className="flex items-center mb-4">
                  {[...Array(testimonial.rating)].map((_, i) => (
                    <Star key={i} className="w-4 h-4 text-accent fill-current" />
                  ))}
                </div>
                
                <p className="text-muted-foreground mb-6 italic">
                  "{testimonial.text}"
                </p>
                
                <div>
                  <div className="font-semibold text-foreground">
                    {testimonial.name}
                  </div>
                  <div className="text-sm text-accent">
                    {testimonial.business}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 lg:py-32 bg-secondary/30">
        <div className="container mx-auto px-4 lg:px-8">
          <div className="card p-12 text-center bg-gradient-to-br from-accent/10 via-transparent to-primary/10 border-accent/20">
            <h2 className="text-3xl md:text-4xl font-bold text-foreground mb-6">
              {t('schedulingDemo.cta.title')}
            </h2>
            <p className="text-lg text-muted-foreground mb-8 max-w-2xl mx-auto">
              {t('schedulingDemo.cta.subtitle')}
            </p>
            
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <button 
                onClick={() => navigate(`/${lang}#contato`)}
                className="btn-primary group"
              >
                <span>{t('schedulingDemo.cta.button')}</span>
                <ArrowRight className="ml-2 w-4 h-4 transition-transform group-hover:translate-x-1" />
              </button>
              
              <button 
                onClick={() => navigate(`/${lang}`)}
                className="btn-outline"
              >
                {t('schedulingDemo.cta.backButton')}
              </button>
            </div>
          </div>
        </div>
      </section>

      <Footer />
    </div>
  );
};

export default SchedulingDemo;