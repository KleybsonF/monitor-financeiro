import os
import sys
import json
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# Adiciona diretório raiz ao path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from checker import BankStatusChecker
from notifier import send_discord_alert

app = FastAPI(title="Monitor Financeiro API", version="1.0.0")

checker = BankStatusChecker(str(BASE_DIR / "banks.json"))

# Cache em memória e arquivo /tmp para persistência entre execuções serverless
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

# Cache de último resultado para carregamento instantâneo da página
CACHE_FILE = Path("/tmp/cache_resultados.json")

def salvar_cache(resultados):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "timestamp": datetime.now().strftime("%d/%m/%Y às %H:%M:%S"),
                "items": resultados
            }, f)
    except Exception:
        pass

def carregar_cache():
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None

@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = BASE_DIR / "public" / "index.html"
    if html_path.exists():
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>Monitor Financeiro Ativo</h1>")

@app.api_route("/status", methods=["GET"])
@app.api_route("/api/status", methods=["GET"])
async def get_status():
    cache = carregar_cache()
    if cache:
        return cache
    resultados = await checker.check_all()
    salvar_cache(resultados)
    return {
        "timestamp": datetime.now().strftime("%d/%m/%Y às %H:%M:%S"),
        "items": resultados
    }

@app.api_route("/check", methods=["GET", "POST"])
@app.api_route("/api/check", methods=["GET", "POST"])
async def check_all_manual():
    resultados = await checker.check_all()
    salvar_cache(resultados)
    return {
        "timestamp": datetime.now().strftime("%d/%m/%Y às %H:%M:%S"),
        "items": resultados
    }

@app.api_route("/cron", methods=["GET", "POST"])
@app.api_route("/api/cron", methods=["GET", "POST"])
async def cron_worker():
    """
    Endpoint executado automaticamente pela Vercel (Cron Jobs) 24/7.
    Varre os 54 bancos e dispara alertas no Discord quando há mudança de status.
    """
    estado_anterior = carregar_estado_anterior()
    novo_estado = {}
    alertas_disparados = 0

    resultados = await checker.check_all()
    salvar_cache(resultados)

    for item in resultados:
        bank_id = item["id"]
        esta_instavel = item["is_instavel"]
        era_instavel = estado_anterior.get(bank_id, False)

        novo_estado[bank_id] = esta_instavel

        # Transição: Ficou instável agora
        if esta_instavel and not era_instavel:
            send_discord_alert(item, is_normalizacao=False)
            alertas_disparados += 1

        # Transição: Normalizou agora
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
