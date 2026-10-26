# Bancada de testes (genérica para qualquer conta)

## Estrutura

```
.claude/agentes/<slug>/            # gitignored
  bancada.json                     # tudo o que é próprio da conta (ver abaixo)
  README.md                        # roteiro, processo, critérios, histórico de versões, estado, onde retomamos
  cenarios.json                    # cenários fixos e personas
  gerar_config.py                  # versões cNN (patch do AI profile)
  configs/cNN-*.json
  tentativas/<data>-<rótulo>-<cenário>.md|.json
  referencias/<telefone>.txt       # conversas reais extraídas
  ambiente/                        # código isolado, cópias dos bancos, snapshots e backups de produção
```

`bancada.json`:
```json
{
  "slug": "<slug>",
  "conta": {"email": "<email>", "prod_user_id": 0, "prod_ai_profile_id": 0},
  "agente": {"nome": "<nome do agente>", "negocio": "<o que a empresa faz e onde>", "idioma": "<ex.: português de Portugal>"},
  "agente_tipo": "<01-sdr-alto-ticket|02-vendedor-autonomo|03-assistente-comercial>",
  "prod": {"crm_url": "https://api.danielfranca.pt", "core_service": "backend-core"},
  "local": {"core": "http://localhost:8101", "crm": "http://localhost:8100", "executors": "http://localhost:8102"}
}
```

A conta de teste local (credenciais, `user_id`, `ai_profile_id`) é lida de
`docs/implementations/_conta-teste-local.md`. Não a copies para a bancada.

## Montar

```bash
S=.claude/skills/diagnosticar-agente/scripts
python $S/preparar_bancada.py <slug> --email X --prod-user-id N --prod-ai-profile-id M \
    --agente "Nome" --negocio "..." --idioma "..."     # pasta + bancada.json + ambiente isolado
# arrancar os 3 backends isolados (comandos impressos pelo script; core primeiro)
python $S/preparar_bancada.py <slug> --copiar-prod     # perfil + Base de Conhecimento de produção → conta de teste local
```

Antes de montar, confirma se as portas estão livres
(`netstat -ano | grep -E ':(8100|8101|8102) .*LISTEN'`). Se outra bancada estiver ligada, usa
`--portas 8111,8110,8112` (core, crm, executors). Arranca os backends com os comandos que o script
imprime: levam `PYTHONUTF8=1`, porque os backends imprimem emojis no arranque e, com a saída num
ficheiro, o Windows rebenta (`UnicodeEncodeError`). Espera que os 3 respondam em `/docs` antes de
simular.

O que o script faz e porquê:
- Desliga o envio para fora nos `.env` da bancada. O SMTP e a UazAPI apontam para endereços mortos,
  porque o core envia emails de assinatura ao arrancar e o core e o crm falam com o WhatsApp.
- Faz `git archive main` dos 3 backends para `ambiente/codigo/`. Assim testa o mesmo código que está
  em produção e não toca na pasta principal nem nas worktrees.
- Copia os `.env`/`.env.local` e reescreve as portas e os bancos. O `backend-crm/.env.local` força
  `EXECUTORS_BASE_URL` com override; sem a reescrita, o CRM da bancada fala com os executores de
  outra sessão.
- Copia os bancos com a API de backup do sqlite, que inclui o WAL. Uma cópia simples do ficheiro
  perde escritas recentes.
- `--copiar-prod` lê o perfil e a Base de Conhecimento de produção pelo `prod_turno.py` (só leitura) e
  aplica-os à conta de teste **só na cópia local**. As mídias continuam a apontar para os URLs de
  produção, o que funciona.

Para testar código de uma worktree (validar um fix): `preparar_bancada.py <slug> --codigo-de <ref>`
recopia o código desse branch para `ambiente/codigo/` sem tocar nos bancos.

## Cenários (`cenarios.json`)

```json
{
  "nome-fixo":  {"wa_name": "Ana", "origem": "conversa real +351…", "mensagens": ["...", "..."]},
  "p-persona":  {"wa_name": "Ana", "origem": "...", "primeira": "...", "persona": "Quem é, o que quer, como reage a cada proposta, quando aceita.", "max_turnos": 14},
  "limite-x":   {"wa_name": "...", "origem": "regra Y — esperado: Z", "setup": "o que tem de existir antes (ex.: evento ocupado)", "primeira": "...", "persona": "..."}
}
```

- **Fixos:** reproduzem a conversa real. Servem de linha de base, mas falham sem razão quando o
  agente pergunta noutra ordem.
- **Personas (`p-*`):** um cliente simulado por IA (gpt-4o-mini, `temperature` 0.4) responde ao que
  o agente disse. Escreve a persona com o objetivo e com **o que faz em cada bifurcação** ("se
  recusarem, aceita a segunda proposta"). Sem isso, o cliente simulado improvisa e o cenário deixa
  de medir.
- **Limite:** um por regra de negócio ou critério crítico. O campo `origem` diz o resultado
  esperado, o que permite ler a transcrição contra ele.

A biblioteca de cenários de cada agente (inbound e outbound) está na skill do agente.

## Correr e medir

```bash
python $S/simular.py <pasta> <cenário> <rótulo> [--prod]            # 1 conversa
python $S/simular.py <pasta> --bateria c1,c2,c3 <rótulo> [--prod]   # várias, em sequência
python $S/simular.py <pasta> --resumo <rótulo>                      # tabela das tentativas desse rótulo
python $S/simular.py <pasta> --aplicar configs/cNN.json             # aplica ao perfil LOCAL
python $S/simular.py <pasta> --perfil [campo ...]                   # perfil local
```

Cada tentativa grava a transcrição (`.md`) e as respostas brutas do Playground (`.json`). O
`--resumo` mostra, por conversa: rotas, categoria final, guardrails, falhas da IA (handoff de
recurso), mídias enviadas, campos em falta, eventos de agenda (com o dia da semana real da data
gravada) e links enviados. **Lê também as transcrições**: o resumo aponta onde olhar, não substitui
a leitura.

O rótulo é a versão (`c05`) para os testes locais e `PROD<n>` para as baterias em produção.

## Playground de produção (`--prod`)

Corre o mesmo motor e a configuração real da conta, sem enviar nada por WhatsApp. Cada turno é um
`railway ssh` ao `backend-core`, onde o `prod_turno.py` cria uma sessão de 30 minutos para a conta
com a função de login do core e chama o CRM. No fim, apaga as marcações `[Playground]` desse lead.

Cuidados:
- Os turnos correm **em sequência**. Dois `railway ssh` em paralelo às vezes devolvem vazio, e o
  `--bateria` já serializa.
- Os eventos reais da conta (agenda, Google) entram nos testes. Antes de concluir "bug", vê se é um
  evento real ou uma sobra de outra conversa.
- O Cloudflare bloqueia o User-Agent do urllib (erro 1010); o script já envia um UA de browser.
- O worker real do WhatsApp é outro serviço (`worker backend-executors`). Para confirmar que um fix
  está ativo, procura-o nos dois serviços de executores.

## Desligar

Pára os 3 backends no fim de cada sessão. As notificações de "comando falhou" desses processos de
fundo são da paragem, não são erro. Nunca pares processos que a bancada não arrancou: as portas
8000–8002 podem ser de outra sessão.
