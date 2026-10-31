const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const readline = require('node:readline');
let listener;
const input = readline.createInterface({ input: process.stdin });
let starting = false;
input.on('line', async (line) => {
  try {
    const config = JSON.parse(line);
    if (config.stop) {
      await listener?.stop();
      process.exit(0);
    }
    if (starting) return;
    starting = true;
    // 从已安装版本解析真实模块名称，不复制或重写 OpenCode 的业务逻辑。
    const sidecar = path.join(config.asar, 'out/main/sidecar.js');
    const source = fs.readFileSync(sidecar, 'utf8');
    const match = source.match(/import\("(\.\/chunks\/node-[^"]+\.js)"\)/);
    if (!match) throw new Error('Unsupported OpenCode desktop layout');
    process.env.OPENCODE_SERVER_USERNAME = 'opencode';
    process.env.OPENCODE_SERVER_PASSWORD = config.password;
    process.env.OPENCODE_DB = config.database;
    for (const key of ['NO_PROXY','no_proxy']) {
      process.env[key] = [process.env[key], 'localhost,127.0.0.1,::1'].filter(Boolean).join(',');
    }
    const modulePath = path.resolve(path.dirname(sidecar), match[1]);
    const { Server } = await import(pathToFileURL(modulePath).href);
    listener = await Server.listen({ hostname:'127.0.0.1', port:config.port,
      username:'opencode', password:config.password, cors:[] });
    console.log('MANAGER_SERVER_READY');
  } catch (error) {
    console.error('Manager server failed:', error.message);
    process.exit(1);
  }
});
input.on('close', async () => { await listener?.stop(); process.exit(0); });
