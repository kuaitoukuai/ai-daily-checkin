#!/usr/bin/env python3
"""Trae CN 每日签到编排器

流程（auto）: 确保 Trae 运行 → API 方案 → 失败则像素方案 → 若本次是脚本启动的则退出 → 推送+桌面通知

用法:
  python daily.py                  # 默认 auto
  python daily.py --mode api       # 只走 API（不启动 Trae）
  python daily.py --mode ui        # 只走像素方案
  python daily.py --no-launch      # 不自动启动 Trae
  python daily.py --no-quit        # 跑完不退出 Trae
  python daily.py --dry-run        # 只检测
"""
import os, sys, json, time, argparse, subprocess, datetime, shutil
import psutil

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
CHECKIN_JS = os.path.join(BASE, "checkin_api.js")
UI_PY = os.path.join(BASE, "checkin_ui.py")
LOG_DIR = os.path.join(ROOT, "logs")
LOG = os.path.join(LOG_DIR, "trae_daily.log")
PROC = "Trae CN.exe"

sys.path.insert(0, BASE)
import notify  # noqa


def find_node():
    for cand in (os.environ.get("NODE"), shutil.which("node"), shutil.which("node.exe")):
        if cand and os.path.exists(cand):
            return cand
    # 常见 bundled 位置
    for ver in ("22.22.2-6", "22.22.2", "20.18.0"):
        p = os.path.join(os.environ.get("USERPROFILE", ""), ".workbuddy", "binaries", "node", "versions", ver, "node.exe")
        if os.path.exists(p):
            return p
    return "node"


def find_exe():
    cands = [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Trae CN", "Trae CN.exe"),
        r"C:\Program Files\Trae CN\Trae CN.exe",
    ]
    for p in cands:
        if p and os.path.exists(p):
            return p
    return cands[0]


def log(msg):
    os.makedirs(LOG_DIR, exist_ok=True)
    line = "[%s] %s" % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg)
    print(line)
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def proc_count():
    return sum(1 for p in psutil.process_iter(['name'])
               if (p.info['name'] or '').lower() == PROC.lower())


def run_json(cmd, timeout):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace")
        out = (p.stdout or "").strip()
        line = [l for l in out.splitlines() if l.strip().startswith("{")]
        if not line:
            return {"ok": False, "scheme": "?", "reason": "无 JSON 输出: " + (out or p.stderr or "")[:200]}
        return json.loads(line[-1])
    except subprocess.TimeoutExpired:
        return {"ok": False, "scheme": "?", "reason": "超时"}
    except Exception as e:
        return {"ok": False, "scheme": "?", "reason": str(e)}


def run_api(dry=False):
    cmd = [find_node(), CHECKIN_JS, "--json"]
    if dry:
        cmd.append("--dry-run")
    log("运行 API 方案 ...")
    return run_json(cmd, 90)


def run_ui(dry=False):
    cmd = [sys.executable, UI_PY]
    if dry:
        cmd.append("--dry-run")
    log("运行像素方案 ...")
    return run_json(cmd, 180)


def find_main_window(timeout=90):
    import win32gui, win32process
    deadline = time.time() + timeout
    while time.time() < deadline:
        pids = {p.info['pid'] for p in psutil.process_iter(['pid', 'name'])
                if (p.info['name'] or '').lower() == PROC.lower()}
        best = None; best_area = 0
        def cb(h, _):
            nonlocal best, best_area
            if not win32gui.IsWindowVisible(h):
                return True
            _, pid = win32process.GetWindowThreadProcessId(h)
            if pid in pids:
                l, t, r, b = win32gui.GetWindowRect(h)
                a = (r - l) * (b - t)
                if a > best_area:
                    best_area = a; best = h
            return True
        win32gui.EnumWindows(cb, None)
        if best and best_area > 100000:
            return best
        time.sleep(1)
    return None


def quit_trae():
    try:
        import win32gui, win32con
        hwnd = find_main_window(30)
        if not hwnd:
            return proc_count() == 0
        win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
        for _ in range(25):
            if proc_count() == 0:
                return True
            time.sleep(1)
        return proc_count() == 0
    except Exception as e:
        log("退出 Trae 失败: " + str(e))
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["auto", "api", "ui"], default="auto")
    ap.add_argument("--no-launch", action="store_true")
    ap.add_argument("--no-quit", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    log("=== 开始 (mode=%s dry=%s) ===" % (args.mode, args.dry_run))
    started = proc_count() > 0
    launched = False

    if args.mode in ("auto", "ui") and not started and not args.no_launch:
        log("启动 Trae ...")
        try:
            subprocess.Popen([find_exe()], close_fds=True)
            launched = True
            if not find_main_window(90):
                log("等待主窗口超时")
        except Exception as e:
            log("启动失败: " + str(e))

    result = None
    if args.mode in ("auto", "api"):
        result = run_api(args.dry_run)
        log("API 结果: " + json.dumps(result.get("human") or result.get("reason"), ensure_ascii=False))

    if args.mode == "ui" or (args.mode == "auto" and not result.get("ok")):
        if proc_count() == 0 and args.mode == "ui" and not args.no_launch:
            try:
                subprocess.Popen([find_exe()], close_fds=True); launched = True; find_main_window(90)
            except Exception as e:
                log("启动失败: " + str(e))
        ui = run_ui(args.dry_run)
        log("UI 结果: " + json.dumps(ui.get("reason"), ensure_ascii=False))
        if not result or not result.get("ok"):
            result = ui
        else:
            result["ui"] = ui

    if launched and not args.no_quit:
        log("关闭 Trae（本次由脚本启动）...")
        log("已退出" if quit_trae() else "退出未确认")

    human = (result or {}).get("human") or (result or {}).get("reason") or "未知结果"
    scheme = (result or {}).get("scheme", "?")
    ok = (result or {}).get("ok", False)
    action = (result or {}).get("action", "")
    title = "Trae 签到 · " + ("成功" if action == "claimed" else "已签到" if action == "already" else "未完成")
    content = human + "\n方案：" + str(scheme).upper()
    log("最终: " + human)
    try:
        nr = notify.notify(title, content, short=human)
        log("通知: " + json.dumps(nr, ensure_ascii=False)[:300])
    except Exception as e:
        log("通知失败: " + str(e))

    sys.exit(0 if ok or action == "already" else 2)


if __name__ == "__main__":
    main()
