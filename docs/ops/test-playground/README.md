# test-playground

Pasta para testes estruturados do Playground de IA.

## Fluxo de trabalho atual

```
1. Operador abre /playground no browser
       ↓
2. Simula conversa como lead (painel esquerdo)
       ↓
3. Marca mensagens com 🔖 e anota feedback em tempo real (painel direito)
       ↓
4. Exporta o ficheiro *-output.md
       ↓
5. Cola o conteúdo do .md nesta conversa com Claude Code
       ↓
6. Claude lê traces + feedback → identifica causas → propõe plano
       ↓
7. Aprovação do plano → implementação → novo ciclo de teste
```

Ver guia completo da interface em `docs/guia-playground-ui.md`.

---

## Convenção de ficheiros

```
<nome-cenario>-input.md    ← contexto e cenários do teste (preenchido antes)
<nome-cenario>-output.md   ← exportado pelo playground UI após a sessão
```

Os ficheiros `*-input.md` continuam úteis para documentar o que se pretende testar
antes de iniciar a sessão (perfil, cenários A/B/C, critérios de avaliação).

Os ficheiros `*-output.md` são agora gerados pelo botão "Exportar .md" da interface —
não são mais escritos manualmente pelo Claude.

---

## O que trazer para a conversa com Claude

Ao colar o `.md` exportado, incluir no mesmo contexto:

- O ficheiro `*-output.md` completo
- O ficheiro `*-input.md` correspondente (se existir), para Claude ter os critérios esperados
- Qualquer comportamento adicional que tenha notado mas não anotado no momento

Claude irá:
1. Ler os `decision_trace` por turno para identificar onde o roteamento divergiu do esperado
2. Cruzar as anotações de feedback com os campos do trace (guardrails, mother_route, effective_route)
3. Identificar o ficheiro e função responsável pelo comportamento
4. Propor um plano de correção antes de implementar

---

## Referência rápida

| Recurso | Valor |
|---|---|
| Interface web | `http://localhost:8080/playground` |
| Serviços necessários | backend-core (8001), backend-crm (8000), backend-executors (8002), frontend-crm (8080) |
| Instrucoes de setup | `docs/instrucoes-playground.md` (secções 1–6) |
| Guia da interface UI | `docs/guia-playground-ui.md` |
| Histórico de fixes | `docs/test-playground/otimizacao.md` |
