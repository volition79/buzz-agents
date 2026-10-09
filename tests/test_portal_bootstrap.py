"""Auto-bootstrap contract and real HTTP bridge tests; fixture values only."""
import copy
import http.client
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from buzz_agents import portal_bootstrap as boot
from buzz_agents.common import ToolError
from buzz_agents.portal_broker import Broker
from buzz_agents.portal_route import Server


def container(cid, project, service, **kwargs):
    data = {'Id':cid*64, 'Name':'/'+project+'-'+service+'-1', 'Image':'sha256:'+'f'*64,
            'State':{'Running':True}, 'Config':{'Labels':{'com.docker.compose.project':project,
            'com.docker.compose.service':service},'Env':[]},
            'NetworkSettings':{'Networks':{'traefik-proxy':{}}}}
    data.update(kwargs)
    return data


def fixture():
    broker = container('a','fixture-setup','broker')
    portal = container('b','fixture-setup','portal')
    relay = container('c','fixture-relay','relay')
    relay['Config']['Env'] = ['RELAY_OWNER_PUBKEY='+'e'*64, 'PRIVATE_TEST_VALUE=do-not-return']
    web = container('d','fixture-relay','web')
    web['Config']['Labels']['traefik.http.routers.relay.rule'] = 'Host(`buzz.srv12345.hstgr.cloud`)'
    return [broker,portal,relay,web]


class BootstrapTests(unittest.TestCase):
    def test_no_domain_env_split_relay_services_and_per_project_url(self):
        data = boot.plan(fixture(), 'a'*12)
        self.assertRegex(data['hostname'], r'^buzz-setup-[a-f0-9]{12}\.srv12345\.hstgr\.cloud$')
        self.assertNotIn('do-not-return', json.dumps(data))
        other = fixture()
        for c in other[:2]: c['Config']['Labels']['com.docker.compose.project']='other'
        self.assertNotEqual(data['hostname'],boot.plan(other,'a'*12)['hostname'])
        command = boot.route_command(data)
        self.assertEqual(command[-4:],['sha256:'+'f'*64,'python','-m','buzz_agents.portal_route'])
        self.assertNotIn('--volume',command)
        self.assertNotIn('--publish',command)
        self.assertIn('traefik.enable=true',command)

    def test_missing_ambiguous_or_foreign_identity_waits(self):
        for data, ident in [(fixture()[:2],'a'*12),(fixture()+[container('e','fixture-setup','portal')],'a'*12),(fixture(),'f'*12)]:
            with self.assertRaises(ToolError):boot.plan(data,ident)
        data=fixture();other=container('e','other-relay','relay')
        other['Config']['Env']=['RELAY_OWNER_PUBKEY='+'d'*64]
        other['Config']['Labels']['traefik.http.routers.other.rule']='Host(`relay.srv98765.hstgr.cloud`)'
        with self.assertRaisesRegex(ToolError,'ambiguous'):boot.plan(data+[other],'a'*12)
        data=fixture();data[-1]['Config']['Labels']['traefik.http.routers.relay.rule']='Host(`relay.custom.example`)'
        with self.assertRaisesRegex(ToolError,'not_found'):boot.plan(data,'a'*12)

    def test_dns_success_mismatch_and_failure(self):
        data=boot.plan(fixture(),'a'*12)
        def dns(host,*_,**__):return [(None,None,None,None,('192.0.2.1',443))]
        boot.verify_dns(data,dns)
        def mismatch(host,*_,**__):return [(None,None,None,None,('192.0.2.2' if host==data['hostname'] else '192.0.2.1',443))]
        with self.assertRaisesRegex(ToolError,'mismatch'):boot.verify_dns(data,mismatch)
        with self.assertRaisesRegex(ToolError,'not_ready'):boot.verify_dns(data,lambda *_a,**_k: (_ for _ in ()).throw(OSError()))

    def test_activate_is_bound_to_plan_and_never_overwrites_foreign_container(self):
        with tempfile.TemporaryDirectory() as tmp:
            broker=Broker('fixture/runtime',root=tmp,control=tmp)
            calls=[]
            def execute(argv):
                calls.append(argv)
                if argv[1:4]==['container','ls','-a']:return b'a b c d'
                if argv[1]=='inspect':return json.dumps(fixture()).encode()
                return b'created'
            with patch.dict(os.environ,{'HOSTNAME':'a'*12}),patch('buzz_agents.portal_broker.execute',execute):
                plan=broker.dispatch({'op':'bootstrap-plan'})
                with self.assertRaisesRegex(ToolError,'plan_changed'):
                    broker.dispatch({'op':'bootstrap-activate','fingerprint':'wrong'})
                with patch('buzz_agents.portal_broker.inspect_container',return_value={'Config':{'Labels':{}}}):
                    with self.assertRaisesRegex(ToolError,'requires_review'):
                        broker.dispatch({'op':'bootstrap-activate','fingerprint':plan['fingerprint']})
                self.assertFalse(any(x[1] in ('create','start','rm') for x in calls))
                with patch('buzz_agents.portal_broker.inspect_container',return_value=None):
                    result=broker.dispatch({'op':'bootstrap-activate','fingerprint':plan['fingerprint']})
                self.assertEqual(result['url'],plan['url'])
                self.assertTrue(Path(tmp,'bootstrap.json').exists())
                self.assertEqual(sum(x[1]=='create' for x in calls),1)
                for bad in [{'op':'bootstrap-plan','hostname':'evil'},{'op':'bootstrap-activate','fingerprint':plan['fingerprint'],'image':'evil'}]:
                    with self.assertRaises(ToolError):broker.dispatch(bad)

    def test_route_reuse_requires_exact_security_and_identity(self):
        data=boot.plan(fixture(),'a'*12)
        cmd=boot.route_command(data)
        tags={}
        for i,item in enumerate(cmd[:-1]):
            if item=='--label':
                key,value=cmd[i+1].split('=',1);tags[key]=value
        existing={'Image':data['image'],'Config':{'Labels':tags,'User':'10002:10002',
                  'Cmd':['python','-m','buzz_agents.portal_route'],'Entrypoint':None,
                  'Env':['BUZZ_ROUTE_HOST='+data['hostname'],'BUZZ_ROUTE_UPSTREAM='+data['upstream']]},
                  'HostConfig':{'ReadonlyRootfs':True,'Privileged':False,'CapDrop':['ALL'],
                  'Memory':256*1024*1024,'NanoCpus':250000000,'PidsLimit':48,
                  'RestartPolicy':{'Name':'unless-stopped'},'SecurityOpt':['no-new-privileges:true']},
                  'Mounts':[],'NetworkSettings':{'Networks':{'traefik-proxy':{}}}}
        boot.check_route(existing,data)
        for field,value in [('Privileged',True),('ReadonlyRootfs',False),('Memory',0),('CapAdd',['SYS_ADMIN']),('ExtraHosts',['upstream:192.0.2.99']),('Dns',['192.0.2.99'])]:
            changed=copy.deepcopy(existing);changed['HostConfig'][field]=value
            with self.assertRaises(ToolError):boot.check_route(changed,data)
        changed=copy.deepcopy(existing);changed['Mounts']=[{'Source':'/var/run/docker.sock'}]
        with self.assertRaises(ToolError):boot.check_route(changed,data)

    def test_portal_waits_for_dns_and_binds_activation_fingerprint(self):
        from buzz_agents.portal import bootstrap_url
        data={'ok':True,**boot.plan(fixture(),'a'*12)}
        calls=[]
        def rpc(request):
            calls.append(request)
            if request['op']=='bootstrap-plan':return data
            return {'ok':True,'url':data['url']}
        with patch('buzz_agents.portal_bootstrap.verify_dns',side_effect=[ToolError('bootstrap_dns_not_ready'),None]),patch('builtins.print'):
            sleeps=[]
            self.assertEqual(bootstrap_url(rpc,sleeps.append),data['url'])
        self.assertEqual(sleeps,[10])
        self.assertEqual(calls[-1],{'op':'bootstrap-activate','fingerprint':data['fingerprint']})


class Echo(BaseHTTPRequestHandler):
    def log_message(self,*_):pass
    def do_GET(self):
        body=b'z'*(14*1024*1024) if self.path=='/zip' else self.headers.get('Cookie','').encode()
        self.send_response(200);self.send_header('Content-Length',str(len(body)))
        self.send_header('Set-Cookie','session=fixture; Secure; HttpOnly')
        self.end_headers();self.wfile.write(body)
    def do_POST(self):
        body=self.rfile.read(int(self.headers['Content-Length']))
        self.send_response(200);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)


class RouteHTTPTests(unittest.TestCase):
    def setUp(self):
        self.upstream=ThreadingHTTPServer(('127.0.0.1',0),Echo)
        self.route=Server(('127.0.0.1',0),'setup.example','127.0.0.1',self.upstream.server_port)
        self.threads=[]
        for server in (self.upstream,self.route):
            t=threading.Thread(target=server.serve_forever,daemon=True);t.start();self.threads.append(t)
    def tearDown(self):
        for server in (self.route,self.upstream):server.shutdown();server.server_close()
        for thread in self.threads:thread.join()
    def call(self,path='/',method='GET',body=None,headers=None):
        conn=http.client.HTTPConnection('127.0.0.1',self.route.server_port,timeout=5)
        h={'Host':'setup.example','X-Forwarded-Proto':'https','Cookie':'fixture-cookie'}
        h.update(headers or {})
        conn.request(method,path,body,headers=h);r=conn.getresponse();result=(r.status,r.read(),r.getheaders());conn.close();return result
    def test_cookie_zip_and_post_pass_without_redirect_or_target_change(self):
        status,body,headers=self.call();self.assertEqual((status,body),(200,b'fixture-cookie'))
        self.assertIn(('Set-Cookie','session=fixture; Secure; HttpOnly'),headers)
        self.assertEqual(len(self.call('/zip')[1]),14*1024*1024)
        self.assertEqual(self.call('/api/login','POST',b'fixture-body')[1],b'fixture-body')
    def test_foreign_host_http_absolute_path_and_transfer_encoding_refused(self):
        self.assertEqual(self.call(headers={'Host':'evil'})[0],421)
        self.assertEqual(self.call(headers={'X-Forwarded-Proto':'http'})[0],421)
        self.assertEqual(self.call('http://evil/')[0],400)
        self.assertEqual(self.call(headers={'Transfer-Encoding':'chunked'})[0],400)
        self.assertEqual(self.call(headers={'Content-Length':'99999999'})[0],413)

    def test_duplicate_content_length_refused(self):
        conn=http.client.HTTPConnection('127.0.0.1',self.route.server_port,timeout=5)
        conn.putrequest('POST','/',skip_host=True)
        conn.putheader('Host','setup.example');conn.putheader('X-Forwarded-Proto','https')
        conn.putheader('Content-Length','0');conn.putheader('Content-Length','0');conn.endheaders()
        self.assertEqual(conn.getresponse().status,400);conn.close()

    def test_upstream_timeout_preserves_existing_deploy_budget(self):
        original=http.client.HTTPConnection
        seen=[]
        def connection(host,port,timeout):
            if port==self.upstream.server_port:seen.append(timeout)
            return original(host,port,timeout=timeout)
        with patch('buzz_agents.portal_route.http.client.HTTPConnection',side_effect=connection):
            self.assertEqual(self.call('/api/device/deploy','POST',b'fixture')[0],200)
        self.assertEqual(seen,[250])
