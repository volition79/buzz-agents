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
        self.assertNotIn('external: true',text)
        self.assertNotIn('traefik-proxy',text)
        self.assertNotIn('BUZZ_SETUP_HOST',text)
        self.assertNotIn('TRAEFIK_HOST',text)
        self.assertNotIn('BUZZ_PUBLIC_URL',text)
        self.assertIn('traefik.enable=false',text)
        self.assertNotIn('\nname:',text)
        self.assertNotIn('password',text.lower())

    def test_public_candidate_images_are_digest_pinned(self):
        import re
        text=(ROOT/'docker-compose.yml').read_text()
        images={role:re.search(r'ghcr.io/volition79/buzz-agents-'+role+r'@sha256:[a-f0-9]{64}',text).group() for role in ('runtime','broker','portal')}
        self.assertEqual(len(images),3)
        self.assertNotIn('BUZZ_SETUP_HOST',text)
        self.assertNotIn('\nname:',text)

    def test_mutable_tags_and_injection_refused(self):
        images={role:'ghcr.io/example/buzz-'+role+'@sha256:'+'a'*64 for role in ('runtime','broker','portal')}
        for bad in ['ghcr.io/example/runtime:latest','$(id)','repo@sha256:short','repo@sha256:'+'a'*64+'\nprivileged: true']:
            with self.assertRaises(ValueError):release.render({**images,'runtime':bad})


class FinalManifestTests(unittest.TestCase):
    def test_compose_covered_and_tampering_refused(self):
        import tempfile,json,hashlib
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);payload=root/'fixture.exe';payload.write_bytes(b'original')
            files={'fixture.exe':{'sha256':hashlib.sha256(payload.read_bytes()).hexdigest(),'size':8}}
            (root/'manifest.json').write_text(json.dumps({'files':files}))
            output=root/'compose.install.yaml'
            images={role:'ghcr.io/example/'+role+'@sha256:'+'a'*64 for role in ('runtime','broker','portal')}
            release.write_release(images,output)
            release.verify_release(output)
            self.assertIn(output.name,json.loads((root/'manifest.json').read_text())['files'])
            self.assertIn(output.name,(root/'SHA256SUMS').read_text())
            self.assertEqual({p.name for p in release.release_assets(output)},
                             {'fixture.exe','compose.install.yaml','manifest.json','SHA256SUMS'})
            output.write_text(output.read_text()+'# changed\n')
            with self.assertRaisesRegex(ValueError,'manifest_hash_mismatch'):release.verify_release(output)
            with self.assertRaisesRegex(ValueError,'manifest_hash_mismatch'):release.release_assets(output)
            release.write_release(images,output)
            payload.write_bytes(b'tampered')
            with self.assertRaisesRegex(ValueError,'manifest_hash_mismatch'):release.write_release(images,output)


if __name__=='__main__':unittest.main()
