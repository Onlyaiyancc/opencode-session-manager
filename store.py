import hashlib
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path


def number(value, default=0, maximum=10000000):
    try:
        result = int(value if value not in (None, '') else default)
    except (TypeError, ValueError):
        raise ValueError('Invalid number')
    if not 0 <= result <= maximum:
        raise ValueError('Number is outside the supported range')
    return result


class Store:
    def __init__(self, path):
        self.path = Path(path).resolve()

    @contextmanager
    def connect(self):
        # 每个请求使用独立只读连接，不把整个数据库加载到内存。
        c = sqlite3.connect(self.path.as_uri() + '?mode=ro', uri=True, timeout=3)
        c.row_factory = sqlite3.Row
        c.execute('PRAGMA query_only=ON')
        try:
            yield c
        finally:
            c.close()

    def summary(self):
        with self.connect() as c:
            tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not {'session','part','message','event_sequence'} <= tables:
                raise ValueError('This OpenCode database schema is not supported. Expected the v1 session schema.')
            row = c.execute('''SELECT count(*) AS total,
                sum(CASE WHEN time_archived>0 THEN 1 ELSE 0 END) AS archived,
                sum(CASE WHEN parent_id IS NOT NULL THEN 1 ELSE 0 END) AS children,
                max(time_updated) AS latest FROM session''').fetchone()
            directories = [dict(r) for r in c.execute('SELECT directory,count(*) AS count FROM session GROUP BY directory ORDER BY count(*) DESC')]
            return {**dict(row), 'archived': row['archived'] or 0, 'children': row['children'] or 0,
                    'database_bytes': self.path.stat().st_size, 'directories': directories}

    def list_sessions(self, filters):
        clauses, parameters = [], []
        query = str(filters.get('q', '')).strip()[:200]
        if query:
            pattern = '%' + query.replace('!','!!').replace('%','!%').replace('_','!_') + '%'
            clauses.append("(s.title LIKE ? ESCAPE '!' OR s.directory LIKE ? ESCAPE '!')")
            parameters.extend((pattern, pattern))
        archive = filters.get('archive', 'all')
        if archive not in ('all','active','archived'):
            raise ValueError('Invalid archive filter')
        if archive == 'archived':
            clauses.append('s.time_archived>0')
        if archive == 'active':
            clauses.append('(s.time_archived IS NULL OR s.time_archived=0)')
        if filters.get('directory'):
            clauses.append('s.directory=?')
            parameters.append(str(filters['directory']))
        if filters.get('children') == '0':
            clauses.append('s.parent_id IS NULL')
        if filters.get('before_ms'):
            clauses.append('s.time_updated<?')
            parameters.append(number(filters['before_ms'], maximum=9999999999999))
        if filters.get('after_ms'):
            clauses.append('s.time_updated>=?')
            parameters.append(number(filters['after_ms'], maximum=9999999999999))
        limit = number(filters.get('limit'), 30, 100)
        if not limit:
            raise ValueError('Page size must be at least 1')
        offset = number(filters.get('offset'))
        where = ' WHERE ' + ' AND '.join(clauses) if clauses else ''
        with self.connect() as c:
            total = c.execute('SELECT count(*) FROM session s'+where, parameters).fetchone()[0]
            rows = c.execute('''SELECT s.id,s.title,s.directory,s.parent_id,s.time_created,s.time_updated,s.time_archived,
                (SELECT count(*) FROM message m WHERE m.session_id=s.id) AS message_count,
                (SELECT count(*) FROM session child WHERE child.parent_id=s.id) AS child_count
                FROM session s'''+where+' ORDER BY s.time_updated DESC,s.id DESC LIMIT ? OFFSET ?', parameters+[limit,offset]).fetchall()
            return {'items':[dict(r) for r in rows], 'total':total, 'offset':offset, 'limit':limit}

    def get_session(self, session_id):
        if not isinstance(session_id, str) or not session_id.startswith('ses_') or len(session_id)>100:
            raise ValueError('Invalid session ID')
        with self.connect() as c:
            row = c.execute('SELECT id,title,directory,parent_id,time_created,time_updated,time_archived FROM session WHERE id=?', (session_id,)).fetchone()
            if row is None:
                raise ValueError('Session no longer exists. Refresh the list.')
            return dict(row)

    def preview(self, session_id, offset=0, limit=12):
        session = self.get_session(session_id)
        offset, limit = number(offset), number(limit,12,30)
        if not limit:
            raise ValueError('Page size must be at least 1')
        with self.connect() as c:
            total = c.execute('SELECT count(*) FROM message WHERE session_id=?', (session_id,)).fetchone()[0]
            rows = c.execute('''SELECT id,time_created,
                CASE WHEN octet_length(data)<=131072 THEN data ELSE NULL END AS data
                FROM message WHERE session_id=? ORDER BY time_created DESC,id DESC LIMIT ? OFFSET ?''', (session_id,limit,offset)).fetchall()
            messages = []
            for row in rows:
                try:
                    info = json.loads(row['data'] or '{}')
                except (ValueError, TypeError):
                    info = {}
                parts = c.execute('''SELECT id,octet_length(data) AS bytes,
                    CASE WHEN octet_length(data)<=131072 THEN data ELSE NULL END AS data
                    FROM part WHERE message_id=? ORDER BY id LIMIT 61''', (row['id'],)).fetchall()
                rendered = []
                for part in parts[:60]:
                    if part['data'] is None:
                        rendered.append({'type':'large','text':'Large content is kept in OpenCode and is not loaded into this preview.','bytes':part['bytes']})
                        continue
                    try:
                        item = json.loads(part['data'])
                    except (ValueError, TypeError):
                        continue
                    kind = item.get('type','other')
                    text = ''
                    truncated = False
                    if kind in ('text','reasoning'):
                        original = str(item.get('text',''))
                        text, truncated = original[:6000], len(original)>6000
                    elif kind == 'tool':
                        state = item.get('state') or {}
                        value = state.get('output') or state.get('error') or state.get('title') or state.get('status') or ''
                        original = str(item.get('tool','Tool'))+'\n'+str(value)
                        text, truncated = original[:6000], len(original)>6000
                    elif kind == 'file':
                        text = str(item.get('filename') or item.get('mime') or 'Attachment')[:300]
                    else:
                        continue
                    rendered.append({'type':kind, 'text':text, 'bytes':part['bytes'], 'truncated':truncated})
                if len(parts)>60:
                    rendered.append({'type':'large','text':'Additional parts omitted from this message preview.','bytes':0})
                messages.append({'id':row['id'],'role':info.get('role','message'),'time':row['time_created'],'parts':rendered})
            return {'session':session,'messages':list(reversed(messages)),'total':total,'offset':offset,'limit':limit}

    def delete_plan(self, ids):
        if not isinstance(ids,list) or not 1 <= len(ids) <= 200 or any(not isinstance(i,str) for i in ids):
            raise ValueError('Select between 1 and 200 sessions')
        requested = set(ids)
        with self.connect() as c:
            rows = [dict(r) for r in c.execute('''SELECT s.id,s.title,s.directory,s.parent_id,s.time_updated,
                coalesce(e.seq,-1) AS seq FROM session s LEFT JOIN event_sequence e ON e.aggregate_id=s.id''')]
        by_id = {r['id']:r for r in rows}
        if not requested <= by_id.keys():
            raise ValueError('Some sessions no longer exist. Refresh the list.')
        selected = set(requested)
        # 循环直到集合稳定，避免递归深度限制，并将所有子会话显式列入预览。
        while True:
            expanded = selected | {r['id'] for r in rows if r['parent_id'] in selected}
            if expanded == selected:
                break
            selected = expanded
        roots = sorted(i for i in selected if by_id[i]['parent_id'] not in selected)
        if not roots:
            raise ValueError('Invalid cyclic session hierarchy')
        sessions = sorted((by_id[i] for i in selected), key=lambda r:r['id'])
        fingerprint = hashlib.sha256(json.dumps(sessions,sort_keys=True).encode()).hexdigest()
        return {'requested':sorted(requested),'roots':roots,'sessions':sessions,'fingerprint':fingerprint}

    def plan_matches(self, plan):
        try:
            return self.delete_plan(plan['requested'])['fingerprint'] == plan['fingerprint']
        except ValueError:
            return False

    def export_markdown(self, session_id):
        session = self.get_session(session_id)
        yield '# '+session['title']+'\n\n'
        yield 'Readable transcript. Embedded attachments and oversized parts are omitted; this is not a full backup.\n\n'
        with self.connect() as c:
            total = c.execute('SELECT count(*) FROM message WHERE session_id=?',(session_id,)).fetchone()[0]
        # 以旧到新顺序分批导出，限制单批内存占用。
        for offset in range(((total-1)//12)*12 if total else -1, -1, -12):
            page = self.preview(session_id,offset,12)
            for message in page['messages']:
                yield '## '+str(message['role']).capitalize()+'\n\n'
                for part in message['parts']:
                    yield part['text']+'\n\n'
                    if part.get('truncated'):
                        yield '[Content truncated to 6,000 characters in this readable export.]\n\n'
