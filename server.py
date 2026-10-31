import argparse
import json
import mimetypes
import os
import secrets
import sqlite3
import threading
import time
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from bridge import OfficialBridge
from store import Store

ROOT = Path(__file__).resolve().parent


class Manager:
    def __init__(self, database, runtime=None, isolated=False):
        self.store = Store(database)
        runtime = runtime or Path(os.environ.get('LOCALAPPDATA',Path.home()/'AppData/Local'))/'OpenCodeSessionManager'
        self.bridge = OfficialBridge(database,runtime,isolated=isolated)
        self.csrf = secrets.token_urlsafe(32)
        self.plans = {}
        self.write_lock = threading.Lock()

    def prepare_delete(self, ids):
        plan = self.store.delete_plan(ids)
        token = secrets.token_urlsafe(24)
        self.plans = {k:v for k,v in self.plans.items() if v['expires']>time.monotonic()}
        self.plans[token] = {'plan':plan,'expires':time.monotonic()+300}
        return {'token':token,'count':len(plan['sessions']),'extra':len(plan['sessions'])-len(set(ids)),
                'sessions':[{k:r[k] for k in ('id','title','time_updated','parent_id')} for r in plan['sessions']]}

    def delete(self, token, confirmation):
        record = self.plans.pop(token,None)
        if not record or record['expires']<time.monotonic():
            raise ValueError('Deletion preview expired. Review it again.')
        plan = record['plan']
        count = len(plan['sessions'])
        if confirmation != f'删除 {count}':
            raise ValueError('Confirmation does not match')
        # 启动可能耗时，必须在启动完成后重新核对会话范围。
        self.bridge.start()
        if not self.store.plan_matches(plan):
            raise ValueError('Sessions changed since the preview. Review the selection again.')
        roots = {r['id']:r for r in plan['sessions']}
        deleted=[]
        for root in plan['roots']:
            # 每个父会话删除前重新核对子树，防止确认后新增会话被意外包含。
            current=self.store.delete_plan([root])
            for item in current['sessions']:
                if item != roots.get(item['id']):
                    raise RuntimeError(f'Selection changed. {len(deleted)} sessions were already deleted; refresh before retrying.')
            self.bridge.request('DELETE','/session/'+root,directory=roots[root]['directory'],ensure=False)
            with self.store.connect() as c:
                remaining=[item['id'] for item in current['sessions'] if c.execute('SELECT 1 FROM session WHERE id=?',(item['id'],)).fetchone()]
            if remaining:
                raise RuntimeError('OpenCode did not complete deletion. Refresh the list before retrying.')
            deleted.extend(item['id'] for item in current['sessions'])
        return {'deleted':len(deleted)}


class Handler(BaseHTTPRequestHandler):
    server_version='SessionManager/1.0'

    def log_message(self, *_):
        pass

    @property
    def manager(self):
        return self.server.manager

    def check_request(self, write=False):
        # 本机绑定、Host 校验和同源令牌共同阻止网页跨站操作本机数据。
        port=self.server.server_address[1]
        hosts={f'127.0.0.1:{port}',f'localhost:{port}'}
        if self.headers.get('Host') not in hosts:
            raise PermissionError('Invalid host')
        origin=self.headers.get('Origin')
        if origin and origin not in {'http://'+h for h in hosts}:
            raise PermissionError('Cross-origin requests are not allowed')
        if write and not secrets.compare_digest(self.headers.get('X-Manager-Token',''),self.manager.csrf):
            raise PermissionError('Invalid request token. Reload this page.')

    def reply(self, data, status=200, kind='application/json; charset=utf-8', extra=None):
        raw=json.dumps(data,ensure_ascii=False).encode() if kind.startswith('application/json') else data
        self.send_response(status)
        self.send_header('Content-Type',kind)
        self.send_header('Content-Length',str(len(raw)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        for key,value in (extra or {}).items():
            self.send_header(key,value)
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        try:
            self.check_request()
            parsed=urllib.parse.urlparse(self.path)
            path=parsed.path
            query={k:v[-1] for k,v in urllib.parse.parse_qs(parsed.query).items()}
            if path=='/api/health':
                return self.reply({'app':'opencode-session-manager','status':'ok'})
            if path=='/api/bootstrap':
                return self.reply({'token':self.manager.csrf,'summary':self.manager.store.summary(),
                    'service_ready':bool(self.manager.bridge.process and self.manager.bridge.process.poll() is None)})
            if path=='/api/sessions':
                return self.reply(self.manager.store.list_sessions(query))
            if path.startswith('/api/session/'):
                parts=path.split('/')
                if len(parts)!=5 or parts[4] not in ('preview','export'):
                    raise ValueError('Unknown session route')
                session_id=parts[3]
                if parts[4]=='preview':
                    return self.reply(self.manager.store.preview(session_id,query.get('offset',0)))
                # 分块写出可读文本，避免大导出占用浏览器或服务端内存。
                self.manager.store.get_session(session_id)
                self.send_response(200)
                self.send_header('Content-Type','text/markdown; charset=utf-8')
                self.send_header('Content-Disposition',f'attachment; filename="{session_id}.md"')
                self.send_header('Cache-Control','no-store')
                self.send_header('X-Content-Type-Options','nosniff')
                self.end_headers()
                for chunk in self.manager.store.export_markdown(session_id):
                    self.wfile.write(chunk.encode())
                return
            files={'/':'index.html','/app.js':'app.js','/styles.css':'styles.css','/favicon.svg':'favicon.svg'}
            if path not in files:
                return self.reply({'error':'Not found'},404)
            file=ROOT/'static'/files[path]
            kind=mimetypes.guess_type(file.name)[0] or 'application/octet-stream'
            return self.reply(file.read_bytes(),kind=kind+'; charset=utf-8')
        except (BrokenPipeError,ConnectionResetError):
            pass
        except Exception as error:
            self.fail(error)

    def do_POST(self):
        try:
            self.check_request(write=True)
            if self.headers.get('Content-Type','').split(';')[0]!='application/json':
                raise ValueError('Expected JSON content')
            size=int(self.headers.get('Content-Length','0'))
            if not 0<size<=65536:
                raise ValueError('Request size is invalid')
            data=json.loads(self.rfile.read(size))
            if not isinstance(data,dict):
                raise ValueError('Expected an object')
            with self.manager.write_lock:
                if self.path=='/api/delete-plan':
                    return self.reply(self.manager.prepare_delete(data.get('ids')))
                if self.path=='/api/delete':
                    return self.reply(self.manager.delete(data.get('token'),data.get('confirmation')))
                if self.path=='/api/update':
                    session=self.manager.store.get_session(data.get('id'))
                    patch={}
                    if 'title' in data:
                        title=data['title']
                        if not isinstance(title,str) or not 1<=len(title.strip())<=250:
                            raise ValueError('Title must contain 1 to 250 characters')
                        patch['title']=title.strip()
                    if 'archived' in data:
                        if not isinstance(data['archived'],bool):
                            raise ValueError('Invalid archive state')
                        patch['time']={'archived':int(time.time()*1000) if data['archived'] else 0}
                    if not patch:
                        raise ValueError('No update was requested')
                    self.manager.bridge.request('PATCH','/session/'+session['id'],patch,directory=session['directory'])
                    updated=self.manager.store.get_session(session['id'])
                    if 'title' in patch and updated['title']!=patch['title']:
                        raise RuntimeError('OpenCode did not save the title')
                    if 'time' in patch and bool(updated['time_archived'])!=data['archived']:
                        raise RuntimeError('OpenCode did not save the archive state')
                    return self.reply(updated)
                if self.path=='/api/service':
                    self.manager.bridge.start()
                    return self.reply({'ready':True})
                if self.path=='/api/shutdown':
                    self.reply({'stopping':True})
                    threading.Thread(target=self.server.shutdown,daemon=True).start()
                    return
                return self.reply({'error':'Not found'},404)
        except (BrokenPipeError,ConnectionResetError):
            pass
        except Exception as error:
            self.fail(error)

    def fail(self, error):
        if isinstance(error,PermissionError):
            return self.reply({'error':str(error)},403)
        if isinstance(error,(ValueError,TypeError,KeyError)):
            return self.reply({'error':str(error)},400)
        if isinstance(error,sqlite3.Error):
            return self.reply({'error':'Could not read the OpenCode database. Check its path and retry after closing OpenCode.'},503)
        if isinstance(error,(RuntimeError,OSError)):
            return self.reply({'error':str(error)},503)
        return self.reply({'error':'An unexpected error occurred. Refresh and retry.'},500)


def main():
    parser=argparse.ArgumentParser(description='Local OpenCode session manager')
    parser.add_argument('--db',default=os.environ.get('OPENCODE_DB',str(Path.home()/'.local/share/opencode/opencode.db')))
    parser.add_argument('--port',type=int,default=8787)
    parser.add_argument('--open',action='store_true')
    args=parser.parse_args()
    if args.open:
        # 重复双击启动脚本时复用已有管理器，避免端口占用错误。
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            with opener.open(f'http://127.0.0.1:{args.port}/api/health',timeout=1) as response:
                existing=json.load(response)
            if existing.get('app')=='opencode-session-manager':
                webbrowser.open(f'http://127.0.0.1:{args.port}')
                print('Opened the existing session manager.',flush=True)
                return
        except (OSError,ValueError):
            pass
    manager=Manager(args.db)
    manager.store.summary()
    httpd=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    httpd.manager=manager
    url=f'http://127.0.0.1:{httpd.server_address[1]}'
    print('OpenCode Session Manager: '+url,flush=True)
    print('Read-only browsing is ready. Close OpenCode Desktop before editing. Press Ctrl+C to stop.',flush=True)
    if args.open:
        webbrowser.open(url)
    try:
        httpd.serve_forever(poll_interval=.3)
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        manager.bridge.close()


if __name__=='__main__':
    main()
