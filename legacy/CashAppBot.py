import discord
from discord.ext import commands
import json, os, random, string
from datetime import datetime

# ===================== CONFIG =====================
TOKEN = "REDACTED_ROTATE_TOKEN"
PREFIX = "-"
CASHAPP_USER = "$prodOutcastRecords"

BETA_ROLE_NAME = "Beta Tester"

TARGET_SERVER_ID = 1466279651021295648  # keys of sorrow
BOT_INFO_CHANNEL_ID = 1469492187673919641  # channel to send GUI message

DATA_DIR = "data"
DATA_FILE = f"{DATA_DIR}/users.json"
PROMO_FILE = f"{DATA_DIR}/promo_codes.json"
LOG_FILE = f"{DATA_DIR}/event_log.json"
BOT_MSG_FILE = f"{DATA_DIR}/bot_message.json"

# ===================== INTENTS =====================
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# ===================== STORAGE =====================
os.makedirs(DATA_DIR, exist_ok=True)

def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return default

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=4)

users = load_json(DATA_FILE, {"paid_users": {}})
promo_codes = load_json(PROMO_FILE, {})
event_log = load_json(LOG_FILE, [])
bot_msg_data = load_json(BOT_MSG_FILE, {})

# ===================== HELPERS =====================
def log_event(event):
    entry = {"time": str(datetime.utcnow()), "event": event}
    event_log.append(entry)
    save_json(LOG_FILE, event_log)
    print(event)

def generate_code(length=8):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def has_role(member, role_name):
    return any(r.name == role_name for r in member.roles)

# ===================== BUTTON UI =====================
class CashAppUI(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="💰 Unlock Vault With Lifetime Access", style=discord.ButtonStyle.green, custom_id="buy_access")
    async def buy_btn(self, interaction: discord.Interaction, _):
        await send_buy_embed(interaction.user)
        await interaction.response.send_message(
            "📩 Check your DMs for payment instructions.", ephemeral=True
        )

    @discord.ui.button(label="🎟 Generate Promo (Admin)", style=discord.ButtonStyle.blurple, custom_id="generate_promo")
    async def promo_btn(self, interaction: discord.Interaction, _):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Admins only.", ephemeral=True)
            return

        code = generate_code()
        promo_codes[code] = {
            "discount": 25,
            "server_id": TARGET_SERVER_ID,
            "created": str(datetime.utcnow())
        }
        save_json(PROMO_FILE, promo_codes)
        await interaction.response.send_message(f"✅ Promo code `{code}` created (25% OFF)", ephemeral=True)
        log_event(f"Promo {code} created by {interaction.user}")

    @discord.ui.button(label="📃 List Available Promos", style=discord.ButtonStyle.gray, custom_id="list_promos")
    async def list_promos_btn(self, interaction: discord.Interaction, _):
        promo_lines = [
            f"`{code}` ({info['discount']}% OFF)"
            for code, info in promo_codes.items()
            if info["server_id"] == TARGET_SERVER_ID
        ]
        
        if not promo_lines:
            await interaction.response.send_message("ℹ No promo codes available at the moment.", ephemeral=True)
            return

        embed = discord.Embed(
            title="📝 Available Promo Codes",
            description="\n".join(promo_lines),
            color=discord.Color.gold(),
            timestamp=datetime.utcnow()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

# ===================== BUY EMBED =====================
async def send_buy_embed(member):
    if has_role(member, BETA_ROLE_NAME):
        await member.send("✅ Beta tester detected — lifetime access is FREE.")
        return

    # List eligible promo codes
    promo_lines = [
        f"`{code}` ({info['discount']}% OFF)"
        for code, info in promo_codes.items()
        if info["server_id"] == TARGET_SERVER_ID
    ]
    promo_text = f"\n\n💸 **Eligible Promo Codes:**\n" + "\n".join(promo_lines) if promo_lines else ""

    embed = discord.Embed(
        title="💰 420Vault Lifetime Access",
        description=(
            "Welcome to **420Vault**, the ultimate resource hub for producers, artists, "
            "and beta testers in the server. By purchasing lifetime access, you unlock a "
            "wealth of exclusive content, tools, and updates that are unavailable to the general public.\n\n"

            "🔹 **What You Get:**\n"
            "- Full access to all current and future Vault content.\n"
            "- Exclusive tools, kits, and resources to accelerate your projects.\n"
            "- Direct support and updates — always free after purchase.\n"
            "- Recognition as a valued member of our creative community.\n\n"

            "💰 **Price:** $150 USD (one-time payment)\n"
            f"💵 **Cash App:** `{CASHAPP_USER}`\n"
            "Include your **Discord username** in the note so we can verify your purchase.\n\n"

            "This pricing helps maintain and expand the Vault while ensuring high-quality content and reliable updates. "
            "It also supports the community and allows us to continue beta testing new tools.\n\n"

            "⚠️ **Important:** Lifetime access is a one-time purchase and unlocks all content permanently. "
            "Beta Testers receive free access — thank you for your support!"
            "IMPORTANT This bot does not process payments or verify transactions. All payments are voluntary and handled directly between users.\n"
           
             f"{promo_text}"
        ),
        color=discord.Color.green(),
        timestamp=datetime.utcnow()
    )

    await member.send(embed=embed)
    log_event(f"{member} requested buy info")


# ===================== EVENTS =====================
@bot.event
async def on_ready():
    print(f"🚀 Logged in as {bot.user}")
    await bot.change_presence(activity=discord.Game("CashApp Access Online"))
    log_event("Bot started")

    bot.add_view(CashAppUI())

    channel = bot.get_channel(BOT_INFO_CHANNEL_ID)
    if not channel:
        print("❌ Bot info channel not found!")
        return

    msg_id = bot_msg_data.get("message_id")
    send_new_message = True

    # Build the full 420Vault explanation
    promo_lines = [
        f"`{code}` ({info['discount']}% OFF)"
        for code, info in promo_codes.items()
        if info["server_id"] == TARGET_SERVER_ID
    ]
    promo_text = f"\n\n💸 **Eligible Promo Codes:**\n" + "\n".join(promo_lines) if promo_lines else ""

    embed = discord.Embed(
        title="🚨 420Vault Lifetime Access System",
        description=(
            "Welcome to **420Vault**, the ultimate resource hub for producers, artists, "
            "and beta testers in the server. By purchasing lifetime access, you unlock a "
            "wealth of exclusive content, tools, and updates that are unavailable to the general public.\n\n"

            "🔹 **What You Get:**\n"
            "- Full access to all current and future Vault content.\n"
            "- Exclusive tools, kits, and resources to accelerate your projects.\n"
            "- Direct support and updates — always free after purchase.\n"
            "- Recognition as a valued member of our creative community.\n\n"

            "💰 **Price:** $150 USD (one-time)\n"
            f"💵 **Cash App:** `{CASHAPP_USER}`\n"
            "Include your **Discord username** in the note so we can verify your purchase.\n\n"

            "Maintaining and improving 420VaultBot takes time, effort, and resources. The one-time $150 payment helps us keep servers running, cover development costs, and ensure the bot stays stable, secure, and fast."
            "It also supports the community and allows us to continue beta testing new tools.\n\n"

            "⚠️ **Important:** Lifetime access is a one-time purchase and unlocks all content permanently. "
            "Beta Testers receive free access — thank you for your support! "
            "IMPORTANT This bot does not process payments or verify transactions. All payments are voluntary and handled directly between users.\n"
            f"{promo_text}"
        ),
        color=discord.Color.green(),
        timestamp=datetime.utcnow()
    )

    # Check if previous message exists
    if msg_id:
        try:
            msg = await channel.fetch_message(msg_id)
            await msg.edit(embed=embed, view=CashAppUI())  # update existing message
            send_new_message = False
        except discord.NotFound:
            send_new_message = True
        except Exception as e:
            print(f"⚠ Error fetching old message: {e}")
            send_new_message = True

    if send_new_message:
        msg = await channel.send(embed=embed, view=CashAppUI())
        await msg.pin()
        bot_msg_data["message_id"] = msg.id
        save_json(BOT_MSG_FILE, bot_msg_data)
        print("✅ Sent CashApp access embed with full explanation")
    else:
        print("ℹ CashApp embed updated with full explanation")
# ===================== VERIFY =====================
@bot.command()
@commands.is_owner()
async def verify(ctx, member: discord.Member):
    users["paid_users"][str(member.id)] = {"verified": str(datetime.utcnow())}
    save_json(DATA_FILE, users)

    await ctx.send(f"✅ {member.mention} manually verified.")
    log_event(f"{member} verified")

# ===================== LIST PROMOS =====================
@bot.command()
@commands.is_owner()
async def list_promos(ctx):
    if not promo_codes:
        await ctx.send("No promo codes.")
        return

    embed = discord.Embed(
        title="📝 Active Promo Codes",
        description="\n".join(
            f"{c} | {v['discount']}% | Server {v['server_id']}"
            for c, v in promo_codes.items()
        ),
        color=discord.Color.gold()
    )
    await ctx.send(embed=embed)

# ===================== LOGS =====================
@bot.command()
@commands.is_owner()
async def logs(ctx, limit: int = 15):
    entries = event_log[-limit:]
    text = "\n".join(f"[{e['time']}] {e['event']}" for e in entries)
    await ctx.send(f"```{text}```")

# ===================== START =====================
bot.run(TOKEN)
