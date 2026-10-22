import asyncio
import sys
from checker import BankStatusChecker

# Garante suporte a UTF-8 no terminal Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

async def main():
    checker = BankStatusChecker("banks.json")
    
    if len(sys.argv) > 1:
        query = sys.argv[1]
        print(f"\n🔍 Consultando status de: '{query}'...")
        res = await checker.check_by_id_or_name(query)
        if not res:
            print(f"❌ Instituição '{query}' não encontrada na lista!")
            return
            
        emoji = "🟢" if res["status"] == "normal" else ("🟡" if res["status"] == "instavel" else "🔴")
        print("\n" + "="*50)
        print(f"{emoji} {res['name']} ({res['category']})")
        print(f"Status: {res['status'].upper()}")
        print(f"Data e Hora: {res['timestamp']}")
        print(f"Diagnóstico: {res['mensagem']}")
        print(f"Método de Consulta: {res.get('metodo', 'Teste de Conectividade')}")
        if res.get("reclamacoes"):
            print(f"Reclamações: {res['reclamacoes']}")
        print("="*50 + "\n")
    else:
        print(f"\n🔍 Verificando todas as {len(checker.banks)} instituições cadastradas...")
        resultados = await checker.check_all()
        print("\n" + "="*70)
        print(f"{'INSTITUIÇÃO':<28} | {'STATUS':<10} | {'HORÁRIO':<19} | {'DETALHES'}")
        print("="*70)
        for r in resultados:
            emoji = "🟢" if r["status"] == "normal" else ("🟡" if r["status"] == "instavel" else "🔴")
            print(f"{emoji} {r['name'][:25]:<26} | {r['status'].upper():<10} | {r['timestamp'].split(' às ')[1]:<19} | {r['mensagem'][:35]}")
        print("="*70 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
