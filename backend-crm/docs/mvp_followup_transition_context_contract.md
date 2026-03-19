# MVP — Contrato mínimo para contexto de transição para Follow-up (sem implementação)

## Status

Documento de desenho de contrato e responsabilidades para o modal de transição.

- Escopo: **somente definição de endpoint/UX/persistência**.
- Fora de escopo neste MVP: implementação de backend, frontend, migrações, testes e rollout.

## 1) Endpoint de leitura para o modal

### Rota proposta

`GET /api/leads/{lead_id}/followup-transition-context`

### Autenticação

- Usuário autenticado do CRM (mesmo modelo usado nos endpoints browser-facing do CRM).
- Não usar endpoints internos com service-token neste fluxo.

### Objetivo

Entregar para o modal um resumo já calculado pelo backend, evitando recálculo de regras no frontend.

### Exemplo de resposta

```json
{
  "lead_id": 123,
  "from_category": "apresentation",
  "to_category": "follow-up",
  "agent_type": "agent_1",
  "followup_defaults": {
    "meeting_or_session_happened_options": ["yes", "no_show", "canceled", "needs_reschedule"],
    "followup_goal_options": ["confirm_interest", "reschedule_meeting", "recover_negotiation"]
  },
  "qualification_pending": {
    "has_pending": true,
    "pending_fields": ["location_preference", "budget_or_price_acceptance"],
    "severity": "low",
    "recommended_for_followup_capture": ["location_preference"]
  }
}
```

## 2) Regra de UX no modal (Opção B)

No `FollowUpTransitionModal`, exibir somente:

1. Aviso leve quando houver pendências de qualification.
2. Bloco opcional de complemento (“Deseja complementar agora?”).
3. Nenhum campo obrigatório adicional de qualification.

Diretriz: preservar o fluxo principal atual, que continua enviando o payload de follow-up para `POST /api/leads/start-followup`.

## 3) Persistência (sem contrato paralelo)

- `start-followup` permanece como dono da transição.
- `followup_contract` permanece como contrato principal do follow-up.
- Complementos opcionais (quando enviados) devem ser persistidos no mesmo fluxo de transição, sem criar contrato paralelo.

## 4) Responsabilidades por camada

- **Backend CRM**: calcula pendências e define o que é útil para follow-up.
- **Frontend (modal)**: apenas exibe o resumo e coleta complementos opcionais.
- **start-followup**: persiste o estado final da transição.

Diretriz: evitar duplicar no frontend regras hoje concentradas no backend/executor.

## 5) Coerência com o estado atual

Este desenho é consistente com o sistema atual porque:

- O modal já é orientado a contexto de follow-up (não tela completa de qualification).
- O frontend não consome qualification state completo nesse ponto do fluxo.
- Endpoints de qualification internos/service-token não são adequados para consumo direto no browser.

## 6) Riscos e mitigação

1. **Acoplamento modal ↔ qualification**  
   Mitigação: bloco de complementação opcional e leve.
2. **Duplicação de regras entre backend e frontend**  
   Mitigação: cálculo centralizado no backend do endpoint de contexto.
3. **Regressão do fluxo atual**  
   Mitigação: manter `start-followup` e payload principal inalterados no MVP.

## 7) Critério de aceite deste MVP de desenho

O time deve considerar este MVP aprovado quando houver alinhamento de produto/engenharia sobre:

- contrato JSON do endpoint de leitura;
- regra de UX opcional (sem obrigatoriedade de qualification);
- persistência no fluxo existente (`start-followup` + `followup_contract`), sem novo contrato.

> Observação: este documento não altera comportamento em produção.
