import { Clock, Users, TrendingUp, Shield } from 'lucide-react';
import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';

type BenefitTranslationItem = {
  key: keyof typeof iconMap;
  title: string;
  description: string;
};

type StatTranslationItem = {
  value: string;
  label: string;
};

const iconMap = {
  automation: Clock,
  service: Users,
  scalability: TrendingUp,
  security: Shield
};

const BenefitsSection = () => {
  const { t, i18n } = useTranslation();

  const benefits = useMemo(() => {
    const items = t('benefits.items', {
      returnObjects: true
    }) as BenefitTranslationItem[];

    return items.map((item) => ({
      ...item,
      icon: iconMap[item.key] ?? Clock
    }));
  }, [i18n.language, t]);

  const stats = t('benefits.stats.items', {
    returnObjects: true
  }) as StatTranslationItem[];

  return (
    <section id="benefits" className="py-20 lg:py-32">
      <div className="container mx-auto px-4 lg:px-8">
        {/* Section Header */}
        <div className="text-center mb-16">
          <div className="inline-flex items-center px-4 py-2 rounded-full bg-accent/10 text-accent border border-accent/20 mb-6">
            <span className="text-sm font-medium">{t('benefits.badge')}</span>
          </div>

          <h2 className="text-heading text-foreground mb-6">
            {t('benefits.title')}
          </h2>

          <p className="text-lg text-muted-foreground max-w-3xl mx-auto">
            {t('benefits.subtitle')}
          </p>
        </div>

        {/* Benefits Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-2 xl:grid-cols-4 gap-8">
          {benefits.map((benefit, index) => {
            const Icon = benefit.icon;
            return (
              <div
                key={benefit.title}
                className="text-center group animate-fade-in"
                style={{ animationDelay: `${index * 150}ms` }}
              >
                {/* Icon */}
                <div className="w-20 h-20 mx-auto rounded-full bg-accent/10 flex items-center justify-center mb-6 group-hover:bg-accent/20 transition-smooth">
                  <Icon className="w-10 h-10 text-accent" />
                </div>

                {/* Content */}
                <h3 className="text-lg font-semibold text-foreground mb-4 group-hover:text-accent transition-smooth">
                  {benefit.title}
                </h3>

                <p className="text-muted-foreground leading-relaxed">
                  {benefit.description}
                </p>
              </div>
            );
          })}
        </div>

        {/* Stats Section */}
        <div className="mt-20 bg-card rounded-3xl p-8 lg:p-12 shadow-card">
          <div className="text-center mb-12">
            <h3 className="text-subheading text-card-foreground mb-4">
              {t('benefits.stats.title')}
            </h3>
            <p className="text-muted-foreground">
              {t('benefits.stats.subtitle')}
            </p>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
            {stats.map((stat) => (
              <div key={stat.label} className="text-center">
                <div className="text-4xl lg:text-5xl font-bold text-accent mb-2">{stat.value}</div>
                <div className="text-sm text-muted-foreground">{stat.label}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
};

export default BenefitsSection;