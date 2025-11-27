import base64
import os
import time
import threading
from dataclasses import dataclass
from typing import Optional

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import SessionNotCreatedException, WebDriverException

# Perfil persistente (reutiliza sessão logada)
PROFILE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "whatsapp_profile")
os.makedirs(PROFILE_DIR, exist_ok=True)

@dataclass
class SessionState:
    driver: Optional[webdriver.Chrome] = None
    logged: bool = False
    lock: threading.Lock = threading.Lock()

class WhatsAppQRManager:
    def __init__(self):
        self.state = SessionState()

    # ------------------------ setup webdriver ------------------------

    def _build_options(self, use_persistent_profile: bool = True):
        opts = webdriver.ChromeOptions()
        if use_persistent_profile:
            opts.add_argument(f"--user-data-dir={os.path.abspath(PROFILE_DIR)}")
        # Flags úteis no Windows
        opts.add_argument("--disable-gpu")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--remote-allow-origins=*")
        # Diminui barulho de logs e ajuda na inicialização
        opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        opts.add_experimental_option("useAutomationExtension", False)
        return opts

    def _new_driver(self, use_persistent_profile: bool = True):
        service = Service(ChromeDriverManager().install())
        options = self._build_options(use_persistent_profile=use_persistent_profile)
        drv = webdriver.Chrome(service=service, options=options)
        drv.set_page_load_timeout(60)
        return drv

    def _is_session_alive(self, driver) -> bool:
        try:
            _ = driver.title  # ping simples
            return True
        except Exception:
            return False

    def _ensure_driver(self):
        # Se já temos driver, valide a sessão
        if self.state.driver:
            if self._is_session_alive(self.state.driver):
                return self.state.driver
            # sessão morta → limpar
            try:
                self.state.driver.quit()
            except Exception:
                pass
            self.state.driver = None

        with self.state.lock:
            if self.state.driver and self._is_session_alive(self.state.driver):
                return self.state.driver

            # 1ª tentativa: perfil persistente
            try:
                print("[WA] Iniciando Chrome (perfil persistente)...")
                driver = self._new_driver(use_persistent_profile=True)
            except (SessionNotCreatedException, WebDriverException) as e:
                print("[WA] Falha com perfil persistente:", e)
                print("[WA] Tentando com perfil LIMPO (temporário)...")
                driver = self._new_driver(use_persistent_profile=False)

            self.state.driver = driver
            self.state.logged = False
            return driver

    # ----------- navegação com lock global (evita corrida) -----------

    def navigate(self, driver, url: str):
        """Navega para a URL sob o lock global para evitar corrida com outras rotas/worker."""
        with self.state.lock:
            driver.get(url)

    def _goto_wa(self, driver, mode:str="active"):
        """
        Leva para web.whatsapp.com.
        - passive: navega até WA se estiver fora; se já estiver, NUNCA dá refresh.
        - active: navega até WA; se já estiver, só refresca se não houver QR visível.
        """
        cur = ""
        try:
            cur = driver.current_url or ""
        except Exception:
            pass

        if "web.whatsapp.com" not in cur:
            print(f"[WA] Go to web.whatsapp.com (mode={mode}) ...")
            driver.get("https://web.whatsapp.com/")
            return
        
        if mode == "passive":
           print("[WA] Passive: already on WA — skip refresh.")
           return 

        # mode == "active"
        #Ja estamos em web.whatsapp.com - evite refresh se QR estiver na tela
        try:
            if self._is_qr_visible(driver):                
                print("[WA] Skip refresh - QR visível (modo passivo).")
                return
        except Exception:
            pass

        print("[WA] Refresh em web.whatsapp.com...")
        driver.refresh()

    # ------------------------ heurísticas de estado ------------------------

    def _is_qr_visible(self, driver) -> bool:
        """
        Tela de QR / login: container com [data-ref] ou [data-testid='qrcode'],
        e, em alguns builds, canvas com aria-label “Scan/Escanear”.
        """
        try:
            if driver.find_elements(By.CSS_SELECTOR, "[data-ref]"):
                return True
            if driver.find_elements(By.CSS_SELECTOR, "[data-testid='qrcode']"):
                return True
            if driver.find_elements(By.CSS_SELECTOR, "canvas[aria-label*='Scan'],canvas[aria-label*='Escan'],canvas[aria-label*='Escaneie']"):
                return True
        except Exception:
            pass
        return False

    def _is_chat_visible(self, driver) -> bool:
        """
        Página logada: presença do elemento #side (barra lateral) ou chat-list.
        """
        try:
            if driver.find_elements(By.ID, "side"):
                return True
            if driver.find_elements(By.CSS_SELECTOR, "[data-testid='chat-list']"):
                return True
        except Exception:
            pass
        return False

    def _detect_logged(self, driver, timeout: int = 8) -> bool:
        """
        Loop curto checando primeiro 'QR visível' (não logado) e depois '#side' (logado).
        """
        end = time.time() + timeout
        while time.time() < end:
            if self._is_qr_visible(driver):
                return False
            if self._is_chat_visible(driver):
                return True
            time.sleep(0.5)
        return False

    # ------------------------ rotas chamadas pelas APIs ------------------------

    def iniciar_e_capturar_qr(self):
        driver = self._ensure_driver()

        # Se já estiver logado, não precisa exibir QR
        if self._detect_logged(driver, timeout=3):
            self.state.logged = True
            return {"status": "logado", "logado": True}

        try:
            self._goto_wa(driver)
            # Espera o QR aparecer
            qr_element = WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[data-ref], [data-testid='qrcode']"))
            )
            time.sleep(1.2)
            img_bytes = qr_element.screenshot_as_png
            b64 = base64.b64encode(img_bytes).decode("utf-8")
            return {"status": "qr_disponivel", "qr_code": b64, "formato": f"data:image/png;base64,{b64}"}
        except Exception as e:
            # Fallback: tenta um driver limpo
            try:
                print("[WA] Tentando fallback completo (novo driver, perfil limpo)...")
                self.stop()
                driver = self._new_driver(use_persistent_profile=False)
                self.state.driver = driver
                self._goto_wa(driver)
                qr_element = WebDriverWait(driver, 30).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "[data-ref], [data-testid='qrcode']"))
                )
                time.sleep(1.2)
                img_bytes = qr_element.screenshot_as_png
                b64 = base64.b64encode(img_bytes).decode("utf-8")
                return {"status": "qr_disponivel", "qr_code": b64, "formato": f"data:image/png;base64,{b64}"}
            except Exception as e2:
                return {"status": "erro", "mensagem": f"{type(e).__name__}: {e} | fallback: {type(e2).__name__}: {e2}"}

    def novo_qr(self):
        driver = self._ensure_driver()
        try:
            self._goto_wa(driver)
            time.sleep(2)
            return self.iniciar_e_capturar_qr()
        except Exception as e:
            return {"status": "erro", "mensagem": str(e)}

    # backend/automations/whatsapp/qr_manager.py

    def verificar_login(self, passive: bool = False):
        driver = self._ensure_driver()
        print(f"[WA]Verificar_login(passive={passive})")

        # Abas que já existiam ANTES desta verificação
        existing_handles = list(driver.window_handles)
        had_tabs_before = len(existing_handles) > 0

        self._goto_wa(driver, mode=("passive" if passive else "active"))

        if not passive:
            try:
                WebDriverWait(driver, 15).until(
                    lambda d: (
                        len(d.find_elements(By.ID, "side")) > 0
                        or len(d.find_elements(By.CSS_SELECTOR, "[data-ref]")) > 0
                    )
                )
            except Exception:
                pass

        ok = self._detect_logged(driver, timeout=5 if passive else 8)
        self.state.logged = ok

        if ok:
            try:
                # Fecha SEMPRE a aba usada para verificação
                driver.close()

                # Se existirem outras abas, volta para a primeira
                remaining = driver.window_handles
                if remaining:
                    driver.switch_to.window(remaining[0])
                else:
                    # Se não houver mais abas, limpar o driver
                    driver.quit()
                    self.driver = None

            except Exception:
                pass

        return {"status": "logado" if ok else "aguardando", "logado": ok}

    def stop(self):
        with self.state.lock:
            if self.state.driver:
                try:
                    self.state.driver.quit()
                except Exception:
                    pass
                self.state.driver = None
                self.state.logged = False
        return {"ok": True, "stopped": True}

# instância global
qr_manager = WhatsAppQRManager()
