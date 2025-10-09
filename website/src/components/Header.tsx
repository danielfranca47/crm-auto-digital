import { Menu, X } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import LanguageSwitcher from './LanguageSwitcher';

const Header = () => {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const { t } = useTranslation();

  const toggleMenu = () => setIsMenuOpen(!isMenuOpen);

  return (
    <header className="fixed top-0 left-0 right-0 z-50 bg-background/95 backdrop-blur-md border-b border-border shadow-sm">
      <div className="container mx-auto px-4 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <a href="#home" className="flex items-center">
            <div className="w-10 h-10 rounded-xl accent-gradient flex items-center justify-center mr-3">
              <div className="w-6 h-6 bg-primary rounded-sm"></div>
            </div>
            <span className="text-xl font-bold text-foreground">{t('header.logo')}</span>
          </a>

          {/* Desktop Navigation */}
          <nav className="hidden md:flex items-center space-x-8">
            <a href="#home" className="text-muted-foreground hover:text-foreground transition-smooth">
              {t('navigation.home')}
            </a>
            <a href="#projects" className="text-muted-foreground hover:text-foreground transition-smooth">
              {t('navigation.projects')}
            </a>
            <a href="#about" className="text-muted-foreground hover:text-foreground transition-smooth">
              {t('navigation.about')}
            </a>
            <a href="#benefits" className="text-muted-foreground hover:text-foreground transition-smooth">
              {t('navigation.benefits')}
            </a>
            <a href="#contact" className="text-muted-foreground hover:text-foreground transition-smooth">
              {t('navigation.contact')}
            </a>
            <LanguageSwitcher />
            {/* Request Quote -> link para #contact */}
            <a
              href="#contact"
              className="btn-primary inline-flex items-center justify-center"
              aria-label={t('navigation.requestQuote') as string}
            >
              {t('navigation.requestQuote')}
            </a>
          </nav>

          {/* Mobile Menu Button */}
          <button
            className="md:hidden p-2 text-muted-foreground hover:text-foreground transition-smooth"
            onClick={toggleMenu}
            aria-label={t('header.mobileMenuToggle') as string}
          >
            {isMenuOpen ? <X size={24} /> : <Menu size={24} />}
          </button>
        </div>

        {/* Mobile Navigation */}
        {isMenuOpen && (
          <div className="md:hidden py-4 border-t border-border bg-background animate-fade-in">
            <nav className="flex flex-col space-y-3">
              <a
                href="#home"
                className="text-muted-foreground hover:text-foreground transition-smooth py-2"
                onClick={toggleMenu}
              >
                {t('navigation.home')}
              </a>
              <a
                href="#projects"
                className="text-muted-foreground hover:text-foreground transition-smooth py-2"
                onClick={toggleMenu}
              >
                {t('navigation.projects')}
              </a>
              <a
                href="#about"
                className="text-muted-foreground hover:text-foreground transition-smooth py-2"
                onClick={toggleMenu}
              >
                {t('navigation.about')}
              </a>
              <a
                href="#benefits"
                className="text-muted-foreground hover:text-foreground transition-smooth py-2"
                onClick={toggleMenu}
              >
                {t('navigation.benefits')}
              </a>
              <a
                href="#contact"
                className="text-muted-foreground hover:text-foreground transition-smooth py-2"
                onClick={toggleMenu}
              >
                {t('navigation.contact')}
              </a>
              <div className="py-2">
                <LanguageSwitcher />
              </div>
              {/* Request Quote -> link para #contact */}
              <a
                href="#contact"
                className="btn-primary text-left mt-4 inline-flex items-center justify-center"
                onClick={toggleMenu}
                aria-label={t('navigation.requestQuote') as string}
              >
                {t('navigation.requestQuote')}
              </a>
            </nav>
          </div>
        )}
      </div>
    </header>
  );
};

export default Header;
