import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { Card } from '@/components/ui/card';
import {
  X,
  Check,
  Phone,
  Calendar,
  Bell,
  FileText,
  BarChart3,
  Clock
} from 'lucide-react';

const ComparisonTable = () => {
  const { t, i18n } = useTranslation();

  const comparisons = useMemo(
    () => [
      {
        icon: Phone,
        category: t('schedulingDemo.comparison.labels.scheduling'),
        manual: t('schedulingDemo.comparison.booking.manual'),
        automated: t('schedulingDemo.comparison.booking.automated')
      },
      {
        icon: Check,
        category: t('schedulingDemo.comparison.labels.confirmation'),
        manual: t('schedulingDemo.comparison.confirmation.manual'),
        automated: t('schedulingDemo.comparison.confirmation.automated')
      },
      {
        icon: Bell,
        category: t('schedulingDemo.comparison.labels.reminders'),
        manual: t('schedulingDemo.comparison.reminders.manual'),
        automated: t('schedulingDemo.comparison.reminders.automated')
      },
      {
        icon: Calendar,
        category: t('schedulingDemo.comparison.labels.calendar'),
        manual: t('schedulingDemo.comparison.calendar.manual'),
        automated: t('schedulingDemo.comparison.calendar.automated')
      },
      {
        icon: BarChart3,
        category: t('schedulingDemo.comparison.labels.reports'),
        manual: t('schedulingDemo.comparison.reports.manual'),
        automated: t('schedulingDemo.comparison.reports.automated')
      }
    ],
    [i18n.language, t]
  );

  return (
    <section className="py-20 lg:py-32 bg-secondary/30">
      <div className="container mx-auto px-4 lg:px-8">
        <div className="text-center mb-16">
          <h2 className="text-heading text-foreground mb-6">
            {t('schedulingDemo.comparison.title')}
          </h2>
          <p className="text-lg text-muted-foreground max-w-3xl mx-auto">
            {t('schedulingDemo.comparison.subtitle')}
          </p>
        </div>

        <div className="max-w-6xl mx-auto">
          <Card className="overflow-hidden">
            {/* Header */}
            <div className="grid grid-cols-3 bg-muted/50">
              <div className="p-6">
                <h3 className="text-lg font-semibold text-foreground">
                  {t('schedulingDemo.comparison.process')}
                </h3>
              </div>
              <div className="p-6 border-l border-border">
                <div className="flex items-center space-x-2">
                  <X className="w-5 h-5 text-destructive" />
                  <h3 className="text-lg font-semibold text-foreground">
                    {t('schedulingDemo.comparison.manual')}
                  </h3>
                </div>
              </div>
              <div className="p-6 border-l border-border">
                <div className="flex items-center space-x-2">
                  <Check className="w-5 h-5 text-green-500" />
                  <h3 className="text-lg font-semibold text-foreground">
                    {t('schedulingDemo.comparison.automated')}
                  </h3>
                </div>
              </div>
            </div>

            {/* Comparison Rows */}
            {comparisons.map((item, index) => (
              <div
                key={`${item.category}-${index}`}
                className={`grid grid-cols-3 animate-fade-in ${
                  index % 2 === 0 ? 'bg-background' : 'bg-muted/20'
                }`}
                style={{ animationDelay: `${index * 100}ms` }}
              >
                <div className="p-6 flex items-center space-x-3">
                  <div className="w-10 h-10 rounded-lg accent-gradient flex items-center justify-center">
                    <item.icon className="w-5 h-5 text-accent-foreground" />
                  </div>
                  <span className="font-medium text-foreground">{item.category}</span>
                </div>

                <div className="p-6 border-l border-border flex items-center space-x-3">
                  <div className="w-6 h-6 rounded-full bg-destructive/20 flex items-center justify-center flex-shrink-0">
                    <X className="w-4 h-4 text-destructive" />
                  </div>
                  <span className="text-muted-foreground">{item.manual}</span>
                </div>

                <div className="p-6 border-l border-border flex items-center space-x-3">
                  <div className="w-6 h-6 rounded-full bg-green-500/20 flex items-center justify-center flex-shrink-0">
                    <Check className="w-4 h-4 text-green-500" />
                  </div>
                  <span className="text-foreground">{item.automated}</span>
                </div>
              </div>
            ))}

            {/* Bottom Summary */}
            <div className="grid grid-cols-3 bg-gradient-to-r from-destructive/10 via-muted/50 to-green-500/10">
              <div className="p-6">
                <div className="flex items-center space-x-2">
                  <Clock className="w-5 h-5 text-accent" />
                  <span className="font-semibold text-foreground">
                    {t('schedulingDemo.comparison.timeSpent.title')}
                  </span>
                </div>
              </div>
              <div className="p-6 border-l border-border text-center">
                <div className="text-2xl font-bold text-destructive mb-1">
                  {t('schedulingDemo.comparison.timeSpent.manualValue')}
                </div>
                <p className="text-sm text-muted-foreground">
                  {t('schedulingDemo.comparison.timeSpent.manualNote')}
                </p>
              </div>
              <div className="p-6 border-l border-border text-center">
                <div className="text-2xl font-bold text-green-500 mb-1">
                  {t('schedulingDemo.comparison.timeSpent.automatedValue')}
                </div>
                <p className="text-sm text-muted-foreground">
                  {t('schedulingDemo.comparison.timeSpent.automatedNote')}
                </p>
              </div>
            </div>
          </Card>

          {/* Bottom Stats */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-8">
            <Card className="p-6 text-center">
              <div className="text-3xl font-bold text-accent mb-2">
                {t('schedulingDemo.comparison.bottomStats.kpi1Value')}
              </div>
              <p className="text-muted-foreground">
                {t('schedulingDemo.comparison.bottomStats.timeSaved')}
              </p>
            </Card>

            <Card className="p-6 text-center">
              <div className="text-3xl font-bold text-accent mb-2">
                {t('schedulingDemo.comparison.bottomStats.kpi2Value')}
              </div>
              <p className="text-muted-foreground">
                {t('schedulingDemo.comparison.bottomStats.noShows')}
              </p>
            </Card>

            <Card className="p-6 text-center">
              <div className="text-3xl font-bold text-accent mb-2">
                {t('schedulingDemo.comparison.bottomStats.kpi3Value')}
              </div>
              <p className="text-muted-foreground">
                {t('schedulingDemo.comparison.bottomStats.availability')}
              </p>
            </Card>
          </div>
        </div>
      </div>
    </section>
  );
};

export default ComparisonTable;
