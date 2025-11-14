"""Runner responsável por executar automações do WhatsApp Web."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import quote

from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver import Chrome, ChromeOptions
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

from .config import AgentConfig

logger = logging.getLogger(__name__)

COMPOSER_SELECTOR = "div[contenteditable='true'][data-testid='conversation-compose-box-input']"
SEND_BUTTON_SELECTOR = "button[data-testid='compose-btn-send']"


class WhatsAppRunner:
    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self._driver: Optional[Chrome] = None

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
        return driver

    def _ensure_driver(self) -> Chrome:
        if self._driver is None:
            self._driver = self._build_driver()
        return self._driver

    def close(self) -> None:
        if self._driver is not None:
            try:
                self._driver.quit()
            except Exception:  # pragma: no cover - apenas tentativa de cleanup
                pass
            self._driver = None

    # ---------- fluxo principal ----------

    def send_whatsapp(self, *, phone: str, message: str) -> Dict[str, str]:
        driver = self._ensure_driver()
        encoded_message = quote(message)
        url = f"https://web.whatsapp.com/send?phone={phone}&text={encoded_message}&app_absent=0"

        logger.info("Abrindo conversa com %s", phone)
        driver.get(url)
        self._wait_for_qr_if_needed(driver)

        composer = self._wait_for_composer(driver)
        composer.click()
        time.sleep(0.3)

        # WhatsApp pode preencher automaticamente o texto via querystring.
        # Forçamos o foco para garantir que o botão de enviar apareça.
        send_button = self._wait_for_send_button(driver)
        send_button.click()
        logger.info("Mensagem enviada para %s", phone)

        return {"status": "sent", "notes": "ok"}

    # ---------- waits ----------

    def _wait_for_composer(self, driver: Chrome, timeout: int = 30):
        try:
            return WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, COMPOSER_SELECTOR))
            )
        except TimeoutException as exc:
            logger.error("Composer não encontrado: %s", exc)
            raise

    def _wait_for_send_button(self, driver: Chrome, timeout: int = 30):
        try:
            return WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, SEND_BUTTON_SELECTOR))
            )
        except TimeoutException:
            logger.warning("Botão de enviar não localizado; tentando fallback ENTER")
            composer = self._wait_for_composer(driver, timeout=5)
            composer.send_keys("\n")
            return composer

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
