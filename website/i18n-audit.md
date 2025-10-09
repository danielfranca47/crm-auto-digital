# i18n Audit

## Files Updated
- `src/main.tsx`: wrapped the app with `I18nextProvider` to keep the active locale across internal routes.
- `src/components/LanguageSwitcher.tsx`: moved language options to i18n, added accessibility labels, ensured language persistence.
- `src/components/Header.tsx`: localized logo label and mobile menu toggle aria label.
- `src/components/ProjectsSection.tsx`: replaced inline data with translations and memoized project list per locale.
- `src/components/BenefitsSection.tsx`: localized benefits grid, stats copy, and values driven by i18n resources.
- `src/components/CtaSection.tsx`: extracted form labels, placeholders, quick actions, guarantees, and CTA copy to `cta.*`.
- `src/components/TestimonialsSection.tsx`: consumes translated badge, title, description, testimonial cards, and stats counters.
- `src/components/Footer.tsx`: rewired brand copy, contact data, navigation links, newsletter, and legal text to locale files.
- `src/i18n/locales/{en,pt,es}.json`: synced new `cta`, `testimonials`, `footer`, and supporting keys with current UI copy.

## Hardcoded Strings Removed
- `src/components/LanguageSwitcher.tsx`: Removed inline language names/flags array and button labels.
- `src/components/Header.tsx`: Removed hardcoded "DigitalPro" logo text and "Toggle menu" aria label.
- `src/components/ProjectsSection.tsx`: Removed section badge, title, description, CTA copy, and card content literals.
- `src/components/BenefitsSection.tsx`: Removed benefits badge, headings, descriptions, and stats literals.
- `src/components/CtaSection.tsx`: Removed badge text, hero copy, form field labels/placeholders, quick action button text, guarantees, and response-time messaging.
- `src/components/TestimonialsSection.tsx`: Removed badge text, section heading/subtitle, testimonial quotes, author roles, and KPI counters.
- `src/components/Footer.tsx`: Removed brand description, contact information, services/company link labels, social aria labels, newsletter copy, and copyright/legal text.

## New Translation Keys
- `languageSwitcher.ariaLabel` – used in `LanguageSwitcher` trigger button.
- `languageSwitcher.changeTo` – used for language option aria labels.
- `languageSwitcher.languages[]` – provides language metadata for the switcher menu.
- `header.logo` – used for the brand text in the header.
- `header.mobileMenuToggle` – used for the mobile toggle button aria label.
- `projects.badge`, `projects.title`, `projects.description`, `projects.bottomNote`, `projects.bottomButton` – used in `ProjectsSection` header and footer copy.
- `projects.items` – array consumed by `ProjectsSection` to render category cards (keys: `professionalWebsites`, `schedulingSystems`, `aiWhatsappAutomation`, `digitalAutoCrm`, `automaticContentCreation`, `personalizedAutomations`).
- `benefits.badge`, `benefits.title`, `benefits.subtitle` – used in `BenefitsSection` header copy.
- `benefits.items` – array providing benefit cards (keys: `automation`, `service`, `scalability`, `security`).
- `benefits.stats.title`, `benefits.stats.subtitle`, `benefits.stats.items` – used to render the metrics tiles in `BenefitsSection`.
- `cta.badge`, `cta.title`, `cta.subtitle`, `cta.form.fields.*`, `cta.form.button`, `cta.quickActions.*`, `cta.guarantee`, `cta.responseTime` – used throughout `CtaSection`.
- `testimonials.badge`, `testimonials.title`, `testimonials.subtitle`, `testimonials.items`, `testimonials.stats` – used in `TestimonialsSection`.
- `footer.brand`, `footer.services.items`, `footer.company.items`, `footer.contact.items`, `footer.social`, `footer.newsletter`, `footer.legal`, `footer.copyright` – used in `Footer` component.

## Remaining Hardcoded Strings
- Several secondary pages (`src/pages/*`) and components (e.g., scheduling/ROI flows) still contain hardcoded literals; they should be audited and migrated to the locale files in upcoming passes.
