import os
import sys
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI
from fastapi.responses import JSONResponse

FUSO_BRASILIA = timezone(timedelta(hours=-3))

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from checker import BankStatusChecker
from notifier import send_discord_alert

app = FastAPI(title="Cron Worker")
checker = BankStatusChecker(str(BASE_DIR / "banks.json"))

ESTADO_FILE = Path("/tmp/estado_bancos.json")

def carregar_estado_anterior():
    if ESTADO_FILE.exists():
        try:
            with open(ESTADO_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def salvar_estado_atual(estado):
    try:
        with open(ESTADO_FILE, "w", encoding="utf-8") as f:
            json.dump(estado, f)
    except Exception:
        pass

CACHE_FILE = Path("/tmp/cache_resultados.json")

def salvar_cache(resultados):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "timestamp": datetime.now(FUSO_BRASILIA).strftime("%d/%m/%Y às %H:%M:%S"),
                "items": resultados
            }, f)
    except Exception:
        pass

@app.api_route("/", methods=["GET", "POST"])
@app.api_route("/cron", methods=["GET", "POST"])
@app.api_route("/api/cron", methods=["GET", "POST"])
async def run_cron():
    estado_anterior = carregar_estado_anterior()
    novo_estado = {}
    alertas_disparados = 0
    detalhes_envio = []

    resultados = await checker.check_all()
    salvar_cache(resultados)

    for item in resultados:
        bank_id = item["id"]
        esta_instavel = item["is_instavel"]
        era_instavel = estado_anterior.get(bank_id, False)

        novo_estado[bank_id] = esta_instavel

        if esta_instavel and not era_instavel:
            ok = send_discord_alert(item, is_normalizacao=False)
            alertas_disparados += 1
            detalhes_envio.append({"banco": bank_id, "tipo": "instabilidade", "discord_ok": ok})
        elif not esta_instavel and era_instavel:
            ok = send_discord_alert(item, is_normalizacao=True)
            alertas_disparados += 1
            detalhes_envio.append({"banco": bank_id, "tipo": "normalizacao", "discord_ok": ok})

    salvar_estado_atual(novo_estado)

    has_discord_token = bool(os.getenv("DISCORD_TOKEN"))
    has_webhook = bool(os.getenv("DISCORD_WEBHOOK_URL"))

    instaveis_agora = [x["id"] for x in resultados if x["is_instavel"]]

    return {
        "status": "ok",
        "timestamp": datetime.now(FUSO_BRASILIA).strftime("%d/%m/%Y às %H:%M:%S"),
        "total_verificados": len(resultados),
        "instaveis_detectados": instaveis_agora,
        "alertas_disparados": alertas_disparados,
        "detalhes_envio": detalhes_envio,
        "config": {
            "has_discord_token": has_discord_token,
            "has_discord_webhook": has_webhook
        }
    }
