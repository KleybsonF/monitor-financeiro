import asyncio
import sys
from checker import BankStatusChecker

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

async def test_all():
    checker = BankStatusChecker("banks.json")
    print(f"Testando {len(checker.banks)} instituições...")
    results = await checker.check_all()
    
    online = [r for r in results if r["status"] == "normal"]
    instaveis = [r for r in results if r["status"] in ["instavel", "offline"]]
    desconhecidos = [r for r in results if r["status"] == "desconhecido"]
    
    print(f"\nResumo: {len(online)} normais, {len(instaveis)} instáveis/offline, {len(desconhecidos)} desconhecidos.\n")
    for r in instaveis + desconhecidos:
        print(f"[{r['status'].upper()}] {r['name']}: {r['mensagem']} (Target: {r['target']})")

if __name__ == "__main__":
    asyncio.run(test_all())
