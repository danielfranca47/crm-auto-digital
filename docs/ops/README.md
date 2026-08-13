# docs/ops — Guia para o Developer

## O que é esta pasta

Documentos operacionais: guias de testes, protocolos de validação e procedimentos
que o Claude segue ao executar tarefas que envolvem o sistema a correr (WhatsApp
real, playground, configurações de ambiente).

---

## Ficheiros

### Ficheiros com `_` — guias pai (processos reutilizáveis)

| Ficheiro | Para que serve |
|---|---|
| `_guia-testes-whatsapp.md` | Processo completo para criar e executar testes WhatsApp real + playground. Usado pelo Claude para criar o arquivo filho de testes. |
| `_guia-testes-desktop-app.md` | Processo para validar apps desktop nativas (ex.: `agent-local`) que não correm num browser — qual ferramenta de automação usar (`computer-use`) e armadilhas conhecidas. |
| `guia-teste-cliente-novo-exe-agent-local.md` | Script permanente (não é sessão única) para guiar um cliente não-técnico numa call testando o `agent-local.exe` no PC dele — onboarding real + confirma em hardware real o empacotamento já graduado (ver `docs/architecture/agent-local-app.md`). |

### Ficheiros regulares — trabalho activo

Arquivos temporários criados durante uma sessão de testes. Depois de os testes
concluírem e os resultados serem registados nos `docs/implementations/`, estes
arquivos são deletados.

Exemplo: `guia-testes-whatsapp-real.md` (arquivo que usámos nesta sessão — fica
como referência histórica, mas em sessões futuras seria deletado após conclusão).

---

## Como funciona o ciclo

```
1. Implementação concluída em docs/implementations/
      ↓
2. Tu pedes para fazer os testes
      ↓
3. Claude lê _guia-testes-whatsapp.md, mapeia os testes pendentes
   e cria um arquivo filho: guia-testes-<slug>.md
      ↓
4. Claude executa os testes (com o teu telemóvel / WhatsApp Web via MCP)
      ↓
5. Claude actualiza os checks em docs/implementations/ com [x]
      ↓
6. Claude deleta o arquivo filho e sugere o próximo passo
```

---

## Prompts úteis

### Quero validar features pendentes no WhatsApp real

```
Lê todos os arquivos em docs/implementations/ (exceto os com _) e mapeia
os testes pendentes que exigem WhatsApp real ou playground. Cria um guia
de testes seguindo docs/ops/_guia-testes-whatsapp.md.
```

### Quero continuar testes de uma sessão anterior

```
Abre docs/ops/guia-testes-[nome].md e continua de onde ficámos.
Verifica primeiro a conexão WhatsApp antes de pedir mensagens.
```

### Quero só os testes de playground (sem precisar do telemóvel)

```
Lê os arquivos docs/implementations/ e mapeia apenas os checks do tipo P
(playground). Cria um guia de testes só para playground.
```

### Quero saber que testes estão pendentes antes de decidir

```
Lê todos os arquivos docs/implementations/ (exceto _) e lista os checks
pendentes [ ], agrupados por tipo (P=playground, W=WhatsApp real, C=configuração).
Não cries nenhum arquivo ainda, só o resumo.
```

---

## O que esperar do Claude

Quando criares o guia de testes, o Claude vai:
1. Listar os testes pendentes por tipo e por dependência
2. Criar o arquivo filho com ordem lógica (infra primeiro, features depois)
3. Verificar a conexão WhatsApp antes de cada pedido de mensagem
4. Actualizar os `docs/implementations/` com os resultados após cada grupo
5. Se encontrar um bug: registá-lo no arquivo de implementação de origem e continuar
6. No final: deletar o arquivo, sugerir o próximo passo (graduar, continuar, ou nova feature)

### O que o Claude precisa de ti durante os testes

- **Escanear o QR code** quando a sessão WhatsApp expirar
- **Enviar as mensagens de teste** pelo telemóvel (ou confirmar quando enviadas)
- **Confirmar o que chegou** no WhatsApp quando o Claude não consegue ver
- **Decidir** quando há um bug se quer corrigir agora ou deixar para depois

### Como partilhar o WhatsApp Web com o Claude

Se tiveres o WhatsApp Web aberto e o MCP Chrome DevTools activo, o Claude consegue:
- Ver a conversa (screenshots)
- Enviar mensagens como o lead (digitando na caixa de texto)
- Verificar o estado sem precisar do teu telemóvel a cada passo

Para activar: abre o WhatsApp Web numa aba do Chrome antes de iniciar os testes e
diz ao Claude "deixei o WhatsApp Web aberto na conversa do lead X".
