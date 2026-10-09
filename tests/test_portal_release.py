import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('portal_release',ROOT/'scripts/render-portal-release.py')
release=importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class ReleaseTests(unittest.TestCase):
    def test_only_immutable_digests_fill_template(self):
        images={role:'ghcr.io/example/buzz-'+role+'@sha256:'+'a'*64 for role in ('runtime','broker','portal')}
        text=release.render(images)
        for role,value in images.items():
            self.assertIn(value,text)
            self.assertNotIn('${BUZZ_'+role.upper()+'_IMAGE',text)
        self.assertIn('${BUZZ_SETUP_HOST',text)
        self.assertNotIn('password',text.lower())

    def test_mutable_tags_and_injection_refused(self):
        images={role:'ghcr.io/example/buzz-'+role+'@sha256:'+'a'*64 for role in ('runtime','broker','portal')}
        for bad in ['ghcr.io/example/runtime:latest','$(id)','repo@sha256:short','repo@sha256:'+'a'*64+'\nprivileged: true']:
            with self.assertRaises(ValueError):release.render({**images,'runtime':bad})


if __name__=='__main__':unittest.main()
