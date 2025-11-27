# backend/automations/whatsapp/send_debug.py
import argparse
import sys
import time
from urllib.parse import quote

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from automations.whatsapp.qr_manager import qr_manager

WAIT_SHORT = 10
WAIT_MED = 20
WAIT_LONG = 60

CSS_QR = "[data-testid='qrcode']"
COMPOSER_SELECTORS = [
    "footer [data-testid='conversation-compose-box-input'] div[contenteditable='true']",
    "footer div[contenteditable='true'][data-tab]",
    "footer div[contenteditable='true']",
]
CSS_SEND_BTN = "[data-testid='compose-btn-send']"
XPATH_SEND_BUTTON = '//*[@id="main"]/footer/div[1]/div/span/div/div[2]/div/div[4]/button/span'
CSS_MSG_OUT = "div.message-out, div[data-testid='msg-container'] div[data-testid='msg-container']"

def wait_for_composer(driver, total_timeout=WAIT_LONG):
    end = time.time() + total_timeout
    while time.time() < end:
        for css in COMPOSER_SELECTORS:
            els = driver.find_elements(By.CSS_SELECTOR, css)
            if els:
                return els[0]
        time.sleep(0.25)
    raise TimeoutError("composer_not_found")

def maybe_click_continue_to_chat(driver) -> bool:
    # textos possíveis (pt/en)
    xp = (
        "//a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'),'continuar') "
        "or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'),'continue') "
        "or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'),'whatsapp web')]"
    )
    links = driver.find_elements(By.XPATH, xp)
    for a in links:
        try:
            a.click()
            time.sleep(0.8)
            return True
        except Exception:
            pass
    return False

def count_sent_bubbles(driver) -> int:
    return len(driver.find_elements(By.CSS_SELECTOR, CSS_MSG_OUT))

def try_enter(driver) -> bool:
    before = count_sent_bubbles(driver)
    composer = wait_for_composer(driver, total_timeout=WAIT_MED)
    composer.click()
    time.sleep(0.2)
    composer.send_keys(Keys.ENTER)
    try:
        WebDriverWait(driver, WAIT_MED).until(lambda d: count_sent_bubbles(d) > before)
        return True
    except Exception:
        return False

def try_button_datatestid(driver) -> bool:
    before = count_sent_bubbles(driver)
    btn = WebDriverWait(driver, WAIT_MED).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, CSS_SEND_BTN))
    )
    btn.click()
    try:
        WebDriverWait(driver, WAIT_MED).until(lambda d: count_sent_bubbles(d) > before)
        return True
    except Exception:
        return False

def try_button_xpath(driver) -> bool:
    before = count_sent_bubbles(driver)
    btn = WebDriverWait(driver, WAIT_MED).until(
        EC.element_to_be_clickable((By.XPATH, XPATH_SEND_BUTTON))
    )
    btn.click()
    try:
        WebDriverWait(driver, WAIT_MED).until(lambda d: count_sent_bubbles(d) > before)
        return True
    except Exception:
        return False

def ensure_logged(driver):
    # se não está logado, abre/atualiza e espera barra lateral
    if not qr_manager._detect_logged(driver, timeout=3):
        qr_manager._goto_wa(driver)
        WebDriverWait(driver, WAIT_LONG).until(
            EC.presence_of_element_located((By.ID, "side"))
        )

def open_chat(driver, phone: str, text: str):
    url = f"https://web.whatsapp.com/send?phone={phone}&text={quote(text)}"
    driver.get(url)

    # se cair na tela do QR, ainda não logou
    if driver.find_elements(By.CSS_SELECTOR, CSS_QR):
        raise RuntimeError("not_logged")

    # tenta achar composer direto; se não achar, clica “Continuar para conversa”
    try:
        wait_for_composer(driver, total_timeout=10)
    except TimeoutError:
        clicked = maybe_click_continue_to_chat(driver)
        if clicked:
            wait_for_composer(driver, total_timeout=WAIT_MED)
        else:
            # tenta uma última vez “na força”
            wait_for_composer(driver, total_timeout=10)

def run(phone: str, text: str, method: str) -> bool:
    driver = qr_manager._ensure_driver()
    ensure_logged(driver)

    print(f"[debug] abrindo chat para {phone!r}...")
    open_chat(driver, phone, text)
    print("[debug] chat aberto, tentando envio...")

    methods = {
        "enter": try_enter,
        "btn": try_button_datatestid,
        "xpath": try_button_xpath,
        "auto": None,
    }

    if method not in methods:
        raise ValueError(f"método inválido: {method} (use: auto|enter|btn|xpath)")

    ok = False
    if method == "auto":
        for name, fn in (("enter", try_enter), ("btn", try_button_datatestid), ("xpath", try_button_xpath)):
            print(f"[debug] tentativa: {name}")
            try:
                ok = fn(driver)
            except Exception:
                ok = False
            if ok:
                print(f"[debug] sucesso via {name}")
                break
    else:
        print(f"[debug] tentativa: {method}")
        ok = methods[method](driver)

    if not ok:
        path = "send_debug_fail.png"
        driver.save_screenshot(path)
        print(f"[debug] envio NÃO confirmado. Screenshot salvo: {path}")

    return ok

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--phone", required=True, help="número com DDI+DDD, apenas dígitos (ex: 351912345678 ou 5547999...)")
    ap.add_argument("--text", required=True, help="mensagem de teste")
    ap.add_argument("--method", default="auto", choices=["auto", "enter", "btn", "xpath"])
    args = ap.parse_args()

    try:
        ok = run(args.phone, args.text, args.method)
        print("\nRESULTADO:", "SENT OK ✅" if ok else "FAILED ❌")
        sys.exit(0 if ok else 2)
    except Exception as e:
        print("ERRO:", e)
        sys.exit(1)
