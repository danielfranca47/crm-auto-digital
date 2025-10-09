import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { format } from 'date-fns';
import { Card } from '@/components/ui/card';
import { Avatar } from '@/components/ui/avatar';
import { MessageCircle, Phone, Video, MoreVertical, ArrowLeft, Smile, Paperclip, Mic } from 'lucide-react';
import type { BookingFormData } from './SchedulingSimulator';

interface WhatsAppMessageProps {
  show: boolean;
  bookingData: BookingFormData | null;
  onReset: () => void;
}

const WhatsAppMessage = ({ show, bookingData, onReset }: WhatsAppMessageProps) => {
  const { t } = useTranslation();
  const [currentStep, setCurrentStep] = useState(0);
  const [isTyping, setIsTyping] = useState(false);

  const serviceNames: { [key: string]: string } = {
    haircut: t('schedulingDemo.services.haircut'),
    beard: t('schedulingDemo.services.beard'),
    combo: t('schedulingDemo.services.combo'),
    facial: t('schedulingDemo.services.facial'),
  };

  const professionalNames: { [key: string]: string } = {
    john: 'John Silva',
    maria: 'Maria Santos',
    carlos: 'Carlos Lima',
  };

  const messages = bookingData ? [
    {
      type: 'business',
      text: t('schedulingDemo.whatsapp.confirmation', {
        name: bookingData.name,
        service: serviceNames[bookingData.service] || bookingData.service,
        date: format(bookingData.date, 'dd/MM/yyyy'),
        time: bookingData.time,
        professional: professionalNames[bookingData.professional] || bookingData.professional
      }),
      delay: 1000
    },
    {
      type: 'business',
      text: t('schedulingDemo.whatsapp.address'),
      delay: 2000
    },
    {
      type: 'business',
      text: t('schedulingDemo.whatsapp.reminder'),
      delay: 3000
    },
    {
      type: 'customer',
      text: t('schedulingDemo.whatsapp.customerReply'),
      delay: 4500
    },
    {
      type: 'business',
      text: t('schedulingDemo.whatsapp.thanks'),
      delay: 5500
    }
  ] : [];

  useEffect(() => {
    if (show && bookingData) {
      setCurrentStep(0);
      const showMessages = async () => {
        for (let i = 0; i < messages.length; i++) {
          await new Promise(resolve => setTimeout(resolve, messages[i].delay));
          
          // Show typing indicator
          setIsTyping(true);
          await new Promise(resolve => setTimeout(resolve, 1500));
          setIsTyping(false);
          
          setCurrentStep(i + 1);
        }
      };
      showMessages();
    }
  }, [show, bookingData]);

  if (!show) {
    return (
      <Card className="p-8 text-center bg-gradient-to-br from-green-500/10 to-green-600/10 border-green-500/20">
        <div className="w-20 h-20 rounded-full bg-green-500/20 flex items-center justify-center mx-auto mb-6">
          <MessageCircle className="w-10 h-10 text-green-500" />
        </div>
        <h3 className="text-xl font-semibold text-foreground mb-3">
          {t('schedulingDemo.whatsapp.waiting.title')}
        </h3>
        <p className="text-muted-foreground">
          {t('schedulingDemo.whatsapp.waiting.description')}
        </p>
      </Card>
    );
  }

  return (
    <Card className="overflow-hidden bg-white text-black max-w-sm mx-auto shadow-2xl">
      {/* WhatsApp Header */}
      <div className="bg-green-600 text-white p-4 flex items-center space-x-3">
        <ArrowLeft className="w-5 h-5" />
        <Avatar className="w-10 h-10 bg-gray-300">
          <div className="w-full h-full bg-gradient-to-br from-blue-400 to-blue-600 flex items-center justify-center text-white text-sm font-medium">
            BS
          </div>
        </Avatar>
        <div className="flex-1">
          <div className="font-medium">Barber Shop Pro</div>
          <div className="text-xs opacity-90">online</div>
        </div>
        <div className="flex space-x-4">
          <Video className="w-5 h-5" />
          <Phone className="w-5 h-5" />
          <MoreVertical className="w-5 h-5" />
        </div>
      </div>

      {/* Messages Area */}
      <div className="h-96 overflow-y-auto p-4 bg-gray-50 space-y-3" style={{
        backgroundImage: `url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23e5e7eb' fill-opacity='0.1'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")`
      }}>
        {messages.slice(0, currentStep).map((message, index) => (
          <div
            key={index}
            className={`flex ${message.type === 'customer' ? 'justify-end' : 'justify-start'} animate-fade-in`}
          >
            <div
              className={`max-w-xs px-4 py-2 rounded-lg shadow-sm ${
                message.type === 'customer'
                  ? 'bg-green-500 text-white'
                  : 'bg-white text-gray-800 border'
              }`}
            >
              <p className="text-sm whitespace-pre-line">{message.text}</p>
              <div className={`text-xs mt-1 ${
                message.type === 'customer' ? 'text-green-100' : 'text-gray-500'
              }`}>
                {new Date().toLocaleTimeString('pt-BR', { 
                  hour: '2-digit', 
                  minute: '2-digit' 
                })}
              </div>
            </div>
          </div>
        ))}

        {/* Typing Indicator */}
        {isTyping && (
          <div className="flex justify-start">
            <div className="bg-white text-gray-800 border px-4 py-2 rounded-lg shadow-sm max-w-xs">
              <div className="flex space-x-1">
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Input Area */}
      <div className="bg-gray-100 p-3 flex items-center space-x-2">
        <div className="flex-1 bg-white rounded-full px-4 py-2 flex items-center">
          <Smile className="w-5 h-5 text-gray-400 mr-2" />
          <div className="text-gray-500 text-sm flex-1">
            {t('schedulingDemo.whatsapp.typeMessage')}
          </div>
          <Paperclip className="w-5 h-5 text-gray-400 ml-2" />
        </div>
        <div className="w-10 h-10 bg-green-500 rounded-full flex items-center justify-center">
          <Mic className="w-5 h-5 text-white" />
        </div>
      </div>

      {/* Demo Badge */}
      <div className="bg-yellow-100 border-t border-yellow-200 p-2 text-center">
        <span className="text-xs text-yellow-800 font-medium">
          {t('schedulingDemo.whatsapp.demoMode')}
        </span>
      </div>
    </Card>
  );
};

export default WhatsAppMessage;