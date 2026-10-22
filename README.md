# 🏦 Bot Financeiro - Monitor de Instabilidade Bancária

Bot interativo para Discord que monitora o status de bancos brasileiros, cooperativas, gateways de pagamento e BaaS (Banking as a Service). O bot dispara alertas automáticos com **data e horário exato** em caso de instabilidade ou normalização e permite consultas interativas em tempo real.

---

## 🚀 Como Iniciar o Bot

### 1. Configurar o `.env`
Abra o arquivo `.env` localizado nesta pasta e preencha com seus dados do Discord:

```env
DISCORD_TOKEN=seu_token_aqui
DISCORD_CHANNEL_ID=id_do_canal_de_alertas
CHECK_INTERVAL_MINUTES=3
```

### 2. Rodar o Bot
- **Pelo atalho:** Basta dar dois cliques em `iniciar_bot.bat`.
- **Ou pelo terminal:**
  ```powershell
  python bot.py
  ```

---

## ⚡ Comandos Interativos no Discord

O bot suporta comandos Slash modernos (`/`) e comandos por prefixo (`!`):

| Comando | Descrição |
| :--- | :--- |
| `/status <banco>` | Consulta o status detalhado de uma instituição em tempo real. Ex: `/status itau`, `/status asaas`, `/status bb`. |
| `/instabilidades` | Lista instantaneamente todas as instituições que estão fora do ar ou com problemas no momento. |
| `/bancos` | Exibe o catálogo completo de instituições e gateways monitorados divididos por categoria. |

---

## 🧪 Teste Rápido pelo Terminal (Sem precisar do Discord ligado)

Você pode testar a checagem a qualquer momento direto pelo prompt de comando:

* Consultar um banco específico:
  ```powershell
  python testar_status.py asaas
  python testar_status.py "banco do brasil"
  python testar_status.py itau
  ```
* Verificar todas as 54 instituições de uma só vez:
  ```powershell
  python testar_status.py
  ```

---

## 📁 Arquivos do Projeto

* `bot.py`: Código principal do Discord Bot (comandos Slash, loop em segundo plano e disparos de alertas).
* `checker.py`: Motor de checagem assíncrono (Statuspage JSON APIs, Downdetector e conectividade direta com bypass TLS/Akamai).
* `banks.json`: Catálogo com as mais de 50 instituições, gateways e adquirentes configurados.
* `testar_status.py`: Utilitário CLI para testes rápidos locais.
* `iniciar_bot.bat`: Script para iniciar o bot com dois cliques no Windows.
* `.env`: Arquivo de credenciais e configurações.
