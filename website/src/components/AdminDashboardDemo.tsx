import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { 
  Calendar, 
  Users, 
  TrendingUp, 
  Clock, 
  Bell,
  CheckCircle,
  AlertCircle,
  DollarSign,
  BarChart3,
  Phone,
  MessageSquare,
  Star
} from 'lucide-react';
import type { BookingFormData } from './SchedulingSimulator';

interface AdminDashboardDemoProps {
  isActive: boolean;
  newBooking: BookingFormData | null;
}

const AdminDashboardDemo = ({ isActive, newBooking }: AdminDashboardDemoProps) => {
  const { t } = useTranslation();
  const [showNotification, setShowNotification] = useState(false);
  const [bookings, setBookings] = useState([
    {
      id: 1,
      customer: 'João Silva',
      service: t('schedulingDemo.services.haircut'),
      time: '09:00',
      status: 'confirmed',
      phone: '(11) 99999-1111'
    },
    {
      id: 2,
      customer: 'Maria Santos',
      service: t('schedulingDemo.services.beard'),
      time: '10:30',
      status: 'pending',
      phone: '(11) 99999-2222'
    },
    {
      id: 3,
      customer: 'Carlos Lima',
      service: t('schedulingDemo.services.combo'),
      time: '14:00',
      status: 'completed',
      phone: '(11) 99999-3333'
    }
  ]);

  const serviceNames: { [key: string]: string } = {
    haircut: t('schedulingDemo.services.haircut'),
    beard: t('schedulingDemo.services.beard'),
    combo: t('schedulingDemo.services.combo'),
    facial: t('schedulingDemo.services.facial'),
  };

  useEffect(() => {
    if (newBooking && isActive) {
      setShowNotification(true);
      
      // Add new booking to the list
      const newBookingItem = {
        id: bookings.length + 1,
        customer: newBooking.name,
        service: serviceNames[newBooking.service] || newBooking.service,
        time: newBooking.time,
        status: 'confirmed' as const,
        phone: newBooking.phone
      };
      
      setBookings(prev => [newBookingItem, ...prev]);

      // Hide notification after 5 seconds
      setTimeout(() => {
        setShowNotification(false);
      }, 5000);
    }
  }, [newBooking, isActive]);

  if (!isActive) {
    return (
      <Card className="p-8 text-center bg-gradient-to-br from-accent/10 via-transparent to-primary/10 border-accent/20">
        <div className="w-20 h-20 rounded-full bg-accent/20 flex items-center justify-center mx-auto mb-6">
          <BarChart3 className="w-10 h-10 text-accent" />
        </div>
        <h3 className="text-xl font-semibold text-foreground mb-3">
          {t('schedulingDemo.admin.title')}
        </h3>
        <p className="text-muted-foreground">
          {t('schedulingDemo.admin.subtitle')}
        </p>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Notification */}
      {showNotification && newBooking && (
        <Card className="p-4 border-green-500/50 bg-green-500/10 animate-fade-in">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-full bg-green-500 flex items-center justify-center">
              <Bell className="w-5 h-5 text-white" />
            </div>
            <div className="flex-1">
              <h4 className="font-semibold text-green-400">
                {t('schedulingDemo.admin.newBooking')}
              </h4>
              <p className="text-sm text-muted-foreground">
                {t('schedulingDemo.admin.notifications.newBooking', { name: newBooking.name })}
              </p>
            </div>
            <Badge variant="secondary" className="bg-green-500/20 text-green-400">
              Novo
            </Badge>
          </div>
        </Card>
      )}

      {/* Dashboard Metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">
                {t('schedulingDemo.admin.dashboard.todayBookings')}
              </p>
              <p className="text-2xl font-bold text-foreground">
                {bookings.length}
              </p>
            </div>
            <Calendar className="w-8 h-8 text-accent" />
          </div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">
                {t('schedulingDemo.admin.dashboard.weekRevenue')}
              </p>
              <p className="text-2xl font-bold text-foreground">R$2.450</p>
            </div>
            <DollarSign className="w-8 h-8 text-accent" />
          </div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">
                {t('schedulingDemo.admin.dashboard.satisfaction')}
              </p>
              <p className="text-2xl font-bold text-foreground">4.8</p>
            </div>
            <Star className="w-8 h-8 text-accent" />
          </div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">
                {t('schedulingDemo.admin.dashboard.noShows')}
              </p>
              <p className="text-2xl font-bold text-foreground">2%</p>
            </div>
            <TrendingUp className="w-8 h-8 text-accent" />
          </div>
        </Card>
      </div>

      {/* Recent Bookings */}
      <Card className="p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-foreground">
            {t('schedulingDemo.admin.recentBookings.title')}
          </h3>
          <Badge variant="outline">{bookings.length} agendamentos</Badge>
        </div>

        <div className="space-y-3">
          {bookings.slice(0, 5).map((booking, index) => (
            <div 
              key={booking.id}
              className={`flex items-center justify-between p-3 rounded-lg border animate-fade-in ${
                index === 0 && newBooking ? 'border-green-500/30 bg-green-500/5' : 'border-border'
              }`}
              style={{ animationDelay: `${index * 100}ms` }}
            >
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 rounded-full bg-accent/20 flex items-center justify-center">
                  <Users className="w-5 h-5 text-accent" />
                </div>
                <div>
                  <p className="font-medium text-foreground">{booking.customer}</p>
                  <p className="text-sm text-muted-foreground">{booking.service}</p>
                </div>
              </div>
              
              <div className="text-right">
                <p className="text-sm font-medium text-foreground">{booking.time}</p>
                <div className="flex items-center space-x-2">
                  {booking.status === 'confirmed' && (
                    <>
                      <CheckCircle className="w-4 h-4 text-green-500" />
                      <span className="text-xs text-green-500">
                        {t('schedulingDemo.admin.recentBookings.confirmed')}
                      </span>
                    </>
                  )}
                  {booking.status === 'pending' && (
                    <>
                      <Clock className="w-4 h-4 text-yellow-500" />
                      <span className="text-xs text-yellow-500">
                        {t('schedulingDemo.admin.recentBookings.pending')}
                      </span>
                    </>
                  )}
                  {booking.status === 'completed' && (
                    <>
                      <CheckCircle className="w-4 h-4 text-accent" />
                      <span className="text-xs text-accent">
                        {t('schedulingDemo.admin.recentBookings.completed')}
                      </span>
                    </>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="p-4 text-center hover:shadow-card-hover transition-smooth cursor-pointer">
          <MessageSquare className="w-8 h-8 text-accent mx-auto mb-2" />
          <p className="text-sm font-medium text-foreground">Enviar Lembrete</p>
        </Card>

        <Card className="p-4 text-center hover:shadow-card-hover transition-smooth cursor-pointer">
          <Phone className="w-8 h-8 text-accent mx-auto mb-2" />
          <p className="text-sm font-medium text-foreground">Contatar Cliente</p>
        </Card>

        <Card className="p-4 text-center hover:shadow-card-hover transition-smooth cursor-pointer">
          <BarChart3 className="w-8 h-8 text-accent mx-auto mb-2" />
          <p className="text-sm font-medium text-foreground">Ver Relatórios</p>
        </Card>
      </div>
    </div>
  );
};

export default AdminDashboardDemo;