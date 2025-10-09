import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { MessageSquare, Bot, User, Calendar, ShoppingBag, Stethoscope, Clock, CheckCircle } from 'lucide-react';

interface Message {
  id: string;
  sender: 'user' | 'bot';
  content: string;
  timestamp: string;
  typing?: boolean;
}

interface DemoScenario {
  id: string;
  icon: React.ElementType;
  name: string;
  description: string;
  color: string;
  initialMessages: Message[];
  responses: { [key: string]: string };
}

const AIWhatsAppDemo = () => {
  const { t } = useTranslation();
  const [selectedScenario, setSelectedScenario] = useState<string>('service');
  const [messages, setMessages] = useState<Message[]>([]);
  const [isTyping, setIsTyping] = useState(false);
  const [metrics, setMetrics] = useState({
    responseTime: 0,
    satisfaction: 98,
    resolved: 95
  });

  const scenarios: DemoScenario[] = [
    {
      id: 'service',
      icon: Calendar,
      name: t('aiWhatsappAutomation.demo.scenarios.service.name'),
      description: t('aiWhatsappAutomation.demo.scenarios.service.description'),
      color: 'bg-blue-500',
      initialMessages: [
        {
          id: '1',
          sender: 'bot',
          content: t('aiWhatsappAutomation.demo.scenarios.service.welcome'),
          timestamp: '10:00'
        }
      ],
      responses: {
        'agendar': t('aiWhatsappAutomation.demo.scenarios.service.responses.schedule'),
        'orçamento': t('aiWhatsappAutomation.demo.scenarios.service.responses.quote'),
        'preço': t('aiWhatsappAutomation.demo.scenarios.service.responses.price'),
        'schedule': t('aiWhatsappAutomation.demo.scenarios.service.responses.schedule'),
        'quote': t('aiWhatsappAutomation.demo.scenarios.service.responses.quote'),
        'price': t('aiWhatsappAutomation.demo.scenarios.service.responses.price')
      }
    },
    {
      id: 'healthcare',
      icon: Stethoscope,
      name: t('aiWhatsappAutomation.demo.scenarios.healthcare.name'),
      description: t('aiWhatsappAutomation.demo.scenarios.healthcare.description'),
      color: 'bg-green-500',
      initialMessages: [
        {
          id: '1',
          sender: 'bot',
          content: t('aiWhatsappAutomation.demo.scenarios.healthcare.welcome'),
          timestamp: '10:00'
        }
      ],
      responses: {
        'consulta': t('aiWhatsappAutomation.demo.scenarios.healthcare.responses.appointment'),
        'exame': t('aiWhatsappAutomation.demo.scenarios.healthcare.responses.exam'),
        'appointment': t('aiWhatsappAutomation.demo.scenarios.healthcare.responses.appointment'),
        'exam': t('aiWhatsappAutomation.demo.scenarios.healthcare.responses.exam')
      }
    },
    {
      id: 'ecommerce',
      icon: ShoppingBag,
      name: t('aiWhatsappAutomation.demo.scenarios.ecommerce.name'),
      description: t('aiWhatsappAutomation.demo.scenarios.ecommerce.description'),
      color: 'bg-purple-500',
      initialMessages: [
        {
          id: '1',
          sender: 'bot',
          content: t('aiWhatsappAutomation.demo.scenarios.ecommerce.welcome'),
          timestamp: '10:00'
        }
      ],
      responses: {
        'produto': t('aiWhatsappAutomation.demo.scenarios.ecommerce.responses.product'),
        'pedido': t('aiWhatsappAutomation.demo.scenarios.ecommerce.responses.order'),
        'entrega': t('aiWhatsappAutomation.demo.scenarios.ecommerce.responses.delivery'),
        'product': t('aiWhatsappAutomation.demo.scenarios.ecommerce.responses.product'),
        'order': t('aiWhatsappAutomation.demo.scenarios.ecommerce.responses.order'),
        'delivery': t('aiWhatsappAutomation.demo.scenarios.ecommerce.responses.delivery')
      }
    }
  ];

  const currentScenario = scenarios.find(s => s.id === selectedScenario)!;

  useEffect(() => {
    setMessages(currentScenario.initialMessages);
    // Update metrics based on scenario
    setMetrics({
      responseTime: Math.floor(Math.random() * 3) + 1,
      satisfaction: 95 + Math.floor(Math.random() * 5),
      resolved: 92 + Math.floor(Math.random() * 8)
    });
  }, [selectedScenario]);

  const handleQuickMessage = (message: string) => {
    const userMessage: Message = {
      id: Date.now().toString(),
      sender: 'user',
      content: message,
      timestamp: new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
    };

    setMessages(prev => [...prev, userMessage]);
    setIsTyping(true);

    // Simulate AI response
    setTimeout(() => {
      setIsTyping(false);
      
      // Find appropriate response
      const lowerMessage = message.toLowerCase();
      let response = t('aiWhatsappAutomation.demo.defaultResponse');
      
      for (const [key, value] of Object.entries(currentScenario.responses)) {
        if (lowerMessage.includes(key.toLowerCase())) {
          response = value;
          break;
        }
      }

      const botMessage: Message = {
        id: (Date.now() + 1).toString(),
        sender: 'bot',
        content: response,
        timestamp: new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
      };

      setMessages(prev => [...prev, botMessage]);
      
      // Update metrics
      setMetrics(prev => ({
        ...prev,
        responseTime: Math.floor(Math.random() * 3) + 1
      }));
    }, 1500);
  };

  const quickMessages = [
    t('aiWhatsappAutomation.demo.quickMessages.schedule'),
    t('aiWhatsappAutomation.demo.quickMessages.price'),
    t('aiWhatsappAutomation.demo.quickMessages.info')
  ];

  return (
    <section className="py-20 px-4 bg-gradient-to-r from-background to-card/30">
      <div className="container mx-auto max-w-7xl">
        <div className="text-center mb-16">
          <Badge variant="secondary" className="mb-4 px-4 py-2">
            <Bot className="w-4 h-4 mr-2" />
            {t('aiWhatsappAutomation.demo.badge')}
          </Badge>
          <h2 className="text-3xl md:text-4xl font-bold mb-4">
            {t('aiWhatsappAutomation.demo.title')}
          </h2>
          <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
            {t('aiWhatsappAutomation.demo.subtitle')}
          </p>
        </div>

        {/* Scenario Selector */}
        <div className="grid md:grid-cols-3 gap-4 mb-12">
          {scenarios.map((scenario) => (
            <Card 
              key={scenario.id}
              className={`cursor-pointer transition-all duration-300 hover-scale ${
                selectedScenario === scenario.id 
                  ? 'ring-2 ring-accent bg-card' 
                  : 'bg-card/50 hover:bg-card/80'
              }`}
              onClick={() => setSelectedScenario(scenario.id)}
            >
              <CardHeader className="text-center">
                <div className={`w-12 h-12 rounded-full ${scenario.color} flex items-center justify-center mx-auto mb-2`}>
                  <scenario.icon className="w-6 h-6 text-white" />
                </div>
                <CardTitle className="text-lg">{scenario.name}</CardTitle>
                <p className="text-sm text-muted-foreground">{scenario.description}</p>
              </CardHeader>
            </Card>
          ))}
        </div>

        {/* Demo Interface */}
        <div className="grid lg:grid-cols-3 gap-8">
          {/* Chat Interface */}
          <div className="lg:col-span-2">
            <Card className="bg-card h-[600px] flex flex-col">
              <CardHeader className="bg-green-600 text-white rounded-t-lg">
                <div className="flex items-center">
                  <div className="w-10 h-10 bg-white/20 rounded-full flex items-center justify-center mr-3">
                    <currentScenario.icon className="w-5 h-5" />
                  </div>
                  <div>
                    <CardTitle className="text-lg text-white">
                      {currentScenario.name} - IA
                    </CardTitle>
                    <p className="text-green-100 text-sm">Online</p>
                  </div>
                </div>
              </CardHeader>
              
              <CardContent className="flex-1 flex flex-col p-0">
                {/* Messages */}
                <div className="flex-1 overflow-y-auto p-4 bg-gray-50 dark:bg-gray-900">
                  {messages.map((message) => (
                    <div
                      key={message.id}
                      className={`flex mb-4 ${
                        message.sender === 'user' ? 'justify-end' : 'justify-start'
                      }`}
                    >
                      <div
                        className={`max-w-xs px-4 py-2 rounded-lg ${
                          message.sender === 'user'
                            ? 'bg-green-500 text-white rounded-br-none'
                            : 'bg-white dark:bg-gray-800 border rounded-bl-none'
                        }`}
                      >
                        <p className="text-sm">{message.content}</p>
                        <p className={`text-xs mt-1 ${
                          message.sender === 'user' ? 'text-green-100' : 'text-muted-foreground'
                        }`}>
                          {message.timestamp}
                        </p>
                      </div>
                    </div>
                  ))}
                  
                  {isTyping && (
                    <div className="flex justify-start mb-4">
                      <div className="bg-white dark:bg-gray-800 border px-4 py-2 rounded-lg rounded-bl-none">
                        <div className="flex space-x-1">
                          <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                          <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                          <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
                
                {/* Quick Messages */}
                <div className="p-4 border-t bg-background">
                  <p className="text-sm text-muted-foreground mb-2">
                    {t('aiWhatsappAutomation.demo.tryMessage')}
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {quickMessages.map((message, index) => (
                      <Button
                        key={index}
                        variant="outline"
                        size="sm"
                        onClick={() => handleQuickMessage(message)}
                        disabled={isTyping}
                        className="text-xs"
                      >
                        {message}
                      </Button>
                    ))}
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Metrics Panel */}
          <div className="space-y-6">
            <Card className="bg-card">
              <CardHeader>
                <CardTitle className="text-lg flex items-center">
                  <Bot className="w-5 h-5 mr-2 text-accent" />
                  {t('aiWhatsappAutomation.demo.metrics.title')}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">
                    {t('aiWhatsappAutomation.demo.metrics.responseTime')}
                  </span>
                  <div className="flex items-center">
                    <Clock className="w-4 h-4 mr-1 text-green-500" />
                    <span className="font-semibold">{metrics.responseTime}s</span>
                  </div>
                </div>
                
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">
                    {t('aiWhatsappAutomation.demo.metrics.satisfaction')}
                  </span>
                  <div className="flex items-center">
                    <CheckCircle className="w-4 h-4 mr-1 text-green-500" />
                    <span className="font-semibold">{metrics.satisfaction}%</span>
                  </div>
                </div>
                
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">
                    {t('aiWhatsappAutomation.demo.metrics.resolved')}
                  </span>
                  <div className="flex items-center">
                    <MessageSquare className="w-4 h-4 mr-1 text-green-500" />
                    <span className="font-semibold">{metrics.resolved}%</span>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="bg-card">
              <CardHeader>
                <CardTitle className="text-lg">
                  {t('aiWhatsappAutomation.demo.capabilities.title')}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-2 text-sm">
                  {[
                    t('aiWhatsappAutomation.demo.capabilities.nlp'),
                    t('aiWhatsappAutomation.demo.capabilities.context'),
                    t('aiWhatsappAutomation.demo.capabilities.multilang'),
                    t('aiWhatsappAutomation.demo.capabilities.learning')
                  ].map((capability, index) => (
                    <li key={index} className="flex items-center">
                      <CheckCircle className="w-4 h-4 mr-2 text-green-500" />
                      {capability}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </section>
  );
};

export default AIWhatsAppDemo;