"""Failure atomicity and quoted launcher paths; not Mac native acceptance."""
import tempfile
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from buzz_agents.connection_bundle import MAC_LAUNCHER
from buzz_agents.portal import Portal


class ConnectionBundleTests(unittest.TestCase):
    def test_failed_zip_write_does_not_consume_pairing_capacity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'Buzz-VPS-Connect.exe').write_bytes(b'MZ-fixture')
            app = Portal(root/'state', 'https://setup.example.com', artifacts=root)
            with patch('buzz_agents.connection_bundle.zipfile.ZipFile.writestr', side_effect=OSError('disk failure')):
                with self.assertRaises(OSError): app.bundle()
            self.assertEqual(app.grants, {})
            self.assertEqual(app.devices, {})

    def test_launcher_handles_spaces_and_unicode_from_another_directory(self):
        with tempfile.TemporaryDirectory(prefix='buzz 맥 space ') as directory:
            root = Path(directory)
            (root/'Buzz-VPS-Connect.command').write_text(MAC_LAUNCHER)
            fake = root/'Buzz-VPS-Connect'
            fake.write_text('#!/bin/sh\ntest -f ./buzz-pairing.json && printf "launcher-ok"\n')
            fake.chmod(0o755)
            (root/'buzz-pairing.json').write_text('{}')
            result = subprocess.run(['sh', str(root/'Buzz-VPS-Connect.command')], cwd='/',
                                    capture_output=True, text=True, check=True)
            self.assertEqual(result.stdout, 'launcher-ok')
