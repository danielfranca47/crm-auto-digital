"""Casos das categorias que sobem sempre. Só passam caminhos e linhas — nada é executado
no repositório real (o teste de ponta a ponta usa um repositório temporário)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "categorias_que_sobem.py"
sys.path.insert(0, str(SCRIPT.parent))

import categorias_que_sobem as cs  # noqa: E402


def categorias(ficheiros, linhas=None):
    return list(cs.classificar(ficheiros, linhas))


# --------------------------------------------------------------------------
# Só pelo caminho do ficheiro
# --------------------------------------------------------------------------

POR_CAMINHO = [
    # regras do próprio agente — vale também para documentação
    (".claude/settings.json", "seguranca_agente"),
    ("scripts/claude_hooks/verificar_comando.py", "seguranca_agente"),
    ("scripts/fila/categorias_que_sobem.py", "seguranca_agente"),
    ("scripts/fila/tests/test_categorias_que_sobem.py", "seguranca_agente"),
    ("docs/ops/fila-automatica.md", "seguranca_agente"),
    (".github/workflows/deploy-frontend-crm.yml", "seguranca_agente"),
    ("CLAUDE.md", "seguranca_agente"),
    # pagamento e cobrança
    ("backend-crm/services/efi_client.py", "pagamento"),
    ("backend-crm/routes/checkout.py", "pagamento"),
    ("backend-crm/routes/admin_billing.py", "pagamento"),
    ("backend-crm/services/plan_gates.py", "pagamento"),
    ("backend-core/app/api/plans.py", "pagamento"),
    ("backend-core/app/api/subscriptions.py", "pagamento"),
    ("backend-core/app/jobs/subscription_jobs.py", "pagamento"),
    ("backend-core/app/services/checkout_links.py", "pagamento"),
    ("frontend-crm/src/pages/Assinatura.tsx", "pagamento"),
    ("frontend-crm/src/components/SubscriptionGate.tsx", "pagamento"),
    ("frontend-crm/src/pages/SaaSAdmin/Plans.tsx", "pagamento"),
    ("frontend-admin/src/pages/AdminPlans.tsx", "pagamento"),
    ("backend-crm/tests/test_efi_webhook.py", "pagamento"),
    # envio real a clientes
    ("backend-core/app/providers/uazapi_client.py", "envio_real"),
    ("backend-core/app/api/whatsapp_send.py", "envio_real"),
    ("backend-core/app/services/email_service.py", "envio_real"),
    ("backend-core/app/api/smtp_accounts.py", "envio_real"),
    ("backend-crm/core_client.py", "envio_real"),
    ("backend-executors/app/clients/core_client.py", "envio_real"),
    ("backend-executors/app/runners/whatsapp.py", "envio_real"),
    ("backend-executors/app/runners/email.py", "envio_real"),
    ("backend-executors/app/workers/email_worker.py", "envio_real"),
    # estrutura da base de dados
    ("backend-crm/migrations/001_create_agents_jobs.sql", "base_de_dados"),
    ("backend-crm/database.py", "base_de_dados"),
    ("backend-crm/models.py", "base_de_dados"),
    ("backend-core/app/db.py", "base_de_dados"),
    ("backend-core/app/seed.py", "base_de_dados"),
    ("backend-core/app/models/user.py", "base_de_dados"),
    # instruções da IA
    ("backend-executors/app/services/decision_engine.py", "instrucoes_ia"),
    ("backend-executors/app/services/field_extractor.py", "instrucoes_ia"),
    ("backend-executors/app/services/meta_prompter.py", "instrucoes_ia"),
    ("backend-crm/automations/assistente_ia/llm.py", "instrucoes_ia"),
    ("backend-crm/services/ai_playbooks/__init__.py", "instrucoes_ia"),
    ("backend-crm/services/spy_agent/module_strategy.py", "instrucoes_ia"),
    ("backend-crm/services/collab_monitor/classifier.py", "instrucoes_ia"),
    ("backend-executors/app/runners/sales_flow_webhook.py", "instrucoes_ia"),
]


@pytest.mark.parametrize("caminho, esperada", POR_CAMINHO)
def test_caminho_sobe(caminho, esperada):
    assert esperada in categorias([caminho])


def test_ficheiro_pode_tocar_em_duas_categorias():
    assert categorias(["backend-core/app/models/subscription.py"]) == ["pagamento", "base_de_dados"]
    assert categorias(["backend-executors/app/runners/sales_flow_webhook.py"]) == [
        "envio_real",
        "instrucoes_ia",
    ]


def test_barras_do_windows_e_prefixo_relativo():
    assert categorias(["backend-crm\\services\\efi_client.py"]) == ["pagamento"]
    assert categorias(["./backend-crm/database.py"]) == ["base_de_dados"]


NAO_SOBE = [
    "website/src/index.css",
    "website/public/hero-mascot.webp",
    "frontend-crm/src/components/KanbanColumn.tsx",
    "frontend-crm/src/components/LeadCard.tsx",
    "frontend-crm/src/pages/UsoDoPlano.tsx",
    "frontend-crm/src/lib/prefix.ts",
    "backend-crm/routes/appointments.py",
    "backend-crm/services/followup_state.py",
    "backend-crm/tests/test_followup_state.py",
    "agent-local/main.py",
    # documentação não muda comportamento, mesmo quando fala de temas sensíveis
    "docs/plans/reembolso-melhorias-futuras.md",
    "docs/plans/plans-subscriptions.md",
    "docs/architecture/billing-efi.md",
    "docs/architecture/sales-flow.md",
    "docs/prompts_llms.md",
    "docs/implementations/feat-tags-de-contato.md",
    "README.md",
]


@pytest.mark.parametrize("caminho", NAO_SOBE)
def test_caminho_nao_sobe(caminho):
    assert categorias([caminho]) == []


# --------------------------------------------------------------------------
# Pelas linhas alteradas, em ficheiros que pelo nome não subiriam
# --------------------------------------------------------------------------

POR_LINHA = [
    ('    ensure_column(conn, "leads", "tag_ids", "TEXT")', "base_de_dados"),
    ('    cur.execute("ALTER TABLE leads ADD COLUMN nota TEXT")', "base_de_dados"),
    ('    conn.execute("create table if not exists tags (id integer)")', "base_de_dados"),
    ('    cur.execute("DROP INDEX idx_leads_phone")', "base_de_dados"),
    ('    conn.execute("CREATE UNIQUE INDEX ux_tags ON tags(user_id, name)")', "base_de_dados"),
    ("    nota = Column(String, nullable=True)", "base_de_dados"),
    ('    __tablename__ = "tags"', "base_de_dados"),
    ("    await send_whatsapp_direct(user_id, phone, texto)", "envio_real"),
    ("    core.send_text(numero, mensagem)", "envio_real"),
    ("    send_email(destinatario, assunto, corpo)", "envio_real"),
    ("    send_followup_now(lead_id)", "envio_real"),
    ('    enqueue_job("whatsapp.send.local", payload)', "envio_real"),
    ("import smtplib", "envio_real"),
    ('    system_prompt = f"Você responde como {nome}"', "instrucoes_ia"),
    ('    prompt += "\\nResponde em português."', "instrucoes_ia"),
    ('    "Você é um assistente de vendas."', "instrucoes_ia"),
    ("    from services.efi_client import criar_cobranca", "pagamento"),
    ('    chave = os.environ["EFI_CLIENT_SECRET"]', "pagamento"),
]


@pytest.mark.parametrize("linha, esperada", POR_LINHA)
def test_linha_sobe(linha, esperada):
    ficheiro = "backend-crm/routes/leads.py"
    assert categorias([ficheiro], {ficheiro: [linha]}) == [esperada]


LINHAS_NORMAIS = [
    "    return {'ok': True}",
    "    if prompt_enviado == True:",
    "    lead = get_lead(conn, user_id, lead_id)",
    "    # ver coluna do Kanban",
    "    cur.execute('SELECT id FROM leads WHERE user_id = ?', (user_id,))",
    "    logger.info('mensagem recebida')",
]


@pytest.mark.parametrize("linha", LINHAS_NORMAIS)
def test_linha_normal_nao_sobe(linha):
    ficheiro = "backend-crm/routes/leads.py"
    assert categorias([ficheiro], {ficheiro: [linha]}) == []


def test_linhas_de_teste_e_de_documentacao_sao_ignoradas():
    linha = ['    conn.execute("CREATE TABLE leads (id INTEGER)")']
    assert categorias(["backend-crm/tests/test_leads.py"], {"backend-crm/tests/test_leads.py": linha}) == []
    assert categorias(["backend-executors/scripts/test_x.py"], {"backend-executors/scripts/test_x.py": linha}) == []
    assert categorias(["docs/architecture/leads-schema.md"], {"docs/architecture/leads-schema.md": linha}) == []


def test_motivo_mostra_ficheiro_e_linha():
    ficheiro = "backend-crm/routes/leads.py"
    resultado = cs.classificar([ficheiro], {ficheiro: ['    ensure_column(conn, "leads", "x", "TEXT")']})
    assert resultado["base_de_dados"] == [f'{ficheiro}: ensure_column(conn, "leads", "x", "TEXT")']


# --------------------------------------------------------------------------
# Leitura do diff
# --------------------------------------------------------------------------

DIFF = """\
diff --git a/backend-crm/routes/leads.py b/backend-crm/routes/leads.py
index 111..222 100644
--- a/backend-crm/routes/leads.py
+++ b/backend-crm/routes/leads.py
@@ -10,0 +11,2 @@
+    ensure_column(conn, "leads", "nota", "TEXT")
+-- isto é conteúdo, não cabeçalho
@@ -30 +32 @@
--- linha removida que começa por dois hífenes
+++ linha acrescentada que começa por dois sinais de mais
diff --git a/website/novo.css b/website/novo.css
new file mode 100644
--- /dev/null
+++ b/website/novo.css
@@ -0,0 +1 @@
+body { margin: 0 }
diff --git a/imagem.png b/imagem.png
Binary files a/imagem.png and b/imagem.png differ
"""


def test_ler_diff_separa_ficheiros_e_linhas():
    ficheiros, linhas = cs.ler_diff(DIFF)
    assert ficheiros == ["backend-crm/routes/leads.py", "website/novo.css"]
    assert linhas["backend-crm/routes/leads.py"] == [
        '    ensure_column(conn, "leads", "nota", "TEXT")',
        "-- isto é conteúdo, não cabeçalho",
        "-- linha removida que começa por dois hífenes",
        "++ linha acrescentada que começa por dois sinais de mais",
    ]
    assert linhas["website/novo.css"] == ["body { margin: 0 }"]


# --------------------------------------------------------------------------
# Ponta a ponta, num repositório temporário
# --------------------------------------------------------------------------


def _git(pasta, *argumentos):
    subprocess.run(
        ["git", "-c", "user.name=teste", "-c", "user.email=teste@example.com", "-c", "commit.gpgsign=false", *argumentos],
        cwd=pasta,
        check=True,
        capture_output=True,
    )


def _escrever(pasta, caminho, texto):
    destino = pasta / caminho
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(texto, encoding="utf-8")


@pytest.fixture
def repositorio(tmp_path):
    _git(tmp_path, "init", "-q", "-b", "main")
    _escrever(tmp_path, "backend-crm/routes/leads.py", "def listar():\n    return []\n")
    _escrever(tmp_path, "website/src/index.css", "body { margin: 0 }\n")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "base")
    _git(tmp_path, "checkout", "-q", "-b", "claude/item")
    return tmp_path


def _correr(pasta, *extra):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--base", "main", "--ramo", "claude/item", *extra],
        cwd=pasta,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_ramo_so_com_estilo_nao_sobe(repositorio):
    _escrever(repositorio, "website/src/index.css", "body { margin: 4px }\n")
    _git(repositorio, "commit", "-q", "-am", "estilo")
    resultado = _correr(repositorio)
    assert resultado.returncode == 0
    assert "NÃO SOBE" in resultado.stdout


def test_ramo_que_cria_coluna_sobe(repositorio):
    _escrever(
        repositorio,
        "backend-crm/routes/leads.py",
        'def listar():\n    ensure_column(conn, "leads", "nota", "TEXT")\n    return []\n',
    )
    _git(repositorio, "commit", "-q", "-am", "coluna")
    resultado = _correr(repositorio, "--json")
    assert resultado.returncode == 1
    saida = json.loads(resultado.stdout)
    assert saida["sobe"] is True
    assert [c["id"] for c in saida["categorias"]] == ["base_de_dados"]


def test_alteracao_feita_na_base_depois_da_separacao_nao_conta(repositorio):
    _escrever(repositorio, "website/src/index.css", "body { margin: 4px }\n")
    _git(repositorio, "commit", "-q", "-am", "estilo")
    _git(repositorio, "checkout", "-q", "main")
    _escrever(repositorio, "backend-crm/services/efi_client.py", "x = 1\n")
    _git(repositorio, "add", ".")
    _git(repositorio, "commit", "-q", "-m", "pagamento na main")
    assert _correr(repositorio).returncode == 0


def test_ficheiro_apagado_tambem_conta(repositorio):
    _git(repositorio, "checkout", "-q", "main")
    _escrever(repositorio, "backend-crm/services/efi_client.py", "x = 1\n")
    _git(repositorio, "add", ".")
    _git(repositorio, "commit", "-q", "-m", "pagamento")
    _git(repositorio, "checkout", "-q", "-B", "claude/item")
    _git(repositorio, "rm", "-q", "backend-crm/services/efi_client.py")
    _git(repositorio, "commit", "-q", "-m", "apaga")
    assert _correr(repositorio).returncode == 1


def test_base_inexistente_e_erro_e_nao_passa_em_silencio(repositorio):
    resultado = subprocess.run(
        [sys.executable, str(SCRIPT), "--base", "nao-existe", "--ramo", "claude/item"],
        cwd=repositorio,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert resultado.returncode == 2
    assert "SOBE" in resultado.stderr
