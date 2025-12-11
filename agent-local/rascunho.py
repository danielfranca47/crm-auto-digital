#1 Pesquisa 
    #Captar escolhas do usuário:
        # hashtags,
        # Quantidade etc.
    #Passo 1: Acessar instagram

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from time import sleep
import random
import os
import pathlib
import pickle
import re
from urllib.parse import urlparse, urljoin

chrome_options = Options()
#chrome_options.add_argument('--headless=new')           # modo headless mais recente
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--disable-dev-shm-usage')
chrome_options.add_argument('--disable-gpu')
chrome_options.add_argument('--lang=pt-BR')
chrome_options.add_argument('--window-size=1920,1080')
chrome_options.add_experimental_option(
    "excludeSwitches", ["enable-logging"]               # reduz logs do Chrome
)

# --- START: replaced driver creation to use persistent profile + helper functions ---
# definir pasta de perfil para manter sessão do Chrome entre execuções
profile_base = os.path.join(os.path.dirname(__file__), "chrome_profiles", "instagram")
os.makedirs(profile_base, exist_ok=True)
chrome_options.add_argument(f"--user-data-dir={profile_base}")  # mantém cookies, localStorage, etc.

# ...existing code...

def sleep_short():
    """3 a 8 segundos (curto)"""
    sleep(random.uniform(3, 8))

def sleep_medium():
    """10 a 20 segundos (médio)"""
    sleep(random.uniform(10, 20))

def sleep_long():
    """80 a 95 segundos (longo)"""
    sleep(random.uniform(80, 95))

def start_driver(options):
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )
    return driver

def is_logged_in(driver):
    # Retorna True se não estiver na página de login/challenge.
    try:
        cur = driver.current_url or ""
        # Se URL indicar login/challenge => não está logado
        if any(k in cur for k in ('/accounts/login', '/challenge', '/accounts/password')):
            return False
        # Tentar detectar elementos de tela inicial que só aparecem quando logado
        # (fallback: ausência de elementos de login indica sessão ativa)
        login_buttons = driver.find_elements(By.XPATH, "//button[contains(., 'Entrar') or contains(., 'Log in') or contains(., 'Login')]")
        if login_buttons:
            # se vemos botão de login visível => não logado
            return False
    except Exception:
        pass
    return True

driver = start_driver(chrome_options)
# --- END replaced driver creation ---

driver.get('https://www.instagram.com/')
sleep_short()
#Se tiver popup de cookies

def handle_instagram_cookies(driver, timeout=10):
    wait = WebDriverWait(driver, timeout)
    # tentar trocar para iframe caso exista (alguns banners usam iframe)
    try:
        iframes = driver.find_elements(By.CSS_SELECTOR, "iframe[src*='consent'], iframe[src*='cookie']")
        if iframes:
            driver.switch_to.frame(iframes[0])
    except Exception:
        pass

    candidates = [
        # português / variações
        (By.XPATH, "//button[normalize-space()='Permitir todos os cookies']"),
        (By.XPATH, "//button[contains(normalize-space(),'Permitir') and contains(.,'cookies')]"),
        (By.XPATH, "//button[normalize-space()='Aceitar tudo' or contains(normalize-space(),'Aceitar')]"),
        # inglês / genérico
        (By.XPATH, "//button[normalize-space()='Accept all' or contains(normalize-space(),'Accept')]"),
        (By.XPATH, "//button[contains(.,'cookie') and (contains(.,'Allow') or contains(.,'Accept'))]"),
        # inputs/buttons alternativos
        (By.XPATH, "//input[@type='submit' and (contains(@value,'Accept') or contains(@value,'Permitir') or contains(@value,'Aceitar'))]"),
    ]

    for by, sel in candidates:
        try:
            el = wait.until(EC.element_to_be_clickable((by, sel)))
            el.click()
            sleep_short()
            try:
                driver.switch_to.default_content()
            except Exception:
                pass
            return True
        except TimeoutException:
            continue
        except Exception:
            continue

    # se não encontrou, tenta um clique genérico no possível banner (fallback)
    try:
        banner_buttons = driver.find_elements(By.CSS_SELECTOR, "button")
        for b in banner_buttons:
            txt = (b.text or "").strip().lower()
            if any(k in txt for k in ("permitir", "aceitar", "cookies", "allow", "accept")):
                try:
                    b.click()
                    sleep_short()
                    return True
                except Exception:
                    continue
    except Exception:
        pass

    return False

# tentar lidar com cookies
try:
    handle_instagram_cookies(driver, timeout=8)
except Exception:
    # não crítico: prosseguir mesmo sem aceitar cookies
    pass

# --- ADDED: função para salvar informações de login ---
def handle_save_login_info(driver, timeout=8):
	"""
	Tenta clicar em botões/inputs que convidem a salvar informações de login.
	Retorna True se clicou em algo, False caso contrário.
	"""
	from selenium.webdriver.common.by import By
	from selenium.webdriver.support.ui import WebDriverWait
	from selenium.webdriver.support import expected_conditions as EC
	from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException

	wait = WebDriverWait(driver, timeout)

	candidates = [
		# textos exatos / variações em português
		(By.XPATH, "//button[normalize-space()='Salvar informações']"),
		(By.XPATH, "//button[contains(normalize-space(),'Salvar') and contains(.,'informações')]"),
		(By.XPATH, "//button[contains(normalize-space(),'Salvar') and contains(.,'dados')]"),
		(By.XPATH, "//button[normalize-space()='Save Info' or contains(normalize-space(),'Save') and contains(.,'Info')]"),
		# valores de input/submit
		(By.XPATH, "//input[@type='button' and (contains(@value,'Salvar') or contains(@value,'Save'))]"),
		(By.XPATH, "//button[contains(.,'Not Now') or contains(.,'Agora não') or contains(.,'Agora NÃo')]"),
	]

	for by, sel in candidates:
		try:
			el = wait.until(EC.element_to_be_clickable((by, sel)))
			try:
				el.click()
			except ElementClickInterceptedException:
				# tentar via script se obstruído
				try:
					driver.execute_script("arguments[0].click();", el)
				except Exception:
					pass
			sleep_short()
			return True
		except TimeoutException:
			continue
		except Exception:
			continue

	# fallback: procurar botões com texto parcial
	try:
		btns = driver.find_elements(By.CSS_SELECTOR, "button,input[type='button'],input[type='submit']")
		for b in btns:
			txt = (b.text or b.get_attribute('value') or "").strip().lower()
			if any(k in txt for k in ("salvar", "save", "informações", "informacoes", "not now", "agora")):
				try:
					if b.is_enabled():
						b.click()
						sleep_short()
						return True
				except Exception:
					try:
						driver.execute_script("arguments[0].click();", b)
						sleep_short()
						return True
					except Exception:
						continue
	except Exception:
		pass

	return False
# --- END ADDED ---

# substituir sleep(185) por loop que espera até que o usuário esteja logado (ou timeout)
# tempo para o usuário fazer login manualmente caso não exista sessão válida
max_wait = 185
poll_interval = 2
elapsed = 0
while elapsed < max_wait:
    if is_logged_in(driver):
        break
    sleep(poll_interval)
    elapsed += poll_interval

if not is_logged_in(driver):
    driver.quit()
    raise Exception("Login não realizado dentro do tempo esperado.")

# Passo 2: salvar informações de login (tenta clicar se aparecer; segue normalmente se não)
sleep_short()
try:
	tryed = handle_save_login_info(driver, timeout=6)
	# opcional: log curto
	print(f"Salvar informações clicado: {tryed}")
except Exception:
	# não crítico: prosseguir mesmo sem salvar
	pass

#Passo 3: Pesquisar pela hashtag (Definido pelo usuário no frontend)
sleep_short()
# clicar na barra de pesquisa - tentar xpaths específicos primeiro, depois alternativas genéricas
search_selectors = [
    # xpaths específicos (mantidos)
    (By.XPATH, '//*[@id="mount_0_0_vY"]/div/div/div[2]/div/div/div[1]/div[1]/div[2]/div/div/div/div/div[2]/div[2]/span/div/a/div/div[1]/div/div/svg'),
    (By.XPATH, '//*[@id="mount_0_0_vY"]/div/div/div[2]/div/div/div[1]/div[1]/div[2]/div/div/div/div/div[2]/div[2]/span/div/a/div/div[2]/div/div/span/span'),
    (By.XPATH, '//*[@id="mount_0_0_Y2"]/div/div/div[2]/div/div/div[1]/div[1]/div[2]/div/div/div/div/div[2]/div[2]/span/div/a/div'),
    (By.XPATH, '//*[@id="mount_0_0_Y2"]/div/div/div[2]/div/div/div[1]/div[1]/div[2]/div/div/div/div/div[2]/div[2]'),

    # seletores genéricos por placeholder / aria-label / name (Português / Inglês)
    (By.CSS_SELECTOR, "input[placeholder*='Pesquisa']"),
    (By.CSS_SELECTOR, "input[placeholder*='Search']"),
    (By.CSS_SELECTOR, "input[aria-label*='Pesquisa']"),
    (By.CSS_SELECTOR, "input[aria-label*='Search']"),
    (By.CSS_SELECTOR, "input[name*='search']"),
    (By.CSS_SELECTOR, "input[type='search']"),

    # botões / links com texto
    (By.XPATH, "//button[contains(normalize-space(.), 'Pesquisa') or contains(normalize-space(.), 'Search')]"),
    (By.XPATH, "//a[contains(normalize-space(.), 'Pesquisa') or contains(normalize-space(.), 'Search')]"),

    # fallback: busca case-insensitive por texto parcial em qualquer elemento clicável
    (By.XPATH, "//*[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'pesquisa')]"),
    (By.XPATH, "//*[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'search')]"),
]

clicked = None
wait = WebDriverWait(driver, 8)
for by, sel in search_selectors:
    try:
        el = wait.until(EC.element_to_be_clickable((by, sel)))
        try:
            el.click()
        except Exception:
            # fallback: click via JS se houver interceptação
            try:
                driver.execute_script("arguments[0].click();", el)
            except Exception as e:
                raise e
        print(f"Clique bem-sucedido no seletor ({by}): {sel}")
        clicked = sel
        break
    except TimeoutException:
        print(f"Timeout aguardando seletor ({by}): {sel}")
    except Exception as e:
        print(f"Erro ao clicar no seletor ({by}) {sel}: {e}")

if not clicked:
    print("Nenhum elemento de pesquisa clicado. Ajustar seletores ou inspecionar DOM.")
sleep_short()

sleep_medium()

    
    #Passo 4: Digitar Hashtag (Definido pelo usuário no frontend)
sleep(15)# Aguarda o usuário digitar a hashtag e carregar os resultados

    #Opcional: Rolar a página para carregar mais posts (se for pretendido mais que) (Definido pelo usuário no frontend)
    #Passo 5: Entrar nos posts e Recolher links dos perfis que postaram (Definido pelo usuário no frontend)
def coletar_links_posts(driver, limite_links=6, max_scrolls=30,
                        scroll_min_px=400, scroll_max_px=800,
                        pause_min=1.8, pause_max=3.5):
    """
    Coleta links de posts de forma mais 'humana':
      - scroll incremental (valores aleatórios)
      - pausas aleatórias entre scrolls
      - saída ao não trazer novos links após algumas tentativas
    Retorna lista com até `limite_links`.
    """
    links = set()
    scrolls = 0
    no_new_counter = 0
    prev_count = 0

    while len(links) < limite_links and scrolls < max_scrolls:
        elementos = driver.find_elements(By.CSS_SELECTOR, 'a[href*="/p/"]')
        for el in elementos:
            href = el.get_attribute("href")
            if href and "/p/" in href:
                links.add(href)
                if len(links) >= limite_links:
                    break

        # se não vieram novos links, contar tentativas sem novidade
        if len(links) == prev_count:
            no_new_counter += 1
        else:
            no_new_counter = 0
            prev_count = len(links)

        if len(links) >= limite_links or no_new_counter > 6:
            # já pegou o suficiente ou não há mais conteúdo novo
            break

        # scroll incremental (mais humano que ir direto ao fim)
        step = random.randint(scroll_min_px, scroll_max_px)
        driver.execute_script("window.scrollBy(0, arguments[0]);", step)

        # pequenas variações: às vezes scroll up de leve (com baixa prob.)
        if random.random() < 0.08:
            driver.execute_script("window.scrollBy(0, -arguments[0]);", random.randint(100, 350))

        # pausa aleatória entre scrolls
        sleep(random.uniform(pause_min, pause_max))

        scrolls += 1

    return list(links)[:limite_links]

sleep_short()  # espera curta antes de começar a coletar
limite_de_links = 6  # ajustar conforme necessidade / entrada do usuário
try:
    posts_links = coletar_links_posts(driver, limite_links=limite_de_links, max_scrolls=40)
    print(f"Links coletados: {len(posts_links)}")
    # salvar para usar no Passo 6
    out_path = os.path.join(os.path.dirname(__file__), "collected_posts.pkl")
    with open(out_path, "wb") as f:
        pickle.dump(posts_links, f)
    # opcional: mostrar alguns links
    for l in posts_links[:5]:
        print(l)
except Exception as e:
    print("Erro ao coletar links:", e)

sleep_medium()
    
    #Passo 6: Entrar no perfil + Recolha de dados
    #Parte 1: Informações do perfil
    #A) Abrir link coletado
    #B) Entrar no perfil
    #C) Recolher dados para análise (1 perfil por vez)
        #Link perfil
        #Nome perfil
        #Número de seguidores
        #Texto Bio
        #descrição dos 3 ultimos posts
        #Link da bio

    #Parte 2: Análise dos dados recolhidos
        #contatos (fone e/ou email)
            #genérico - identificar nos dados anteriores os padrões de telefone e email e redes sociais
        #site - análise do site (desconsiderar por agora)
        #Dados anteriores= link do post, hashtag da pesquisa
    #D)Organizar dados na planilha
        #Cada perfil em uma linha
        #Colunas para cada dado recolhido 
    #E)Exportar planilha

def open_post_and_visit_profile(driver, post_url, timeout=8):
    """
    Abre o post e tenta achar/abrir o link do perfil do autor.
    Tenta múltiplos métodos e imprime qual funcionou.
    Retorna profile_url ou None.
    """
    driver.get(post_url)
    sleep_short()
    wait = WebDriverWait(driver, timeout)

    # 1) tentar anchors visíveis (CSS genérico)
    try:
        anchors = driver.find_elements(By.CSS_SELECTOR, "a[href^='/'], a[href^='http']")
        for a in anchors:
            href = a.get_attribute("href") or ""
            if not href:
                continue
            if any(x in href for x in ("/p/", "/explore", "/reel", "/stories")):
                continue
            m = re.match(r"https?://(www\.)?instagram\.com/([^/?#]+)/?$", href)
            if m:
                profile_url = href
                try:
                    a.click()
                    print(f"[open_post] clicou anchor CSS -> {href}")
                except Exception:
                    try:
                        driver.execute_script("arguments[0].click();", a)
                        print(f"[open_post] clicou anchor CSS via JS -> {href}")
                    except Exception:
                        driver.get(profile_url)
                        print(f"[open_post] navegou via driver.get para -> {href}")
                sleep_short()
                return profile_url
    except Exception:
        pass

    # 2) tentar seletor por texto/username dentro do post (mais genérico)
    try:
        candidates = driver.find_elements(By.XPATH, "//a[.//span and (contains(@href,'/') or contains(@href,'instagram.com'))]")
        for c in candidates:
            href = c.get_attribute("href") or ""
            if href and "/p/" not in href:
                driver.execute_script("arguments[0].click();", c)
                print(f"[open_post] clicou candidato XPATH de fallback -> {href}")
                sleep_short()
                return href
    except Exception:
        pass

    # 3) tentativa por CSS que contenha username (fallback)
    try:
        el = driver.find_element(By.CSS_SELECTOR, "header a[href*='instagram.com/'], a[href*='instagram.com/']")
        href = el.get_attribute("href")
        if href:
            try:
                el.click()
                print(f"[open_post] clicou anchor header CSS -> {href}")
            except Exception:
                driver.get(href)
                print(f"[open_post] navegou header CSS -> {href}")
            sleep_short()
            return href
    except Exception:
        pass

    # 4) fallback geral: procurar qualquer anchor com pattern de perfil via XPath fornecido (muito genérico)
    try:
        el = driver.find_element(By.XPATH, "//*[contains(@href,'instagram.com') and not(contains(@href,'/p/'))]")
        href = el.get_attribute("href")
        if href:
            try:
                el.click()
                print(f"[open_post] clicou fallback xpath -> {href}")
            except Exception:
                driver.get(href)
                print(f"[open_post] navegou fallback xpath -> {href}")
            sleep_short()
            return href
    except Exception:
        pass

    print(f"[open_post] não encontrou perfil no post: {post_url}")
    return None


def collect_profile_info(driver, timeout=8):
    """
    Heurísticas múltiplas para extrair: profile_url, username, display_name, followers, bio_text, bio_links.
    Imprime qual método encontrou cada campo.
    """
    wait = WebDriverWait(driver, timeout)
    info = {
        "profile_url": driver.current_url,
        "username": None,
        "display_name": None,
        "followers": None,
        "bio_text": None,
        "bio_links": [],
    }

    # username via URL (sempre primeiro fallback)
    try:
        parsed = urlparse(driver.current_url)
        path = parsed.path.strip("/")
        if path and "/" not in path:
            info["username"] = path
            print(f"[collect_profile] username via URL -> {info['username']}")
    except Exception:
        pass

    # display_name: tentar várias estratégias (XPATH, CSS, header h1, spans)
    display_attempts = [
        ("xpath_header_h1", By.XPATH, "//header//h1"),
        ("xpath_section2_span_dir_auto", By.XPATH, '//header//section[2]//span[@dir="auto"]'),
        ("css_header_h1", By.CSS_SELECTOR, "header h1"),
        ("css_header_spans", By.CSS_SELECTOR, "header span[dir='auto']"),
    ]
    for desc, by, sel in display_attempts:
        try:
            el = driver.find_element(by, sel)
            txt = (el.text or "").strip()
            if txt and not txt.startswith("@"):
                info["display_name"] = txt
                print(f"[collect_profile] display_name encontrado por {desc} -> {txt}")
                break
        except Exception:
            continue

    # followers: tentar link /followers, título com número ou spans no header
    followers_attempts = [
        ("xpath_followers_link", By.XPATH, "//a[contains(@href,'/followers')]/span | //a[contains(@href,'/followers')]/div"),
        ("xpath_span_title", By.XPATH, "//header//section[2]//span[@title]"),
        ("css_followers", By.CSS_SELECTOR, "header a[href*='/followers'] span, header span[title]"),
    ]
    for desc, by, sel in followers_attempts:
        try:
            el = driver.find_element(by, sel)
            val = (el.get_attribute("title") or el.text or "").strip()
            if val:
                info["followers"] = val
                print(f"[collect_profile] followers por {desc} -> {val}")
                break
        except Exception:
            continue

    # bio_text: várias abordagens (classes, selectors genéricos)
    bio_attempts = [
        ("xpath_bio_class_ap3a", By.XPATH, '//header//section[1]//span[contains(@class,"_ap3a")]'),
        ("css_header_section1_spans", By.CSS_SELECTOR, "header section:first-of-type span"),
        ("generic_header_spans", By.XPATH, "//header//div//span"),
    ]
    bio_texts = []
    for desc, by, sel in bio_attempts:
        try:
            els = driver.find_elements(by, sel)
            for b in els:
                t = (b.get_attribute("innerText") or b.text or "").strip()
                if t and len(t) > 0:
                    bio_texts.append(t)
            if bio_texts:
                info["bio_text"] = "\n".join(dict.fromkeys(bio_texts))
                print(f"[collect_profile] bio_text por {desc}")
                break
        except Exception:
            continue
    if not info["bio_text"]:
        print("[collect_profile] bio_text não encontrado por seletores padrão")

    # bio_links: tentar CSS genérico e o popup
    try:
        # direto
        anchors = driver.find_elements(By.CSS_SELECTOR, "header a[href^='http'], header a[href*='l.instagram.com']")
        if anchors:
            links = [a.get_attribute("href") for a in anchors if a.get_attribute("href")]
            info["bio_links"] = list(dict.fromkeys(links))
            print(f"[collect_profile] bio_links por CSS direto -> {len(info['bio_links'])} links")
        else:
            # tentar botão de links (ícone) e ler dialog
            try:
                btn = driver.find_element(By.XPATH, '//header//section[1]//button[.//svg]')
                try:
                    btn.click()
                    print("[collect_profile] abriu popup de links (clicou botão de ícone)")
                except Exception:
                    driver.execute_script("arguments[0].click();", btn)
                    print("[collect_profile] abriu popup de links (clicou JS)")
                sleep_short()
                dialog_anchors = driver.find_elements(By.XPATH, '//div[@role="dialog"]//a[starts-with(@href,"http")]')
                info["bio_links"] = [a.get_attribute("href") for a in dialog_anchors if a.get_attribute("href")]
                # fechar se possível
                try:
                    close_btn = driver.find_element(By.XPATH, '//div[@role="button" and (@aria-label="Close" or @aria-label="Fechar")]')
                    try:
                        close_btn.click()
                    except Exception:
                        driver.execute_script("arguments[0].click();", close_btn)
                except Exception:
                    pass
                print(f"[collect_profile] bio_links por popup -> {len(info['bio_links'])} links")
            except Exception:
                pass
    except Exception:
        pass

    return info


# --- ADDED/REPLACED: helpers e função de extração de perfil mais resiliente ---
import time
from selenium.common.exceptions import NoSuchElementException, TimeoutException, ElementClickInterceptedException

def extrair_emails(texto):
    if not texto:
        return ""
    padrao_email = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
    emails = re.findall(padrao_email, texto)
    return ", ".join(sorted(set(emails)))


def extrair_telefones(texto):
    if not texto:
        return ""
    padrao_tel = r"\+?\d[\d\s().-]{7,}"
    tels = re.findall(padrao_tel, texto)
    return ", ".join(sorted(set(tels)))


def coletar_links_bio(driver, timeout=5):
    """
    Retorna lista de links encontrados na bio (cobre link direto e popup de links).
    Imprime qual método encontrou os links.
    """
    wait = WebDriverWait(driver, timeout)
    links_encontrados = []

    # Cenário A: apenas um link direto
    try:
        direct_anchors = driver.find_elements(By.CSS_SELECTOR, "header a[href^='http'], header a[href*='l.instagram.com']")
        for a in direct_anchors:
            href = a.get_attribute("href")
            if href:
                links_encontrados.append(href)
        if links_encontrados:
            links_encontrados = list(dict.fromkeys(links_encontrados))
            print(f"[coletar_links_bio] links diretos encontrados -> {len(links_encontrados)}")
            return links_encontrados
    except Exception:
        pass

    # Cenário B: Mais de um link-> abrir popup
    try:
        # procurar botão com SVG (ícone de link) ou texto que indique links
        btn_selectors = [
            (By.XPATH, '//header//section[1]//button[.//svg[@aria-label="Link icon" or contains(@aria-label,"Link")]]'),
            (By.XPATH, '//header//section[1]//button[.//span[contains(translate(., "ABCDEFGHIJKLMNOPQRSTUVWXYZ","abcdefghijklmnopqrstuvwxyz"), "link")]]'),
            (By.XPATH, '//header//section[1]//div[@role="button" and (contains(.,"more") or contains(.,"mais"))]'),
        ]
        clicked = False
        for by, sel in btn_selectors:
            try:
                btn = driver.find_element(by, sel)
                try:
                    btn.click()
                except Exception:
                    driver.execute_script("arguments[0].click();", btn)
                clicked = True
                print(f"[coletar_links_bio] abriu popup via selector {by} {sel}")
                break
            except Exception:
                continue

        if clicked:
            # aguardar dialog
            try:
                wait.until(EC.presence_of_element_located((By.XPATH, '//div[@role="dialog"]')), timeout=timeout)
            except Exception:
                pass
            anchors = driver.find_elements(By.XPATH, '//div[@role="dialog"]//a[starts-with(@href,"http")]')
            for a in anchors:
                href = a.get_attribute("href")
                if href:
                    links_encontrados.append(href)

            # tentar fechar
            try:
                close_btn = driver.find_element(By.XPATH, '//div[@role="button" and (@aria-label="Close" or @aria-label="Fechar")]')
                try:
                    close_btn.click()
                except Exception:
                    driver.execute_script("arguments[0].click();", close_btn)
            except Exception:
                pass

            if links_encontrados:
                links_encontrados = list(dict.fromkeys(links_encontrados))
                print(f"[coletar_links_bio] links via popup -> {len(links_encontrados)}")
                return links_encontrados

    except Exception:
        pass

    print("[coletar_links_bio] nenhum link encontrado na bio")
    return []


def extrair_dados_perfil(driver, link_perfil=None, timeout=8):
    """
    Navega ao perfil (se link_perfil fornecido) e extrai campos principais.
    Imprime qual método seletor funcionou para cada campo.
    """
    if link_perfil:
        try:
            driver.get(link_perfil)
            sleep_short()
        except Exception:
            pass

    wait = WebDriverWait(driver, timeout)
    dados = {
        "username": "",
        "link_perfil": driver.current_url,
        "nome_exibicao": "",
        "seguidores": "",
        "bio_texto": "",
        "bio_links": [],
        "contatos_email": "",
        "contatos_telefone": "",
    }

    # USERNAME (da URL preferencialmente)
    try:
        parsed = urlparse(driver.current_url)
        path = parsed.path.strip("/")
        if path and "/" not in path:
            dados["username"] = path
            print(f"[extrair_dados_perfil] username via URL -> {dados['username']}")
    except Exception:
        pass

    # NOME DE EXIBIÇÃO: múltiplas heurísticas
    display_attempts = [
        ("xpath_section2_span_dir_auto", By.XPATH, '//header//section[2]//span[@dir="auto"]'),
        ("xpath_header_h1", By.XPATH, "//header//h1"),
        ("css_header_span_dir_auto", By.CSS_SELECTOR, "header span[dir='auto']"),
    ]
    for desc, by, sel in display_attempts:
        try:
            el = driver.find_element(by, sel)
            txt = (el.text or "").strip()
            if txt and not txt.startswith("@"):
                dados["nome_exibicao"] = txt
                print(f"[extrair_dados_perfil] nome_exibicao por {desc} -> {txt}")
                break
        except Exception:
            continue

    # SEGUIDORES: tentar /followers, span[@title], ou spans no header
    followers_attempts = [
        ("xpath_followers_link", By.XPATH, "//a[contains(@href,'/followers')]/span | //a[contains(@href,'/followers')]/div"),
        ("xpath_span_title", By.XPATH, "//header//section[2]//span[@title]"),
        ("css_followers", By.CSS_SELECTOR, "header a[href*='/followers'] span, header span[title]"),
    ]
    for desc, by, sel in followers_attempts:
        try:
            el = driver.find_element(by, sel)
            val = (el.get_attribute("title") or el.text or "").strip()
            if val:
                dados["seguidores"] = val
                print(f"[extrair_dados_perfil] seguidores por {desc} -> {val}")
                break
        except Exception:
            continue

    # expandir bio se houver botão "more"/"mais"
    try:
        more_selectors = [
            (By.XPATH, '//header//section[1]//div[@role="button"]//span[normalize-space()="more" or normalize-space()="mais"]'),
            (By.XPATH, '//header//section[1]//button[normalize-space()="more" or normalize-space()="mais"]'),
        ]
        for by, sel in more_selectors:
            try:
                btn_more = driver.find_element(by, sel)
                try:
                    btn_more.click()
                except Exception:
                    driver.execute_script("arguments[0].click();", btn_more)
                print(f"[extrair_dados_perfil] clicou expand bio via {by} {sel}")
                sleep_short()
                break
            except Exception:
                continue
    except Exception:
        pass

    # BIO: várias abordagens
    bio_attempts = [
        ("xpath_bio_class_ap3a", By.XPATH, '//header//section[1]//span[contains(@class,"_ap3a") or contains(@class,"_aaco")]'),
        ("css_header_section1_spans", By.CSS_SELECTOR, "header section:first-of-type span"),
        ("generic_header_spans", By.XPATH, "//header//div//span"),
    ]
    bio_texts = []
    for desc, by, sel in bio_attempts:
        try:
            els = driver.find_elements(by, sel)
            for b in els:
                t = (b.get_attribute("innerText") or b.text or "").strip()
                if t:
                    bio_texts.append(t)
            if bio_texts:
                dados["bio_texto"] = "\n".join(dict.fromkeys(bio_texts))
                dados["contatos_email"] = extrair_emails(dados["bio_texto"])
                dados["contatos_telefone"] = extrair_telefones(dados["bio_texto"])
                print(f"[extrair_dados_perfil] bio_texto por {desc}")
                break
        except Exception:
            continue
    if not dados["bio_texto"]:
        print("[extrair_dados_perfil] bio_texto não encontrada por seletores padrão")

    # LINKS DA BIO
    try:
        links = coletar_links_bio(driver, timeout=timeout)
        dados["bio_links"] = links
    except Exception:
        dados["bio_links"] = []
    print(f"[extrair_dados_perfil] bio_links coletados -> {len(dados['bio_links'])}")

    # atualizar link_perfil final
    try:
        dados["link_perfil"] = driver.current_url
    except Exception:
        pass

    return dados

# --- REPLACED: step6 para usar extrair_dados_perfil (em vez de collect_profile_info) ---
def step6_process_posts_profiles(driver, posts_links, save_path=None, per_profile_delay=True):
    """
    Itera pelos posts_links (lista), abre o post, vai ao perfil, coleta info e retorna lista de dicts.
    Usa extrair_dados_perfil (com selectors genéricos e prints).
    """
    collected = []
    for i, post in enumerate(posts_links, 1):
        try:
            profile_url = open_post_and_visit_profile(driver, post)
            if not profile_url:
                print(f"[Passo6] não encontrou perfil para post: {post}")
                continue

            sleep_short()
            info = extrair_dados_perfil(driver, link_perfil=profile_url, timeout=8)
            info["source_post"] = post
            collected.append(info)
            print(f"[Passo6] ({i}/{len(posts_links)}) coletado: {info.get('username') or info.get('link_perfil')}")

            # salvar incremental se solicitado
            if save_path:
                try:
                    with open(save_path, "wb") as f:
                        pickle.dump(collected, f)
                except Exception:
                    pass

            # pausa entre perfis para reduzir taxa
            if per_profile_delay:
                sleep(random.uniform(5, 12))
        except Exception as e:
            print(f"[Passo6] erro ao processar post {post}: {e}")
            continue

    return collected
sleep_medium()
driver.quit()


#2 Agente de IA (nao usa navegador)
  #Levar dados capturados na pesquisa em consideração
  #Fazer copy com o contexto para a proposta pretendida

#3 Prospeccao (utiliza navegador)
  #Passo 1: Entrar no perfil
  #Passo 2: Curtir 3 primeiros posts
  #Passo 3: Seguir
  #Passo 4: Enviar mensagem
  #Passo 5: Comentar no ultimo post (Fazer comentário sobre o tema e dizer que enviou uma mensagem)

#Realizar ações de boas praticas padroes que fizemos nas automações anteriores
  #dar tempo aleatório de espera entre as ações (5 à 12 segundos)
  #Fechar navegador
  #Aproveitar abas (se já tiver abertas)