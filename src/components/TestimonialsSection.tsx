import { Fragment, useMemo } from 'react';
import { Star, Quote } from 'lucide-react';
import { useTranslation } from 'react-i18next';

type TestimonialItem = {
  name: string;
  role: string;
  content: string;
  rating: number;
  avatar: string;
};

type StatItem = {
  value: string;
  label: string;
};

const TestimonialsSection = () => {
  const { t, i18n } = useTranslation();

  const testimonials = useMemo(
    () => t('testimonials.items', { returnObjects: true }) as TestimonialItem[],
    [i18n.language, t]
  );

  const stats = useMemo(
    () => t('testimonials.stats', { returnObjects: true }) as StatItem[],
    [i18n.language, t]
  );

  return (
    <section className="py-20 lg:py-32 bg-muted/30">
      <div className="container mx-auto px-4 lg:px-8">
        {/* Section Header */}
        <div className="text-center mb-16">
          <div className="inline-flex items-center px-4 py-2 rounded-full bg-accent/10 text-accent border border-accent/20 mb-6">
            <span className="text-sm font-medium">{t('testimonials.badge')}</span>
          </div>

          <h2 className="text-heading text-foreground mb-6">
            {t('testimonials.title')}
          </h2>

          <p className="text-lg text-muted-foreground max-w-3xl mx-auto">
            {t('testimonials.subtitle')}
          </p>
        </div>

        {/* Testimonials Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          {testimonials.map((testimonial, index) => (
            <div
              key={testimonial.name}
              className="bg-card rounded-2xl p-8 shadow-card hover:shadow-card-hover transition-smooth animate-fade-in group"
              style={{ animationDelay: `${index * 150}ms` }}
            >
              {/* Quote Icon */}
              <div className="w-12 h-12 rounded-full bg-accent/10 flex items-center justify-center mb-6 group-hover:bg-accent/20 transition-smooth">
                <Quote className="w-6 h-6 text-accent" />
              </div>

              {/* Rating */}
              <div className="flex items-center mb-4">
                {Array.from({ length: testimonial.rating || 0 }).map((_, i) => (
                  <Star key={i} className="w-4 h-4 text-accent fill-current" />
                ))}
              </div>

              {/* Content */}
              <p className="text-card-foreground mb-6 italic leading-relaxed">
                "{testimonial.content}"
              </p>

              {/* Author */}
              <div className="flex items-center">
                <div className="w-12 h-12 rounded-full bg-accent text-accent-foreground flex items-center justify-center font-semibold mr-4">
                  {testimonial.avatar}
                </div>
                <div>
                  <div className="font-semibold text-card-foreground">{testimonial.name}</div>
                  <div className="text-sm text-muted-foreground">{testimonial.role}</div>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Bottom Stats */}
        <div className="mt-16 text-center">
          <div className="inline-flex items-center space-x-8 bg-card rounded-2xl px-8 py-6 shadow-card">
            {stats.map((stat, index) => (
              <Fragment key={stat.label}>
                <div className="text-center">
                  <div className="text-2xl font-bold text-accent">{stat.value}</div>
                  <div className="text-sm text-muted-foreground">{stat.label}</div>
                </div>
                {index < stats.length - 1 && <div className="w-px h-12 bg-border" />}
              </Fragment>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
};

export default TestimonialsSection;