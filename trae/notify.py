#!/usr/bin/env python3
"""通知模块：PushPlus 微信推送 + Windows 桌面 Toast。任一失败不影响主流程。"""
import json, os, sys, subprocess
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(BASE, "..", "config.json")
TOAST_PS1 = os.path.join(BASE, "toast.ps1")


def load_config():
    try:
        with open(CONFIG, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def pushplus_token():
    cfg = load_config()
    return os.environ.get("PUSHPLUS_TOKEN") or cfg.get("pushplus_token") or ""


def push(title, content, timeout=10):
    token = pushplus_token()
    if not token:
        return {"ok": False, "reason": "未配置 pushplus_token"}
    body = json.dumps({"token": token, "title": title, "content": content, "template": "txt"},
                      ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request("http://www.pushplus.plus/send", data=body,
                                 headers={"Content-Type": "application/json; charset=utf-8"},
                                 method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.loads(r.read().decode("utf-8", "replace"))
        return {"ok": d.get("code") == 200, "resp": d}
    except Exception as e:
        return {"ok": False, "reason": str(e)}


def toast(title, message, timeout=15):
    if not os.path.exists(TOAST_PS1):
        return {"ok": False, "reason": "缺少 toast.ps1"}
    cmd = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
           "-File", TOAST_PS1, "-Title", title, "-Message", message]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace")
        out = (p.stdout or "").strip()
        return {"ok": p.returncode == 0 and out.startswith("ok"), "out": out[:200]}
    except Exception as e:
        return {"ok": False, "reason": str(e)}


def notify(title, content, short=None):
    cfg = load_config().get("notify", {})
    out = {}
    if cfg.get("push", True):
        out["push"] = push(title, content)
    if cfg.get("toast", True):
        out["toast"] = toast(title, short or content)
    return out


if __name__ == "__main__":
    t = sys.argv[1] if len(sys.argv) > 1 else "ai-daily-checkin 通知测试"
    c = sys.argv[2] if len(sys.argv) > 2 else "测试消息"
    print(json.dumps(notify(t, c), ensure_ascii=False))
