# backend/automations/whatsapp/whatsapp_worker.py
import threading
import time
import traceback
from dataclasses import dataclass
from typing import Optional, Tuple
from urllib.parse import quote

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from database import get_connection
from automations.whatsapp.qr_manager import qr_manager  # reuso do gerenciador

# Tempos
WAIT_SHORT = 10
WAIT_MED = 25
WAIT_LONG = 60
WAIT_AFTER_TYPE = 1.0   # respiro após digitar a mensagem no composer
IDLE_TIMEOUT_SEC = 12.0 # Auto-stop quando fila ficar vazia

# Seletores
CSS_COMPOSERS = [
    "footer [data-testid='conversation-compose-box-input'] div[contenteditable='true']",
    "#main footer div[contenteditable='true']",
    "footer div[contenteditable='true']",
]
CSS_SEND_BTNS = [
    "[data-testid='compose-btn-send']",
]
# XPATH 'estrito' do botão + fallback genérico
XPATH_SEND_BTN_STRICT = "//*[@id='main']/footer/div[1]/div/span/div/div[2]/div/div[4]/button/span"
XPATH_SEND_BTN_FALLBACK = "//*[@id='main']/footer//button[.//span or .//*[@data-icon]]"

# “Continuar para conversa”
XPATH_CONTINUE = (
    "//a[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'continuar') "
    " or contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'continue')]"
)
CSS_CONTINUE_TESTID = "[data-testid='fallback_block_continue']"

# Heurística de bolhas de mensagem enviada
BUBBLE_OUT_CANDIDATES = [
    "div.message-out",
    "div[data-testid='msg-container'] div.message-out",
    "div[data-testid='msg-container'][data-visual-context='outgoing']",
]

@dataclass
class WorkerState:
    running: bool = False
    last_error: Optional[str] = None
    processed_ok: int = 0
    processed_fail: int = 0
    last_item: Optional[dict] = None


class WhatsWorker:
    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self.state = WorkerState()

    # ---------- controle ----------
    def start(self):
        if self._thread and self._thread.is_alive():
            print("[Worker] já está rodando.")
            return False
        self._stop.clear()
        self.state = WorkerState(running=True)
        self._thread = threading.Thread(target=self._run_loop, name="WhatsWorker", daemon=True)
        self._thread.start()
        print("[Worker] iniciado.")
        return True

    def stop(self):
        self._stop.set()
        self.state.running = False
        print("[Worker] stop solicitado.")
        return True

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # ---------- helpers de navegação ----------
    def _goto_wa_force(self, driver, retries: int = 3) -> bool:
        for i in range(retries):
            try:
                with qr_manager.state.lock:
                    print(f"[Worker] Navegando para WA (tentativa {i+1}/{retries})...")
                    driver.get("https://web.whatsapp.com")
                ok = WebDriverWait(driver, 15).until(
                    lambda d: "whatsapp.com" in (getattr(d, "current_url", "") or "")
                )
                if ok:
                    print("[Worker] Estamos em web.whatsapp.com.")
                    return True
            except Exception as e:
                print(f"[Worker] Falha ao navegar para WA: {e}")
            time.sleep(2)
        return False

    # ---------- DB ----------
    def _fetch_one_pending(self) -> Optional[dict]:
        with get_connection() as conn:
            row = conn.execute("""
                SELECT id, lead_id, message_id, phone, body, attempts, enqueuedAt
                  FROM prospection_whatsapp_queue
                 WHERE status='pending'
                 ORDER BY enqueuedAt ASC
                 LIMIT 1
            """).fetchone()
            return dict(row) if row else None

    def _mark(self, item_id: int, lead_id: int, message_id: int, ok: bool, notes: str = ""):
        status = "sent" if ok else "failed"
        with get_connection() as conn:
            conn.execute("""
                UPDATE prospection_whatsapp_queue
                   SET status=?, processedAt=CURRENT_TIMESTAMP,
                       attempts = attempts + 1,
                       lastError = ?
                 WHERE id=? AND status='pending'
            """, (status, notes, item_id))
            conn.execute("""
                INSERT INTO prospection_logs (lead_id, channel, message_id, action, notes)
                VALUES (?, 'whatsapp', ?, ?, ?)
            """, (lead_id, message_id, status, notes))
            conn.commit()

    def _update_lead_category(self, lead_id: int, new_category: str, note: str = ""):
        """
        Atualiza a coluna leads.category e registra um log de movimento.
        """
        try:
            with get_connection() as conn:
                conn.execute(
                    "UPDATE leads SET category=?, lastMovement=CURRENT_TIMESTAMP WHERE id=?",
                    (new_category, lead_id),
                )
                conn.execute(
                    """
                    INSERT INTO prospection_logs (lead_id, channel, message_id, action, notes)
                    VALUES (?, 'whatsapp', NULL, 'moved_stage', ?)
                    """,
                    (lead_id, f"auto:{new_category} {note}".strip() or None),
                )
                conn.commit()
            print(f"[Worker] Lead {lead_id} → categoria='{new_category}'.")
        except Exception as e:
            print(f"[Worker] Falha ao atualizar categoria do lead {lead_id}: {e}")

    # ---------- util/esperas ----------
    def _wait_for_composer(self, driver, timeout: int):
        end = time.time() + timeout
        while time.time() < end:
            for sel in CSS_COMPOSERS:
                try:
                    el = WebDriverWait(driver, 3).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, sel))
                    )
                    time.sleep(0.2)
                    return el
                except Exception:
                    pass
            time.sleep(0.2)
        raise TimeoutError("composer_timeout")

    def _maybe_click_continue_to_chat(self, driver) -> bool:
        try:
            btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, CSS_CONTINUE_TESTID))
            )
            btn.click()
            time.sleep(0.8)
            print("[Worker] Clicou em 'Continuar para conversa' (data-testid).")
            return True
        except Exception:
            pass
        try:
            btn = WebDriverWait(driver, 7).until(
                EC.element_to_be_clickable((By.XPATH, XPATH_CONTINUE))
            )
            btn.click()
            time.sleep(0.8)
            print("[Worker] Clicou em 'Continuar para conversa' (xpath).")
            return True
        except Exception:
            return False

    def _open_chat(self, driver, phone_digits: str, text: str) -> Tuple[bool, str]:
        url = f"https://web.whatsapp.com/send?phone={phone_digits}&text={quote(text)}"
        for i in range(2):
            try:
                with qr_manager.state.lock:
                    print(f"[Worker] Abrindo chat: {phone_digits} (tentativa {i+1}/2)")
                    driver.get(url)
                time.sleep(1.2)

                if driver.find_elements(By.CSS_SELECTOR, "[data-ref]"):
                    print("[Worker] Tela de QR detectada (não logado).")
                    return False, "not_logged"

                self._maybe_click_continue_to_chat(driver)

                try:
                    alerts = driver.find_elements(By.CSS_SELECTOR, "[data-testid='alert']")
                    for a in alerts:
                        txt = (a.text or "").strip().lower()
                        if ("número" in txt and "inválid" in txt) or ("invalid" in txt and "number" in txt):
                            print("[Worker] Número inválido detectado.")
                            return False, "invalid_number"
                except Exception:
                    pass

                self._wait_for_composer(driver, timeout=WAIT_LONG)
                print("[Worker] Composer disponível.")
                return True, ""
            except Exception as e:
                print(f"[Worker] Falha ao abrir chat (tentativa {i+1}): {e}")
                time.sleep(1.5)

        return False, "open_timeout"

    def _count_out_bubbles(self, driver) -> int:
        total = 0
        for sel in BUBBLE_OUT_CANDIDATES:
            try:
                total += len(driver.find_elements(By.CSS_SELECTOR, sel))
            except Exception:
                pass
        return total

    def _has_send_button(self, driver) -> bool:
        try:
            return len(driver.find_elements(By.CSS_SELECTOR, "[data-testid='compose-btn-send']")) > 0
        except Exception:
            return False

    def _composer_text(self, composer) -> str:
        try:
            # contenteditable → melhor usar textContent
            return (composer.get_attribute("textContent") or "").strip()
        except Exception:
            return ""

    def _confirm_sent(self, driver, composer, pre_bubbles: int, timeout: int = WAIT_MED) -> bool:
        """
        Confirma envio por:
          1) aumento de bolhas de saída, OU
          2) desaparecimento do botão enviar E composer vazio (sinal de flush)
        """
        end = time.time() + timeout
        while time.time() < end:
            post = self._count_out_bubbles(driver)
            if post > pre_bubbles:
                print("[Worker] Envio confirmado por bolha.")
                return True

            has_btn = self._has_send_button(driver)
            comp_txt = self._composer_text(composer)
            if (not has_btn) and comp_txt == "":
                print("[Worker] Envio confirmado por composer vazio + botão ausente.")
                return True

            time.sleep(0.25)
        return False

    # ---------- envio ----------
    def _send_whatsapp(self, driver, phone_digits: str, text: str) -> Tuple[bool, str]:
        ok_open, reason = self._open_chat(driver, phone_digits, text)
        if not ok_open:
            return False, reason

        composer = self._wait_for_composer(driver, timeout=WAIT_MED)

        # força o texto no composer (sempre)
        try:
            composer.click()
            time.sleep(0.1)
            composer.send_keys(Keys.CONTROL, 'a'); time.sleep(0.05)
            composer.send_keys(Keys.BACK_SPACE);   time.sleep(0.05)
            composer.send_keys(text)
            time.sleep(WAIT_AFTER_TYPE)
        except Exception:
            try:
                composer.click()
            except Exception:
                pass

        pre = self._count_out_bubbles(driver)

        # ENTER primeiro; depois botão
        sent = False
        reason_fail = "sendfail"
        try:
            composer.send_keys(Keys.ENTER)
            sent = True
            print("[Worker] Enviado via ENTER no composer.")
        except Exception:
            sent = False

        if not sent:
            try:
                btn = None
                for css in CSS_SEND_BTNS:
                    try:
                        btn = WebDriverWait(driver, 3).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, css))
                        )
                        if btn:
                            break
                    except Exception:
                        pass
                if not btn:
                    try:
                        btn = WebDriverWait(driver, 3).until(
                            EC.element_to_be_clickable((By.XPATH, XPATH_SEND_BTN_STRICT))
                        )
                    except Exception:
                        btn = None
                if not btn:
                    btn = WebDriverWait(driver, 3).until(
                        EC.element_to_be_clickable((By.XPATH, XPATH_SEND_BTN_FALLBACK))
                    )
                btn.click()
                sent = True
                print("[Worker] Enviado via botão (fallback).")
            except Exception:
                sent = False
                reason_fail = "send_button_not_found"

        if not sent:
            return False, reason_fail

        # Confirma envio (melhorado)
        if self._confirm_sent(driver, composer, pre, timeout=WAIT_MED):
            return True, ""

        return False, "send_confirm_timeout"

    # ---------- loop ----------
    def _run_loop(self):
        driver = None
        idle_sleep = 2.0  # quando não há itens, dorme e NÃO navega
        last_activity_ts = time.time()  # marca quando houve “trabalho real” pela última vez

        while not self._stop.is_set():
            try:
                # 1) pega um pendente antes de navegar
                item = self._fetch_one_pending()
                self.state.last_item = item

                if not item:
                    # Fila vazia → verifica ociosidade para auto-stop
                    idle_for = time.time() - last_activity_ts
                    if idle_for >= IDLE_TIMEOUT_SEC:
                        print(f"[Worker] Fila vazia por ~{int(idle_for)}s — auto-stop.")
                        break
                    time.sleep(idle_sleep)
                    continue

                # 2) garante driver e login apenas se vamos processar
                driver = qr_manager._ensure_driver()
                if not qr_manager._detect_logged(driver, timeout=5):
                    if not self._goto_wa_force(driver):
                        self.state.last_error = "nao_abriu_wa"
                        time.sleep(2)
                        continue
                    if not qr_manager._detect_logged(driver, timeout=10):
                        self.state.last_error = "aguardando_login"
                        print("[Worker] Aguardando login...")
                        time.sleep(3)
                        continue

                # 3) processa item
                print(f"[Worker] Processando item fila id={item['id']} lead={item['lead_id']} msg={item['message_id']}")
                phone = str(item["phone"]).strip()
                body  = str(item["body"]).strip()
                if not phone or not body:
                    self._mark(item["id"], item["lead_id"], item["message_id"], ok=False, notes="dados_incompletos")
                    # atualiza categoria → volta/permanece em to-prospect
                    self._update_lead_category(item["lead_id"], "to-prospect", "dados_incompletos")
                    self.state.processed_fail += 1
                    last_activity_ts = time.time()
                    continue

                ok, reason = self._send_whatsapp(driver, phone, body)

                if ok:
                    self._mark(item["id"], item["lead_id"], item["message_id"], ok=True, notes="")
                    # sucesso → marcar como prospectado
                    self._update_lead_category(item["lead_id"], "prospected", "envio_ok")
                    self.state.processed_ok += 1
                else:
                    self._mark(item["id"], item["lead_id"], item["message_id"], ok=False, notes=reason or "timeout")
                    # falha → volta/permanece em to-prospect com motivo
                    self._update_lead_category(item["lead_id"], "to-prospect", f"fail:{reason}")
                    self.state.processed_fail += 1
                    print(f"[Worker] Falhou envio: {reason}")

                # registrou atividade real (enviou/marcou)
                last_activity_ts = time.time()

                # pausa curta entre itens (sem navegar)
                time.sleep(0.8)

            except Exception as e:
                self.state.last_error = f"{type(e).__name__}: {e}"
                print("[Worker] EXCEPTION:", self.state.last_error)
                traceback.print_exc()
                time.sleep(2)

        self.state.running = False
        print("[Worker] finalizado.")


# Singleton
worker = WhatsWorker()
