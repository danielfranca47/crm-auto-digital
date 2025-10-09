import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useTranslation } from 'react-i18next';
import { Calendar } from '@/components/ui/calendar';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { format } from 'date-fns';
import { CalendarIcon, Clock, User, Phone, Scissors, Sparkles } from 'lucide-react';
import { cn } from '@/lib/utils';
import WhatsAppMessage from './WhatsAppMessage';
import AdminDashboardDemo from './AdminDashboardDemo';

const bookingSchema = z.object({
  service: z.string().min(1, { message: "Please select a service" }),
  professional: z.string().min(1, { message: "Please select a professional" }),
  date: z.date({ required_error: "Please select a date" }),
  time: z.string().min(1, { message: "Please select a time" }),
  name: z.string().trim().min(2, { message: "Name must be at least 2 characters" }).max(50, { message: "Name must be less than 50 characters" }),
  phone: z.string().trim().min(10, { message: "Please enter a valid phone number" }).max(15, { message: "Phone number is too long" }),
});

// Export this type so other components can use it
export type BookingFormData = z.infer<typeof bookingSchema>;

const SchedulingSimulator = () => {
  const { t } = useTranslation();
  const [showMessage, setShowMessage] = useState(false);
  const [bookingData, setBookingData] = useState<BookingFormData | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const form = useForm<BookingFormData>({
    resolver: zodResolver(bookingSchema),
  });

  const services = [
    { id: 'haircut', name: t('schedulingDemo.services.haircut'), duration: '30 min', price: '$25' },
    { id: 'beard', name: t('schedulingDemo.services.beard'), duration: '20 min', price: '$15' },
    { id: 'combo', name: t('schedulingDemo.services.combo'), duration: '45 min', price: '$35' },
    { id: 'facial', name: t('schedulingDemo.services.facial'), duration: '60 min', price: '$50' },
  ];

  const professionals = [
    { id: 'john', name: 'John Silva', specialty: t('schedulingDemo.professionals.senior') },
    { id: 'maria', name: 'Maria Santos', specialty: t('schedulingDemo.professionals.specialist') },
    { id: 'carlos', name: 'Carlos Lima', specialty: t('schedulingDemo.professionals.expert') },
  ];

  const timeSlots = [
    '09:00', '09:30', '10:00', '10:30', '11:00', '11:30',
    '14:00', '14:30', '15:00', '15:30', '16:00', '16:30', '17:00'
  ];

  const onSubmit = async (data: BookingFormData) => {
    setIsSubmitting(true);
    
    // Simulate API call
    await new Promise(resolve => setTimeout(resolve, 1500));
    
    setBookingData(data);
    setShowMessage(true);
    setIsSubmitting(false);
  };

  const resetDemo = () => {
    setShowMessage(false);
    setBookingData(null);
    form.reset();
  };

  return (
    <div className="max-w-7xl mx-auto">
      {/* Dual View Toggle */}
      <div className="flex justify-center mb-8">
        <div className="inline-flex rounded-lg bg-muted p-1">
          <button 
            className="px-4 py-2 rounded-md text-sm font-medium transition-colors bg-accent text-accent-foreground"
          >
            Visão Completa (Cliente + Admin)
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 items-start">
        
        {/* Booking Form */}
        <Card className="p-8">
          <div className="flex items-center mb-6">
            <div className="w-12 h-12 rounded-xl accent-gradient flex items-center justify-center mr-4">
              <Calendar className="w-6 h-6 text-accent-foreground" />
            </div>
            <div>
              <h3 className="text-2xl font-bold text-foreground">
                {t('schedulingDemo.form.title')}
              </h3>
              <p className="text-muted-foreground">
                {t('schedulingDemo.form.subtitle')}
              </p>
            </div>
          </div>

          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
              
              {/* Service Selection */}
              <FormField
                control={form.control}
                name="service"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className="flex items-center">
                      <Scissors className="w-4 h-4 mr-2" />
                      {t('schedulingDemo.form.service')}
                    </FormLabel>
                    <Select onValueChange={field.onChange} defaultValue={field.value}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder={t('schedulingDemo.form.selectService')} />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {services.map((service) => (
                          <SelectItem key={service.id} value={service.id}>
                            <div className="flex justify-between items-center w-full">
                              <span>{service.name}</span>
                              <div className="text-xs text-muted-foreground ml-4">
                                {service.duration} • {service.price}
                              </div>
                            </div>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* Professional Selection */}
              <FormField
                control={form.control}
                name="professional"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className="flex items-center">
                      <User className="w-4 h-4 mr-2" />
                      {t('schedulingDemo.form.professional')}
                    </FormLabel>
                    <Select onValueChange={field.onChange} defaultValue={field.value}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder={t('schedulingDemo.form.selectProfessional')} />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {professionals.map((prof) => (
                          <SelectItem key={prof.id} value={prof.id}>
                            <div>
                              <div className="font-medium">{prof.name}</div>
                              <div className="text-xs text-muted-foreground">{prof.specialty}</div>
                            </div>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* Date Selection */}
              <FormField
                control={form.control}
                name="date"
                render={({ field }) => (
                  <FormItem className="flex flex-col">
                    <FormLabel className="flex items-center">
                      <CalendarIcon className="w-4 h-4 mr-2" />
                      {t('schedulingDemo.form.date')}
                    </FormLabel>
                    <Popover>
                      <PopoverTrigger asChild>
                        <FormControl>
                          <Button
                            variant={"outline"}
                            className={cn(
                              "w-full pl-3 text-left font-normal",
                              !field.value && "text-muted-foreground"
                            )}
                          >
                            {field.value ? (
                              format(field.value, "PPP")
                            ) : (
                              <span>{t('schedulingDemo.form.selectDate')}</span>
                            )}
                            <CalendarIcon className="ml-auto h-4 w-4 opacity-50" />
                          </Button>
                        </FormControl>
                      </PopoverTrigger>
                      <PopoverContent className="w-auto p-0" align="start">
                        <Calendar
                          mode="single"
                          selected={field.value}
                          onSelect={field.onChange}
                          disabled={(date) =>
                            date < new Date() || date.getDay() === 0
                          }
                          initialFocus
                          className={cn("p-3 pointer-events-auto")}
                        />
                      </PopoverContent>
                    </Popover>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* Time Selection */}
              <FormField
                control={form.control}
                name="time"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className="flex items-center">
                      <Clock className="w-4 h-4 mr-2" />
                      {t('schedulingDemo.form.time')}
                    </FormLabel>
                    <div className="grid grid-cols-3 gap-2">
                      {timeSlots.map((time) => (
                        <Button
                          key={time}
                          type="button"
                          variant={field.value === time ? "default" : "outline"}
                          size="sm"
                          onClick={() => field.onChange(time)}
                          className="h-10"
                        >
                          {time}
                        </Button>
                      ))}
                    </div>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* Customer Information */}
              <div className="space-y-4">
                <h4 className="font-semibold text-foreground flex items-center">
                  <Phone className="w-4 h-4 mr-2" />
                  {t('schedulingDemo.form.customerInfo')}
                </h4>
                
                <FormField
                  control={form.control}
                  name="name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{t('schedulingDemo.form.name')}</FormLabel>
                      <FormControl>
                        <Input placeholder={t('schedulingDemo.form.namePlaceholder')} {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="phone"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{t('schedulingDemo.form.phone')}</FormLabel>
                      <FormControl>
                        <Input placeholder={t('schedulingDemo.form.phonePlaceholder')} {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              <Button 
                type="submit" 
                className="w-full h-12 text-lg" 
                disabled={isSubmitting}
              >
                {isSubmitting ? (
                  <div className="flex items-center">
                    <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin mr-2" />
                    {t('schedulingDemo.form.scheduling')}
                  </div>
                ) : (
                  <div className="flex items-center">
                    <Sparkles className="w-5 h-5 mr-2" />
                    {t('schedulingDemo.form.scheduleButton')}
                  </div>
                )}
              </Button>
            </form>
          </Form>

          {showMessage && (
            <div className="mt-6">
              <Button 
                variant="outline" 
                onClick={resetDemo}
                className="w-full"
              >
                {t('schedulingDemo.form.tryAgain')}
              </Button>
            </div>
          )}
        </Card>

        {/* WhatsApp Simulation */}
        <div className="sticky top-8">
          <WhatsAppMessage 
            show={showMessage}
            bookingData={bookingData}
            onReset={resetDemo}
          />
        </div>

        {/* Admin Dashboard */}
        <div className="sticky top-8">
          <AdminDashboardDemo 
            isActive={showMessage}
            newBooking={bookingData}
          />
        </div>
      </div>
    </div>
  );
};

export default SchedulingSimulator;