"""Offline upgrade-regression gates; no Discord token or network required."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('upgrade_release', ROOT / 'upgrade_existing.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class V640Tests(unittest.TestCase):
    def test_version(self):
        self.assertEqual(mod.version(ROOT), (6, 4, 1))
        self.assertEqual((ROOT / 'app/version.py').read_text().strip(), "VERSION='6.4.1'")

    def test_critical_modules_and_gui_routes(self):
        self.assertEqual([item for item in mod.REQUIRED if not (ROOT / item).is_file()], [])
        bot = (ROOT / 'app/bot.py').read_text()
        command = (ROOT / 'app/views/command_center.py').read_text()
        legacy = (ROOT / 'app/cogs/legacy_commands.py').read_text()
        auth = (ROOT / 'app/views/auth_native.py').read_text()
        self.assertIn('self.add_view(CommandCenterView(self))', bot)
        self.assertIn('HelpCommandDirectoryView(ctx.author.id,admin_access)', legacy)
        self.assertIn('class HelpCommandDirectoryView', command)
        self.assertIn('ConfirmTwoFactorModal', auth)
        self.assertIn('Welcome to 420Vault!', auth)
        self.assertIn('send_profile(ctx,member)', legacy)

    def test_user_state_excluded(self):
        source = [p.relative_to(ROOT).as_posix() for p in mod.sources()]
        for path in source:
            self.assertFalse(set(Path(path).parts) & mod.SKIP_DIRS)
            self.assertNotIn(Path(path).name, mod.SKIP_NAMES)
            self.assertNotIn(Path(path).suffix.lower(), mod.SKIP_EXT)

    def test_preflight_blocks_downgrade(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / 'installed'
            (d / 'app').mkdir(parents=True)
            (d / 'app/bot.py').write_text('# bot')
            (d / 'VERSION').write_text('99.0.0')
            with self.assertRaisesRegex(ValueError, 'downgrade'):
                mod.preflight(d)

    def test_dryrun_and_preservation(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / 'installed'
            (d / 'app').mkdir(parents=True)
            (d / 'app/bot.py').write_text('# old bot')
            (d / 'VERSION').write_text('6.3.6')
            (d / 'data').mkdir()
            (d / 'data/licenses.sqlite').write_bytes(b'userdb')
            (d / '.env').write_text('SECRET=keep')
            self.assertEqual(mod.main([str(d), '--dry-run']), 0)
            self.assertEqual((d / 'app/bot.py').read_text(), '# old bot')
            self.assertEqual(mod.main([str(d)]), 0)
            self.assertEqual((d / 'data/licenses.sqlite').read_bytes(), b'userdb')
            self.assertEqual((d / '.env').read_text(), 'SECRET=keep')
            self.assertEqual(mod.version(d), (6,4,1))
            self.assertTrue(list((d / 'backups').glob('source_pre_v640_*')))

if __name__ == '__main__': unittest.main()
