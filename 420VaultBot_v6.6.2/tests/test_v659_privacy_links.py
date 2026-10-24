import tempfile, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class ReleaseSourceTests(unittest.TestCase):
    def test_profile_private_fields_require_private_mode(self):
        s=(ROOT/'app/views/user_profile.py').read_text(encoding='utf-8')
        self.assertIn('show_private: bool = False', s)
        self.assertIn('if owner and show_private:', s)
        self.assertIn("profile_embed(ctx.bot, ctx.guild, member, ctx.author.id, show_private=False)", s)
        self.assertIn("View Private Details", s)
        self.assertIn("show_private=True", (ROOT/'app/views/auth_native.py').read_text(encoding='utf-8'))

    def test_specific_list_admin_ui_present(self):
        s=(ROOT/'app/views/admin.py').read_text(encoding='utf-8')
        self.assertIn("Add Link to List", s)
        self.assertIn("link_add_to_list", s)
        self.assertIn("LinkAddToListModal", s)
        self.assertIn("add_urls_to_list", (ROOT/'app/services/link_library.py').read_text(encoding='utf-8'))

    def test_version(self):
        self.assertEqual((ROOT/'VERSION').read_text().strip(),'6.5.9')
        self.assertIn("VERSION='6.5.9'",(ROOT/'app/version.py').read_text())

if __name__=='__main__': unittest.main()
