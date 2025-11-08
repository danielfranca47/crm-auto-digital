"""Executa jobs de WhatsApp via Selenium local."""
from __future__ import annotations

import logging
import time
import urllib.parse
from pathlib import Path
from typing import Any, Dict, Optional

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

from .config import settings

logger = logging.getLogger(__name__)


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

    def send_message(self, payload: Dict[str, Any]) -> Dict[str, str]:
        driver = self.ensure_driver()
        phone = payload.get("phone")
        message = payload.get("body")

        if not phone or not message:
            raise ValueError("Payload incompleto para job whatsapp_send")

        logger.info("Abrindo WhatsApp Web para %s", phone)
        driver.get("https://web.whatsapp.com")

        # Aguarda painel carregar (usuário precisa ter feito login previamente)
        WebDriverWait(driver, 60).until(
            EC.presence_of_element_located((By.ID, "side"))
        )

        # Esta implementação é um MVP simplificado: apenas abre a tela de mensagem usando a URL API
        # (o usuário confirma e envia manualmente, mantendo a sessão ativa).
        encoded = urllib.parse.quote_plus(message)
        send_url = f"https://web.whatsapp.com/send?phone={phone}&text={encoded}"
        driver.get(send_url)

        # Dá alguns segundos para o usuário visualizar a mensagem pré-preenchida
        time.sleep(5)
        logger.info("Mensagem preparada para %s", phone)

        return {"notes": "Mensagem preparada no WhatsApp Web"}


runner = WhatsAppRunner()
