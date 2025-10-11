import { ArrowRight, Phone, Mail, MessageCircle, Calendar } from 'lucide-react';
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

type QuickAction = {
  key: string;
  icon: keyof typeof iconMap;
  label: string;
};

type Guarantee = {
  title: string;
  description: string;
};

const iconMap = {
  calendar: Calendar,
  messageCircle: MessageCircle,
  phone: Phone,
  mail: Mail
};

const CtaSection = () => {
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    phone: '',
    message: ''
  });
  const [formStatus, setFormStatus] = useState<{
    type: 'idle' | 'success' | 'error';
    message?: string;
  }>({ type: 'idle' });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [honeypot, setHoneypot] = useState('');
  const { t, i18n } = useTranslation();

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (honeypot.trim().length > 0) {
      return;
    }

    setIsSubmitting(true);
    setFormStatus({ type: 'idle' });

    const apiBaseUrl = import.meta.env.VITE_API_BASE_URL;
    const formToken = import.meta.env.VITE_FORM_TOKEN;

    if (!apiBaseUrl || !formToken) {
      console.error('Missing API configuration for lead submission');
      setFormStatus({
        type: 'error',
        message: t('cta.form.errorMessage', 'Ocorreu um erro ao enviar o formulário. Tente novamente mais tarde.')
      });
      setIsSubmitting(false);
      return;
    }

    try {
      await new Promise((resolve) => setTimeout(resolve, 400));

      const utmParams = new URLSearchParams(window.location.search);
      const utmPayload: Record<string, string | undefined> = {
        utm_source: utmParams.get('utm_source') || undefined,
        utm_medium: utmParams.get('utm_medium') || undefined,
        utm_campaign: utmParams.get('utm_campaign') || undefined,
        utm_term: utmParams.get('utm_term') || undefined,
        utm_content: utmParams.get('utm_content') || undefined
      };

      const response = await fetch(`${apiBaseUrl}/public/leads`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-form-token': formToken
        },
        body: JSON.stringify({
          fullName: formData.name,
          email: formData.email,
          phone: formData.phone,
          message: formData.message,
          ...utmPayload
        })
      });

      if (!response.ok) {
        throw new Error('Failed to submit form');
      }

      setFormStatus({
        type: 'success',
        message: t('cta.form.successMessage', 'Obrigado! Recebemos o seu contato e retornaremos em breve.')
      });
      setFormData({ name: '', email: '', phone: '', message: '' });
    } catch (error) {
      console.error('Error submitting lead form', error);
      setFormStatus({
        type: 'error',
        message: t('cta.form.errorMessage', 'Ocorreu um erro ao enviar o formulário. Tente novamente mais tarde.')
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const quickActions = useMemo(
    () => t('cta.quickActions.items', { returnObjects: true }) as QuickAction[],
    [i18n.language, t]
  );

  const guarantee = t('cta.guarantee', { returnObjects: true }) as Guarantee;
  const responseTime = t('cta.responseTime', { returnObjects: true }) as Guarantee;

  return (
    <section id="contact" className="py-20 lg:py-32 hero-gradient">
      <div className="container mx-auto px-4 lg:px-8">
        <div className="max-w-6xl mx-auto">
          {/* Header */}
          <div className="text-center mb-16">
            <div className="inline-flex items-center px-4 py-2 rounded-full bg-accent/20 text-accent border border-accent/30 mb-6">
              <span className="text-sm font-medium">{t('cta.badge')}</span>
            </div>

            <h2 className="text-heading text-primary-foreground mb-6">
              {t('cta.title')}
            </h2>

            <p className="text-xl text-primary-foreground/90 max-w-3xl mx-auto">
              {t('cta.subtitle')}
            </p>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-start">
            {/* Contact Form */}
            <div className="bg-background/95 backdrop-blur-sm rounded-3xl p-8 lg:p-10 shadow-hero">
              <h3 className="text-subheading text-foreground mb-6">
                {t('cta.form.title')}
              </h3>

              <form onSubmit={handleSubmit} className="space-y-6">
                <div className="hidden" aria-hidden>
                  <label htmlFor="company">Company</label>
                  <input
                    id="company"
                    name="company"
                    type="text"
                    tabIndex={-1}
                    autoComplete="off"
                    value={honeypot}
                    onChange={(event) => setHoneypot(event.target.value)}
                  />
                </div>
                <div>
                  <label htmlFor="name" className="block text-sm font-medium text-foreground mb-2">
                    {t('cta.form.fields.name.label')}
                  </label>
                  <input
                    type="text"
                    id="name"
                    name="name"
                    value={formData.name}
                    onChange={handleInputChange}
                    required
                    className="w-full px-4 py-3 rounded-xl border border-input bg-background text-foreground focus:ring-2 focus:ring-accent focus:border-transparent transition-smooth"
                    placeholder={t('cta.form.fields.name.placeholder')}
                  />
                </div>

                <div>
                  <label htmlFor="email" className="block text-sm font-medium text-foreground mb-2">
                    {t('cta.form.fields.email.label')}
                  </label>
                  <input
                    type="email"
                    id="email"
                    name="email"
                    value={formData.email}
                    onChange={handleInputChange}
                    required
                    className="w-full px-4 py-3 rounded-xl border border-input bg-background text-foreground focus:ring-2 focus:ring-accent focus:border-transparent transition-smooth"
                    placeholder={t('cta.form.fields.email.placeholder')}
                  />
                </div>

                <div>
                  <label htmlFor="phone" className="block text-sm font-medium text-foreground mb-2">
                    {t('cta.form.fields.phone.label')}
                  </label>
                  <input
                    type="tel"
                    id="phone"
                    name="phone"
                    value={formData.phone}
                    onChange={handleInputChange}
                    required
                    className="w-full px-4 py-3 rounded-xl border border-input bg-background text-foreground focus:ring-2 focus:ring-accent focus:border-transparent transition-smooth"
                    placeholder={t('cta.form.fields.phone.placeholder')}
                  />
                </div>

                <div>
                  <label htmlFor="message" className="block text-sm font-medium text-foreground mb-2">
                    {t('cta.form.fields.message.label')}
                  </label>
                  <textarea
                    id="message"
                    name="message"
                    value={formData.message}
                    onChange={handleInputChange}
                    rows={4}
                    className="w-full px-4 py-3 rounded-xl border border-input bg-background text-foreground focus:ring-2 focus:ring-accent focus:border-transparent transition-smooth"
                    placeholder={t('cta.form.fields.message.placeholder')}
                  />
                </div>

                {formStatus.type !== 'idle' && formStatus.message && (
                  <p
                    className={
                      formStatus.type === 'success'
                        ? 'text-sm font-medium text-green-600'
                        : 'text-sm font-medium text-red-500'
                    }
                  >
                    {formStatus.message}
                  </p>
                )}

                <button type="submit" className="btn-hero w-full" disabled={isSubmitting}>
                  <span className="flex items-center justify-center">
                    {isSubmitting ? t('cta.form.sending', 'Enviando...') : t('cta.form.button')}
                    <ArrowRight className="ml-2 w-5 h-5" />
                  </span>
                </button>
              </form>
            </div>

            {/* Contact Info */}
            <div className="space-y-8">
              {/* Quick Actions */}
              <div className="space-y-4">
                <h3 className="text-subheading text-primary-foreground mb-6">
                  {t('cta.quickActions.title')}
                </h3>

                <div className="space-y-3">
                  {quickActions.map((action) => {
                    const Icon = iconMap[action.icon] ?? Calendar;

                    return (
                      <button
                        key={action.key}
                        className="w-full flex items-center justify-between bg-primary-foreground/10 backdrop-blur-sm border border-primary-foreground/20 rounded-xl p-4 text-primary-foreground hover:bg-primary-foreground/20 transition-smooth group"
                      >
                        <div className="flex items-center">
                          <Icon className="w-5 h-5 mr-3 text-accent" />
                          <span>{action.label}</span>
                        </div>
                        <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-smooth" />
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Guarantee */}
              <div className="bg-primary-foreground/10 backdrop-blur-sm rounded-2xl p-6 border border-primary-foreground/20">
                <h4 className="text-lg font-semibold text-primary-foreground mb-3">
                  {guarantee.title}
                </h4>
                <p className="text-primary-foreground/90 text-sm leading-relaxed">
                  {guarantee.description}
                </p>
              </div>

              {/* Response Time */}
              <div className="bg-accent/10 backdrop-blur-sm rounded-2xl p-6 border border-accent/30">
                <h4 className="text-lg font-semibold text-accent mb-3">
                  {responseTime.title}
                </h4>
                <p className="text-primary-foreground/90 text-sm leading-relaxed">
                  {responseTime.description}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};

export default CtaSection;