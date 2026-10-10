import hashlib
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('history',Path(__file__).resolve().parents[1]/'scripts/provider-history.py')
history=importlib.util.module_from_spec(spec);spec.loader.exec_module(history)
class HistoryTests(unittest.TestCase):
    def record(self,raw=b'MZprovider'):
        return {'tag':'portal-candidate-123456789abc-1-1','sha256':hashlib.sha256(raw).hexdigest(),'size':len(raw)}
    def test_verified_embedded_and_standalone_bytes(self):
        raw=b'MZprovider';r=self.record(raw)
        history.verify_bytes(raw,r)
        self.assertEqual(history.embedded_provider(b'MZouterjunk'+raw+b'tail',r),raw)
        with self.assertRaises(ValueError):history.embedded_provider(b'MZouterjunk'+raw+b'tail',self.record(b'MZdifferent'))
        with self.assertRaises(ValueError):history.verify_bytes(raw+b'changed',r)
    def test_invalid_or_duplicate_catalog_fails_closed(self):
        for changed in ({'size':True},{'sha256':'x'},{'tag':'../escape'}):
            with self.assertRaises(ValueError):history.catalog([{**self.record(),**changed}])
        with self.assertRaises(ValueError):history.catalog([])
        with self.assertRaises(ValueError):history.catalog([self.record(),self.record()])
    def test_publication_blocks_missing_or_changed_release(self):
        saved=history.catalog([self.record()])
        history.check_catalog(saved,saved)
        missing=history.catalog([self.record(),{**self.record(), 'tag':'portal-candidate-123456789abc-2-1'}])
        with self.assertRaises(ValueError):history.check_catalog(saved,missing)
        with self.assertRaises(ValueError):history.check_catalog(saved,history.catalog([self.record(b'MZchanged')]))
