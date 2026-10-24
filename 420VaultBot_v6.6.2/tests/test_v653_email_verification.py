import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
AUTH=(ROOT/'app/views/auth_native.py').read_text(encoding='utf-8')

class V653EmailVerificationTests(unittest.TestCase):
 def test_version(self):
  self.assertEqual((ROOT/'VERSION').read_text().strip(),'6.5.5')
  self.assertIn("VERSION = '6.5.5'",(ROOT/'app/version.py').read_text())
 def test_central_sender_uses_registered_account_email(self):
  block=AUTH.split('async def _send_verification_code',1)[1].split('def panel_embed',1)[0]
  self.assertIn("account=await asyncio.to_thread(bot.auth.account,gid,uid)",block)
  self.assertIn("recipient=str(account['email']",block)
  self.assertIn('await bot.auth.send_email(',block)
 def test_create_uses_central_sender(self):
  block=AUTH.split('class CreateAccountModal',1)[1].split('class LoginModal',1)[0]
  self.assertIn('_send_verification_code',block)
  self.assertIn('Verification email sent to:',block)
 def test_resend_uses_registered_email(self):
  block=AUTH.split('async def resend(self,i,b):',1)[1].split("@discord.ui.button(label='Forgot Password'",1)[0]
  self.assertIn("recipient=str(a['email']).strip().lower()",block)
  self.assertIn('_send_verification_code',block)
  self.assertNotIn('except Exception:pass',block)
 def test_resend_defers_before_delivery(self):
  block=AUTH.split('async def resend(self,i,b):',1)[1].split("@discord.ui.button(label='Forgot Password'",1)[0]
  self.assertLess(block.index('i.response.defer'),block.index('_send_verification_code'))
 def test_logging_present(self):
  self.assertIn('auth_verification_email_failed',AUTH)
  self.assertIn('auth_verification_email_resent',AUTH)

if __name__=='__main__':unittest.main()
