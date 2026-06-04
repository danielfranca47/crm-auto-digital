"""Runner responsável por executar automações do WhatsApp Web."""

from __future__ import annotations
import logging
import time
from pathlib import Path
from typing import Dict, Optional, Tuple
from urllib.parse import quote

from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver import Chrome, ChromeOptions
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

from .config import AgentConfig

logger = logging.getLogger(__name__)

# --- Tempos herdados do worker antigo ---
WAIT_SHORT = 10
WAIT_MED = 25
WAIT_LONG = 60
WAIT_AFTER_TYPE = 1.0

# --- Seletores herdados do worker antigo ---
CSS_COMPOSERS = [
    "footer [data-testid='conversation-compose-box-input'] div[contenteditable='true']",
    "#main footer div[contenteditable='true']",
    "footer div[contenteditable='true']",
]
CSS_SEND_BTNS = ["[data-testid='compose-btn-send']"]
XPATH_SEND_BTN_STRICT = "//*[@id='main']/footer/div[1]/div/span/div/div[2]/div/div[4]/button/span"
XPATH_SEND_BTN_FALLBACK = "//*[@id='main']/footer//button[.//span or .//*[@data-icon]]"

XPATH_CONTINUE = (
    "//a[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'continuar') "
    " or contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'continue')]"
)
CSS_CONTINUE_TESTID = "[data-testid='fallback_block_continue']"

BUBBLE_OUT_CANDIDATES = [
    "div.message-out",
    "div[data-testid='msg-container'] div.message-out",
    "div[data-testid='msg-container'][data-visual-context='outgoing']",
]


class WhatsAppRunner:
    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self._driver: Optional[Chrome] = None
        self._main_handle: Optional[str] = None

    # ---------- driver helpers ----------

    def _build_driver(self) -> Chrome:
        options = ChromeOptions()
        options.add_argument(f"--user-data-dir={self.config.user_data_dir}")
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--no-sandbox")
        if self.config.headless:
            options.add_argument("--headless=new")
        if self.config.chrome_binary:
            options.binary_location = self.config.chrome_binary

        Path(self.config.user_data_dir).mkdir(parents=True, exist_ok=True)
        driver_path = ChromeDriverManager().install()
        service = Service(driver_path)
        driver = Chrome(service=service, options=options)
        driver.set_page_load_timeout(60)
        logger.info("Driver do Chrome inicializado com perfil %s", self.config.user_data_dir)
        self._main_handle = driver.current_window_handle
        return driver

    def _ensure_driver(self) -> Chrome:
        if self._driver is None:
            self._driver = self._build_driver()
        return self._driver

    def _ensure_whatsapp_tab(self) -> Chrome:
        driver = self._ensure_driver()

        try:
            handles = driver.window_handles
        except Exception as exc:  # pragma: no cover - proteção operacional
            logger.warning("Sessão do driver perdida (%s). Recriando instância.", exc)
            self.close()
            driver = self._ensure_driver()
            handles = driver.window_handles

        if not handles:
            driver.get("https://web.whatsapp.com")
            handles = driver.window_handles

        # Preferir a aba que já está no WhatsApp; caso contrário, manter a principal conhecida
        chosen_handle = None
        for handle in list(handles):
            try:
                driver.switch_to.window(handle)
                url = driver.current_url
                if "web.whatsapp.com" in (url or ""):
                    chosen_handle = handle
                    break
            except Exception:
                continue

        if not chosen_handle:
            main = self._main_handle or handles[0]
            if main not in handles:
                main = handles[0]
            chosen_handle = main

        self._main_handle = chosen_handle

        # Fecha abas temporárias (incluindo a de verificação) e mantém apenas a principal
        for handle in list(handles):
            if handle == chosen_handle:
                continue
            try:
                driver.switch_to.window(handle)
                driver.close()
                logger.info("Aba temporária fechada após verificação/login do WhatsApp")
            except Exception:
                logger.debug("Não foi possível fechar aba temporária: %s", handle)

        driver.switch_to.window(chosen_handle)
        return driver

    def close(self) -> None:
        if self._driver is not None:
            try:
                self._driver.quit()
            except Exception:  # pragma: no cover - apenas tentativa de cleanup
                pass
            self._driver = None

    # ---------- fluxo principal ----------

    def send_whatsapp(self, *, phone: str, message: str) -> Dict[str, str]:
        driver = self._ensure_whatsapp_tab()

        ok_open, reason = self._open_chat(driver, phone_digits=phone, text=message)
        if not ok_open:
            logger.error("Falha ao abrir chat para %s: %s", phone, reason)
            return {"status": "failed", "notes": reason}

        try:
            composer = self._wait_for_composer(driver, timeout=WAIT_MED)
        except TimeoutException:
            return {"status": "failed", "notes": "composer_timeout"}

        success, detail = self._type_and_send(driver, composer, message)
        if success:
            logger.info("Mensagem enviada para %s", phone)
            return {"status": "sent", "notes": detail or "ok"}

        logger.error("Falha ao enviar mensagem para %s: %s", phone, detail)
        return {"status": "failed", "notes": detail or "sendfail"}

    # ---------- helpers herdados ----------

    def _open_chat(self, driver: Chrome, phone_digits: str, text: str) -> Tuple[bool, str]:
        url = f"https://web.whatsapp.com/send?phone={phone_digits}&text={quote(text)}"
        for attempt in range(3):
            try:
                logger.info("Abrindo chat %s (tentativa %s)", phone_digits, attempt + 1)
                driver.get(url)
                time.sleep(1.2)

                if driver.find_elements(By.CSS_SELECTOR, "[data-ref]"):
                    if attempt < 2:
                        # Aguardar scan do QR (até 120 s) e tentar de novo
                        logger.warning("Tela de QR detectada. Aguardando scan do utilizador (120s)…")
                        self._wait_for_qr_if_needed(driver, timeout=120)
                        time.sleep(1.0)
                        continue
                    return False, "not_logged"

                self._maybe_click_continue_to_chat(driver)

                if self._detect_invalid_number(driver):
                    return False, "invalid_number"

                self._wait_for_composer(driver, timeout=WAIT_LONG)
                logger.info("Composer disponível para %s", phone_digits)
                return True, ""
            except Exception as exc:
                logger.warning("Falha ao abrir chat (%s/%s): %s", attempt + 1, 3, exc)
                time.sleep(1.5)

        return False, "open_timeout"

    def _detect_invalid_number(self, driver: Chrome) -> bool:
        try:
            alerts = driver.find_elements(By.CSS_SELECTOR, "[data-testid='alert']")
            for alert in alerts:
                txt = (alert.text or "").strip().lower()
                if ("número" in txt and "inválid" in txt) or ("invalid" in txt and "number" in txt):
                    logger.warning("Número inválido detectado pelo WhatsApp Web.")
                    return True
        except Exception:
            return False
        return False

    def _maybe_click_continue_to_chat(self, driver: Chrome) -> bool:
        try:
            btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, CSS_CONTINUE_TESTID))
            )
            btn.click()
            time.sleep(0.8)
            logger.info("Clique em 'Continuar para conversa' via data-testid")
            return True
        except Exception:
            pass
        try:
            btn = WebDriverWait(driver, 7).until(
                EC.element_to_be_clickable((By.XPATH, XPATH_CONTINUE))
            )
            btn.click()
            time.sleep(0.8)
            logger.info("Clique em 'Continuar para conversa' via xpath")
            return True
        except Exception:
            return False

    def _wait_for_composer(self, driver: Chrome, timeout: int):
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
                    continue
            time.sleep(0.2)
        raise TimeoutException("composer_timeout")

    def _type_and_send(self, driver: Chrome, composer, text: str) -> Tuple[bool, str]:
        try:
            composer.click()
            time.sleep(0.1)
            composer.send_keys(Keys.CONTROL, "a")
            time.sleep(0.05)
            composer.send_keys(Keys.BACK_SPACE)
            time.sleep(0.05)
            composer.send_keys(text)
            time.sleep(WAIT_AFTER_TYPE)
        except Exception as exc:
            logger.warning("Falha ao preencher texto no composer: %s", exc)
            try:
                composer.click()
            except Exception:
                pass

        pre_bubbles = self._count_out_bubbles(driver)

        sent = self._try_send_via_enter(composer)
        reason = "send_button_not_found"
        if not sent:
            sent = self._try_click_send(driver)
            if not sent:
                return False, reason

        if self._confirm_sent(driver, composer, pre_bubbles, timeout=WAIT_MED):
            return True, "sent"

        return False, "send_confirm_timeout"

    def _try_send_via_enter(self, composer) -> bool:
        try:
            composer.send_keys(Keys.ENTER)
            logger.info("Envio via ENTER no composer")
            return True
        except Exception:
            return False

    def _try_click_send(self, driver: Chrome) -> bool:
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
                    continue
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
            logger.info("Envio via botão de enviar")
            return True
        except Exception as exc:
            logger.error("Não foi possível clicar no botão de envio: %s", exc)
            return False

    def _count_out_bubbles(self, driver: Chrome) -> int:
        total = 0
        for sel in BUBBLE_OUT_CANDIDATES:
            try:
                total += len(driver.find_elements(By.CSS_SELECTOR, sel))
            except Exception:
                continue
        return total

    def _has_send_button(self, driver: Chrome) -> bool:
        try:
            return len(driver.find_elements(By.CSS_SELECTOR, "[data-testid='compose-btn-send']")) > 0
        except Exception:
            return False

    def _composer_text(self, composer) -> str:
        try:
            return (composer.get_attribute("textContent") or "").strip()
        except Exception:
            return ""

    def _confirm_sent(self, driver: Chrome, composer, pre_bubbles: int, timeout: int = WAIT_MED) -> bool:
        end = time.time() + timeout
        while time.time() < end:
            post = self._count_out_bubbles(driver)
            if post > pre_bubbles:
                logger.info("Envio confirmado por nova bolha de saída")
                return True

            has_btn = self._has_send_button(driver)
            comp_txt = self._composer_text(composer)
            if (not has_btn) and comp_txt == "":
                logger.info("Envio confirmado por composer vazio + ausência de botão")
                return True

            time.sleep(0.25)
        return False

    def _wait_for_qr_if_needed(self, driver: Chrome, timeout: int = 30):
        try:
            driver.find_element(By.CSS_SELECTOR, "canvas[aria-label='Scan me!']")
            logger.warning("QRCode exibido. Realize o login no WhatsApp Web.")
            WebDriverWait(driver, timeout).until_not(
                EC.presence_of_element_located((By.CSS_SELECTOR, "canvas[aria-label='Scan me!']"))
            )
        except NoSuchElementException:
            return


__all__ = ["WhatsAppRunner"]
