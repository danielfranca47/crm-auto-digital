function applyTemplateSelect(prev, templateKey) {
  const currentMode = prev.agent_mode;
  const shouldSuggestMode = !currentMode || currentMode === "sdr_scheduler" || currentMode === "closer";
  const suggestedMode = templateKey.startsWith("closer")
    ? "direto"
    : templateKey.startsWith("consult")
    ? "consultivo"
    : "agenda";

  return {
    ...prev,
    template_key: templateKey,
    agent_mode: shouldSuggestMode ? suggestedMode : currentMode,
  };
}

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function main() {
  const scenario1Start = {
    template_key: "closer_agressivo",
    agent_mode: "consultivo",
  };
  const scenario1End = applyTemplateSelect(scenario1Start, "closer_agressivo");
  assert(
    scenario1End.agent_mode === "consultivo",
    "Cenário 1 falhou: template não pode sobrescrever agent_mode escolhido manualmente",
  );
  console.log("OK: cenário 1 -> modo manual preservado após troca de template");

  const scenario2Start = {
    template_key: "",
    agent_mode: "agenda",
  };
  const scenario2End = applyTemplateSelect(scenario2Start, "sdr_padrao");
  assert(
    scenario2End.agent_mode === "agenda",
    "Cenário 2 falhou: SDR padrão sem mudança manual deve manter/usar agenda",
  );
  console.log("OK: cenário 2 -> SDR padrão mantém modo agenda");

  const legacyStart = {
    template_key: "sdr_padrao",
    agent_mode: "sdr_scheduler",
  };
  const legacyEnd = applyTemplateSelect(legacyStart, "consultor_especialista");
  assert(
    legacyEnd.agent_mode === "consultivo",
    "Legado falhou: modo legado deveria ser auto-sugerido para novo modo do template",
  );
  console.log("OK: legado -> auto-sugestão de modo ao trocar template");
}

main();
