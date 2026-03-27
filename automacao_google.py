import os
import time
import traceback
import logging
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException, NoSuchElementException
from selenium.webdriver.chrome.service import Service

load_dotenv() # para linkar e ocultar os dados de email e senha

site_ixc = os.getenv("SITE_IXC")
email_ixc = os.getenv("EMAIL")
senha_ixc = os.getenv("SENHA")

site_radius = os.getenv("SITE_R")
usuario_radius = os.getenv("USUARIO_R")
senha_radius = os.getenv("SENHA_R")

# print(siteIx, email,senha , siteRa , usuario , senhaR ) teste para ver se o .env não dava none

# --- CONFIGURAÇÃO DE LOGS ---
base_dir = os.path.dirname(os.path.abspath(__file__))
log_path = os.path.join(base_dir, "automacao.log")
logging.basicConfig(filename=log_path, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def log_info(msg):
    print(msg)
    logging.info(msg)

def log_erro(msg):
    print("ERRO:", msg)
    logging.error(msg)

# --- CAMINHO DO CHROMEDRIVER ---
caminho_chromedriver = r"C:\Users\DIEGO\Desktop\pro\chromedriver.exe"

# --- LEITURA DE CLIENTES ---
nome_arquivo = os.path.join(base_dir, "clientes.txt")
with open(nome_arquivo, "r", encoding="utf-8") as f:
    lista_nomes = [linha.strip() for linha in f if linha.strip()]

# --- ABRE O NAVEGADOR ---
options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
service = Service(caminho_chromedriver)
driver = webdriver.Chrome(service=service, options=options)
wait = WebDriverWait(driver, 25)  # tempo maior para elementos pesados

# --- FUNÇÕES AUXILIARES ---
def safe_wait(locator, condition='presence', timeout=25):
    try:
        if condition == 'presence':
            return WebDriverWait(driver, timeout).until(EC.presence_of_element_located(locator))
        elif condition == 'visible':
            return WebDriverWait(driver, timeout).until(EC.visibility_of_element_located(locator))
        elif condition == 'clickable':
            return WebDriverWait(driver, timeout).until(EC.element_to_be_clickable(locator))
        else:
            raise ValueError("Condição inválida")
    except (TimeoutException, StaleElementReferenceException, NoSuchElementException) as e:
        # re-raise para o caller tratar
        raise

def remover_overlay():
    try:
        driver.execute_script("""
        var overlay = document.getElementById('backgroundContent');
        if (overlay) { overlay.style.display = 'none'; }
        """)
        time.sleep(0.3)
    except Exception:
        pass

def click_js(element):
    driver.execute_script("arguments[0].click();", element)

def garantir_pagina_clientes():
    """
    Garante que estamos na lista de clientes do IXC.
    Tenta clicar em Cadastros -> Cliente até que o campo de pesquisa apareça.
    Retorna o elemento do campo de pesquisa (não limpo).
    """
    tries = 0
    while tries < 3:
        try:
            remover_overlay()
            # tenta localizar campo de pesquisa diretamente
            campo = driver.find_element(By.CSS_SELECTOR, "input.gridActionsSearchInput[placeholder='Consultar por Razão social']")
            if campo.is_displayed():
                return campo
        except Exception:
            pass

        try:
            # clica em Cadastros
            try:
                el_cadastros = safe_wait((By.XPATH, "//a[text()='Cadastros']"), 'clickable', timeout=8)
                click_js(el_cadastros)
            except:
                pass

            time.sleep(0.5)
            try:
                el_cliente = safe_wait((By.XPATH, "//a[contains(@rel,'cliente')]"), 'clickable', timeout=8)
                click_js(el_cliente)
            except:
                pass

            # aguarda campo de pesquisa aparecer
            campo = safe_wait((By.CSS_SELECTOR, "input.gridActionsSearchInput[placeholder='Consultar por Razão social']"), 'presence', timeout=10)
            return campo
        except Exception:
            tries += 1
            time.sleep(1)
    # se não conseguiu, levanta para o caller decidir
    raise TimeoutException("Não foi possível garantir a página de clientes")

def encontrar_primeira_linha_da_tabela(retries=5, wait_between=1):
    """
    Tenta localizar a primeira linha da tabela que contém o cliente.
    Se não encontrar, retorna None.
    """
    for i in range(retries):
        try:
            remover_overlay()
            elemento = driver.find_element(By.XPATH, "/html/body/div[2]/div/div[7]/table/tbody/tr[1]/td[1]/div")
            if elemento.is_displayed():
                return elemento
        except Exception:
            time.sleep(wait_between)
    return None

def garantir_limpeza_pesquisa():
    """
    Limpa o campo de pesquisa EXAUSTIVAMENTE e retorna o elemento limpo.
    Usa vários métodos (click, Ctrl+A, BACKSPACE, JS) para garantir que o valor seja removido.
    """
    try:
        campo = safe_wait((By.CSS_SELECTOR, "input.gridActionsSearchInput[placeholder='Consultar por Razão social']"), 'visible', timeout=10)
        try:
            campo.click()
        except Exception:
            try:
                driver.execute_script("arguments[0].scrollIntoView(true);", campo)
            except:
                pass
        # tentar vários métodos para garantir limpeza
        try:
            campo.send_keys(Keys.CONTROL, 'a')
            time.sleep(0.1)
            campo.send_keys(Keys.BACKSPACE)
            time.sleep(0.1)
        except Exception:
            pass
        # JS clear final (garante)
        try:
            driver.execute_script("arguments[0].value = '';", campo)
        except Exception:
            pass

        # verifica e repete se necessário
        try:
            valor = campo.get_attribute("value") or ""
            if valor.strip() != "":
                campo.send_keys(Keys.CONTROL, 'a')
                time.sleep(0.05)
                campo.send_keys(Keys.BACKSPACE)
                driver.execute_script("arguments[0].value = '';", campo)
                time.sleep(0.05)
        except Exception:
            pass

        return campo
    except Exception as e:
        log_erro(f"Falha ao limpar campo de pesquisa: {e}")
        # re-raise para o caller poder escolher pular
        raise

# --- FLUXO PRINCIPAL ---
try:
    log_info("Acessando IXC...")
    driver.get(site_ixc)

    # --- LOGIN IXC (manual 2FA esperado) ---
    safe_wait((By.ID, "email"), 'presence').send_keys(email_ixc)
    safe_wait((By.ID, "btn-next-login"), 'clickable').click()
    safe_wait((By.ID, "password"), 'presence').send_keys(senha_ixc)
    safe_wait((By.ID, "btn-enter-login"), 'clickable').click()
    time.sleep(1)
    try:
        # tentar clicar novamente por segurança
        safe_wait((By.ID, "btn-enter-login"), 'clickable', timeout=5).click()
    except:
        pass

    log_info("Aguarde completar o 2FA manualmente - espera Cadastros aparecer...")
    safe_wait((By.XPATH, "//a[text()='Cadastros']"), 'presence', timeout=120)
    log_info("Login OK.")

    # Fecha modal "Lembrar"
    try:
        btn_lembrar = safe_wait((By.XPATH, "//button[contains(text(),'Lembrar')]"), 'clickable', timeout=5)
        click_js(btn_lembrar)
    except:
        pass

    # Acessa clientes inicialmente
    safe_wait((By.XPATH, "//a[text()='Cadastros']"), 'clickable').click()
    remover_overlay()
    safe_wait((By.XPATH, "//a[contains(@rel,'cliente')]"), 'clickable').click()
    remover_overlay()

    # Abre aba Radius e loga
    driver.execute_script("window.open('');")
    guia_radius = driver.window_handles[1]
    guia_ixc = driver.window_handles[0]

    driver.switch_to.window(guia_radius)
    driver.get(site_radius)
    safe_wait((By.XPATH, "/html/body/form/table/tbody/tr[3]/td[2]/input"), 'presence').send_keys(usuario_radius)
    safe_wait((By.XPATH, "/html/body/form/table/tbody/tr[4]/td[2]/input"), 'presence').send_keys(senha_radius)
    safe_wait((By.XPATH, "/html/body/form/table/tbody/tr[6]/td/div/input[1]"), 'clickable').click()

    driver.switch_to.window(guia_ixc)

    # --- PROCESSA CADA CLIENTE ---
    for nome_cliente in lista_nomes:
        log_info(f"--- Iniciando: {nome_cliente} ---")
        try:
            # Garantir que estamos na listagem de clientes e pegar campo de pesquisa (re-obtém sempre)
            try:
                # garante que estamos na tela de clientes e recupera o campo
                campo_pesquisa = garantir_pagina_clientes()
            except Exception as e:
                log_erro(f"Falha ao garantir página de clientes para '{nome_cliente}': {e}")
                # tenta continuar pra próximo cliente
                continue

            # Fecha possíveis modais
            try:
                modal = driver.find_element(By.CLASS_NAME, "ixc-modal")
                if modal.is_displayed():
                    log_info("Fechando modal...")
                    try:
                        driver.find_element(By.ID, "closeButton").click()
                    except:
                        pass
                    time.sleep(0.8)
            except Exception:
                pass

            # Limpa e pesquisa (usa a função robusta)
            try:
                campo_pesquisa = garantir_limpeza_pesquisa()
                campo_pesquisa.send_keys(nome_cliente)
                campo_pesquisa.send_keys(Keys.ENTER)
                time.sleep(1)
            except Exception as e:
                log_erro(f"Erro ao limpar/digitar pesquisa para '{nome_cliente}': {e}")
                continue

            # Espera pela primeira linha (com retries)
            cliente_div = encontrar_primeira_linha_da_tabela(retries=6, wait_between=1)
            if not cliente_div:
                log_erro(f"Cliente '{nome_cliente}' não apareceu na tabela. Pulando.")
                continue

            # Duplo clique para abrir cliente
            try:
                ActionChains(driver).double_click(cliente_div).perform()
            except Exception:
                try:
                    click_js(cliente_div)
                    time.sleep(0.3)
                    click_js(cliente_div)
                except:
                    pass
            time.sleep(2)

            # Aba serviços
            try:
                safe_wait((By.XPATH, "/html/body/form[2]/div[3]/ul/li[7]/a"), 'clickable', timeout=10).click()
            except Exception:
                log_erro(f"Não consegui clicar em 'Serviços' para '{nome_cliente}'. Tentando continuar.")
                # tenta voltar e continuar
                try:
                    driver.switch_to.window(guia_ixc)
                    safe_wait((By.XPATH, "/html/body/form[3]/div[1]/div[3]/a[4]"), 'clickable', timeout=8).click()
                    safe_wait((By.XPATH, "/html/body/form[2]/div[1]/div[3]/a[5]"), 'clickable', timeout=8).click()
                    # limpa campo para garantir próximo
                    try:
                        garantir_limpeza_pesquisa()
                    except:
                        pass
                except:
                    pass
                continue

            # Seleciona o serviço e pega o campo com valor
            try:
                celula_servico = safe_wait((By.XPATH, "/html/body/form[2]/div[3]/div[7]/dl/div/div/div[6]/table/tbody/tr[1]/td[4]/div/div"), 'clickable', timeout=10)
                ActionChains(driver).double_click(celula_servico).perform()
                time.sleep(0.8)

                safe_wait((By.XPATH, "/html/body/form[3]/div[2]/nav[3]/div/span"), 'clickable').click()
                safe_wait((By.XPATH, "/html/body/form[3]/div[2]/nav[3]/ul/li[3]"), 'clickable').click()
                campo_input = safe_wait((By.XPATH, "/html/body/form[3]/div[3]/div[1]/dl[3]/dd/div/input"), 'presence', timeout=10)
                valor_copiado = campo_input.get_attribute("value")
            except Exception:
                log_erro(f"Falha ao obter valor para '{nome_cliente}':\n{traceback.format_exc()}")
                # volta para a lista e continua
                try:
                    driver.switch_to.window(guia_ixc)
                    safe_wait((By.XPATH, "/html/body/form[3]/div[1]/div[3]/a[4]"), 'clickable', timeout=8).click()
                    safe_wait((By.XPATH, "/html/body/form[2]/div[1]/div[3]/a[5]"), 'clickable', timeout=8).click()
                    try:
                        garantir_limpeza_pesquisa()
                    except:
                        pass
                except:
                    pass
                continue

            # Vai para o Radius e aplica
            try:
                driver.switch_to.window(guia_radius)
                safe_wait((By.XPATH, "/html/body/table/tbody/tr[2]/td/table/tbody/tr/td/div/table/tbody/tr/td[2]/span[2]"), 'clickable', timeout=10).click()
                time.sleep(0.6)
                safe_wait((By.XPATH, "/html/body/table/tbody/tr[2]/td/table/tbody/tr/td/div/div[2]/table/tbody/tr[2]/td[2]"), 'clickable', timeout=10).click()
                time.sleep(0.6)
                campo_id = safe_wait((By.XPATH, "/html/body/table/tbody/tr[3]/td/table[1]/tbody/tr[1]/td/table[2]/tbody/tr/td[1]/table/tbody/tr/td/table/tbody/tr/td/form/table/tbody/tr[1]/td[2]/input"), 'presence', timeout=10)
                campo_id.clear()
                campo_id.send_keys(valor_copiado)
                safe_wait((By.XPATH, "/html/body/table/tbody/tr[3]/td/table[1]/tbody/tr[1]/td/table[2]/tbody/tr/td[1]/table/tbody/tr/td/table/tbody/tr/td/form/p[2]/input"), 'clickable', timeout=10).click()
                safe_wait((By.XPATH, "/html/body/table/tbody/tr[3]/td/table[1]/tbody/tr[1]/td/table[4]/tbody/tr[1]/td/table[2]/tbody/tr[2]/td[3]/font/a"), 'clickable', timeout=10).click()
                select_element = safe_wait((By.ID, "srvid"), 'presence', timeout=10)
                Select(select_element).select_by_value("45")
                safe_wait((By.XPATH, "/html/body/table/tbody/tr[3]/td/table[1]/tbody/tr[1]/td/table[2]/tbody/tr/td/table/tbody/tr/td/form/p[3]/input"), 'clickable', timeout=10).click()
            except Exception:
                log_erro(f"Erro ao aplicar no Radius para '{nome_cliente}':\n{traceback.format_exc()}")
            finally:
                # volta para o IXC sempre (mesmo que dê erro no Radius)
                driver.switch_to.window(guia_ixc)

            log_info(f"Cliente '{nome_cliente}' processado com sucesso.")

            # Volta na interface do IXC para lista e aguarda
            try:
                safe_wait((By.XPATH, "/html/body/form[3]/div[1]/div[3]/a[4]"), 'clickable', timeout=8).click()
                safe_wait((By.XPATH, "/html/body/form[2]/div[1]/div[3]/a[5]"), 'clickable', timeout=8).click()
            except Exception:
                # se não conseguir usar esses botões, reabrir a listagem de clientes
                log_info("Botões de voltar não funcionaram, reabrindo a listagem de clientes.")
                try:
                    safe_wait((By.XPATH, "//a[text()='Cadastros']"), 'clickable', timeout=8).click()
                    safe_wait((By.XPATH, "//a[contains(@rel,'cliente')]"), 'clickable', timeout=8).click()
                except:
                    pass

            # garante que tabela carregou antes do próximo cliente
            if not encontrar_primeira_linha_da_tabela(retries=6, wait_between=1):
                log_erro("Após retornar, tabela não carregou. Continuando para o próximo cliente.")

            # **LIMPA O CAMPO DE PESQUISA PARA GARANTIR QUE NÃO REPITE O MESMO CLIENTE**
            try:
                garantir_limpeza_pesquisa()
            except:
                pass

        except Exception:
            log_erro(f"Erro inesperado no cliente '{nome_cliente}':\n{traceback.format_exc()}")
            # tenta garantir que estamos em IXC para continuar com o próximo
            try:
                driver.switch_to.window(guia_ixc)
            except:
                pass
            # tentar limpar campo antes de continuar
            try:
                garantir_limpeza_pesquisa()
            except:
                pass
            continue

except Exception:
    log_erro("Erro geral na automação:\n" + traceback.format_exc())

finally:
    log_info("Finalizando automação e encerrando navegador.")
    try:
        driver.quit()
    except:
        pass