# Confiabilidade de Integrações Externas — Melhorias Futuras

> Contexto: itens deixados de fora da graduação de
> `docs/implementations/primeiro-assinante-smtp-e-webhook-efi.md` (12/08/2026).
> O primeiro assinante real pagante quase ficou sem acesso porque o SMTP
> falhava silenciosamente há semanas, e o `current_period_end` da sua
> subscription foi inflado 5× por reentregas do webhook Efí sem detecção. O
> fix pontual de cada problema já foi feito e graduado; estes dois itens são
> as auditorias mais amplas que a Investigação daquele incidente recomendou,
> para o mesmo padrão de falha não se repetir noutro ponto do sistema.

---

## M1 — Auditoria de falhas silenciosas em dependências externas

**Prioridade: MÉDIA**

**Em palavras simples:** o SMTP falhou 100% das vezes durante semanas sem
nenhum sinal visível além de uma linha de log que ninguém lia — o padrão
`try/except` não-bloqueante que protege operações de negócio de falhas de
serviço externo também esconde a falha por completo. O mesmo padrão existe
noutras integrações (UazAPI, Efí, LLM) e pode estar a falhar do mesmo jeito
sem ninguém saber.

**O que precisaria existir:**
- Mapear todos os pontos com `try/except` que engolem falha de um serviço
  externo (SMTP, UazAPI, Efí, LLM) e definir alerta/notificação ao admin
  quando a taxa de falha for anómala
- Mapear que outras portas/egress a Railway restringe que o sistema hoje
  assume abertas (o bloqueio da 587 só foi descoberto pelo incidente)
- Validar entrega real (não só "sem erro no log") de cada tipo de email de
  produção

---

## M2 — Auditoria de efeitos de reentrega em todos os handlers de webhook

**Prioridade: MÉDIA**

**Em palavras simples:** webhooks são reentregues por design pelos
provedores externos (a Efí reentregou a mesma notificação de pagamento
várias vezes). O fix de idempotência por `charge_id` já foi aplicado no
webhook da Efí (`billing-efi.md`), mas os outros webhooks do sistema nunca
foram auditados para o mesmo risco.

**O que precisaria existir:** mapear todos os webhooks do sistema
(`/webhooks/efi`, `/webhooks/payment/{gateway}`, `/webhooks/whatsapp/*`) e
verificar, para cada um, o que acontece se o mesmo evento chegar 2–5×: que
estado é duplicado/inflado, que jobs são re-enfileirados, que emails são
reenviados. Documentar a garantia (ou falta dela) por endpoint.

---

## Relação com outros documentos

- O fix pontual de idempotência do webhook Efí (`charge_id`) já está
  documentado em `docs/architecture/billing-efi.md`, secção "Activação".
- A correção do SMTP (porta 2587) já está documentada em
  `docs/architecture/auth-email.md`, tabela de configuração SMTP.
- Uma política de idempotência **padrão** para qualquer evento externo
  futuro (chave de dedup genérica, não só o fix pontual do `charge_id`) foi
  cogitada no mesmo incidente mas descartada nesta triagem — revisitar se
  M2 revelar mais de um webhook com o mesmo problema.
