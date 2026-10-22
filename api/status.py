import os
import sys
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI

FUSO_BRASILIA = timezone(timedelta(hours=-3))

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from checker import BankStatusChecker

app = FastAPI(title="Status API")
checker = BankStatusChecker(str(BASE_DIR / "banks.json"))

CACHE_FILE = Path("/tmp/cache_resultados.json")

def carregar_cache():
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None

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
@app.api_route("/status", methods=["GET", "POST"])
@app.api_route("/api/status", methods=["GET", "POST"])
async def get_status():
    cache = carregar_cache()
    if cache:
        return cache
    resultados = await checker.check_all()
    salvar_cache(resultados)
    return {
        "timestamp": datetime.now(FUSO_BRASILIA).strftime("%d/%m/%Y às %H:%M:%S"),
        "items": resultados
    }
