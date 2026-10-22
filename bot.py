import os
import sys
from datetime import datetime
import asyncio
import logging

# Garante suporte a UTF-8 no terminal Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv

from checker import BankStatusChecker

# Carrega variáveis de ambiente
load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL_MINUTES", "3"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("BankBot")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
checker = BankStatusChecker(os.path.join(os.path.dirname(__file__), "banks.json"))

# Bancos principais que disparam menção @everyone em caso de instabilidade
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

# Rastreamento de estado de instabilidade para não inundar o canal
# {bank_id: bool}
bancos_estado = {}

def get_status_color_and_emoji(status: str):
    if status == "normal":
        return discord.Color.green(), "🟢"
    elif status == "instavel":
        return discord.Color.gold(), "🟡"
    elif status == "offline":
        return discord.Color.red(), "🔴"
    else:
        return discord.Color.greyple(), "⚪"

@bot.event
async def on_ready():
    logger.info(f"Bot conectado com sucesso como {bot.user} (ID: {bot.user.id})")
    
    # Sincroniza comandos Slash
    try:
        synced = await bot.tree.sync()
        logger.info(f"Sincronizados {len(synced)} comandos Slash.")
    except Exception as e:
        logger.error(f"Erro ao sincronizar comandos Slash: {e}")

    # Inicia a verificação periódica se o canal estiver configurado
    if not monitorar_servicos.is_running():
        monitorar_servicos.start()

@tasks.loop(minutes=CHECK_INTERVAL)
async def monitorar_servicos():
    if not CHANNEL_ID or CHANNEL_ID == "id_do_canal_de_alertas_aqui":
        logger.warning("DISCORD_CHANNEL_ID não configurado no .env. Alertas automáticos pausados.")
        return

    try:
        canal = bot.get_channel(int(CHANNEL_ID))
    except (ValueError, TypeError):
        canal = None

    if not canal:
        logger.warning(f"Canal de alertas {CHANNEL_ID} não encontrado.")
        return

    logger.info("Executando checagem periódica dos bancos e gateways...")
    resultados = await checker.check_all()

    for item in resultados:
        bank_id = item["id"]
        esta_instavel = item["is_instavel"]
        estado_anterior = bancos_estado.get(bank_id, False)

        # Transição: Ficou INSTÁVEL agora
        if esta_instavel and not estado_anterior:
            bancos_estado[bank_id] = True
            is_principal = bank_id in BANCOS_PRINCIPAIS
            
            embed = discord.Embed(
                title=f"⚠️ Instabilidade: {item['name']}",
                color=discord.Color.red() if item["status"] == "offline" else discord.Color.gold(),
            )
            embed.add_field(name="📋 Diagnóstico", value=f"**{item['mensagem']}**", inline=False)
            embed.add_field(name="🕒 Horário", value=f"`{item['timestamp']}`", inline=True)
            embed.add_field(name="⚡ Status", value=f"`{item['status'].upper()}`", inline=True)
            embed.add_field(name="🔍 Método de Consulta", value=item.get("metodo", "Teste de Conectividade"), inline=False)
            
            # Só menciona @everyone se for um dos bancos principais da lista
            mention = "@everyone" if is_principal else None
            
            try:
                await canal.send(content=mention, embed=embed)
                logger.info(f"Alerta enviado para {item['name']} (Principal: {is_principal})")
            except Exception as e:
                logger.error(f"Erro ao enviar alerta no Discord: {e}")

        # Transição: NORMALIZOU
        elif not esta_instavel and estado_anterior:
            bancos_estado[bank_id] = False
            
            embed = discord.Embed(
                title=f"✅ Normalizado: {item['name']}",
                description="O serviço voltou a responder normalmente.",
                color=discord.Color.green(),
            )
            embed.add_field(name="🕒 Horário", value=f"`{item['timestamp']}`", inline=True)
            
            try:
                await canal.send(embed=embed)
                logger.info(f"Notificação de normalização enviada para {item['name']}")
            except Exception as e:
                logger.error(f"Erro ao enviar notificação de normalização: {e}")

@monitorar_servicos.before_loop
async def before_monitorar():
    await bot.wait_until_ready()

# ================= COMANDOS INTERATIVOS =================

@bot.tree.command(name="status", description="Consulta o status atual de um banco ou gateway específico")
@app_commands.describe(banco="Nome ou código do banco (ex: nubank, itau, asaas, inter)")
async def slash_status(interaction: discord.Interaction, banco: str):
    await interaction.response.defer()
    
    resultado = await checker.check_by_id_or_name(banco)
    if not resultado:
        await interaction.followup.send(
            f"❌ Instituição `{banco}` não encontrada na lista. Use `/bancos` para ver todas as instituições monitoradas."
        )
        return

    cor, emoji = get_status_color_and_emoji(resultado["status"])
    
    embed = discord.Embed(
        title=f"{emoji} {resultado['name']}",
        color=cor
    )
    embed.add_field(name="📋 Diagnóstico", value=f"**{resultado['mensagem']}**", inline=False)
    embed.add_field(name="⚡ Status", value=f"`{resultado['status'].upper()}`", inline=True)
    embed.add_field(name="🕒 Horário", value=f"`{resultado['timestamp']}`", inline=True)
    embed.add_field(name="🔍 Método de Consulta", value=resultado.get("metodo", "Teste de Conectividade"), inline=False)
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="instabilidades", description="Lista todas as instituições com instabilidade ou fora do ar agora")
async def slash_instabilidades(interaction: discord.Interaction):
    await interaction.response.defer()
    
    resultados = await checker.check_all()
    com_problema = [r for r in resultados if r["is_instavel"]]
    
    agora_str = datetime.now().strftime("%d/%m/%Y às %H:%M:%S")

    if not com_problema:
        embed = discord.Embed(
            title="✅ Tudo Operacional!",
            description="Nenhuma instituição monitorada está com instabilidade detectada no momento.",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        embed.set_footer(text=f"Checagem realizada em {agora_str}")
        await interaction.followup.send(embed=embed)
        return

    embed = discord.Embed(
        title=f"⚠️ {len(com_problema)} Instituição(ões) com Instabilidade",
        description=f"Status verificado em `{agora_str}`:",
        color=discord.Color.gold(),
        timestamp=datetime.now()
    )

    for item in com_problema[:25]:  # Discord limita campos a 25 por embed
        emoji = "🔴" if item["status"] == "offline" else "🟡"
        embed.add_field(
            name=f"{emoji} {item['name']} ({item['category']})",
            value=f"**Status:** {item['status'].upper()}\n**Detalhes:** {item['mensagem']}",
            inline=False
        )

    await interaction.followup.send(embed=embed)

@bot.tree.command(name="bancos", description="Exibe a lista de todos os bancos e serviços monitorados")
async def slash_bancos(interaction: discord.Interaction):
    # Agrupa bancos por categoria
    categorias = {}
    for b in checker.banks:
        cat = b.get("category", "Geral")
        categorias.setdefault(cat, []).append(b["name"])

    embed = discord.Embed(
        title=f"🏦 Instituições Monitoradas ({len(checker.banks)})",
        description="Você pode consultar o status de qualquer uma usando `/status <nome>`",
        color=discord.Color.blue()
    )

    for cat, lista in categorias.items():
        embed.add_field(
            name=f"📌 {cat} ({len(lista)})",
            value=", ".join(lista[:15]) + ("..." if len(lista) > 15 else ""),
            inline=False
        )

    embed.set_footer(text="Bot Financeiro • Use /status <nome> para verificar")
    await interaction.response.send_message(embed=embed)

# Comandos prefixados de fallback (ex: !status itau)
@bot.command(name="status")
async def cmd_status(ctx, *, banco: str):
    resultado = await checker.check_by_id_or_name(banco)
    if not resultado:
        await ctx.send(f"❌ Banco `{banco}` não encontrado. Digite `!bancos` para ver a lista.")
        return

    cor, emoji = get_status_color_and_emoji(resultado["status"])
    embed = discord.Embed(
        title=f"{emoji} {resultado['name']}",
        color=cor
    )
    embed.add_field(name="📋 Diagnóstico", value=f"**{resultado['mensagem']}**", inline=False)
    embed.add_field(name="⚡ Status", value=f"`{resultado['status'].upper()}`", inline=True)
    embed.add_field(name="🕒 Horário", value=f"`{resultado['timestamp']}`", inline=True)
    embed.add_field(name="🔍 Método de Consulta", value=resultado.get("metodo", "Teste de Conectividade"), inline=False)
    await ctx.send(embed=embed)

@bot.command(name="instabilidades")
async def cmd_instabilidades(ctx):
    msg = await ctx.send("🔍 Verificando status de todas as instituições, aguarde...")
    resultados = await checker.check_all()
    com_problema = [r for r in resultados if r["is_instavel"]]
    
    agora_str = datetime.now().strftime("%d/%m/%Y às %H:%M:%S")

    if not com_problema:
        embed = discord.Embed(
            title="✅ Tudo Operacional!",
            description="Nenhuma instituição monitorada está com instabilidade no momento.",
            color=discord.Color.green()
        )
        embed.set_footer(text=f"Checagem em {agora_str}")
        await msg.edit(content=None, embed=embed)
        return

    embed = discord.Embed(
        title=f"⚠️ {len(com_problema)} Instituição(ões) com Instabilidade",
        description=f"Status verificado em `{agora_str}`:",
        color=discord.Color.gold()
    )
    for item in com_problema[:25]:
        emoji = "🔴" if item["status"] == "offline" else "🟡"
        embed.add_field(
            name=f"{emoji} {item['name']}",
            value=f"**Status:** {item['status'].upper()} - {item['mensagem']}",
            inline=False
        )
    await msg.edit(content=None, embed=embed)

@bot.command(name="bancos")
async def cmd_bancos(ctx):
    nomes = [b["name"] for b in checker.banks]
    await ctx.send(f"🏦 **{len(nomes)} instituições monitoradas:**\n" + ", ".join(nomes[:30]) + "\n*(e outras... digite !status <nome>)*")

if __name__ == "__main__":
    if not TOKEN or TOKEN == "seu_token_do_bot_aqui":
        print("\n❌ ERRO: O DISCORD_TOKEN não foi configurado!")
        print("Edite o arquivo .env dentro da pasta 'bot financeiro' e adicione o token do seu bot.")
        print("Exemplo: DISCORD_TOKEN=MTE5OTg0...\n")
        sys.exit(1)

    print("Iniciando Bot Financeiro...")
    bot.run(TOKEN)
