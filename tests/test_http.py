import json
import re
import sqlite3
import subprocess
import sys
import threading
import unittest
import urllib.error
import urllib.request

from app.server import Handler, Manager, ThreadingHTTPServer, ROOT
from tests import test_store


class HttpTests(unittest.TestCase):
    def test_root_entrypoint_works_outside_project_directory(self):
        result=subprocess.run([sys.executable,str(ROOT.parent/'main.py'),'--help'],
            cwd=self.fixture.temp.name,capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('--db',result.stdout)
        self.assertIn('--port',result.stdout)

    def test_translated_html_preserves_javascript_element_ids(self):
        html=(ROOT/'static/index.html').read_text(encoding='utf-8')
        script=(ROOT/'static/app.js').read_text(encoding='utf-8')
        ids=set(re.findall(r'id="([^"]+)"',html))
        required=set(re.findall(r"\$\('#([a-z][\w-]*)",script))
        self.assertEqual(required-ids,set())

    def setUp(self):
        self.fixture=test_store.StoreTests()
        self.fixture.setUp()
        self.manager=Manager(self.fixture.path)
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.server.manager=self.manager
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.url='http://127.0.0.1:'+str(self.server.server_address[1])
        self.opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.fixture.tearDown()

    def request(self,path,body=None,headers=None):
        merged={'Content-Type':'application/json'}
        merged.update(headers or {})
        request=urllib.request.Request(self.url+path,data=json.dumps(body).encode() if body is not None else None,headers=merged)
        return self.opener.open(request,timeout=5)

    def test_static_and_bounded_preview(self):
        with self.request('/') as r:
            self.assertIn("frame-ancestors 'none'",r.headers['Content-Security-Policy'])
            self.assertIn('全部会话'.encode(),r.read())
        with self.request('/api/session/ses_new/preview') as r:
            data=r.read()
            self.assertLess(len(data),30000)
            self.assertNotIn(b'base64,',data)
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.request('/app/server.py')
        self.assertEqual(error.exception.code,404)

    def test_origin_host_and_csrf(self):
        cases=[({},None,{'Origin':'https://untrusted.example'}),
               ({},None,{'Host':'untrusted.example'}),
               ({'ids':['ses_old']},'/api/delete-plan',{})]
        for body,path,headers in cases:
            with self.assertRaises(urllib.error.HTTPError) as error:
                self.request(path or '/api/bootstrap',body if path else None,headers)
            self.assertEqual(error.exception.code,403)

    def test_confirmation_and_stale_plan_are_rejected(self):
        headers={'X-Manager-Token':self.manager.csrf}
        with self.request('/api/delete-plan',{'ids':['ses_old']},headers) as r:
            plan=json.load(r)
        self.assertEqual(plan['count'],2)
        with self.assertRaises(urllib.error.HTTPError) as error:
                self.request('/api/delete',{'token':plan['token'],'confirmation':'删除 1'},headers)
        self.assertEqual(error.exception.code,400)
        self.assertEqual(self.manager.store.summary()['total'],3)

    def test_delete_revalidates_after_service_startup(self):
        path=self.fixture.path
        class StartupChangesSession:
            def start(self):
                c=sqlite3.connect(path)
                c.execute("UPDATE event_sequence SET seq=seq+1 WHERE aggregate_id='ses_new'")
                c.commit()
                c.close()

            def request(self,*args,**kwargs):
                raise AssertionError('Deletion must not run after the selection changed during startup')

        plan=self.manager.prepare_delete(['ses_old'])
        self.manager.bridge=StartupChangesSession()
        with self.assertRaisesRegex(ValueError,'changed since the preview'):
            self.manager.delete(plan['token'],'删除 2')
        self.assertEqual(self.manager.store.summary()['total'],3)

    def test_export_is_explicitly_not_a_full_backup(self):
        with self.request('/api/session/ses_new/export') as r:
            self.assertIn('attachment',r.headers['Content-Disposition'])
            body=r.read()
            self.assertNotIn(b'base64,',body)
            self.assertIn(b'not a full backup',body)


if __name__=='__main__':
    unittest.main()
