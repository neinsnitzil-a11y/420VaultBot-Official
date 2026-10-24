from __future__ import annotations
import asyncio, time
import discord
from argon2 import PasswordHasher
from app.services.auth import AccountLocked, TwoFactorRequired, TwoFactorInvalid, validate_password
from app.core.security import is_admin
from app.views.user_profile import profile_embed, UserProfileView

PH=PasswordHasher(time_cost=3,memory_cost=65536,parallelism=2,hash_len=32,salt_len=16)

def panel_embed():
    e=discord.Embed(title='🔐 420Vault Account',description='A **420Vault account and active session are required** to use this bot.\n\nYour 420Vault password is separate from Discord. **Never enter your Discord password.**',color=discord.Color.dark_green())
    e.add_field(name='New here?',value='Choose **Create Account** and provide a username, an email you control, and a strong password.',inline=False)
    e.add_field(name='Already registered?',value='Choose **Sign In**. Sessions expire after **10 minutes of inactivity**.',inline=False)
    e.add_field(name='Two-factor security',value='Enable **Authenticator 2FA** to require a rotating 6-digit code (or one-time recovery code) in addition to your password.',inline=False)
    e.add_field(name='Account recovery',value='**Forgot Password** sends a one-time reset code to your registered recovery email. 2FA recovery codes remain required at login if 2FA is enabled.',inline=False)
    e.add_field(name='Your profile',value='After signing in, choose **My Profile** to add your bio, website, producer/artist info, DAW, genres, socials, timezone, and interests.',inline=False)
    return e

async def _reply(i:discord.Interaction,msg:str):
    if i.response.is_done(): await i.followup.send(msg,ephemeral=True)
    else: await i.response.send_message(msg,ephemeral=True)

class CreateAccountModal(discord.ui.Modal,title='Create 420Vault Account'):
    username=discord.ui.TextInput(label='Username',min_length=3,max_length=32,placeholder='Your 420Vault username')
    email=discord.ui.TextInput(label='Recovery email',max_length=254,placeholder='you@example.com')
    password=discord.ui.TextInput(label='Password',style=discord.TextStyle.short,min_length=12,max_length=128,placeholder='12+ chars, upper/lowercase + number')
    confirm=discord.ui.TextInput(label='Confirm password',style=discord.TextStyle.short,min_length=12,max_length=128)
    def __init__(self,bot): super().__init__(timeout=300);self.bot=bot
    async def on_submit(self,i):
        if not i.guild:return await _reply(i,'This must be used in the server login channel.')
        if str(self.password)!=str(self.confirm):return await _reply(i,'❌ Passwords do not match.')
        if await asyncio.to_thread(self.bot.auth.account,i.guild.id,i.user.id):return await _reply(i,'❌ A 420Vault account is already bound to your Discord account. Use **Sign In** or **Forgot Password**.')
        try:
            code=await asyncio.to_thread(self.bot.auth.register,i.guild.id,i.user.id,str(self.username),str(self.email),str(self.password))
            await self.bot.auth.send_email(str(self.email).strip().lower(),'420Vault email verification',f'Your 420Vault verification code is:\n\n{code}\n\nIt expires in 15 minutes. Do not share this code. If you did not create this account, ignore this email.',i.guild.id)
            await _reply(i,'✅ Account created. I sent a verification code to your recovery email. Click **Verify Email** in this channel to finish setup.')
        except Exception as exc:
            # If mail delivery failed after registration, keep the account so Resend Verification can recover it.
            await _reply(i,f'❌ {exc}')

class LoginModal(discord.ui.Modal,title='Sign In to 420Vault'):
    username=discord.ui.TextInput(label='Username',min_length=3,max_length=32)
    password=discord.ui.TextInput(label='Password',min_length=1,max_length=128)
    twofa=discord.ui.TextInput(label='2FA code (if enabled)',required=False,max_length=32,placeholder='123456 or recovery code')
    def __init__(self,bot):super().__init__(timeout=300);self.bot=bot
    async def on_submit(self,i):
        if not i.guild:return await _reply(i,'This must be used in the server login channel.')
        try:r=await asyncio.to_thread(self.bot.auth.verify_login,i.guild.id,i.user.id,str(self.username),str(self.password),str(self.twofa))
        except AccountLocked as exc:
            mins=max(1,(exc.until-int(time.time())+59)//60);return await _reply(i,f'🔒 Account temporarily locked. Try again in about **{mins} minute(s)** or use **Forgot Password**.')
        except TwoFactorRequired as exc:return await _reply(i,f'🛡️ {exc}')
        except TwoFactorInvalid as exc:
            state=await asyncio.to_thread(self.bot.auth.record_login_failure,i.guild.id,i.user.id)
            if state.get('locked'):return await _reply(i,'🔒 Too many incorrect sign-in/2FA attempts. The account is temporarily locked and active sessions were revoked.')
            return await _reply(i,f'🛡️ {exc}')
        except PermissionError as exc:return await _reply(i,f'❌ {exc}')
        if not r:
            state=await asyncio.to_thread(self.bot.auth.record_login_failure,i.guild.id,i.user.id)
            if state.get('new_lock') and state.get('account'):
                a=state['account'];mins=max(1,(state['lock_until']-int(time.time())+59)//60)
                try:await self.bot.auth.send_email(a['email'],'420Vault security alert',f'Your 420Vault account was temporarily locked after 3 incorrect sign-in attempts. All active sessions were revoked. Lock duration: about {mins} minutes. If this was not you, use Forgot Password in the Discord #login panel to reset your password.',i.guild.id)
                except Exception:pass
                return await _reply(i,'🔒 Too many incorrect attempts. The account is temporarily locked and its active sessions were revoked. A security notice was sent to the registered email.',i.guild.id)
            return await _reply(i,'❌ Unable to sign in. Check your credentials or use **Forgot Password**.')
        await asyncio.to_thread(self.bot.auth.create_session,i.guild.id,i.user.id)
        self.bot.db.audit(i.guild.id,i.user.id,'auth_login','native Discord login; 10-minute idle session')
        await _reply(i,'🔓 **Signed in successfully.** Your session expires after **10 minutes of inactivity**.')

class VerifyEmailModal(discord.ui.Modal,title='Verify Recovery Email'):
    code=discord.ui.TextInput(label='Verification code',min_length=8,max_length=80)
    def __init__(self,bot):super().__init__(timeout=300);self.bot=bot
    async def on_submit(self,i):
        r=await asyncio.to_thread(self.bot.auth.consume_email_token_for,str(self.code).strip(),'verify_email',i.guild.id,i.user.id)
        if not r or int(r['guild_id'])!=i.guild.id or int(r['user_id'])!=i.user.id:return await _reply(i,'❌ Invalid or expired verification code.')
        self.bot.db.execute('UPDATE auth_accounts SET email_verified=1,updated_at=? WHERE guild_id=? AND discord_user_id=?',(int(time.time()),i.guild.id,i.user.id))
        self.bot.db.audit(i.guild.id,i.user.id,'auth_email_verified','native Discord verification')
        await _reply(i,'✅ Recovery email verified. You can now **Sign In**.')
        # Private welcome after successful verification; DM failure never blocks the account.
        try:
            account = await asyncio.to_thread(self.bot.auth.account, i.guild.id, i.user.id)
            name = discord.utils.escape_markdown(str(account['username']) if account else i.user.display_name)
            welcome = discord.Embed(
                title='Welcome to 420Vault!',
                description=(f'Hey **{name}**, your account is created and your email is verified.\n\n'
                             '**Get started**\n'
                             '• Select **Sign In** in the login panel.\n'
                             '• Complete required Terms verification.\n'
                             '• Use **420_help** to explore available features.\n'
                             '• Activate a license or select a subscription if needed.\n\n'
                             '**Security:** Never share your password, verification codes, or license key.'),
                color=discord.Color.green())
            welcome.set_footer(text='420VaultBot • Account welcome')
            await i.user.send(embed=welcome)
        except (discord.Forbidden, discord.HTTPException):
            pass


class ResetPasswordModal(discord.ui.Modal,title='Reset 420Vault Password'):
    code=discord.ui.TextInput(label='Reset code from email',min_length=8,max_length=80)
    password=discord.ui.TextInput(label='New password',min_length=12,max_length=128)
    confirm=discord.ui.TextInput(label='Confirm new password',min_length=12,max_length=128)
    def __init__(self,bot):super().__init__(timeout=300);self.bot=bot
    async def on_submit(self,i):
        if str(self.password)!=str(self.confirm):return await _reply(i,'❌ Passwords do not match.')
        try:validate_password(str(self.password))
        except ValueError as exc:return await _reply(i,f'❌ {exc}')
        r=await asyncio.to_thread(self.bot.auth.consume_email_token_for,str(self.code).strip(),'reset_password',i.guild.id,i.user.id)
        if not r or int(r['guild_id'])!=i.guild.id or int(r['user_id'])!=i.user.id:return await _reply(i,'❌ Invalid or expired reset code.')
        self.bot.db.execute('UPDATE auth_accounts SET password_hash=?,failed_login_count=0,lock_until=0,last_failed_at=NULL,updated_at=? WHERE guild_id=? AND discord_user_id=?',(PH.hash(str(self.password)),int(time.time()),i.guild.id,i.user.id))
        await asyncio.to_thread(self.bot.auth.revoke,i.guild.id,i.user.id)
        self.bot.db.execute('DELETE FROM auth_challenges WHERE guild_id=? AND user_id=?',(i.guild.id,i.user.id))
        self.bot.db.audit(i.guild.id,i.user.id,'auth_password_reset','native Discord reset; sessions revoked; lock cleared')
        await _reply(i,'✅ Password changed. All sessions were signed out and any temporary login lock was cleared. Use **Sign In** with your new password.')



class ConfirmTwoFactorModal(discord.ui.Modal,title='Confirm Authenticator 2FA'):
    code=discord.ui.TextInput(label='6-digit authenticator code',min_length=6,max_length=6,placeholder='123456')
    def __init__(self,bot):super().__init__(timeout=300);self.bot=bot
    async def on_submit(self,i):
        try:
            codes=await asyncio.to_thread(self.bot.auth.confirm_twofa_setup,i.guild.id,i.user.id,str(self.code))
            block='\n'.join(codes)
            await _reply(i,'✅ **2FA is now enabled.** All existing sessions were revoked.\n\n**Save these one-time recovery codes somewhere safe. Each can be used once:**\n```'+block+'```\nDo not share them. They cannot be shown again.')
        except Exception as exc: await _reply(i,f'❌ {exc}')

class DisableTwoFactorModal(discord.ui.Modal,title='Disable Authenticator 2FA'):
    code=discord.ui.TextInput(label='Authenticator or recovery code',min_length=6,max_length=32,placeholder='123456 or recovery code')
    def __init__(self,bot):super().__init__(timeout=300);self.bot=bot
    async def on_submit(self,i):
        try:
            await asyncio.to_thread(self.bot.auth.disable_twofa,i.guild.id,i.user.id,str(self.code))
            await _reply(i,'🔓 **2FA disabled.** All active sessions were revoked; sign in again with your password.')
        except Exception as exc: await _reply(i,f'❌ {exc}')

class SMTPSetupModal(discord.ui.Modal,title='Configure 420Vault Email'):
    host=discord.ui.TextInput(label='SMTP Host',default='smtp.gmail.com',max_length=200)
    port=discord.ui.TextInput(label='SMTP Port',default='587',max_length=5)
    username=discord.ui.TextInput(label='SMTP Username',placeholder='bot@example.com',max_length=254)
    password=discord.ui.TextInput(label='SMTP App Password',placeholder='Use an app password, not your normal email password',max_length=256)
    sender=discord.ui.TextInput(label='From / Test Email',placeholder='bot@example.com',max_length=254)
    def __init__(self,bot,gid,allow_reconfigure=False):
        super().__init__(timeout=300);self.bot=bot;self.gid=gid;self.allow_reconfigure=allow_reconfigure
        old=bot.smtp_settings.get(gid)
        if old:
            self.host.default=old['host'];self.port.default=str(old['port']);self.username.default=old['username'];self.sender.default=old['from_email'];self.password.required=False;self.password.placeholder='Leave blank to keep the saved app password'
    async def on_submit(self,i):
        if not i.guild or i.guild.id!=self.gid:return await _reply(i,'❌ Invalid server context.')
        settings=self.bot.db.guild(self.gid)
        if not is_admin(i,settings):return await _reply(i,'❌ Only the server owner or an authorized 420Vault administrator can configure email.')
        if self.bot.smtp_settings.configured(self.gid) and not self.allow_reconfigure:return await _reply(i,'🔒 Email is already configured. Use **420_admin → Security → Reconfigure SMTP** to change it.')
        try:
            self.bot.smtp_settings.save(self.gid,str(self.host),int(str(self.port)),str(self.username),str(self.password),str(self.sender),'420Vault Security','STARTTLS')
            await self.bot.auth.send_email(str(self.sender).strip(),'420Vault SMTP test','420VaultBot email delivery is configured correctly. This mailbox will be used for verification, password recovery, and security alerts.',self.gid)
            self.bot.smtp_settings.mark_tested(self.gid)
            await asyncio.to_thread(self.bot.db.audit,self.gid,i.user.id,'smtp_configured','SMTP saved and test email delivered; credential encrypted at rest')
            await _reply(i,'✅ **SMTP configured and tested successfully.** A test email was sent to the From/Test address. The login system can now send verification and password-reset emails.')
        except Exception as exc:
            await _reply(i,f'❌ SMTP test failed, so the configuration was **not enabled**.\n`{type(exc).__name__}: {str(exc)[:700]}`\n\nFor Gmail use `smtp.gmail.com`, port `587`, your full Gmail address, and a Google **App Password**.')

class AuthPanelView(discord.ui.View):
    def __init__(self,bot,gid=None):
        super().__init__(timeout=None);self.bot=bot;self.gid=gid
        if gid is not None and self.bot.smtp_settings.configured(gid):
            for item in list(self.children):
                if getattr(item,'custom_id',None)=='420auth:smtp_setup':self.remove_item(item)
    @discord.ui.button(label='Create Account',emoji='🆕',style=discord.ButtonStyle.success,custom_id='420auth:create')
    async def create(self,i,b):await i.response.send_modal(CreateAccountModal(self.bot))
    @discord.ui.button(label='Sign In',emoji='🔐',style=discord.ButtonStyle.primary,custom_id='420auth:login')
    async def login(self,i,b):
        if await asyncio.to_thread(self.bot.auth.session_active,i.guild.id,i.user.id,False):return await _reply(i,'🔓 You already have an active 420Vault session.')
        if not await asyncio.to_thread(self.bot.auth.account,i.guild.id,i.user.id):return await _reply(i,'🆕 No 420Vault account is bound to your Discord account yet. Click **Create Account** first.')
        await i.response.send_modal(LoginModal(self.bot))
    @discord.ui.button(label='Verify Email',emoji='✉️',style=discord.ButtonStyle.secondary,custom_id='420auth:verify')
    async def verify(self,i,b):await i.response.send_modal(VerifyEmailModal(self.bot))
    @discord.ui.button(label='Resend Verification',emoji='📨',style=discord.ButtonStyle.secondary,custom_id='420auth:resend',row=1)
    async def resend(self,i,b):
        a=await asyncio.to_thread(self.bot.auth.account,i.guild.id,i.user.id)
        if a and not a['email_verified']:
            try:
                code=await asyncio.to_thread(self.bot.auth.issue_email_token,i.guild.id,i.user.id,'verify_email',900)
                await self.bot.auth.send_email(a['email'],'420Vault email verification',f'Your new 420Vault verification code is:\n\n{code}\n\nIt expires in 15 minutes. Do not share this code.',i.guild.id)
            except Exception:pass
        await _reply(i,'📧 If your account still needs verification, a new code has been sent to its registered recovery email.')
    @discord.ui.button(label='Forgot Password',emoji='🔑',style=discord.ButtonStyle.secondary,custom_id='420auth:forgot')
    async def forgot(self,i,b):
        a=await asyncio.to_thread(self.bot.auth.account,i.guild.id,i.user.id)
        # Always use a generic outward response. The account is bound to the Discord ID.
        if a:
            try:
                code=await asyncio.to_thread(self.bot.auth.issue_email_token,i.guild.id,i.user.id,'reset_password',900)
                await self.bot.auth.send_email(a['email'],'420Vault password reset',f'Your one-time 420Vault password reset code is:\n\n{code}\n\nIt expires in 15 minutes. Do not share it. If you did not request this reset, you can ignore this email.',i.guild.id)
            except Exception:pass
        await _reply(i,'📧 If a 420Vault account is registered to your Discord account, a reset code has been sent to its recovery email. Click **Enter Reset Code** when it arrives.')
    @discord.ui.button(label='Enter Reset Code',emoji='🔁',style=discord.ButtonStyle.secondary,custom_id='420auth:reset')
    async def reset(self,i,b):await i.response.send_modal(ResetPasswordModal(self.bot))
    @discord.ui.button(label='Enable 2FA',emoji='🛡️',style=discord.ButtonStyle.success,custom_id='420auth:2fa_enable',row=2)
    async def twofa_enable(self,i,b):
        if not i.guild:return await _reply(i,'This must be used inside a server.')
        try:
            secret,uri=await asyncio.to_thread(self.bot.auth.begin_twofa_setup,i.guild.id,i.user.id)
            await _reply(i,'🛡️ **Authenticator 2FA setup**\n1. Open Google Authenticator, Microsoft Authenticator, Authy, 1Password, or another TOTP app.\n2. Add an account manually with this secret:\n```'+secret+'```\n3. Use **Time-based / TOTP**, 6 digits, 30-second period.\n4. Then click **Confirm 2FA** and enter the current 6-digit code.\n\nAdvanced authenticator URI (keep private):\n```'+uri+'```')
        except Exception as exc: await _reply(i,f'❌ {exc}')
    @discord.ui.button(label='Confirm 2FA',emoji='✅',style=discord.ButtonStyle.primary,custom_id='420auth:2fa_confirm',row=2)
    async def twofa_confirm(self,i,b):
        if not i.guild:return await _reply(i,'This must be used inside a server.')
        await i.response.send_modal(ConfirmTwoFactorModal(self.bot))
    @discord.ui.button(label='Disable 2FA',emoji='🧯',style=discord.ButtonStyle.danger,custom_id='420auth:2fa_disable',row=2)
    async def twofa_disable(self,i,b):
        if not i.guild:return await _reply(i,'This must be used inside a server.')
        if not await asyncio.to_thread(self.bot.auth.twofa_enabled,i.guild.id,i.user.id):return await _reply(i,'2FA is not enabled on your account.')
        await i.response.send_modal(DisableTwoFactorModal(self.bot))
    @discord.ui.button(label='Configure Email',emoji='⚙️',style=discord.ButtonStyle.secondary,custom_id='420auth:smtp_setup',row=2)
    async def smtp_setup(self,i,b):
        if not i.guild:return await _reply(i,'This must be used inside a server.')
        if self.bot.smtp_settings.configured(i.guild.id):return await _reply(i,'🔒 Email is already configured. Administrators can change it from **420_admin → Security → Reconfigure SMTP**.')
        if not is_admin(i,self.bot.db.guild(i.guild.id)):return await _reply(i,'❌ Only the server owner or an authorized 420Vault administrator can perform the one-time email setup.')
        await i.response.send_modal(SMTPSetupModal(self.bot,i.guild.id,False))
    @discord.ui.button(label='My Profile',emoji='👤',style=discord.ButtonStyle.primary,custom_id='420auth:profile',row=1)
    async def profile(self,i,b):
        if not i.guild:return await _reply(i,'This must be used inside a server.')
        account=await asyncio.to_thread(self.bot.auth.account,i.guild.id,i.user.id)
        if not account:return await _reply(i,'🆕 Create your 420Vault account first.')
        if not await asyncio.to_thread(self.bot.auth.session_active,i.guild.id,i.user.id,True):return await _reply(i,'🔐 Sign in first to open or edit your profile.')
        e,_=profile_embed(self.bot,i.guild,i.user,i.user.id)
        await i.response.send_message(embed=e,view=UserProfileView(self.bot,i.guild.id,i.user.id),ephemeral=True)

    @discord.ui.button(label='Sign Out',emoji='🚪',style=discord.ButtonStyle.danger,custom_id='420auth:logout',row=1)
    async def logout(self,i,b):
        await asyncio.to_thread(self.bot.auth.revoke,i.guild.id,i.user.id);await _reply(i,'🔒 Signed out. Your 420Vault session was revoked.')

async def ensure_auth_panel(bot,guild:discord.Guild,channel:discord.TextChannel):
    # Make this a panel-only channel. Members can see/use components but cannot post credentials into chat.
    try:
        await channel.set_permissions(guild.default_role,view_channel=True,read_message_history=True,send_messages=False,add_reactions=False,reason='420Vault native authentication channel')
        if guild.me: await channel.set_permissions(guild.me,view_channel=True,read_message_history=True,send_messages=True,embed_links=True,reason='420Vault native authentication panel')
    except (discord.Forbidden,discord.HTTPException):pass
    keep=None
    try:
        async for m in channel.history(limit=100):
            if m.author==bot.user and m.embeds and m.embeds[0].title=='🔐 420Vault Account':
                if keep is None:keep=m
                else:
                    try:await m.delete()
                    except Exception:pass
    except (discord.Forbidden,discord.HTTPException):pass
    if keep:
        try:await keep.edit(embed=panel_embed(),view=AuthPanelView(bot,guild.id));return keep
        except Exception:pass
    return await channel.send(embed=panel_embed(),view=AuthPanelView(bot,guild.id))
