import asyncio
from datetime import datetime, timezone, timedelta
import json
import logging
import re
from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession

logger = logging.getLogger(__name__)

# Fuso Horário Oficial de Brasília (UTC-3)
FUSO_BRASILIA = timezone(timedelta(hours=-3))

BROWSER_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Sec-Ch-Ua": '"Not A(Brand";v="99", "Google Chrome";v="120", "Chromium";v="120"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}

class BankStatusChecker:
    def __init__(self, banks_file: str = "banks.json"):
        with open(banks_file, "r", encoding="utf-8") as f:
            self.banks = json.load(f)

    async def check_statuspage(self, session: AsyncSession, target_url: str):
        try:
            resp = await session.get(target_url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                indicator = data.get("status", {}).get("indicator", "none")
                description = data.get("status", {}).get("description", "Operacional")

                # Dicionário de tradução dos termos em inglês da Statuspage
                traducoes = {
                    "All Systems Operational": "Todos os sistemas operacionais",
                    "Partial System Outage": "Instabilidade Parcial",
                    "Major System Outage": "Interrupção Crítica de Sistemas",
                    "Minor Service Outage": "Oscilação / Lentidão Parcial",
                    "Degraded Performance": "Desempenho Degradado",
                    "Under Maintenance": "Em Manutenção Programada"
                }
                desc_pt = traducoes.get(description, description)

                # Identifica incidentes ativos
                unresolved = data.get("incidents", [])
                incident_msg = ""
                if unresolved:
                    first = unresolved[0]
                    incident_msg = f"{first.get('name', '')} ({first.get('status', '')})"

                # Filtro específico para a Celcoin: ignorar falhas exclusivas de DETRAN e débitos veiculares
                if "celcoin" in target_url:
                    falhas_reais = [
                        c for c in data.get("components", [])
                        if c.get("status") not in ["operational", "none", None]
                        and not any(p in c.get("name", "").lower() for p in ["detran", "veicular", "veiculo", "veículo", "ipva"])
                    ]
                    falhas_criticas = [
                        c for c in falhas_reais
                        if c.get("status") in ["major_outage", "critical"]
                    ]
                    # Se não houver falhas críticas fora do DETRAN, considera operacional
                    if not falhas_criticas:
                        return {
                            "status": "normal",
                            "is_instavel": False,
                            "mensagem": "Sistemas principais operacionais (Pix, Boletos e Contas ativos)",
                            "metodo": "API Oficial de Status (Statuspage)"
                        }

                # Identifica exatamente quais componentes/módulos estão fora do ar
                affected_components = [
                    c['name'] for c in data.get("components", [])
                    if c.get("status") not in ["operational", "none", None]
                ]
                comp_str = f"Módulos afetados: {', '.join(affected_components[:3])}" if affected_components else ""

                if incident_msg and comp_str:
                    detalhe = f"{desc_pt} — {incident_msg} ({comp_str})"
                elif comp_str:
                    detalhe = f"{desc_pt} ({comp_str})"
                elif incident_msg:
                    detalhe = f"{desc_pt} — {incident_msg}"
                else:
                    detalhe = desc_pt

                if indicator in ["major", "critical"]:
                    return {
                        "status": "offline",
                        "is_instavel": True,
                        "mensagem": detalhe,
                        "metodo": "API Oficial de Status (Statuspage)"
                    }
                elif indicator in ["minor"]:
                    return {
                        "status": "instavel",
                        "is_instavel": True,
                        "mensagem": detalhe,
                        "metodo": "API Oficial de Status (Statuspage)"
                    }
                else:
                    return {
                        "status": "normal",
                        "is_instavel": False,
                        "mensagem": desc_pt,
                        "metodo": "API Oficial de Status (Statuspage)"
                    }
            return {
                "status": "desconhecido",
                "is_instavel": False,
                "mensagem": f"HTTP {resp.status_code}",
                "metodo": "API Oficial de Status (Statuspage)"
            }
        except Exception as e:
            return {
                "status": "desconhecido",
                "is_instavel": False,
                "mensagem": f"Falha na consulta da API de status: {str(e)}",
                "metodo": "API Oficial de Status (Statuspage)"
            }

    async def get_downdetector_live_feed(self, session: AsyncSession) -> dict:
        now = asyncio.get_event_loop().time()
        if hasattr(self, "_dd_feed_cache") and (now - getattr(self, "_dd_feed_time", 0)) < 90:
            return self._dd_feed_cache

        feed = {}
        try:
            resp = await session.get("https://downdetector.com.br", headers=BROWSER_HEADERS, timeout=10)
            if resp.status_code == 200:
                clean = resp.text.replace(r'\"', '"')
                pattern = r'"name":"([^"]+)".*?"slug":"([^"]+)".*?"status":"(success|warning|danger)".*?"sparkline":\[([^\]]+)\]'
                matches = re.findall(pattern, clean)
                for name, slug, status, spark in matches:
                    counts = [int(x) for x in spark.split(",") if x.strip().isdigit()]
                    latest = counts[-1] if counts else 0
                    feed[slug] = {
                        "name": name,
                        "status": status,
                        "latest_reports": latest,
                    }
                self._dd_feed_cache = feed
                self._dd_feed_time = now
        except Exception as e:
            logger.warning(f"Erro ao buscar feed do Downdetector: {e}")

        return feed

    async def check_downdetector_or_site(self, session: AsyncSession, slug: str, fallback_url: str = None):
        # 1. Checa feed em tempo real da página principal do Downdetector
        feed = await self.get_downdetector_live_feed(session)
        if slug in feed:
            entry = feed[slug]
            status_dd = entry["status"]
            reports = entry["latest_reports"]

            if status_dd in ["warning", "danger"]:
                return {
                    "status": "instavel" if status_dd == "warning" else "offline",
                    "is_instavel": True,
                    "mensagem": f"Pico de reclamações no Downdetector ({reports} queixas recentes - Alerta {status_dd.upper()})",
                    "metodo": "Downdetector (Relatos de Usuários)"
                }
            elif status_dd == "success":
                # Downdetector diz que está tudo bem. Se tiver fallback_url, confirma conectividade
                if fallback_url:
                    res_http = await self.check_http(session, fallback_url)
                    if res_http["is_instavel"]:
                        return res_http
                return {
                    "status": "normal",
                    "is_instavel": False,
                    "mensagem": f"Operação normal segundo relatos ({reports} queixas recentes no padrão)",
                    "metodo": "Downdetector (Relatos de Usuários)"
                }

        # 2. Se a instituição não estiver no feed principal, consulta a página individual
        dd_url = f"https://downdetector.com.br/fora-do-ar/{slug}/"
        try:
            resp = await session.get(dd_url, headers=BROWSER_HEADERS, timeout=8)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                banner = soup.find(id="company-status") or soup.find("div", class_="company-status")
                text_content = banner.get_text(separator=" ", strip=True).lower() if banner else ""

                if any(w in text_content for w in ["problemas", "fora do ar", "interrupção", "falha"]):
                    if "não indicam problemas" in text_content or "sem problemas" in text_content:
                        pass
                    else:
                        return {
                            "status": "instavel",
                            "is_instavel": True,
                            "mensagem": "Possíveis problemas reportados por usuários no Downdetector",
                            "metodo": "Downdetector (Relatos de Usuários)"
                        }
        except Exception:
            pass

        # 3. Fallback de conectividade direta caso não haja alerta no Downdetector
        if fallback_url:
            res_http = await self.check_http(session, fallback_url)
            return res_http

        return {
            "status": "normal",
            "is_instavel": False,
            "mensagem": "Serviço ativo sem alertas críticos",
            "metodo": "Downdetector (Relatos de Usuários)"
        }

    async def check_http(self, session: AsyncSession, target_url: str):
        try:
            start = asyncio.get_event_loop().time()
            resp = await session.get(target_url, timeout=10, allow_redirects=True)
            elapsed = int((asyncio.get_event_loop().time() - start) * 1000)

            if 200 <= resp.status_code < 400:
                return {
                    "status": "normal",
                    "is_instavel": False,
                    "mensagem": f"Online e respondendo ({elapsed}ms)",
                    "metodo": "Teste Direto de Conectividade (HTTP/TLS)"
                }
            elif 500 <= resp.status_code < 600:
                return {
                    "status": "instavel",
                    "is_instavel": True,
                    "mensagem": f"Erro interno no servidor (HTTP {resp.status_code})",
                    "metodo": "Teste Direto de Conectividade (HTTP/TLS)"
                }
            elif resp.status_code in [401, 403]:
                return {
                    "status": "normal",
                    "is_instavel": False,
                    "mensagem": f"Servidor ativo (WAF/HTTP {resp.status_code} em {elapsed}ms)",
                    "metodo": "Teste Direto de Conectividade (HTTP/TLS)"
                }
            else:
                return {
                    "status": "instavel",
                    "is_instavel": True,
                    "mensagem": f"Resposta inesperada (HTTP {resp.status_code})",
                    "metodo": "Teste Direto de Conectividade (HTTP/TLS)"
                }
        except asyncio.TimeoutError:
            return {
                "status": "offline",
                "is_instavel": True,
                "mensagem": "Tempo limite de resposta esgotado (Timeout > 10s)",
                "metodo": "Teste Direto de Conectividade (HTTP/TLS)"
            }
        except Exception as e:
            return {
                "status": "offline",
                "is_instavel": True,
                "mensagem": f"Falha de conexão / Indisponível ({str(e)})",
                "metodo": "Teste Direto de Conectividade (HTTP/TLS)"
            }

    async def _run_check_raw(self, session: AsyncSession, bank: dict):
        bank_type = bank.get("type", "http")
        target = bank.get("target", "")
        fallback_url = bank.get("fallback_url")

        if bank_type == "statuspage":
            return await self.check_statuspage(session, target)
        elif bank_type == "downdetector":
            return await self.check_downdetector_or_site(session, target, fallback_url=fallback_url)
        else:
            return await self.check_http(session, target)

    async def check_single_bank(self, session: AsyncSession, bank: dict):
        bank_type = bank.get("type", "http")

        # 1ª Tentativa de Verificação
        res = await self._run_check_raw(session, bank)

        # Mecanismo de Confirmação Dupla:
        # Se acusar instabilidade ou queda, o bot aguarda 2 segundos e faz uma nova tentativa.
        # Só confirma a instabilidade se a segunda tentativa também falhar, eliminando falsos positivos.
        if res["is_instavel"]:
            await asyncio.sleep(2)
            res_retry = await self._run_check_raw(session, bank)
            if not res_retry["is_instavel"]:
                res = res_retry

        return {
            "id": bank["id"],
            "name": bank["name"],
            "category": bank.get("category", "Geral"),
            "type": bank_type,
            "target": bank.get("target", ""),
            "status": res["status"],
            "is_instavel": res["is_instavel"],
            "mensagem": res["mensagem"],
            "metodo": res.get("metodo", "Teste de Conectividade"),
            "timestamp": datetime.now(FUSO_BRASILIA).strftime("%d/%m/%Y às %H:%M:%S")
        }

    async def check_all(self):
        # Concorrência otimizada para execução ultrarrápida em Serverless
        semaphore = asyncio.Semaphore(25)

        async with AsyncSession(impersonate="chrome120") as session:
            async def sem_check(bank):
                async with semaphore:
                    return await self.check_single_bank(session, bank)

            tasks = [sem_check(b) for b in self.banks]
            results = await asyncio.gather(*tasks)
            return results

    async def check_by_id_or_name(self, query: str):
        query_norm = query.lower().strip()
        matched_bank = None
        for b in self.banks:
            if query_norm == b["id"] or query_norm in b["name"].lower():
                matched_bank = b
                break

        if not matched_bank:
            for b in self.banks:
                if query_norm in b["id"]:
                    matched_bank = b
                    break

        if not matched_bank:
            return None

        async with AsyncSession(impersonate="chrome120") as session:
            return await self.check_single_bank(session, matched_bank)
