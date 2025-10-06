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

# Mantemos uma referência ao job agendado para podermos re-agendá-lo sem criar jobs duplicados
job = None

def agendar_checada(interval_seconds: int):
    """(Re)agenda o job `checar_api` com o intervalo em segundos.

    Remove o job anterior (se existir) e agenda um novo com o intervalo solicitado.
    """
    global job
    # Remove job anterior
    if job is not None:
        try:
            schedule.cancel_job(job)
        except Exception:
            # Se falhar, ignoramos — pode acontecer se o job já tiver sido executado/removido
            pass

    # Agendamento: se o intervalo for múltiplo de 60, usamos `.minutes`, senão `.seconds`
    if interval_seconds % 60 == 0:
        minutes = interval_seconds // 60
        job = schedule.every(minutes).minutes.do(checar_api)
    else:
        job = schedule.every(interval_seconds).seconds.do(checar_api)


def checar_api():
    global estado_anterior
    try:
        print("Verificando API...")
        r = requests.get(API_URL, timeout=10)
        # tentamos obter json só para debug; se falhar, capturamos a exceção abaixo
        try:
            data = r.json()
        except Exception:
            data = {"status_code": r.status_code, "text": r.text}

        status_atual = "ok" if r.status_code == 200 else "fora"

        # Se mudou de ok → fora, envia alerta de queda e reduz intervalo para 5s
        if estado_anterior == "ok" and status_atual == "fora":
            print("🚨 API fora do ar:", data)
            enviar_slack(f"{alerta_queda}\nRetorno da API:\n{gerar_texto_do_json(data)}")
            # diminui frequência para 5 segundos
            agendar_checada(5)

        # Se mudou de fora → ok, envia alerta de recuperação e volta para 60s
        elif estado_anterior == "fora" and status_atual == "ok":
            print("✅ API voltou ao normal:", data)
            enviar_slack(recuperacao)
            # restaura frequência para 60 segundos
            agendar_checada(60)

        estado_anterior = status_atual

    except Exception as e:
        # Em caso de erro na requisição (timeout, DNS, etc) consideramos como fora e reduzimos intervalo
        print("Erro ao verificar API:", e)
        enviar_slack(f"❌ Erro ao verificar API: {str(e)}")
        if estado_anterior != "fora":
            # só re-agendamos quando há transição para evitar churn de jobs
            agendar_checada(5)
        estado_anterior = "fora"


# Agenda inicial: 60 segundos (1 minuto)
agendar_checada(60)


print("🔍 Monitoramento iniciado...")
try:
    while True:
        schedule.run_pending()
        time.sleep(1)
except KeyboardInterrupt:
    print("Monitoramento interrompido pelo usuário")
