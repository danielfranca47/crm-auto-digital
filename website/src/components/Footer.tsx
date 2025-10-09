import {
  Facebook,
  Instagram,
  Linkedin,
  Twitter,
  Mail,
  Phone,
  MapPin,
  Clock,
  ArrowUp
} from 'lucide-react';
import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';

type NavItem = {
  label: string;
  href: string;
};

type ContactItem = {
  key: string;
  icon: keyof typeof contactIconMap;
  value: string;
};

type SocialItem = {
  key: string;
  icon: keyof typeof socialIconMap;
  aria: string;
  href: string;
};

const contactIconMap = {
  phone: Phone,
  mail: Mail,
  mapPin: MapPin,
  clock: Clock
};

const socialIconMap = {
  facebook: Facebook,
  instagram: Instagram,
  linkedin: Linkedin,
  twitter: Twitter
};

const Footer = () => {
  const { t, i18n } = useTranslation();

  const scrollToTop = () => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const services = useMemo(
    () => t('footer.services.items', { returnObjects: true }) as NavItem[],
    [i18n.language, t]
  );

  const companyLinks = useMemo(
    () => t('footer.company.items', { returnObjects: true }) as NavItem[],
    [i18n.language, t]
  );

  const contactItems = useMemo(
    () => t('footer.contact.items', { returnObjects: true }) as ContactItem[],
    [i18n.language, t]
  );

  const socialItems = useMemo(
    () => t('footer.social.items', { returnObjects: true }) as SocialItem[],
    [i18n.language, t]
  );

  return (
    <footer className="bg-primary text-primary-foreground">
      {/* Main Footer */}
      <div className="container mx-auto px-4 lg:px-8 py-16">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
          {/* Company Info */}
          <div className="lg:col-span-2">
            <div className="flex items-center mb-6">
              <div className="w-10 h-10 rounded-xl accent-gradient flex items-center justify-center mr-3">
                <div className="w-6 h-6 bg-primary rounded-sm"></div>
              </div>
              <span className="text-2xl font-bold">{t('footer.brand.name')}</span>
            </div>

            <p className="text-primary-foreground/80 mb-6 max-w-md leading-relaxed">
              {t('footer.brand.description')}
            </p>

            {/* Contact Info */}
            <div className="space-y-3">
              {contactItems.map((item) => {
                const Icon = contactIconMap[item.icon] ?? Phone;

                return (
                  <div key={item.key} className="flex items-center">
                    <Icon className="w-4 h-4 mr-3 text-accent" />
                    <span className="text-sm">{item.value}</span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Services */}
          <div>
            <h4 className="text-lg font-semibold mb-6">{t('footer.services.title')}</h4>
            <ul className="space-y-3">
              {services.map((service) => (
                <li key={service.label}>
                  <a href={service.href} className="text-primary-foreground/80 hover:text-accent transition-smooth text-sm">
                    {service.label}
                  </a>
                </li>
              ))}
            </ul>
          </div>

          {/* Company */}
          <div>
            <h4 className="text-lg font-semibold mb-6">{t('footer.company.title')}</h4>
            <ul className="space-y-3">
              {companyLinks.map((link) => (
                <li key={link.label}>
                  <a href={link.href} className="text-primary-foreground/80 hover:text-accent transition-smooth text-sm">
                    {link.label}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Social Media & Newsletter */}
        <div className="mt-12 pt-8 border-t border-primary-foreground/20">
          <div className="flex flex-col lg:flex-row justify-between items-center">
            {/* Social Media */}
            <div className="flex items-center space-x-6 mb-6 lg:mb-0">
              <span className="text-sm font-medium">{t('footer.social.label')}</span>
              <div className="flex space-x-4">
                {socialItems.map((item) => {
                  const Icon = socialIconMap[item.icon] ?? Facebook;

                  return (
                    <a
                      key={item.key}
                      href={item.href}
                      className="w-10 h-10 rounded-full bg-primary-foreground/10 hover:bg-accent hover:text-accent-foreground flex items-center justify-center transition-smooth"
                      aria-label={item.aria}
                    >
                      <Icon className="w-4 h-4" />
                    </a>
                  );
                })}
              </div>
            </div>

            {/* Newsletter */}
            <div className="flex items-center space-x-4">
              <span className="text-sm font-medium">{t('footer.newsletter.label')}</span>
              <div className="flex">
                <input
                  type="email"
                  placeholder={t('footer.newsletter.placeholder')}
                  className="px-4 py-2 rounded-l-lg bg-primary-foreground/10 border border-primary-foreground/20 text-primary-foreground placeholder-primary-foreground/60 focus:outline-none focus:ring-2 focus:ring-accent"
                />
                <button className="px-4 py-2 bg-accent text-accent-foreground rounded-r-lg hover:bg-accent/90 transition-smooth font-medium">
                  {t('footer.newsletter.button')}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Bottom Footer */}
      <div className="border-t border-primary-foreground/20 py-6">
        <div className="container mx-auto px-4 lg:px-8">
          <div className="flex flex-col md:flex-row justify-between items-center">
            <div className="text-sm text-primary-foreground/60 mb-4 md:mb-0">
              {t('footer.copyright')}
            </div>

            <div className="flex items-center space-x-6">
              <a href="#" className="text-sm text-primary-foreground/60 hover:text-accent transition-smooth">
                {t('footer.legal.privacy')}
              </a>
              <a href="#" className="text-sm text-primary-foreground/60 hover:text-accent transition-smooth">
                {t('footer.legal.terms')}
              </a>
              <button
                onClick={scrollToTop}
                className="w-8 h-8 rounded-full bg-accent text-accent-foreground flex items-center justify-center hover:scale-110 transition-bounce"
                aria-label={t('footer.legal.backToTop')}
              >
                <ArrowUp className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </footer>
  );
};

export default Footer;