import base64
import csv
import json
import os
import secrets
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


class OfficialBridge:
    def __init__(self, database, runtime_dir, isolated=False):
        self.database = str(Path(database).resolve())
        self.runtime_dir = Path(runtime_dir)
        self.isolated = isolated
        self.process = None
        self.port = None
        self.password = secrets.token_urlsafe(32)
        self.lock = threading.Lock()
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def start(self):
        with self.lock:
            if self.process and self.process.poll() is None:
                return
            local = Path(os.environ.get('LOCALAPPDATA', Path.home()/'AppData/Local'))
            desktop = Path(os.environ.get('OPENCODE_DESKTOP_DIR', local/'Programs/@opencode-aidesktop'))
            executable, asar = desktop/'OpenCode.exe', desktop/'resources/app.asar'
            if not executable.exists() or not asar.exists():
                raise RuntimeError('OpenCode Desktop was not found. Set OPENCODE_DESKTOP_DIR to its installation folder.')
            self.runtime_dir.mkdir(parents=True, exist_ok=True)
            with socket.socket() as sock:
                sock.bind(('127.0.0.1',0))
                self.port = sock.getsockname()[1]
            env = dict(os.environ, ELECTRON_RUN_AS_NODE='1', OPENCODE_DB=self.database,
                       XDG_STATE_HOME=str(self.runtime_dir/'state'))
            if self.isolated:
                # 集成测试使用独立配置和数据目录，不接触用户的提供商与插件配置。
                env.update(XDG_DATA_HOME=str(self.runtime_dir/'data'),XDG_CONFIG_HOME=str(self.runtime_dir/'config'),
                           XDG_CACHE_HOME=str(self.runtime_dir/'cache'),OPENCODE_CONFIG_CONTENT='{"plugin":[],"mcp":{}}')
            log = (self.runtime_dir/'official-server.log').open('ab')
            try:
                self.process = subprocess.Popen([str(executable),str(Path(__file__).with_name('official-server.cjs'))],
                    stdin=subprocess.PIPE,stdout=log,stderr=log,text=True,encoding='utf-8',env=env,
                    cwd=self.runtime_dir,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            finally:
                log.close()
            self.process.stdin.write(json.dumps({'asar':str(asar),'database':self.database,'port':self.port,'password':self.password})+'\n')
            self.process.stdin.flush()
            deadline = time.monotonic()+35
            while time.monotonic()<deadline:
                if self.process.poll() is not None:
                    raise RuntimeError('OpenCode management service could not start. See the local runtime log.')
                try:
                    self.request('GET','/global/health',ensure=False,timeout=1)
                    return
                except (OSError,RuntimeError,ValueError):
                    time.sleep(.2)
            self.close()
            raise RuntimeError('OpenCode management service took too long to start. Retry after closing OpenCode Desktop.')

    def request(self, method, route, body=None, directory=None, ensure=True, timeout=60):
        if ensure:
            self.start()
        if not route.startswith('/') or '://' in route:
            raise ValueError('Invalid internal route')
        url = f'http://127.0.0.1:{self.port}'+route
        if directory:
            url += ('&' if '?' in url else '?')+urllib.parse.urlencode({'directory':directory})
        auth = base64.b64encode(('opencode:'+self.password).encode()).decode()
        headers = {'Authorization':'Basic '+auth,'Accept':'application/json'}
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers['Content-Type']='application/json'
        request = urllib.request.Request(url,data=data,headers=headers,method=method)
        if method != 'GET' and not self.isolated:
            self.require_desktop_closed()
        try:
            with self.opener.open(request,timeout=timeout) as response:
                raw = response.read(4*1024*1024+1)
                if len(raw)>4*1024*1024:
                    raise RuntimeError('OpenCode returned an unexpectedly large response')
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as error:
            # 不把上游堆栈、文件正文或认证头回显到网页。
            raise RuntimeError(f'OpenCode rejected the operation (HTTP {error.code}). Refresh and retry.') from None

    def require_desktop_closed(self):
        if os.name != 'nt':
            return
        # 管理服务独立运行；编辑前排除桌面端同时执行任务的情况。
        result = subprocess.run(['tasklist','/FI','IMAGENAME eq OpenCode.exe','/FO','CSV','/NH'],
            capture_output=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),timeout=8)
        if result.returncode:
            raise RuntimeError('Could not check OpenCode Desktop. Close it before editing and retry.')
        own_pid = self.process.pid if self.process else None
        for row in csv.reader(result.stdout.decode(errors='replace').splitlines()):
            if len(row)>1 and row[0].lower()=='opencode.exe' and row[1].isdigit() and int(row[1])!=own_pid:
                raise RuntimeError('Close OpenCode Desktop before editing sessions. You can continue browsing here.')

    def close(self):
        process = self.process
        if process and process.poll() is None:
            try:
                process.stdin.write('{"stop":true}\n')
                process.stdin.flush()
                process.wait(timeout=5)
            except (OSError,subprocess.TimeoutExpired):
                process.terminate()
                process.wait(timeout=5)
        self.process = None
        if process and process.stdin:
            process.stdin.close()
