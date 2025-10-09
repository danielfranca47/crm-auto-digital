import { ArrowRight, Play } from 'lucide-react';
import { useTranslation } from 'react-i18next';

const HeroSection = () => {
  const { t } = useTranslation();
  return (
    <section 
      id="home"  // 🔹 Adicionado para o menu âncora
      className="relative min-h-screen flex items-center justify-center overflow-hidden hero-gradient"
    >
      {/* Content */}
      <div className="relative z-10 container mx-auto px-4 lg:px-8 text-center">
        <div className="max-w-5xl mx-auto">
          {/* Badge */}
          <div className="inline-flex items-center px-4 py-2 rounded-full bg-accent/20 text-accent border border-accent/30 mb-8 animate-fade-in">
            <span className="text-sm font-medium">{t('hero.badge')}</span>
          </div>

          {/* Main Heading */}
          <h1 className="text-hero text-primary-foreground mb-6 animate-fade-in animate-delay-100">
            {t('hero.title')}
          </h1>

          {/* Subtitle */}
          <p className="text-xl lg:text-2xl text-primary-foreground/90 mb-12 max-w-3xl mx-auto animate-fade-in animate-delay-200">
            {t('hero.subtitle')}
          </p>

          {/* CTA Buttons */}
          <div className="flex flex-col sm:flex-row gap-4 justify-center animate-fade-in animate-delay-300">
            <button className="btn-hero inline-flex items-center justify-center group">
              <span>{t('hero.ctaPrimary')}</span>
              <ArrowRight className="ml-2 w-5 h-5 transition-smooth group-hover:translate-x-1" />
            </button>
            
            <button className="inline-flex items-center justify-center px-8 py-4 rounded-xl font-semibold text-primary-foreground border-2 border-primary-foreground/30 hover:border-primary-foreground/50 transition-smooth hover:bg-primary-foreground/10 group">
              <Play className="mr-2 w-5 h-5" />
              <span>{t('hero.ctaSecondary')}</span>
            </button>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8 mt-16 animate-fade-in animate-delay-400">
            <div className="text-center">
              <div className="text-3xl font-bold text-accent mb-2">200+</div>
              <div className="text-sm text-primary-foreground/80">{t('hero.stats.projects')}</div>
            </div>
            <div className="text-center">
              <div className="text-3xl font-bold text-accent mb-2">98%</div>
              <div className="text-sm text-primary-foreground/80">{t('hero.stats.satisfaction')}</div>
            </div>
            <div className="text-center">
              <div className="text-3xl font-bold text-accent mb-2">5+</div>
              <div className="text-sm text-primary-foreground/80">{t('hero.stats.experience')}</div>
            </div>
            <div className="text-center">
              <div className="text-3xl font-bold text-accent mb-2">24h</div>
              <div className="text-sm text-primary-foreground/80">{t('hero.stats.support')}</div>
            </div>
          </div>
        </div>
      </div>

      {/* Scroll Indicator */}
      <div className="absolute bottom-8 left-1/2 transform -translate-x-1/2 animate-bounce">
        <div className="w-6 h-10 border-2 border-primary-foreground/50 rounded-full flex justify-center">
          <div className="w-1 h-3 bg-accent rounded-full mt-2"></div>
        </div>
      </div>
    </section>
  );
};

export default HeroSection;
