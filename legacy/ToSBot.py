import discord
from discord.ext import commands

# ===== CONFIG =====
BOT_TOKEN = "REDACTED_ROTATE_TOKEN"
LEGAL_CHANNEL_ID = 1466672707687944194  # Channel where ToS is posted
TOS_MESSAGE_ID = 1469055109207166997  # <-- Paste the message ID of the ToS message after first post
TOS_LOG_CHANNEL_ID = 1468518873610584128
TOS_ACCEPTED_ROLE_ID = 1469049504245350515
# ==================

intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)


class ToSView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # Persist indefinitely

    @discord.ui.button(label="Agree to Server ToS", style=discord.ButtonStyle.success, custom_id="agree_tos")
    async def agree_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.user
        guild = interaction.guild
        role = guild.get_role(TOS_ACCEPTED_ROLE_ID) if TOS_ACCEPTED_ROLE_ID else None

        if role and role in member.roles:
            await interaction.response.send_message("You already agreed to the server ToS.", ephemeral=True)
            return

        if role:
            # Check bot hierarchy
            bot_role = guild.me.top_role
            if role.position >= bot_role.position:
                await interaction.response.send_message(
                    "Cannot assign role: role is higher than the bot's role.", ephemeral=True
                )
                return
            await member.add_roles(role)

        log_channel = guild.get_channel(TOS_LOG_CHANNEL_ID)
        if log_channel:
            await log_channel.send(f"✅ {member.mention} agreed to the server ToS.")

        await interaction.response.send_message("You have successfully agreed to the server ToS.", ephemeral=True)


@bot.event
async def on_ready():
    print(f"🖤 Logged in as {bot.user} ({bot.user.id})")

    try:
        channel = bot.get_channel(LEGAL_CHANNEL_ID)
        if channel:
            if TOS_MESSAGE_ID == 0:
                # First-time run: send ToS manually
                tos_message = """
KEYS OF SORROW — COMMUNITY NOTICE
⚖️ LEGAL DISCLAIMER & TERMS OF USE

KEYS OF SORROW — COMMUNITY NOTICE

By joining, remaining in, or interacting with this server, you acknowledge and agree to the following terms in full.

1. INFORMATIONAL PURPOSE ONLY

This server exists for educational, archival, and informational discussion purposes only.
All content shared, indexed, referenced, or discussed within this community is provided as information, not as a product, service, or transaction.

This server does not:

Sell software, plugins, samples, or media

Distribute files directly

Host copyrighted material

Guarantee access to any external resource

We provide references and links publicly available on the internet for informational awareness.

2. NO OWNERSHIP OR AFFILIATION

Keys of Sorrow and its staff:

Do not own any third-party software, presets, plugins, samples, or intellectual property referenced

Are not affiliated with any DAW, plugin manufacturer, sample company, or developer

Do not claim authorship or rights over any third-party material

All trademarks, copyrights, and intellectual property remain the property of their respective owners.

3. USER RESPONSIBILITY & FREE CHOICE

Every member acts independently and voluntarily.

You are solely responsible for:

How you access information

How you use external links

Ensuring compliance with your local, regional, and national laws

Any downloads, installations, or actions taken outside this server

No user is required, pressured, or incentivized to access any specific material.

Freedom of information does not remove personal responsibility.

4. NO FILE HOSTING / NO DIRECT DISTRIBUTION

This server does not:

Upload files

Store files

Transfer files

Act as a file-sharing service

All links point to external locations not controlled, owned, or operated by this community or its staff.

If a third-party link becomes unavailable, altered, restricted, or removed, the server holds no responsibility.

5. NO COMMERCIAL TRANSACTIONS

Keys of Sorrow does not engage in:

Selling pirated software

Charging for copyrighted material

Forcing paid access to specific content

Marketplace-style exchanges

Any optional support, donations, or memberships (if applicable) relate to community infrastructure and access to indexing tools, not ownership of content.

Access levels relate to search scope and discovery tools, not the sale of media.

6. EDUCATIONAL & ARCHIVAL CONTEXT

Many discussions and resources exist for:

Learning production techniques

Studying sound design

Understanding software ecosystems

Preserving historical or discontinued tools

Academic or personal research

Members are encouraged to:

Support developers when possible

Purchase licenses for tools they rely on professionally

Use information responsibly and ethically

7. NO LEGAL ADVICE

Nothing within this server constitutes legal advice.

Members seeking legal clarity regarding software usage, licensing, or intellectual property should consult:

Official developers

Licensed legal professionals

Local regulations

8. MODERATION & COMPLIANCE

The moderation team reserves the right to:

Remove content

Restrict access

Revoke roles

Remove users

Enforce server rules

Any activity that:

Involves scams

Involves resale of third-party material

Misrepresents the server

Puts the community at legal or ethical risk

may result in immediate removal without warning.

9. ACCEPTANCE OF TERMS

By remaining in this server, you confirm that:

You understand this disclaimer

You accept full responsibility for your actions

You acknowledge this server is informational only

You waive liability against the server, staff, and contributors

If you do not agree with these terms, you must leave the server immediately.

🖤 FINAL STATEMENT

Underground ≠ illegal.
Knowledge is not ownership.
Information is not coercion.

Move smart.
Respect the craft.
Respect the law where you live.
"""
                # Split into chunks if >2000 chars
                chunks = []
                while len(tos_message) > 2000:
                    split_index = tos_message.rfind("\n", 0, 2000)
                    if split_index == -1:
                        split_index = 2000
                    chunks.append(tos_message[:split_index])
                    tos_message = tos_message[split_index:]
                chunks.append(tos_message)

                view = ToSView()
                for chunk in chunks[:-1]:
                    await channel.send(content=chunk)
                msg = await channel.send(content=chunks[-1], view=view)
                print(f"✅ ToS message sent. Message ID: {msg.id}")
                print("⚠️ Update TOS_MESSAGE_ID in your config with this ID for future runs.")
            else:
                # Bot restarted: fetch existing message and attach button
                msg = await channel.fetch_message(TOS_MESSAGE_ID)
                view = ToSView()
                await msg.edit(view=view)
                print("✅ ToS bot is listening for button clicks.")
    except Exception as e:
        print(f"❌ Failed to attach ToS view: {e}")


bot.run(BOT_TOKEN)
