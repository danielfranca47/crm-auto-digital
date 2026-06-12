function applyAgentModel(profile, model) {
  if (model === "agendador_com_humano") {
    return { ...profile, agent_mode: "consultivo", requires_handoff: true, human_in_loop: true };
  }
  if (model === "direto_autonomo") {
    return { ...profile, agent_mode: "direto", requires_handoff: false, human_in_loop: false };
  }
  return { ...profile, agent_mode: "agenda", requires_handoff: false, human_in_loop: false };
}

function normalizeForSave(profile) {
  const model = profileToAgentModelUi(profile);
  return applyAgentModel(profile, model);
}

function profileToAgentModelUi(profile) {
  const mode = String(profile.agent_mode || "").toLowerCase();
  const requires = Boolean(profile.requires_handoff);
  const human = Boolean(profile.human_in_loop);

  if (mode === "consultivo") return "agendador_com_humano";
  if (mode === "direto" || mode === "closer") return "direto_autonomo";
  if (mode === "sdr_scheduler") return "agendador_com_humano";
  if (mode === "agenda") return requires || human ? "agendador_com_humano" : "hibrido_agendador";
  return "hibrido_agendador";
}

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
  // Cenário 1: escolhe closer, depois escolhe modelo consultivo manualmente, salva/recarrega
  let profile = { template_key: "", agent_mode: "agenda", requires_handoff: false, human_in_loop: false };
  profile = applyTemplateSelect(profile, "closer_agressivo");
  profile = applyAgentModel(profile, "agendador_com_humano"); // escolha manual via novo UI model
  const reloadedUiModel = profileToAgentModelUi(profile);
  assert(profile.agent_mode === "consultivo", "Cenário 1 falhou: agent_mode deveria permanecer consultivo");
  assert(reloadedUiModel === "agendador_com_humano", "Cenário 1 falhou: UI deveria refletir agendador_com_humano");
  console.log("OK: cenário 1 -> template não sobrescreve escolha manual do modelo");

  // Cenário 2: SDR padrão sem mexer dropdown => agenda
  let profile2 = { template_key: "", agent_mode: "agenda", requires_handoff: false, human_in_loop: false };
  profile2 = applyTemplateSelect(profile2, "sdr_padrao");
  assert(profile2.agent_mode === "agenda", "Cenário 2 falhou: padrão deve permanecer agenda");
  console.log("OK: cenário 2 -> SDR padrão mantém agent_mode agenda");

  // Compat legado vindo do backend
  assert(profileToAgentModelUi({ agent_mode: "sdr_scheduler" }) === "agendador_com_humano", "Legado sdr_scheduler mapeamento inválido");
  assert(profileToAgentModelUi({ agent_mode: "closer" }) === "direto_autonomo", "Legado closer mapeamento inválido");
  console.log("OK: legado -> mapeamento para agent_model_ui correto");

  // Normalização obrigatória no save
  const normalized = normalizeForSave({
    agent_mode: "closer",
    requires_handoff: false,
    human_in_loop: false,
  });
  assert(normalized.agent_mode === "direto", "Normalização falhou: closer deve virar direto");
  assert(normalized.requires_handoff === false, "Normalização falhou: direto deve manter handoff false");
  assert(normalized.human_in_loop === false, "Normalização falhou: direto deve manter human_in_loop false");
  console.log("OK: save normaliza agent_mode legado para consultivo|agenda|direto");
}

main();
