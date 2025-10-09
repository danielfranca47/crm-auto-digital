import { useMemo } from 'react';
import { Globe } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Button } from '@/components/ui/button';

type LanguageOption = {
  code: string;
  name: string;
  flag: string;
};

const LanguageSwitcher = () => {
  const { i18n, t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();

  const languages = useMemo(
    () => t('languageSwitcher.languages', { returnObjects: true }) as LanguageOption[],
    [i18n.language, t]
  );

  const currentLanguage =
    languages?.find((lang) => lang.code === i18n.language) || languages?.[0];

  const handleLanguageChange = (langCode: string) => {
    // Extract current path without language prefix
    const pathWithoutLang = location.pathname.replace(/^\/[a-z]{2}/, '') || '/';

    // Navigate to new language path
    const newPath = `/${langCode}${pathWithoutLang}`;
    navigate(newPath);

    // Change i18n language
    i18n.changeLanguage(langCode);
    localStorage.setItem('i18nextLng', langCode);
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          className="gap-2"
          aria-label={t('languageSwitcher.ariaLabel')}
        >
          <Globe className="w-4 h-4" aria-hidden="true" />
          <span className="hidden sm:inline">
            {currentLanguage?.flag} {currentLanguage?.name}
          </span>
          <span className="sm:hidden">{currentLanguage?.flag}</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        {languages?.map((language) => (
          <DropdownMenuItem
            key={language.code}
            onClick={() => handleLanguageChange(language.code)}
            className={i18n.language === language.code ? 'bg-accent' : ''}
            aria-label={t('languageSwitcher.changeTo', { language: language.name })}
          >
            <span className="mr-2">{language.flag}</span>
            {language.name}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
};

export default LanguageSwitcher;