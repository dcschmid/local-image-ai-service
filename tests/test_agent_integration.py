"""Verify portable installation, updates and preservation of agent configuration."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import agent_integration as integration
from recipes import recipes


class AgentIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_skill_package_is_reproducible_and_contains_the_current_inventory(self):
        first = integration.package_skill(self.root / 'first.skill')
        second = integration.package_skill(self.root / 'second.skill')
        self.assertEqual(first['sha256'], second['sha256'])
        with zipfile.ZipFile(first['path']) as archive:
            self.assertEqual(len(archive.namelist()), 4)
            self.assertTrue(all(name.startswith('local-image-ai/') and '..' not in name for name in archive.namelist()))
            catalog = archive.read('local-image-ai/references/catalog.md').decode()
            for recipe in recipes(): self.assertIn('`' + recipe['id'] + '`', catalog)
            self.assertNotIn('anima-psx', catalog)

    def test_managed_skill_updates_but_preserves_local_edits_and_unmanaged_files(self):
        destination = integration.install_skill(self.root)
        self.assertEqual(integration.install_skill(self.root), destination)
        original = (destination / 'SKILL.md').read_bytes()
        (destination / 'SKILL.md').write_bytes(original + b'\nUser customization\n')
        with self.assertRaisesRegex(ValueError, 'local edits'): integration.install_skill(self.root)
        self.assertIn('User customization', (destination / 'SKILL.md').read_text())
        (destination / 'SKILL.md').write_bytes(original)
        (destination / 'custom.txt').write_text('preserve')
        with self.assertRaisesRegex(ValueError, 'unmanaged files'): integration.install_skill(self.root)
        self.assertEqual((destination / 'custom.txt').read_text(), 'preserve')

    def test_unmanaged_and_symlinked_skill_destinations_are_preserved(self):
        target = self.root / integration.NAME;target.mkdir()
        (target / 'SKILL.md').write_text('unmanaged')
        with self.assertRaisesRegex(ValueError, 'not managed'): integration.install_skill(self.root)
        (target / 'SKILL.md').unlink();target.rmdir()
        elsewhere = self.root / 'elsewhere';elsewhere.mkdir();target.symlink_to(elsewhere)
        with self.assertRaisesRegex(ValueError, 'symlink'): integration.install_skill(self.root)
        self.assertTrue(target.is_symlink())

    def test_routing_keeps_existing_instructions_and_is_idempotent(self):
        path = self.root / 'AGENTS.md';original = '# User profile\nPreserve these rules.\n'
        path.write_text(original)
        integration.install_routing(self.root)
        installed = path.read_text()
        self.assertTrue(installed.startswith(original))
        self.assertEqual(installed.count(integration.START), 1)
        self.assertIn('only when the\nuser explicitly requests it', installed)
        self.assertEqual((self.root / 'AGENTS.md.before-local-image-ai').read_text(), original)
        integration.install_routing(self.root)
        self.assertEqual(path.read_text(), installed)
        path.write_text(installed + integration.START)
        with self.assertRaisesRegex(ValueError, 'ambiguous'): integration.install_routing(self.root)
        self.assertEqual(path.read_text(), installed + integration.START)

    def test_registration_preserves_other_servers_and_handles_an_empty_configuration(self):
        for original in ('', '[mcp_servers.existing]\ncommand="preserve-me"\n'):
            config = self.root / 'config.toml';config.write_text(original)
            def register(argv, **kwargs):
                config.write_text(original + '\n[mcp_servers.local-image-ai]\ncommand=' + json.dumps(argv[-2]) + '\nargs=["mcp"]\n')
                return type('Result', (), dict(returncode=0))()
            with patch.object(integration.subprocess, 'run', side_effect=register), patch.object(integration.shutil, 'which', return_value='/codex'), \
                    patch.object(Path, 'is_file', return_value=True):
                self.assertEqual(integration.register_codex(self.root), config)
            self.assertIn('args=["mcp"]', config.read_text())
            self.assertTrue(config.read_text().startswith(original))

    def test_registration_rolls_back_partial_and_unexpected_config_changes(self):
        for error in (False, True):
            config = self.root / 'config.toml';original = 'model="user-choice"\n';config.write_text(original)
            def register(argv, **kwargs):
                config.write_text('model="unexpected"\n')
                return type('Result', (), dict(returncode=int(error), stderr='failed'))()
            with patch.object(integration.subprocess, 'run', side_effect=register), patch.object(integration.shutil, 'which', return_value='/codex'), \
                    patch.object(Path, 'is_file', return_value=True):
                with self.assertRaises(RuntimeError): integration.register_codex(self.root)
            self.assertEqual(config.read_text(), original)

    def test_registration_preserves_existing_entries_if_codex_normalizes_them(self):
        config = self.root / 'config.toml'
        original = '[mcp_servers.existing]\ncommand="preserve"\nargs=["custom"]\nenabled=false\n'
        config.write_text(original)
        def register(argv, **kwargs):
            config.write_text('[mcp_servers.existing]\ncommand="preserve"\nargs=[]\nenabled=true\n'
                              + '[mcp_servers.local-image-ai]\ncommand=' + json.dumps(argv[-2]) + '\nargs=["mcp"]\n')
            return type('Result', (), dict(returncode=0))()
        with patch.object(integration.subprocess, 'run', side_effect=register), patch.object(integration.shutil, 'which', return_value='/codex'), \
                patch.object(Path, 'is_file', return_value=True):
            integration.register_codex(self.root)
        self.assertTrue(config.read_text().startswith(original))


if __name__ == '__main__': unittest.main()
