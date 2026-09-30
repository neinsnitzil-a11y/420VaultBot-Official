from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Optional

import discord
from discord.ext import commands

from app.core.security import is_admin
from app.core.user_channels import command_channel_allowed


@dataclass(frozen=True)
class FieldSpec:
    name: str
    label: str
    placeholder: str = ''
    required: bool = True
    default: str = ''
    max_length: int = 400
    kind: str = 'str'  # str, int, member, channel


@dataclass(frozen=True)
class CommandSpec:
    name: str
    label: str
    emoji: str
    category: str
    description: str
    admin: bool = False
    fields: tuple[FieldSpec, ...] = ()
    special: Optional[str] = None


CATEGORIES = {
    'account': ('Account & Help', '🔐', False),
    'search': ('Search & Browse', '🔎', False),
    'vault': ('Vault Tools', '💾', False),
    'access': ('Access & Subscription', '🎟️', False),
    'admin_core': ('Admin • Setup & System', '⚙️', True),
    'admin_data': ('Admin • Vault, Drive & Links', '🗄️', True),
    'admin_license': ('Admin • Licensing & Payments', '🔑', True),
}


def F(name, label, placeholder='', required=True, default='', max_length=400, kind='str'):
    return FieldSpec(name, label, placeholder, required, default, max_length, kind)


SPECS = (
    CommandSpec('auth','Auth','🔐','account','Open the existing account/sign-in workflow.'),
    CommandSpec('profile','My Profile','👤','account','Open your profile, or view another member’s public profile.',fields=(F('member','Member (optional)','@user or user ID',False,kind='member'),)),
    CommandSpec('logout','Logout','🚪','account','Revoke your current 420Vault session.'),
    CommandSpec('help','Help','❓','account','Show the existing command help.'),
    CommandSpec('user_manual','User Manual','📘','account','Open the user manual GUI.'),
    CommandSpec('tos','Terms / ToS','📜','account','Open the Terms verification workflow.'),
    CommandSpec('features','Feature Center','🌿','account','Open the existing feature center.'),
    CommandSpec('sources','Search Sources','🧭','account','Show the available search sources.'),
    CommandSpec('status','Bot Status','🟢','account','Show current bot operational status.'),
    CommandSpec('version','Version','🏷️','account','Show the running bot version.'),

    CommandSpec('search','Search Links','🔎','search','Open unified link search.',fields=(F('query','Search query','serum presets, trap drum kit...',False),)),
    CommandSpec('search_site','Search by Site','🌐','search','Search a specific website/domain.',fields=(F('domain','Website / domain','example.com'),F('query','Optional keywords','serum, omnisphere...',False))),
    CommandSpec('vault_search','Vault Search','💾','search','Open physical Vault search.',fields=(F('query','Search query','808, kick, loop...',False),)),
    CommandSpec('drive_search','Drive Search','☁️','search','Open Google Drive search.'),
    CommandSpec('server_search','Remote Server Search','🖥️','search','Open configured remote-server search.'),
    CommandSpec('sendlink','Send Random Link','📨','search','Send a random matching link to a channel.',fields=(F('query','Search term','serum'),F('channel','Destination channel','Channel mention or ID',kind='channel'))),

    CommandSpec('vault_stats','Vault Stats','📊','vault','Show physical Vault indexing statistics.'),
    CommandSpec('vault_random','Random Vault File','🎲','vault','Pull a random Vault audio/file result.'),
    CommandSpec('vault_search_type','Search by Type','🧩','vault','Search Vault by file extension.',fields=(F('extension','File extension','wav'),F('limit','Results per page','5',False,'5',kind='int'),F('page','Page','1',False,'1',kind='int'))),
    CommandSpec('vault_search_size','Search by Size','📐','vault','Search Vault using a size comparison.',fields=(F('operator','Operator','>, >=, <, <=, ='),F('value','Size','100MB'),F('limit','Results per page','5',False,'5',kind='int'),F('page','Page','1',False,'1',kind='int'))),
    CommandSpec('vault_search_terms','Search Terms','🎚️','vault','Search Vault by music-production terms.',fields=(F('terms','Terms','kicks snares 808s'),)),
    CommandSpec('vault_list','Browse Vault Folder','📁','vault','List a Vault folder.',fields=(F('path','Vault-relative path','Drums/Kits',False),F('page','Page','1',False,'1',kind='int'))),
    CommandSpec('download_vault','Download Vault File','⬇️','vault','Download an indexed Vault file by ID.',fields=(F('file_id','Vault file ID','12345',kind='int'),)),

    CommandSpec('subscribe','Subscribe','💳','access','Open subscription plan selection.'),
    CommandSpec('subscription','My Subscription','📅','access','Show your active subscription/admin entitlement.'),

    CommandSpec('admin_manual','Admin Manual','📕','admin_core','Open the administrator manual GUI.',True),
    CommandSpec('setup','Setup','🛠️','admin_core','Open the existing server setup GUI.',True),
    CommandSpec('admin','Admin GUI','⚙️','admin_core','Open the existing full admin GUI.',True),
    CommandSpec('diagnostics','Diagnostics','🩺','admin_core','Run the existing diagnostics report.',True),
    CommandSpec('showchannels','Show Channels','📋','admin_core','Show configured search/license/log channels.',True),
    CommandSpec('lockdown','Lockdown','🚨','admin_core','Enable command lockdown.',True),
    CommandSpec('unlock','Unlock','✅','admin_core','Disable command lockdown.',True),
    CommandSpec('exportserver','Export Server','📦','admin_core','Export roles/channels/server information.',True),

    CommandSpec('vault_path','Set Vault Path','🗂️','admin_data','Set the physical Vault root path.',True,(F('path','Vault root folder','E:\\420Vault'),)),
    CommandSpec('reindex_vault','Reindex Vault','🔄','admin_data','Run the existing full Vault reindex.',True),
    CommandSpec('admin_delete_vault_index','Delete Vault Index','🗑️','admin_data','Clear the index only; files on disk stay untouched.',True),
    CommandSpec('drive_config','Drive Config','☁️','admin_data','Open Drive config or set a Drive folder URL/ID.',True,(F('folder','Drive folder URL / ID','Leave blank to open Drive GUI',False),)),
    CommandSpec('drive_sync','Drive Sync','🔄','admin_data','Start the existing background Drive metadata sync.',True),
    CommandSpec('drive_status','Drive Status','📈','admin_data','Show Drive sync/index status.',True),
    CommandSpec('importlinks','Import Link List','📥','admin_data','Import a TXT/CSV link list using the existing ingest workflow.',True,(F('list_name','List name','Imported Links',False,'Imported Links'),),special='attachment'),
    CommandSpec('reloadlinks','Reload Links','♻️','admin_data','Reload all configured link sources.',True),

    CommandSpec('addlicense','Add License / Grant','✨','admin_license','Create an explicit administrator access grant and DM activation.',True,(F('user','User','@user or user ID',kind='member'),F('days_valid','Days valid','0 = lifetime',False,'0',kind='int'),F('max_activations','Max activations','1',False,'1',kind='int'))),
    CommandSpec('approvepayment','Approve Payment','💵','admin_license','Approve a pending Cash App/manual transaction.',True,(F('transaction_id','Transaction ID','123',kind='int'),)),
    CommandSpec('resendlicense','Resend License','📨','admin_license','Resend the latest active license DM.',True,(F('user','User','@user or user ID',kind='member'),)),
    CommandSpec('revokelicense','Revoke License','⛔','admin_license','Revoke a license code.',True,(F('code','License code','420V-XXXX-XXXX-XXXX'),)),
    CommandSpec('showlicense','Show License','🔍','admin_license','DM private details for a license.',True,(F('code','License code','420V-XXXX-XXXX-XXXX'),)),
    CommandSpec('listlicenses','List Licenses','📜','admin_license','DM recent licenses, optionally filtered by status.',True,(F('status_filter','Optional status','active / inactive / expired / revoked',False),)),
    CommandSpec('resetuserlicenses','Reset User Licenses','♻️','admin_license','Reset a user’s license bindings.',True,(F('user','User','@user or user ID',kind='member'),)),
)

SPEC_BY_NAME = {x.name:x for x in SPECS}


def _interaction_is_admin(interaction: discord.Interaction):
    if not interaction.guild_id:
        return False
    st = interaction.client.db.guild(interaction.guild_id)
    return bool(is_admin(interaction, st))


async def _ensure_interaction_command_zone(interaction: discord.Interaction):
    """Enforce the same channel zones for persistent/help buttons as prefix commands."""
    if not interaction.guild:
        return True
    admin = _interaction_is_admin(interaction)
    if command_channel_allowed(interaction.guild, interaction.channel, interaction.client.db, admin=admin):
        return True
    message = ('⛔ 420Vault commands are restricted to the **AUDIO VAULT** channels.'
               + (' Administrators may also use **🧪-bot-testing**.' if admin else ''))
    if not interaction.response.is_done():
        await interaction.response.send_message(message, ephemeral=True)
    else:
        await interaction.followup.send(message, ephemeral=True)
    return False


class _InvocationMessage:
    """Small message facade used by original prefix callbacks when launched from a button."""
    def __init__(self, interaction: discord.Interaction, attachments=None):
        self.id = int(interaction.id)
        self.author = interaction.user
        self.channel = interaction.channel
        self.guild = interaction.guild
        self.attachments = list(attachments or [])
        self.content = ''

    async def delete(self, *args, **kwargs):
        # There is no typed command message to remove when a button is used.
        return None


class InteractionCommandContext:
    """Compatibility context so legacy 420_ callbacks keep their existing workflow."""
    def __init__(self, bot, interaction: discord.Interaction, command, attachments=None):
        self.bot = bot
        self.interaction = interaction
        self.author = interaction.user
        self.guild = interaction.guild
        self.channel = interaction.channel
        self.command = command
        self.prefix = '420_'
        self.invoked_with = command.name
        self.message = _InvocationMessage(interaction, attachments)

    async def send(self, content=None, **kwargs):
        kwargs.pop('ephemeral', None)
        if not self.interaction.response.is_done():
            await self.interaction.response.send_message(content=content, **kwargs)
            try:
                return await self.interaction.original_response()
            except Exception:
                return None
        return await self.interaction.followup.send(content=content, wait=True, **kwargs)


async def _resolve_member(guild: discord.Guild, raw: str):
    digits = re.sub(r'\D', '', raw or '')
    if not digits:
        raise ValueError('Enter a user mention or user ID.')
    uid = int(digits)
    member = guild.get_member(uid)
    if member is None:
        try:
            member = await guild.fetch_member(uid)
        except Exception:
            member = None
    if member is None:
        raise ValueError('That user could not be found in this server.')
    return member


def _resolve_channel(guild: discord.Guild, raw: str):
    digits = re.sub(r'\D', '', raw or '')
    if not digits:
        raise ValueError('Enter a channel mention or channel ID.')
    ch = guild.get_channel(int(digits))
    if not isinstance(ch, discord.TextChannel):
        raise ValueError('That is not a text channel in this server.')
    return ch


async def _convert_fields(interaction: discord.Interaction, spec: CommandSpec, values: dict[str,str]):
    out = {}
    for f in spec.fields:
        raw = (values.get(f.name) or '').strip()
        if not raw and f.default:
            raw = f.default
        if not raw and not f.required:
            # Preserve callback defaults where sensible. Optional Discord objects stay None.
            if f.kind == 'int':
                continue
            if f.kind in ('member','channel'):
                out[f.name] = None
            else:
                out[f.name] = '' if f.name not in ('status_filter',) else None
            continue
        if not raw and f.required:
            raise ValueError(f'**{f.label}** is required.')
        if f.kind == 'int':
            try: out[f.name] = int(raw)
            except Exception: raise ValueError(f'**{f.label}** must be a whole number.')
        elif f.kind == 'member':
            out[f.name] = await _resolve_member(interaction.guild, raw)
        elif f.kind == 'channel':
            out[f.name] = _resolve_channel(interaction.guild, raw)
        else:
            out[f.name] = raw
    return out


async def invoke_existing_command(interaction: discord.Interaction, spec: CommandSpec, values=None, attachments=None):
    values = values or {}
    command = interaction.client.get_command(spec.name)
    if command is None:
        if not interaction.response.is_done():
            return await interaction.response.send_message(f'❌ `420_{spec.name}` is not loaded.', ephemeral=True)
        return await interaction.followup.send(f'❌ `420_{spec.name}` is not loaded.', ephemeral=True)
    ctx = InteractionCommandContext(interaction.client, interaction, command, attachments=attachments)
    try:
        # Acknowledge immediately so searches/reindexing can take longer than Discord's interaction window.
        # Follow-up messages stay public, matching the original prefix-command workflow.
        if not interaction.response.is_done():
            await interaction.response.defer(thinking=True)
        # Run the same bot/cog/command checks used by the prefix command before the callback.
        allowed = await command.can_run(ctx)
        if not allowed:
            return
        kwargs = await _convert_fields(interaction, spec, values)
        await command.callback(command.cog, ctx, **kwargs)
        if interaction.guild:
            try:
                await interaction.client.log_event(interaction.guild.id,'COMMAND_BUTTON',f'{interaction.user} ({interaction.user.id}) ran 420_{spec.name} from the v6.2.4 Command Center')
            except Exception:
                pass
    except commands.CheckFailure:
        return
    except Exception as exc:
        text = f'❌ Command failed: `{type(exc).__name__}: {str(exc)[:1200]}`'
        if not interaction.response.is_done():
            await interaction.response.send_message(text, ephemeral=True)
        else:
            await interaction.followup.send(text, ephemeral=True)


class CommandInputModal(discord.ui.Modal):
    def __init__(self, spec: CommandSpec):
        super().__init__(title=f'420_{spec.name}'[:45], timeout=300)
        self.spec = spec
        self.inputs = {}
        for f in spec.fields:
            item = discord.ui.TextInput(
                label=f.label[:45],
                placeholder=f.placeholder[:100] if f.placeholder else None,
                required=f.required,
                default=(f.default or None),
                max_length=f.max_length,
            )
            self.inputs[f.name] = item
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction):
        values = {name: str(item.value or '') for name,item in self.inputs.items()}
        if self.spec.special == 'attachment':
            return await self._attachment_flow(interaction, values)
        await invoke_existing_command(interaction, self.spec, values)

    async def _attachment_flow(self, interaction: discord.Interaction, values):
        await interaction.response.send_message('📥 Upload the `.txt` or `.csv` link-list file in this channel within **60 seconds**. I’ll pass that exact attachment into the existing `420_importlinks` workflow.', ephemeral=True)
        try:
            msg = await interaction.client.wait_for(
                'message', timeout=60,
                check=lambda m: m.author.id == interaction.user.id and m.channel.id == interaction.channel.id and bool(m.attachments)
            )
        except asyncio.TimeoutError:
            return await interaction.followup.send('⌛ Import cancelled because no attachment was received within 60 seconds.', ephemeral=True)
        await invoke_existing_command(interaction, self.spec, values, attachments=msg.attachments)


class CommandButton(discord.ui.Button):
    def __init__(self, spec: CommandSpec, row: int):
        style = discord.ButtonStyle.danger if spec.admin and spec.name in ('lockdown','admin_delete_vault_index','revokelicense') else (discord.ButtonStyle.secondary if spec.admin else discord.ButtonStyle.primary)
        super().__init__(label=spec.label[:80], emoji=spec.emoji, style=style, row=row)
        self.spec = spec

    async def callback(self, interaction: discord.Interaction):
        if not await _ensure_interaction_command_zone(interaction):
            return
        if self.spec.admin:
            st = interaction.client.db.guild(interaction.guild_id)
            if not is_admin(interaction, st):
                return await interaction.response.send_message('⛔ Administrator access is required.', ephemeral=True)
        if self.spec.fields:
            return await interaction.response.send_modal(CommandInputModal(self.spec))
        await invoke_existing_command(interaction, self.spec)


class CommandPageView(discord.ui.View):
    def __init__(self, owner_id: int, category: str):
        super().__init__(timeout=900)
        self.owner_id = owner_id
        specs = [s for s in SPECS if s.category == category]
        for idx,spec in enumerate(specs[:20]):
            self.add_item(CommandButton(spec, row=idx//4))

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message('Open your own 420Vault Command Center panel.', ephemeral=True)
        return False


class CategoryButton(discord.ui.Button):
    def __init__(self, key: str, row: int):
        title,emoji,admin = CATEGORIES[key]
        super().__init__(label=title, emoji=emoji, style=discord.ButtonStyle.secondary if admin else discord.ButtonStyle.primary, custom_id=f'420vault:cmdcenter:category:{key}', row=row)
        self.key=key;self.admin_only=admin

    async def callback(self, interaction: discord.Interaction):
        if not await _ensure_interaction_command_zone(interaction):
            return
        if self.admin_only:
            st = interaction.client.db.guild(interaction.guild_id)
            if not is_admin(interaction, st):
                return await interaction.response.send_message('⛔ Administrator access is required.', ephemeral=True)
        title,emoji,_ = CATEGORIES[self.key]
        specs=[s for s in SPECS if s.category==self.key]
        e=discord.Embed(title=f'{emoji} {title}',description='Every button below launches the same existing `420_` command workflow. Commands that need input open a form first.',color=discord.Color.dark_green())
        e.add_field(name='Commands on this page',value=' • '.join(f'`420_{s.name}`' for s in specs),inline=False)
        await interaction.response.send_message(embed=e,view=CommandPageView(interaction.user.id,self.key),ephemeral=True)


class CommandCenterView(discord.ui.View):
    """Persistent launcher posted into configured 420Vault user/search channels."""
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot=bot
        keys=list(CATEGORIES)
        for idx,key in enumerate(keys):
            self.add_item(CategoryButton(key,row=idx//3))


def command_center_embed():
    e=discord.Embed(
        title='🎛️ 420VaultBot Command Center',
        description='**v6.2.4 button controls** — use the buttons below instead of memorizing commands.\n\nThe original `420_` commands remain available and their existing workflows are unchanged.',
        color=discord.Color.dark_green(),
    )
    e.add_field(name='👤 User controls',value='Account/profile • manuals • search • Vault • Drive • remote server • subscriptions',inline=False)
    e.add_field(name='🛡️ Administrator controls',value='Setup • Admin GUI • diagnostics • Vault/Drive/link management • licensing • payment approval • security controls',inline=False)
    e.set_footer(text='420VaultBot v6.2.4 • Buttons call the existing command backend')
    return e

HELP_PAGE_SIZE = 20


def _help_specs(include_admin: bool):
    """Commands shown directly inside 420_help.

    Regular members receive every user command. Administrators receive the same
    user commands plus every administrator command. Permission checks remain in
    the original callbacks, so the button layer never bypasses command security.
    """
    return [s for s in SPECS if include_admin or not s.admin]


def help_directory_embed(include_admin: bool, page: int = 0):
    specs = _help_specs(include_admin)
    pages = max(1, (len(specs) + HELP_PAGE_SIZE - 1) // HELP_PAGE_SIZE)
    page = max(0, min(page, pages - 1))
    chunk = specs[page * HELP_PAGE_SIZE:(page + 1) * HELP_PAGE_SIZE]
    e = discord.Embed(
        title='🎛️ 420VaultBot Help & Command Buttons',
        description=(
            '**Every command on this help page has a button.** Use **Previous** / **Next** '
            'to move through the complete command directory. Commands that need information '
            'open a form first; the original `420_` workflows and permission checks are unchanged.\n\n'
            f'**Page {page + 1} of {pages} • {len(specs)} command buttons available**'
        ),
        color=discord.Color.dark_green(),
    )
    if chunk:
        e.add_field(
            name='Commands on this page',
            value=' • '.join(f'`420_{s.name}`' for s in chunk),
            inline=False,
        )
    if include_admin:
        e.add_field(name='🛡️ Admin access', value='Administrator commands are included on these pages and still require the existing admin checks.', inline=False)
    else:
        e.add_field(name='👤 User access', value='These pages contain every user command. Administrator-only controls remain visible only to administrators.', inline=False)
    e.set_footer(text='420VaultBot v6.2.4 • 420_help is the complete button command directory')
    return e


class HelpDirectoryNavButton(discord.ui.Button):
    def __init__(self, direction: int, disabled: bool = False):
        label = 'Previous' if direction < 0 else 'Next'
        emoji = '◀️' if direction < 0 else '▶️'
        super().__init__(label=label, emoji=emoji, style=discord.ButtonStyle.secondary, row=4, disabled=disabled)
        self.direction = direction

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        view.page += self.direction
        view.rebuild()
        await interaction.response.edit_message(embed=view.embed(), view=view)


class HelpDirectoryPageIndicator(discord.ui.Button):
    def __init__(self, page: int, pages: int):
        super().__init__(label=f'Page {page + 1}/{pages}', style=discord.ButtonStyle.secondary, row=4, disabled=True)


class HelpCommandDirectoryView(discord.ui.View):
    """Direct button directory returned by 420_help.

    Discord caps a message at 25 components, so commands are presented 20 at a
    time with navigation on the fifth row. This keeps every active command one
    click away from 420_help without changing the command backend.
    """
    def __init__(self, owner_id: int, include_admin: bool, page: int = 0):
        super().__init__(timeout=900)
        self.owner_id = owner_id
        self.include_admin = bool(include_admin)
        self.specs = _help_specs(self.include_admin)
        self.pages = max(1, (len(self.specs) + HELP_PAGE_SIZE - 1) // HELP_PAGE_SIZE)
        self.page = max(0, min(int(page), self.pages - 1))
        self.rebuild()

    def embed(self):
        return help_directory_embed(self.include_admin, self.page)

    def rebuild(self):
        self.clear_items()
        start = self.page * HELP_PAGE_SIZE
        chunk = self.specs[start:start + HELP_PAGE_SIZE]
        for idx, spec in enumerate(chunk):
            self.add_item(CommandButton(spec, row=idx // 5))
        self.add_item(HelpDirectoryNavButton(-1, disabled=self.page <= 0))
        self.add_item(HelpDirectoryPageIndicator(self.page, self.pages))
        self.add_item(HelpDirectoryNavButton(1, disabled=self.page >= self.pages - 1))

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message('Run `420_help` to open your own command-button directory.', ephemeral=True)
            return False
        return await _ensure_interaction_command_zone(interaction)
