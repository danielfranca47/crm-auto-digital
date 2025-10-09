import { LucideIcon } from 'lucide-react';
import { ArrowRight } from 'lucide-react';
import { useNavigate, useParams } from 'react-router-dom';

interface ProjectCardProps {
  title: string;
  description: string;
  buttonText: string;
  icon: LucideIcon;
  delay?: number;
  link?: string;
}

const ProjectCard = ({ title, description, buttonText, icon: Icon, delay = 0, link }: ProjectCardProps) => {
  const navigate = useNavigate();
  const { lang } = useParams();
  
  const handleClick = () => {
    if (link) {
      navigate(`/${lang}${link}`);
    }
  };
  return (
    <div 
      className="portfolio-card animate-fade-in group"
      style={{ animationDelay: `${delay}ms` }}
    >
      {/* Icon */}
      <div className="w-16 h-16 rounded-xl accent-gradient flex items-center justify-center mb-6 group-hover:scale-110 transition-bounce">
        <Icon className="w-8 h-8 text-accent-foreground" />
      </div>

      {/* Content */}
      <div className="flex-1">
        <h3 className="text-subheading text-card-foreground mb-4 transition-smooth">
          {title}
        </h3>
        
        <p className="text-muted-foreground mb-6 leading-relaxed">
          {description}
        </p>
      </div>

      {/* Button */}
      <button 
        onClick={handleClick}
        className="btn-outline w-full group/btn"
      >
        <span className="flex items-center justify-center">
          {buttonText}
          <ArrowRight className="ml-2 w-4 h-4 transition-smooth group-hover/btn:translate-x-1" />
        </span>
      </button>
    </div>
  );
};

export default ProjectCard;