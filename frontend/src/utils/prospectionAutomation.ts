import { ProspectionTask, ProspectionMethod } from '@/types/prospection';

export class ProspectionAutomation {
  static async simulateEmailSend(leadName: string, email?: string): Promise<boolean> {
    // Simulate email sending delay
    await new Promise(resolve => setTimeout(resolve, 2000));
    
    console.log(`📧 Email enviado para ${leadName}${email ? ` (${email})` : ''}`);
    return Math.random() > 0.1; // 90% success rate
  }

  static async simulateWhatsAppSend(leadName: string, phone: string): Promise<boolean> {
    // Simulate WhatsApp sending delay
    await new Promise(resolve => setTimeout(resolve, 1500));
    
    console.log(`📱 WhatsApp enviado para ${leadName} (${phone})`);
    return Math.random() > 0.05; // 95% success rate
  }

  static async processAutomatedTasks(
    tasks: ProspectionTask[],
    leadName: string,
    phone: string,
    email?: string
  ): Promise<ProspectionTask[]> {
    const updatedTasks = [...tasks];

    for (const task of updatedTasks) {
      if (task.automatedTask && !task.completed) {
        let success = false;

        try {
          switch (task.method) {
            case 'email':
              success = await this.simulateEmailSend(leadName, email);
              break;
            case 'whatsapp':
              success = await this.simulateWhatsAppSend(leadName, phone);
              break;
          }

          if (success) {
            task.completed = true;
            task.completedAt = new Date();
          }
        } catch (error) {
          console.error(`Erro ao processar tarefa ${task.method} para ${leadName}:`, error);
        }
      }
    }

    return updatedTasks;
  }

  static getAutomationStatus(method: ProspectionMethod): string {
    switch (method) {
      case 'email':
        return 'Enviando e-mail...';
      case 'whatsapp':
        return 'Enviando mensagem WhatsApp...';
      case 'call':
        return 'Aguardando ligação manual';
      default:
        return 'Processando...';
    }
  }

  static getCompletionMessage(method: ProspectionMethod, success: boolean): string {
    if (!success) {
      return `Falha ao enviar via ${method}`;
    }

    switch (method) {
      case 'email':
        return 'E-mail enviado com sucesso!';
      case 'whatsapp':
        return 'Mensagem WhatsApp enviada!';
      case 'call':
        return 'Ligação concluída';
      default:
        return 'Tarefa concluída';
    }
  }
}