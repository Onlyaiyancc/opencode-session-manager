import json
import os
import tempfile
import unittest
from pathlib import Path

from bridge import OfficialBridge
from store import Store
from server import Manager


@unittest.skipUnless(os.name=='nt' and os.environ.get('OPENCODE_RUN_INTEGRATION')=='1',
                     'Set OPENCODE_RUN_INTEGRATION=1 on Windows with OpenCode Desktop installed')
class OfficialIntegrationTests(unittest.TestCase):
    def test_real_official_mutations_on_temporary_database(self):
        # 只允许临时库，禁止用真实会话作为测试样本。
        with tempfile.TemporaryDirectory(prefix='oc-manager-test-') as folder:
            base = Path(folder)
            database = base/'isolated.db'
            bridge = OfficialBridge(database,base/'runtime',isolated=True)
            try:
                bridge.start()
                session = bridge.request('POST','/session',{'title':'Manager integration fixture'},directory=str(base))
                session_id = session['id']
                store = Store(database)
                self.assertEqual(store.get_session(session_id)['title'],'Manager integration fixture')
                updated = bridge.request('PATCH','/session/'+session_id,{'title':'Renamed fixture'},directory=str(base))
                self.assertEqual(updated['title'],'Renamed fixture')
                bridge.request('PATCH','/session/'+session_id,{'time':{'archived':123456}},directory=str(base))
                self.assertEqual(store.get_session(session_id)['time_archived'],123456)
                bridge.request('PATCH','/session/'+session_id,{'time':{'archived':0}},directory=str(base))
                self.assertEqual(store.list_sessions({'archive':'active'})['total'],1)
                child = bridge.request('POST','/session',{'title':'Nested fixture','parentID':session_id},directory=str(base))
                self.assertEqual(len(store.delete_plan([session_id])['sessions']),2)
                manager=Manager(database,base/'manager-runtime',isolated=True)
                manager.bridge=bridge
                plan=manager.prepare_delete([session_id])
                result=manager.delete(plan['token'],'删除 2')
                self.assertEqual(result['deleted'],2)
                self.assertEqual(store.summary()['total'],0)
                with store.connect() as c:
                    self.assertEqual(c.execute('SELECT count(*) FROM event_sequence').fetchone()[0],0)
                    self.assertEqual(c.execute('SELECT count(*) FROM event').fetchone()[0],0)
                print(json.dumps({'official_integration':'passed','real_database_modified':False}))
            except Exception:
                log=base/'runtime/official-server.log'
                if log.exists():
                    print(log.read_text(encoding='utf-8',errors='replace')[-3500:])
                raise
            finally:
                bridge.close()


if __name__ == '__main__':
    unittest.main()
