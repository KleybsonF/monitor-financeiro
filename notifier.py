import os
import requests
import logging

logger = logging.getLogger(__name__)

BANCOS_PRINCIPAIS = {
    "banco-do-brasil",
    "caixa",
    "bradesco",
    "itau",
    "santander",
    "sicredi",
    "sicoob",
    "banco-inter",
    "btg-pactual",
    "asaas",
    "widepay",
    "cora",
    "cellcoin",
    "iugu",
    "efi",
    "rami-capital",
    "c6-bank",
    "mercado-pago",
    "lytex",
    "negociarie",
    "modobank",
    "cielo"
}

def send_discord_alert(item: dict, is_normalizacao: bool = False):
    token = os.getenv("DISCORD_TOKEN")
    channel_id = os.getenv("DISCORD_CHANNEL_ID")
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")

    if not webhook_url and (not token or not channel_id or token == "seu_token_do_bot_aqui"):
        logger.warning("Credenciais do Discord não configuradas no ambiente.")
        return False

    is_principal = item["id"] in BANCOS_PRINCIPAIS

    if is_normalizacao:
        embed = {
            "title": f"✅ Normalizado: {item['name']}",
            "description": "O serviço voltou a responder normalmente.",
            "color": 0x2ecc71,  # Verde
            "fields": [
                {"name": "🕒 Horário", "value": f"`{item['timestamp']}`", "inline": True}
            ]
        }
        content = None
    else:
        cor = 0xe74c3c if item["status"] == "offline" else 0xf1c40f  # Vermelho ou Amarelo
        embed = {
            "title": f"⚠️ Instabilidade: {item['name']}",
            "color": cor,
            "fields": [
                {"name": "📋 Diagnóstico", "value": f"**{item['mensagem']}**", "inline": False},
                {"name": "⚡ Status", "value": f"`{item['status'].upper()}`", "inline": True},
                {"name": "🕒 Horário", "value": f"`{item['timestamp']}`", "inline": True},
                {"name": "🔍 Método de Consulta", "value": item.get("metodo", "Teste de Conectividade"), "inline": False}
            ]
        }
        content = "@everyone" if is_principal else None

    payload = {
        "content": content,
        "embeds": [embed]
    }

    try:
        # Se tiver Webhook URL configurado, usa ele
        if webhook_url:
            resp = requests.post(webhook_url, json=payload, timeout=8)
            return resp.status_code in [200, 204]

        # Caso contrário, usa a API REST oficial de Bot do Discord
        url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
        headers = {
            "Authorization": f"Bot {token}",
            "Content-Type": "application/json"
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=8)
        if resp.status_code in [200, 201]:
            logger.info(f"Alerta enviado com sucesso para {item['name']}")
            return True
        else:
            logger.error(f"Erro ao enviar no Discord: HTTP {resp.status_code} - {resp.text}")
            return False
    except Exception as e:
        logger.error(f"Falha na requisição para o Discord: {e}")
        return False
