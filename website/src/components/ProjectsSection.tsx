import ProjectCard from './ProjectCard';
import {
  Globe,
  Calendar,
  MessageCircle,
  Users,
  PenTool,
  MessageSquare,
  ArrowRight
} from 'lucide-react';
import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';

const iconMap = {
  professionalWebsites: Globe,
  schedulingSystems: Calendar,
  aiWhatsappAutomation: MessageCircle,
  digitalAutoCrm: Users,
  automaticContentCreation: PenTool,
  personalizedAutomations: MessageSquare
};

type ProjectTranslationItem = {
  key: keyof typeof iconMap;
  title: string;
  description: string;
  button: string;
  link?: string;
};

const ProjectsSection = () => {
  const { t, i18n } = useTranslation();

  const projects = useMemo(() => {
    const items = t('projects.items', {
      returnObjects: true
    }) as ProjectTranslationItem[];

    return items.map((item) => ({
      ...item,
      icon: iconMap[item.key] ?? Globe
    }));
  }, [i18n.language, t]);

  return (
    <section id="projects" className="py-20 lg:py-32 bg-secondary/30">
      <div className="container mx-auto px-4 lg:px-8">
        {/* Section Header */}
        <div className="text-center mb-16">
          <div className="inline-flex items-center px-4 py-2 rounded-full bg-accent/10 text-accent border border-accent/20 mb-6">
            <span className="text-sm font-medium">{t('projects.badge')}</span>
          </div>

          <h2 className="text-heading text-foreground mb-6">
            {t('projects.title')}
          </h2>

          <p className="text-lg text-muted-foreground max-w-3xl mx-auto">
            {t('projects.description')}
          </p>
        </div>

        {/* Projects Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          {projects.map((project, index) => (
            <ProjectCard
              key={project.key}
              title={project.title}
              description={project.description}
              buttonText={project.button}
              icon={project.icon}
              link={project.link}
              delay={index * 100}
            />
          ))}
        </div>

        {/* Bottom CTA */}
        <div className="text-center mt-16">
          <p className="text-muted-foreground mb-6">
            {t('projects.bottomNote')}
          </p>
          <button className="btn-primary inline-flex items-center">
            <span>{t('projects.bottomButton')}</span>
            <ArrowRight className="ml-2 w-4 h-4" />
          </button>
        </div>
      </div>
    </section>
  );
};

export default ProjectsSection;