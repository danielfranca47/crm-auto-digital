import { useTranslation } from 'react-i18next';
import { useEffect } from 'react';

const SEOHead = () => {
  const { t, i18n } = useTranslation();

  useEffect(() => {
    // Update document title
    document.title = t('meta.title');
    
    // Update meta description
    const metaDescription = document.querySelector('meta[name="description"]');
    if (metaDescription) {
      metaDescription.setAttribute('content', t('meta.description'));
    }

    // Update Open Graph title
    const ogTitle = document.querySelector('meta[property="og:title"]');
    if (ogTitle) {
      ogTitle.setAttribute('content', t('meta.title'));
    }

    // Update Open Graph description
    const ogDescription = document.querySelector('meta[property="og:description"]');
    if (ogDescription) {
      ogDescription.setAttribute('content', t('meta.description'));
    }

    // Update canonical URL with language
    const canonical = document.querySelector('link[rel="canonical"]');
    if (canonical) {
      const baseUrl = 'https://digitalpro.com.br';
      const currentPath = window.location.pathname.replace(/^\/[a-z]{2}/, '') || '/';
      canonical.setAttribute('href', `${baseUrl}/${i18n.language}${currentPath}`);
    }

    // Add hreflang tags
    const existingHreflangs = document.querySelectorAll('link[rel="alternate"][hreflang]');
    existingHreflangs.forEach(el => el.remove());

    const languages = ['en', 'pt', 'es'];
    const baseUrl = 'https://digitalpro.com.br';
    const currentPath = window.location.pathname.replace(/^\/[a-z]{2}/, '') || '/';

    languages.forEach(lang => {
      const hreflangLink = document.createElement('link');
      hreflangLink.rel = 'alternate';
      hreflangLink.hreflang = lang;
      hreflangLink.href = `${baseUrl}/${lang}${currentPath}`;
      document.head.appendChild(hreflangLink);
    });

    // Add x-default hreflang
    const defaultHreflang = document.createElement('link');
    defaultHreflang.rel = 'alternate';
    defaultHreflang.hreflang = 'x-default';
    defaultHreflang.href = `${baseUrl}/en${currentPath}`;
    document.head.appendChild(defaultHreflang);

  }, [t, i18n.language]);

  return null;
};

export default SEOHead;