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
limite_de_links = 1  # ajustar conforme necessidade / entrada do usuário / frontend
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

# ...existing code...
def simple_step6_process(driver, posts_links=None, per_profile_delay=True, timeout=8):
    """
    MVP: para cada post em posts_links:
      - abre o post
      - tenta localizar o link do perfil por múltiplos seletores (genéricos)
      - entra no perfil (click ou driver.get)
      - captura nome de exibição (com múltiplas heurísticas)
      - imprime OK/NOT FOUND e qual método funcionou
      - aplica sleeps dinâmicos entre perfis
    """
    # carregar lista salva se não fornecida
    if not posts_links:
        fp = os.path.join(os.path.dirname(__file__), "collected_posts.pkl")
        try:
            if os.path.exists(fp):
                with open(fp, "rb") as f:
                    posts_links = pickle.load(f)
                print(f"[Passo6] carregados {len(posts_links)} links de {fp}")
            else:
                print("[Passo6] nenhum posts_links fornecido e arquivo não encontrado")
                return
        except Exception as e:
            print(f"[Passo6] erro ao carregar posts_links: {e}")
            return

    for i, post in enumerate(posts_links, 1):
        try:
            # abrir post
            driver.get(post)
            sleep_medium()

            profile_href = None
            method_used = None

            # Método 1: anchors visíveis (CSS) - relativo ou absoluto
            try:
                anchors = driver.find_elements(By.CSS_SELECTOR, "a[href^='https://'], a[href^='http://'], a[href^='/']")
                for a in anchors:
                    href = a.get_attribute("href") or ""
                    if not href:
                        continue
                    if any(x in href for x in ("/p/", "/reel", "/explore", "/stories")):
                        continue
                    # normalizar href relativo
                    if href.startswith("/"):
                        href = urljoin("https://www.instagram.com", href)
                    if "instagram.com" in href:
                        profile_href = href
                        method_used = f"anchor_css (href={a.get_attribute('href')})"
                        # tentar clicar primeiro
                        try:
                            a.click()
                            print(f"[Passo6] ({i}) entrou via {method_used} (click)")
                        except Exception:
                            driver.get(profile_href)
                            print(f"[Passo6] ({i}) entrou via {method_used} (driver.get)")
                        sleep_short()
                        break
            except Exception:
                pass
            # Resultado
            # Se encontrou o perfil, tentar capturar nome de exibição
            display_name = None #nome de exibição do perfil
            if profile_href:
                # garantir que estamos na página do perfil
                try:
                    # se a navegação anterior não levou ao perfil, navegar explicitamente
                    if urlparse(driver.current_url).path.strip("/") != urlparse(profile_href).path.strip("/"):
                        driver.get(profile_href)
                        sleep_short()
                except Exception:
                    pass

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
                            display_name = txt
                            print(f"[Passo6] nome_exibicao por {desc} -> {txt}")
                            break
                    except Exception:
                        continue

                if not display_name:
                    print(f"[Passo6] nome_exibicao NÃO encontrado para {profile_href}")

                # --- INICIO: captura de seguidores ---
                followers = None
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
                            followers = val
                            print(f"[Passo6] seguidores por {desc} -> {val}")
                            break
                    except Exception:
                        continue

                if not followers:
                    print(f"[Passo6] seguidores NÃO encontrado para {profile_href}")
                # --- FIM: captura de seguidores ---

                # BIO_TEXT
                bio_text = None
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
                            bio_text = "\n".join(dict.fromkeys(bio_texts))
                            print(f"[Passo6] bio_text por {desc} -> {bio_text}")
                            break
                    except Exception:
                        continue

                if not bio_text:
                    print(f"[Passo6] bio_text NÃO encontrado para {profile_href}")

                # Novas validações podem ser adicionadas aqui para capturar mais dados do perfil
                # //Ajustar para desconsiderar links de redes sociais que contem facebook, threads
                # --- NOVO: coletar links da bio ---
                def coletar_links_bio(driver, timeout=5):
                    """
                    Retorna lista de links encontrados na bio (cobre link direto e popup de links).
                    Usa sleeps dinâmicos, deduplica e imprime qual método encontrou os links.
                    """
                    wait = WebDriverWait(driver, timeout)
                    links_encontrados = []

                    # Cenário A: link direto abaixo da bio / header
                    try:
                        direct_anchors = driver.find_elements(By.CSS_SELECTOR, "header a[href^='http'], header a[href*='l.instagram.com']")
                        for a in direct_anchors:
                            href = a.get_attribute("href")
                            if href:
                                links_encontrados.append(href)
                        if links_encontrados:
                            links_encontrados = list(dict.fromkeys(links_encontrados))
                            print(f"[coletar_links_bio] links diretos encontrados -> {len(links_encontrados)}")
                            sleep_short()
                            return links_encontrados
                    except Exception:
                        pass

                    # Cenário B: botão com popup de múltiplos links
                    try:
                        btn_selectors = [
                            (By.XPATH, '//header//section[1]//button[.//svg[@aria-label="Link icon" or contains(@aria-label,"Link")]]'),
                            (By.XPATH, '//header//section[1]//button[.//span[contains(translate(., "ABCDEFGHIJKLMNOPQRSTUVWXYZ","abcdefghijklmnopqrstuvwxyz"), "link")]]'),
                            (By.XPATH, '//header//section[1]//div[@role="button" and (contains(., "more") or contains(., "mais"))]'),
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
                                sleep_short()
                                break
                            except Exception:
                                continue

                        if clicked:
                            try:
                                wait.until(EC.presence_of_element_located((By.XPATH, '//div[@role="dialog"]')), timeout)
                            except Exception:
                                pass
                            anchors = driver.find_elements(By.XPATH, '//div[@role="dialog"]//a[starts-with(@href,"http")]')
                            for a in anchors:
                                href = a.get_attribute("href")
                                if href:
                                    links_encontrados.append(href)

                            # tentar fechar popup
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
                                sleep_short()
                                return links_encontrados

                    except Exception:
                        pass

                    print("[coletar_links_bio] nenhum link encontrado na bio")
                    return []                
                
                bio_links = None
                try:
                    bio_links = coletar_links_bio(driver, timeout=8)
                    if bio_links:
                        print(f"[Passo6] bio_links encontrados -> {len(bio_links) if bio_links else 0}")
                        for bl in bio_links:
                            print(f"  - {bl}")
                    else:
                        print(f"[Passo6] bio_links NENHUM para {profile_href}")
                except Exception as e:
                    bio_links = []
                    print(f"[Passo6] erro coletar_links_bio: {e}")


                print(f"[Passo6] OK ({i}/{len(posts_links)}): perfil aberto -> {profile_href}  (método: {method_used})")
            else:
                print(f"[Passo6] NOT FOUND ({i}/{len(posts_links)}): perfil não localizado para post -> {post}")

        except Exception as e:
            print(f"[Passo6] erro ao processar ({i}/{len(posts_links)}) {post}: {e}")

        # pausa dinâmica entre perfis
        if per_profile_delay:
            sleep_medium()

try:
    simple_step6_process(driver, posts_links if 'posts_links' in globals() else None)
except Exception as e:
    print(f"[Passo6] falha geral: {e}")

sleep_long()
driver.quit()


    #C) Recolher dados para análise (1 perfil por vez)
        #Link perfil -  profile_href ok
        #Nome perfil - display_name ok
        #Número de seguidores - followers ok
        #Texto Bio - bio_text ok
        #Link da bio - bio_links ok
        #descrição dos 3 ultimos posts

    #Parte 2: Análise dos dados recolhidos
        #contatos (fone e/ou email)
            #genérico - identificar nos dados anteriores os padrões de telefone e email e redes sociais
        #site - análise do site (desconsiderar por agora)
        #Dados anteriores= link do post, hashtag da pesquisa
    #D)Organizar dados na planilha
        #Cada perfil em uma linha
        #Colunas para cada dado recolhido 
    #E)Exportar planilha

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