#!/usr/bin/env node
// Trae CN 每日签到 —— 方案 A：API
// 读本机登录态（storage.json 的 iCubeAuthInfo 条目）→ 解密 token → 调 checkin_credits 接口
//
// 用法:
//   node checkin_api.js            # 人类可读
//   node checkin_api.js --json     # 机器可读（供 daily.py）
//   node checkin_api.js --dry-run  # 只查状态，不领取
//
// 配置优先级：config.json > 环境变量 > 自动探测
//   TRAE_STORAGE / TRAE_DEVICE_ID
const fs = require('fs');
const os = require('os');
const path = require('path');
const { subtle } = require('crypto').webcrypto;

// ---------- 配置 ----------
const BASE = __dirname;
const CONFIG_PATHS = [path.join(BASE, '..', 'config.json'), path.join(BASE, 'config.json')];

function loadConfig() {
  for (const p of CONFIG_PATHS) {
    try {
      if (fs.existsSync(p)) return JSON.parse(fs.readFileSync(p, 'utf8'));
    } catch (e) { /* ignore */ }
  }
  return {};
}

const CFG = loadConfig();
const TRAE_CFG = CFG.trae || {};
const APPDATA = process.env.APPDATA || path.join(os.homedir(), 'AppData', 'Roaming');
const TRAE_DIR = path.join(APPDATA, 'Trae CN');

const STORAGE = TRAE_CFG.storage_path || process.env.TRAE_STORAGE ||
  path.join(TRAE_DIR, 'User', 'globalStorage', 'storage.json');

function detectDeviceId() {
  if (TRAE_CFG.device_id) return String(TRAE_CFG.device_id);
  if (process.env.TRAE_DEVICE_ID) return String(process.env.TRAE_DEVICE_ID);
  // 从 aha 日志里捞真实的 X-Device-Id
  try {
    const logDir = path.join(TRAE_DIR, 'logs', 'aha_log');
    if (fs.existsSync(logDir)) {
      const files = fs.readdirSync(logDir)
        .filter(f => f.endsWith('.log'))
        .map(f => path.join(logDir, f))
        .sort((a, b) => fs.statSync(b).mtimeMs - fs.statSync(a).mtimeMs);
      for (const f of files) {
        const txt = fs.readFileSync(f, 'utf8');
        const m = [...txt.matchAll(/device_id\s*[:=]\s*(\d{6,})/g)];
        if (m.length) return m[m.length - 1][1];
      }
    }
  } catch (e) { /* ignore */ }
  return '';
}

const DEVICE_ID = detectDeviceId();
const HOST = 'https://api.trae.cn';
const JSON_MODE = process.argv.includes('--json');
const DRY = process.argv.includes('--dry-run');

// ---------- "tc" 信封解密（AES-CBC + SHA-512 派生） ----------
const K1 = 6, O2 = 32, JN = 64, np = 64;
const Ode = Uint8Array.from([82,9,106,213,48,54,165,56,191,64,163,158,129,243,215,251,124,227,57,130,155,47,255,135,52,142,67,68,196,222,233,203,84,123,148,50,166,194,35,61,238,76,149,11,66,250,195,78,8,46,161,102,40,217,36,178,118,91,162,73,109,139,209,37]);
const Nde = Uint8Array.from([31,221,168,51,136,7,199,49,177,18,16,89,39,128,236,95,96,81,127,169,25,181,74,13,45,229,122,159,147,201,156,239,160,224,59,77,174,42,245,176,200,235,187,60,131,83,153,97,23,43,4,126,186,119,214,38,225,105,20,99,85,33,12,125]);

async function sha512(buf) { return new Uint8Array(await subtle.digest('SHA-512', buf)); }

async function decryptBlob(blob) {
  if (!(blob[0] === 0x74 && blob[1] === 0x63 && blob[2] === 5 && blob[3] === 16 && blob[4] === 0 && blob[5] === 0)) {
    throw new Error('未知信封版本（魔数不匹配），客户端可能已升级加密格式');
  }
  const key = blob.slice(K1, K1 + O2);
  const salt = new Uint8Array(JN);
  for (let i = 0; i < JN; i++) salt[i] = Ode[i] ^ Nde[i];
  const h1 = await sha512(key);
  const n = new Uint8Array(np + JN);
  n.set(h1, 0); n.set(salt, np);
  const c = await sha512(n);
  const aesKey = c.slice(0, 16), iv = c.slice(16, 32);
  const ct = blob.slice(K1 + O2);
  if (ct.length % 16 !== 0) throw new Error('密文长度非 16 对齐: ' + ct.length);
  const k = await subtle.importKey('raw', aesKey, { name: 'AES-CBC' }, false, ['decrypt']);
  const pt = new Uint8Array(await subtle.decrypt({ name: 'AES-CBC', iv }, k, ct));
  const head = pt.slice(0, 64), body = pt.slice(64);
  const chk = await sha512(body);
  for (let i = 0; i < 64; i++) if (chk[i] !== head[i]) throw new Error('完整性校验失败');
  return Buffer.from(body).toString('utf8');
}

function loadAuth() {
  if (!fs.existsSync(STORAGE)) throw new Error('找不到 Trae CN 配置: ' + STORAGE + '（确认已安装并登录 Trae CN）');
  const d = JSON.parse(fs.readFileSync(STORAGE, 'utf8'));
  const b64 = d['iCubeAuthInfo://icube.cloudide'];
  if (!b64) throw new Error('未找到 iCubeAuthInfo://icube.cloudide，请先登录 Trae CN');
  return b64;
}

async function post(ep, token, body) {
  if (!DEVICE_ID) throw new Error('未取得 x-device-id，请在 config.json 填写 trae.device_id');
  const r = await fetch(HOST + ep, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': 'Cloud-IDE-JWT ' + token,
      'X-User-Region': 'CN',
      'x-device-id': DEVICE_ID,
    },
    body: JSON.stringify(body),
  });
  const txt = await r.text();
  let json; try { json = JSON.parse(txt); } catch { json = { raw: txt.slice(0, 300) }; }
  return { status: r.status, json };
}

async function balance(token) {
  const r = await post('/trae/api/v2/pay/ide_user_ent_usage', token, {});
  const s = r.json?.usage_summary;
  if (!s) return null;
  return { total: s.total_amount, used: s.consumed_amount, left: +(s.total_amount - s.consumed_amount).toFixed(2) };
}

function emit(res, code) {
  if (JSON_MODE) process.stdout.write(JSON.stringify(res) + '\n');
  else console.log(res.human || res.reason || '');
  process.exit(code);
}

(async () => {
  const res = { scheme: 'api', ok: false, action: 'failed', reason: '', account: '', userId: '', credits: null, balance: null, human: '' };
  try {
    const info = JSON.parse(await decryptBlob(Uint8Array.from(Buffer.from(loadAuth(), 'base64'))));
    const token = info.token;
    if (!token) throw new Error('登录态里 token 为空');
    res.account = info.account?.username || '';
    res.userId = info.userId || '';
    res.tokenExpires = info.expiredAt;
    res.tokenDaysLeft = Math.floor((new Date(info.expiredAt) - Date.now()) / 86400000);

    const b = await balance(token);
    res.balance = b;

    const st = await post('/trae/api/v2/ug/checkin_credits/status', token, { req_source: 2 });
    const j = st.json || {};
    res.status = j;

    if (j.code !== 0 && j.code !== undefined) {
      res.reason = `状态接口异常 code=${j.code} msg=${j.message || ''}`;
      res.human = `❌ ${res.reason}`;
      emit(res, 2);
    }

    if (j.checked_in === true) {
      res.ok = true; res.action = 'already'; res.reason = '今日已签到';
      res.credits = j.credits ?? null;
      res.human = `✅ ${res.account} 今日已签到（奖励 ${j.credits ?? '-'}），余额 ${b ? b.left : '-'}`;
      emit(res, 0);
    }

    if (j.enable === false) {
      res.ok = true; res.action = 'disabled'; res.reason = '签到活动未开启';
      res.human = `⚠ ${res.account} 签到活动未开启，跳过`;
      emit(res, 0);
    }

    if (DRY) {
      res.ok = true; res.action = 'would_claim'; res.reason = '可签到(dry-run)';
      res.human = `🟡 ${res.account} 可签到（dry-run 未领取），余额 ${b ? b.left : '-'}`;
      emit(res, 0);
    }

    let cl = await post('/trae/api/v2/ug/checkin_credits/claim', token, { req_source: 2 });
    if (cl.status !== 200) cl = await post('/trae/api/v2/ug/checkin_credits/claim', token, { req_source: 1 });
    res.claim = cl.json;

    const st2 = await post('/trae/api/v2/ug/checkin_credits/status', token, { req_source: 2 });
    const ok2 = st2.json?.checked_in === true;
    const b2 = await balance(token);
    res.balanceAfter = b2;
    if (ok2) {
      res.ok = true; res.action = 'claimed'; res.reason = '领取成功';
      res.credits = st2.json?.credits ?? null;
      res.human = `🎉 ${res.account} 签到成功 +${res.credits ?? '?'}，余额 ${b2 ? b2.left : '-'}`;
      emit(res, 0);
    } else {
      res.reason = '领取后复核仍未签到';
      res.human = `❌ ${res.account} 领取失败：${JSON.stringify(cl.json).slice(0, 160)}`;
      emit(res, 2);
    }
  } catch (e) {
    res.reason = e.message;
    res.human = `❌ API 方案失败：${e.message}`;
    emit(res, 2);
  }
})();
