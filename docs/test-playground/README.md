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

## Referência rápida

| Recurso | Valor |
|---|---|
| Utilizador de teste | `user_id=3`, `playground_test@test.com` |
| Endpoint playground | `POST http://localhost:8000/api/playground/chat` |
| Instrucoes completas | `docs/instrucoes-playground.md` |
