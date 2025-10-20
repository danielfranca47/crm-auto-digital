import Header from '@/components/Header';
import Footer from '@/components/Footer';
import { useTranslation } from 'react-i18next';

const ComingSoon = () => {
  const { t, i18n } = useTranslation();

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col">
      <Header />
      <main className="flex-1 flex items-center py-20">
        <div className="container mx-auto px-4 lg:px-8">
          <div className="max-w-3xl mx-auto text-center">
            <div className="inline-flex items-center px-4 py-2 rounded-full bg-accent/10 text-accent border border-accent/20 mb-6">
              <span className="text-sm font-medium">{t('comingSoon.badge')}</span>
            </div>

            <h1 className="text-4xl lg:text-5xl font-bold mb-6">
              {t('comingSoon.title')}
            </h1>

            <p className="text-lg text-muted-foreground leading-relaxed mb-10">
              {t('comingSoon.description')}
            </p>

            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <a href={`/${i18n.language}`} className="btn-primary">
                {t('comingSoon.ctaPrimary')}
              </a>
              <a href={`/${i18n.language}#contact`} className="btn-outline">
                {t('comingSoon.ctaSecondary')}
              </a>
            </div>
          </div>
        </div>
      </main>
      <Footer />
    </div>
  );
};

export default ComingSoon;
