import requests
import schedule
import time
import os
from dotenv import load_dotenv

# Carrega variáveis do .env
load_dotenv()

API_URL = os.getenv("API_URL")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")

# Templates
alerta_queda = """🤖 ALERTA DE SISTEMA
O SaaS Prod apresentou falha ou indisponibilidade.
Estou registrando e notificando imediatamente.
Verifiquem o mais rápido possível."""

recuperacao = """🤖 SISTEMA RESTAURADO
O SaaS Prod voltou ao status operacional.
Missão cumprida. Continuarei monitorando."""

# Funções auxiliares
def gerar_texto_do_json(data, indent=0):
    texto = ""
    espaco = "  " * indent
    if isinstance(data, dict):
        for chave, valor in data.items():
            if isinstance(valor, (dict, list)):
                texto += f"{espaco}{chave}:\n{gerar_texto_do_json(valor, indent + 1)}"
            else:
                texto += f"{espaco}{chave}: {valor}\n"
    elif isinstance(data, list):
        for item in data:
            texto += gerar_texto_do_json(item, indent)
    else:
        texto += f"{espaco}{data}\n"
    return texto

def enviar_slack(msg):
    payload = {"text": msg}
    r = requests.post(SLACK_WEBHOOK_URL, json=payload)
    print("Mensagem Slack:", r.status_code, r.text)

# Estado inicial: assumimos que a API está OK
estado_anterior = "ok"

def checar_api():
    global estado_anterior
    try:
        print("Verificando API...")
        r = requests.get(API_URL, timeout=10)
        data = r.json()
        
        status_atual = "ok" if r.status_code == 200 else "fora"
        
        # Se mudou de ok → fora, envia alerta de queda
        if estado_anterior == "ok" and status_atual == "fora":
            print("🚨 API fora do ar:", data)
            enviar_slack(f"{alerta_queda}\nRetorno da API:\n{gerar_texto_do_json(data)}")
        
        # Se mudou de fora → ok, envia alerta de recuperação
        elif estado_anterior == "fora" and status_atual == "ok":
            print("✅ API voltou ao normal:", data)
            enviar_slack(recuperacao)
        
        estado_anterior = status_atual
        
    except Exception as e:
        print("Erro ao verificar API:", e)
        enviar_slack(f"❌ Erro ao verificar API: {str(e)}")

# Agenda para rodar a cada 1 minuto
schedule.every(1).minute.do(checar_api)


print("🔍 Monitoramento iniciado...")
while True:
    schedule.run_pending()
    time.sleep(1)
