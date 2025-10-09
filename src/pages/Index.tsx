import Header from '@/components/Header';
import HeroSection from '@/components/HeroSection';
import ProjectsSection from '@/components/ProjectsSection';
import BenefitsSection from '@/components/BenefitsSection';
import TestimonialsSection from '@/components/TestimonialsSection';
import CtaSection from '@/components/CtaSection';
import Footer from '@/components/Footer';
import { useTranslation } from 'react-i18next';

const Index = () => {
  const { t } = useTranslation();
  return (
    <div className="min-h-screen bg-background">
      <Header />
      <main>
        <HeroSection />
        <section id="about" className="py-20 lg:py-32">
          <div className="container mx-auto px-4 lg:px-8 text-center">
            <div className="max-w-4xl mx-auto">
              <div className="inline-flex items-center px-4 py-2 rounded-full bg-accent/10 text-accent border border-accent/20 mb-8">
                <span className="text-sm font-medium">{t('about.badge')}</span>
              </div>
              
              <h2 className="text-heading text-foreground mb-8">
                {t('about.title')}
              </h2>
              
              <p className="text-lg text-muted-foreground leading-relaxed mb-8">
                {t('about.description1')}
              </p>

              <p className="text-muted-foreground leading-relaxed">
                {t('about.description2')}
              </p>
            </div>
          </div>
        </section>
        <ProjectsSection />
        <BenefitsSection />
        <TestimonialsSection />
        <CtaSection />
      </main>
      <Footer />
    </div>
  );
};

export default Index;