import os
import sys
import json
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI
from fastapi.responses import JSONResponse

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

@app.api_route("/", methods=["GET", "POST"])
@app.api_route("/cron", methods=["GET", "POST"])
@app.api_route("/api/cron", methods=["GET", "POST"])
async def run_cron():
    estado_anterior = carregar_estado_anterior()
    novo_estado = {}
    alertas_disparados = 0

    resultados = await checker.check_all()

    for item in resultados:
        bank_id = item["id"]
        esta_instavel = item["is_instavel"]
        era_instavel = estado_anterior.get(bank_id, False)

        novo_estado[bank_id] = esta_instavel

        if esta_instavel and not era_instavel:
            send_discord_alert(item, is_normalizacao=False)
            alertas_disparados += 1
        elif not esta_instavel and era_instavel:
            send_discord_alert(item, is_normalizacao=True)
            alertas_disparados += 1

    salvar_estado_atual(novo_estado)

    return {
        "status": "ok",
        "timestamp": datetime.now().strftime("%d/%m/%Y às %H:%M:%S"),
        "total_verificados": len(resultados),
        "alertas_disparados": alertas_disparados
    }
