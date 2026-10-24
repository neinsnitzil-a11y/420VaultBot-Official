import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
AUTH=(ROOT/'app/views/auth_native.py').read_text(encoding='utf-8')

class V655VerifyDeliveryTests(unittest.TestCase):
    def test_version(self):
        self.assertEqual((ROOT/'VERSION').read_text().strip(),'6.5.5')
        self.assertIn("VERSION = '6.5.5'",(ROOT/'app/version.py').read_text())
    def test_central_delivery_uses_account_email(self):
        block=AUTH.split('async def _send_verification_code',1)[1].split('def panel_embed',1)[0]
        self.assertIn("account=await asyncio.to_thread(bot.auth.account,gid,uid)",block)
        self.assertIn("recipient=str(account['email']",block)
        self.assertIn('await bot.auth.send_email(',block)
    def test_verify_button_sends_before_entry(self):
        block=AUTH.split('async def verify(self,i,b):',1)[1].split("@discord.ui.button(label='Resend Verification'",1)[0]
        self.assertIn('_send_verification_code',block)
        self.assertIn('Verification email sent to:',block)
        self.assertIn('VerificationCodeEntryView',block)
        self.assertNotIn('send_modal(VerifyEmailModal',block)
    def test_resend_uses_same_delivery_path(self):
        block=AUTH.split('async def resend(self,i,b):',1)[1].split("@discord.ui.button(label='Forgot Password'",1)[0]
        self.assertIn('_send_verification_code',block)
        self.assertIn('Verification email sent to:',block)
    def test_exact_email_confirmation_is_private(self):
        self.assertIn("f'📧 **Verification email sent to: {recipient}**",AUTH)
    def test_entry_button_opens_modal(self):
        block=AUTH.split('class VerificationCodeEntryView',1)[1].split('class AuthPanelView',1)[0]
        self.assertIn('Enter Verification Code',block)
        self.assertIn('send_modal(VerifyEmailModal(self.bot))',block)

if __name__=='__main__':unittest.main()
