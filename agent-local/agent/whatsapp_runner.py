"""Executa jobs de WhatsApp via Selenium local."""
from __future__ import annotations

import logging
import time
import urllib.parse
from pathlib import Path
from typing import Any, Dict, Optional

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

from .config import settings

logger = logging.getLogger(__name__)


WAIT_MED = 25
WAIT_LONG = 60
WAIT_AFTER_TYPE = 1.0

CSS_COMPOSERS = [
    "footer [data-testid='conversation-compose-box-input'] div[contenteditable='true']",
    "#main footer div[contenteditable='true']",
    "footer div[contenteditable='true']",
]

XPATH_COMPOSERS = [
    "//*[@id='main']/footer/div[1]/div/span/div/div[2]/div/div[3]/div/p",
    "//*[@id='main']/footer/div[1]/div/span/div/div[2]/div/div[3]/div/p/span",
]

CSS_SEND_BUTTONS = [
    "[data-testid='compose-btn-send']",
]

XPATH_SEND_BTN_STRICT = "//*[@id='main']/footer/div[1]/div/span/div/div[2]/div/div[4]/button/span"
XPATH_SEND_BTN_FALLBACK = "//*[@id='main']/footer//button[.//span or .//*[@data-icon]]"

CSS_CONTINUE_TESTID = "[data-testid='fallback_block_continue']"
XPATH_CONTINUE = (
    "//a[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'continuar') "
    " or contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'continue')]"
)

QR_SELECTORS = [
    "[data-ref]",
    "canvas[aria-label]",
    "div[data-testid='qrcode']",
]

BUBBLE_OUT_CANDIDATES = [
    "div.message-out",
    "div[data-testid='msg-container'] div.message-out",
    "div[data-testid='msg-container'][data-visual-context='outgoing']",
]


class WhatsAppRunner:
    def __init__(self) -> None:
        self._driver: Optional[webdriver.Chrome] = None

    def ensure_driver(self) -> webdriver.Chrome:
        if self._driver:
            return self._driver

        options = webdriver.ChromeOptions()
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        if settings.headless:
            options.add_argument("--headless=new")

        profile = settings.chrome_profile_path
        if profile:
            Path(profile).parent.mkdir(parents=True, exist_ok=True)
            options.add_argument(f"--user-data-dir={profile}")
            logger.info("Reutilizando perfil do Chrome em %s", profile)

        service = Service(ChromeDriverManager().install())
        self._driver = webdriver.Chrome(service=service, options=options)
        self._driver.set_window_size(1200, 900)
        return self._driver

    def close(self) -> None:
        if self._driver:
            try:
                self._driver.quit()
            finally:
                self._driver = None

    # ------------------------------------------------------------------
    # Helpers privados
    # ------------------------------------------------------------------
    def _is_qr_visible(self, driver: webdriver.Chrome) -> bool:
        for selector in QR_SELECTORS:
            try:
                if driver.find_elements(By.CSS_SELECTOR, selector):
                    return True
            except Exception:  # noqa: BLE001 - Selenium pode lançar vários erros
                continue
        return False

    def _ensure_logged_in(self, driver: webdriver.Chrome) -> None:
        logger.debug("Validando sessão do WhatsApp Web")
        driver.get("https://web.whatsapp.com")
        try:
            WebDriverWait(driver, WAIT_LONG).until(
                EC.presence_of_element_located((By.ID, "side"))
            )
        except TimeoutException as exc:  # noqa: PERF203 - precisamos diferenciar
            if self._is_qr_visible(driver):
                raise RuntimeError("WhatsApp Web não está logado (QR code exibido)") from exc
            raise RuntimeError("Não foi possível carregar a interface do WhatsApp Web") from exc

    def _maybe_click_continue(self, driver: webdriver.Chrome) -> None:
        try:
            btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, CSS_CONTINUE_TESTID))
            )
            btn.click()
            time.sleep(0.8)
            return
        except Exception:  # noqa: BLE001 - tentativa opcional
            pass
        try:
            btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, XPATH_CONTINUE))
            )
            btn.click()
            time.sleep(0.8)
        except Exception:
            return

    def _wait_for_composer(self, driver: webdriver.Chrome, timeout: int = WAIT_LONG):
        end = time.time() + timeout
        while time.time() < end:
            for selector in CSS_COMPOSERS:
                try:
                    element = WebDriverWait(driver, 3).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    time.sleep(0.2)
                    return element
                except Exception:
                    continue
            for xpath in XPATH_COMPOSERS:
                try:
                    element = WebDriverWait(driver, 3).until(
                        EC.presence_of_element_located((By.XPATH, xpath))
                    )
                    time.sleep(0.2)
                    return element
                except Exception:
                    continue
            time.sleep(0.2)
        raise TimeoutError("composer_timeout")

    def _detect_invalid_number(self, driver: webdriver.Chrome) -> bool:
        try:
            alerts = driver.find_elements(By.CSS_SELECTOR, "[data-testid='alert']")
            for alert in alerts:
                text = (alert.text or "").strip().lower()
                if ("inválid" in text and "número" in text) or ("invalid" in text and "number" in text):
                    return True
        except Exception:  # noqa: BLE001
            return False
        return False

    def _open_chat(self, driver: webdriver.Chrome, phone: str, message: str):
        encoded = urllib.parse.quote_plus(message)
        url = f"https://web.whatsapp.com/send?phone={phone}&text={encoded}"
        for attempt in range(2):
            logger.debug("Abrindo chat do WhatsApp (tentativa %s)", attempt + 1)
            driver.get(url)
            time.sleep(1.2)

            if self._is_qr_visible(driver):
                raise RuntimeError("WhatsApp Web não está logado (QR code exibido)")

            self._maybe_click_continue(driver)

            if self._detect_invalid_number(driver):
                raise RuntimeError("Número de WhatsApp inválido ou não cadastrado")

            try:
                composer = self._wait_for_composer(driver, timeout=WAIT_LONG)
                logger.debug("Composer localizado")
                return composer
            except TimeoutError:
                logger.debug("Timeout aguardando composer, nova tentativa")
                continue

        raise RuntimeError("Não foi possível abrir a conversa no WhatsApp (timeout)")

    def _count_out_bubbles(self, driver: webdriver.Chrome) -> int:
        total = 0
        for selector in BUBBLE_OUT_CANDIDATES:
            try:
                total += len(driver.find_elements(By.CSS_SELECTOR, selector))
            except Exception:  # noqa: BLE001
                continue
        return total

    def _composer_text(self, composer) -> str:
        try:
            return (composer.get_attribute("textContent") or "").strip()
        except Exception:  # noqa: BLE001
            return ""

    def _normalize_composer(self, driver: webdriver.Chrome, composer):
        """Garante interação com o campo de digitação real (mesmo nó do worker antigo)."""
        try:
            if (composer.get_attribute("contenteditable") or "").lower() == "true":
                return composer
        except Exception:
            pass
        for xpath in XPATH_COMPOSERS:
            try:
                normalized = driver.find_element(By.XPATH, xpath)
                if normalized:
                    return normalized
            except Exception:
                continue
        try:
            inner = composer.find_element(By.XPATH, ".//p")
            if inner:
                return inner
        except Exception:
            pass
        return composer

    def _send_via_enter(self, composer) -> bool:
        try:
            composer.send_keys(Keys.ENTER)
            logger.debug("Mensagem enviada via ENTER")
            return True
        except Exception:  # noqa: BLE001
            logger.debug("Falha ao enviar via ENTER", exc_info=True)
            return False

    def _find_send_button(self, driver: webdriver.Chrome):
        for css in CSS_SEND_BUTTONS:
            try:
                return WebDriverWait(driver, 3).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, css))
                )
            except Exception:
                continue
        try:
            return WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable((By.XPATH, XPATH_SEND_BTN_STRICT))
            )
        except Exception:
            pass
        try:
            return WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable((By.XPATH, XPATH_SEND_BTN_FALLBACK))
            )
        except Exception:
            return None

    def _confirm_sent(self, driver: webdriver.Chrome, composer, pre_count: int) -> bool:
        end = time.time() + WAIT_MED
        while time.time() < end:
            post_count = self._count_out_bubbles(driver)
            logger.debug("Confirmação envio: pre=%s post=%s", pre_count, post_count)
            if post_count > pre_count:
                logger.debug("Envio confirmado por nova bolha")
                return True

            has_button = bool(self._find_existing_send_button(driver))
            composer_text = self._composer_text(composer)
            logger.debug(
                "Estado composer: texto='%s' botao_envio=%s",
                composer_text,
                has_button,
            )
            if not has_button and composer_text == "":
                logger.debug("Envio confirmado por composer vazio")
                return True

            time.sleep(0.25)
        logger.debug("Confirmação de envio não detectada dentro do tempo limite")
        return False

    def _find_existing_send_button(self, driver: webdriver.Chrome) -> Optional[object]:
        for css in CSS_SEND_BUTTONS:
            try:
                elems = driver.find_elements(By.CSS_SELECTOR, css)
                if elems:
                    return elems[0]
            except Exception:
                continue
        return None

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------
    def send_message(self, payload: Dict[str, Any]) -> Dict[str, str]:
        driver = self.ensure_driver()
        phone = (payload.get("phone") or "").strip()
        message = (payload.get("body") or "").strip()

        if not phone or not message:
            raise ValueError("Payload incompleto para job whatsapp_send")

        logger.info("Iniciando envio de WhatsApp para %s", phone)

        self._ensure_logged_in(driver)

        composer = self._open_chat(driver, phone, message)
        composer = self._normalize_composer(driver, composer)
        logger.debug(
            "Composer normalizado: tag=%s contenteditable=%s",
            getattr(composer, "tag_name", "?"),
            composer.get_attribute("contenteditable"),
        )

        try:
            composer.click()
            time.sleep(0.1)
            composer.send_keys(Keys.CONTROL, "a")
            time.sleep(0.05)
            composer.send_keys(Keys.BACKSPACE)
            time.sleep(0.05)
        except Exception:  # noqa: BLE001
            logger.debug("Não foi possível limpar composer via atalho", exc_info=True)

        try:
            composer.send_keys(message)
            time.sleep(WAIT_AFTER_TYPE)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError("Falha ao preencher a mensagem no WhatsApp") from exc

        pre_count = self._count_out_bubbles(driver)
        logger.debug("Bolhas antes do envio: %s", pre_count)

        sent = self._send_via_enter(composer)
        if not sent:
            button = self._find_send_button(driver)
            if not button:
                raise RuntimeError("Não foi possível localizar o botão de envio do WhatsApp")
            button.click()
            sent = True
            logger.debug("Mensagem enviada via botão")
            time.sleep(0.2)

        if not sent:
            raise RuntimeError("Falha ao acionar envio da mensagem no WhatsApp")

        if not self._confirm_sent(driver, composer, pre_count):
            logger.error("Confirmação de envio falhou (phone=%s)", phone)
            raise RuntimeError("Não foi possível confirmar o envio da mensagem no WhatsApp")

        logger.info("Mensagem enviada com sucesso para %s", phone)
        return {"notes": f"Mensagem enviada para {phone}"}


runner = WhatsAppRunner()
