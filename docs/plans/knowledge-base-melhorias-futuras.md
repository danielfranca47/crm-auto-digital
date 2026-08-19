# Base de Conhecimento — melhorias futuras

> Contexto: itens deixados de fora da graduação de
> `docs/implementations/fix-knowledge-narrativo-repeticao.md` (19/08/2026), que introduziu
> o dedup de categorias narrativas (`social_proof`, `pitch_script`, `product_details`) —
> ver [`docs/architecture/knowledge-base.md`](../architecture/knowledge-base.md#dedup-de-categorias-narrativas-evitar-repetição-entre-turnos).

---

## M1 — Dedup por uso confirmado, não por disponibilidade

**Prioridade: BAIXA**

Hoje uma categoria narrativa é marcada como "mostrada" assim que é **disponibilizada** no
prompt da IA filha (tinha conteúdo e ainda não estava em `knowledge_categories_shown`) —
não quando a IA **de facto a cita** na resposta. Confirmado em teste real: a prova social
apareceu disponível num turno mas a filha optou por não a usar; mesmo assim foi marcada
como mostrada e nunca mais reapareceu para aquele lead.

**Impacto:** conteúdo configurado pelo operador pode nunca chegar a ser dito a um lead
específico, "gasto" sem uso.

**Correção proposta:** estender `ChildResult` com um campo tipo `narrative_categories_used:
list[str]`, espelhando o padrão já existente de `media_keys_to_send` (onde a própria IA
declara quais mídias anexou). Marcar como mostrado só quando a IA confirmar o uso, não
quando o conteúdo é meramente oferecido.

---

## M2 — Dedup por conteúdo, não só por categoria

**Prioridade: BAIXA**

O registo em `leads.knowledge_categories_shown` guarda só o nome da categoria (`"social_proof"`),
não uma referência ao texto exibido. Se o operador editar o conteúdo de uma categoria já
mostrada a um lead, esse lead nunca verá a versão nova — o sistema só sabe "a categoria já
foi usada", não "este texto específico já foi usado".

**Nota:** é o mesmo padrão já aceito hoje em `leads.triggers_fired`/`phases_triggered`
(Fluxo de Venda) — não é uma regressão nova, é uma limitação consciente já presente noutra
parte do sistema.

**Correção proposta:** guardar um hash (ou versão) do `content_text` junto da categoria em
`knowledge_categories_shown`, e só suprimir quando o hash bater com o que já foi mostrado.

---

## M3 — Reset de categorias mostradas em reengajamento

**Prioridade: BAIXA**

Quando um lead reengaja depois de ficar inativo (o sistema já tem lógica dedicada para
isso — `reactivation_mode`/`reactivation_msg` no AI Profile), `knowledge_categories_shown`
não é limpo. Categorias narrativas continuam suprimidas para sempre, mesmo quando recontar
a informação faria sentido depois de tanto tempo.

**Correção proposta:** quando a lógica de reativação existente detectar reengajamento,
limpar `knowledge_categories_shown` (avaliar se `triggers_fired`/`phases_triggered` do
Fluxo de Venda também deveriam ser limpos no mesmo momento — ficaria fora do escopo deste
item específico, mas é a mesma pergunta de fundo).
