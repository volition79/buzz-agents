"""CI38218457605: legacy route metadata existed before Docker finished starting.
Observed failure source8a9b7050944c735840edaff23459f17313423dd2; synthetic replay.
"""
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('bootstrap_fixture',Path(__file__).resolve().parents[1]/'scripts/verify-bootstrap-docker.py')
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)

def state(running=False,restarting=False):
    return {'Config':{'Labels':{'com.docker.compose.config-hash':'present'}},
            'State':{'Running':running,'Restarting':restarting}}

class BootstrapReadinessTests(unittest.TestCase):
    def test_create_labels_do_not_prove_running(self):
        states=iter([None,state(),state(True,True),state(True)])
        waits=[]
        result=fixture.wait_compose_route(lambda:next(states),waits.append,4)
        self.assertTrue(result['State']['Running'])
        self.assertFalse(result['State']['Restarting'])
        self.assertEqual(waits,[2,2,2])
    def test_persistent_failure_still_blocks_release(self):
        for value in (None,state(),state(True,True),{'State':{'Running':True}}):
            with self.subTest(value=value):
                with self.assertRaisesRegex(AssertionError,'did not reach running'):
                    fixture.wait_compose_route(lambda:value,lambda _:None,2)
