import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from store import Store


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'fixture.db'
        c = sqlite3.connect(self.path)
        c.executescript('''
          CREATE TABLE session(id TEXT PRIMARY KEY,project_id TEXT,parent_id TEXT,title TEXT,directory TEXT,
            time_created INTEGER,time_updated INTEGER,time_archived INTEGER,agent TEXT,model TEXT);
          CREATE TABLE message(id TEXT PRIMARY KEY,session_id TEXT,time_created INTEGER,time_updated INTEGER,data TEXT);
          CREATE TABLE part(id TEXT PRIMARY KEY,message_id TEXT,session_id TEXT,time_created INTEGER,time_updated INTEGER,data TEXT);
          CREATE TABLE event_sequence(aggregate_id TEXT PRIMARY KEY,seq INTEGER);
          CREATE TABLE event(id TEXT PRIMARY KEY,aggregate_id TEXT);
          INSERT INTO session VALUES('ses_old','p',NULL,'100% complete','C:/code',1,100,NULL,NULL,NULL);
          INSERT INTO session VALUES('ses_new','p','ses_old','Research <script>','C:/paper',1,200,NULL,NULL,NULL);
          INSERT INTO session VALUES('ses_archive','p',NULL,'Archived note','C:/code',1,150,180,NULL,NULL);
          INSERT INTO event_sequence VALUES('ses_old',1),('ses_new',2),('ses_archive',1);
          INSERT INTO message VALUES('msg_a','ses_new',1,1,'{"role":"user"}');
        ''')
        c.execute('INSERT INTO part VALUES(?,?,?,?,?,?)', ('prt_big','msg_a','ses_new',1,1,json.dumps({'type':'file','url':'data:application/pdf;base64,'+'X'*300000})))
        c.execute('INSERT INTO part VALUES(?,?,?,?,?,?)', ('prt_text','msg_a','ses_new',1,1,json.dumps({'type':'text','text':'Hello <script>alert(1)</script>'})))
        c.commit()
        c.close()
        self.store = Store(self.path)

    def tearDown(self):
        self.temp.cleanup()

    def test_search_is_literal_and_parameterized(self):
        self.assertEqual(self.store.list_sessions({'q':'%'})['total'], 1)
        self.assertEqual(self.store.list_sessions({'q':"' OR 1=1 --"})['total'], 0)
        self.assertEqual(self.store.list_sessions({'archive':'archived'})['total'], 1)
        self.assertEqual(self.store.list_sessions({'children':'0'})['total'], 2)

    def test_time_boundary_is_exclusive(self):
        result = self.store.list_sessions({'before_ms':'150'})
        self.assertEqual([s['id'] for s in result['items']], ['ses_old'])

    def test_oversized_content_is_never_in_preview(self):
        result = self.store.preview('ses_new')
        encoded = json.dumps(result)
        self.assertLess(len(encoded), 30000)
        self.assertNotIn('base64,', encoded)
        self.assertIn('Large content', encoded)
        self.assertIn('Hello <script>', encoded)

    def test_delete_plan_lists_children_and_detects_changes(self):
        plan = self.store.delete_plan(['ses_old'])
        self.assertEqual({s['id'] for s in plan['sessions']}, {'ses_old','ses_new'})
        self.assertEqual(plan['roots'], ['ses_old'])
        self.assertEqual(self.store.delete_plan(['ses_new','ses_old'])['roots'], ['ses_old'])
        self.assertTrue(self.store.plan_matches(plan))
        c = sqlite3.connect(self.path)
        c.execute("UPDATE event_sequence SET seq=seq+1 WHERE aggregate_id='ses_new'")
        c.commit()
        c.close()
        self.assertFalse(self.store.plan_matches(plan))

    def test_missing_session_and_bad_pagination(self):
        with self.assertRaises(ValueError):
            self.store.get_session('ses_missing')
        with self.assertRaises(ValueError):
            self.store.list_sessions({'limit':'10000'})

    def test_export_marks_truncated_text(self):
        c=sqlite3.connect(self.path)
        c.execute('UPDATE part SET data=? WHERE id=?',
                  (json.dumps({'type':'text','text':'A'*6500+'END_MARKER'}),'prt_text'))
        c.commit()
        c.close()
        transcript=''.join(self.store.export_markdown('ses_new'))
        self.assertIn('[Content truncated',transcript)
        self.assertNotIn('END_MARKER',transcript)


if __name__ == '__main__':
    unittest.main()
