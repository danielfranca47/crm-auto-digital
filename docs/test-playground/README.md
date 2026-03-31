# test-playground

Pasta para testes estruturados do Playground de IA.

## Convenção de ficheiros

```
<nome-cenario>-input.md    ← preenchido pelo operador antes do teste
<nome-cenario>-output.md   ← gerado pelo Claude após executar o teste
```

## Fluxo de trabalho

1. **Operador** cria `<nome>-input.md` com a configuração do bot e as mensagens a simular
2. **Claude** lê o input, cria o AI Profile no banco, executa as mensagens via playground e gera `<nome>-output.md`
3. O output regista por turno: resposta do agente, decisões mãe/filha, campos qualificados, trace completo

## Requisitos antes de iniciar

- Os 3 serviços devem estar online (ver `docs/instrucoes-playground.md` secção 3)
- Token JWT válido (expira em 120 min — fazer login se necessário)

## Bug conhecido: criação de AI Profile via API

O `backend-core` tem um bug menor na criação de AI Profile via API: a **background task do meta-prompter falha com HTTP 500**, mas o perfil é criado na mesma na base de dados.

**Sintoma:** a chamada `POST /ai-profiles` devolve 500, mesmo que o perfil tenha sido persistido com sucesso.

**Solução para o playground:** em vez de criar o AI Profile via API, criá-lo **directamente na base de dados** do `backend-core` (`app/core.db`, tabela `ai_profiles`).

```sql
-- Exemplo de inserção directa (ajustar valores conforme o cenário de teste)
INSERT INTO ai_profiles (
    user_id, agent_mode, presentation_variant, offer_pack, ...
) VALUES (
    3, 'consultivo', 'sales', 'default', ...
);
```

Desta forma evita-se o 500 da API e o perfil fica disponível imediatamente para o utilizador de teste (`user_id=3`).

## Referência rápida

| Recurso | Valor |
|---|---|
| Utilizador de teste | `user_id=3`, `playground_test@test.com` |
| Endpoint playground | `POST http://localhost:8000/api/playground/chat` |
| Instrucoes completas | `docs/instrucoes-playground.md` |
