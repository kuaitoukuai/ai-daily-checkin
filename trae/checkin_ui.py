#!/usr/bin/env python3
"""Trae CN 签到 —— 方案 B：截图像素识别 + 点击

流程：找主窗口 → 移到竖屏并最大化 → 强制前置 → 点左下角账号行 → 找「升级权益」深色锚点
      → 推算右侧签到胶囊 → 用中位亮度判「可点 / 已签到」→ 可点则点击。

用法:
  python checkin_ui.py --dry-run   # 只识别，不点击
  python checkin_ui.py             # 可点时点击
  python checkin_ui.py --launch --quit   # 未运行则启动，完成后退出

注意：坐标按 100% 缩放、竖屏 1080x1920、窗口最大化校准；不同 DPI/语言/主题可能需要重调。
"""
import sys, json, time, argparse, subprocess, ctypes
from ctypes import wintypes
import os

try:
    import win32gui, win32con, win32process
    import psutil
    import numpy as np
    from PIL import ImageGrab
except ImportError as e:
    print(json.dumps({"ok": False, "scheme": "ui", "reason": f"缺少依赖: {e}（pip install pywin32 psutil numpy pillow）"}, ensure_ascii=False))
    sys.exit(2)

BASE = os.path.dirname(os.path.abspath(__file__))
SHOT_DIR = os.path.join(BASE, "..", "shots")
PROC = "Trae CN.exe"
USER32 = ctypes.windll.user32
KERNEL32 = ctypes.windll.kernel32

# 相对锚点的胶囊偏移（像素）；如版面变化可在此调整
PILL_DX0, PILL_DY0, PILL_DX1, PILL_DY1 = -77, 20, -9, 50
ACCOUNT_CLICK_DX, ACCOUNT_CLICK_FROM_BOTTOM = 100, 34


def log(*a):
    print(*a, file=sys.stderr)


def find_exe():
    cands = [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Trae CN", "Trae CN.exe"),
        r"C:\Program Files\Trae CN\Trae CN.exe",
    ]
    for p in cands:
        if p and os.path.exists(p):
            return p
    return cands[0]


def proc_count():
    return sum(1 for p in psutil.process_iter(['name'])
               if (p.info['name'] or '').lower() == PROC.lower())


def pids_by_name():
    return {p.info['pid'] for p in psutil.process_iter(['pid', 'name'])
            if (p.info['name'] or '').lower() == PROC.lower()}


def find_main_window():
    pids = pids_by_name()
    best = None
    def cb(hwnd, _):
        nonlocal best
        if not win32gui.IsWindowVisible(hwnd):
            return True
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        if pid not in pids:
            return True
        l, t, r, b = win32gui.GetWindowRect(hwnd)
        a = (r - l) * (b - t)
        if best is None or a > best[1]:
            best = (hwnd, a, (l, t, r, b))
        return True
    win32gui.EnumWindows(cb, None)
    return best


class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_ulong), ("rcMonitor", RECT),
                ("rcWork", RECT), ("dwFlags", ctypes.c_ulong)]


def monitors():
    out = []
    Proc = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong,
                              ctypes.POINTER(RECT), ctypes.c_double)
    def cb(h, hdc, rc, d):
        mi = MONITORINFO(); mi.cbSize = ctypes.sizeof(MONITORINFO)
        USER32.GetMonitorInfoW(h, ctypes.byref(mi))
        out.append((mi.rcMonitor.left, mi.rcMonitor.top, mi.rcMonitor.right,
                    mi.rcMonitor.bottom, mi.dwFlags))
        return 1
    USER32.EnumDisplayMonitors(0, 0, Proc(cb), 0)
    return out


def robust_foreground(hwnd):
    if win32gui.IsIconic(hwnd):
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE); time.sleep(0.4)
    fg = USER32.GetForegroundWindow()
    fg_tid = USER32.GetWindowThreadProcessId(fg, None)
    cur = KERNEL32.GetCurrentThreadId()
    USER32.AttachThreadInput(cur, fg_tid, True)
    try:
        USER32.BringWindowToTop(hwnd)
        USER32.SetForegroundWindow(hwnd)
        USER32.SetActiveWindow(hwnd)
    finally:
        USER32.AttachThreadInput(cur, fg_tid, False)
    time.sleep(0.4)
    return USER32.GetForegroundWindow() == hwnd


def click(sx, sy):
    USER32.SetCursorPos(sx, sy); time.sleep(0.12)
    USER32.mouse_event(0x0002, 0, 0, 0, 0); time.sleep(0.07)
    USER32.mouse_event(0x0004, 0, 0, 0, 0)


def press_esc():
    USER32.keybd_event(0x1B, 0, 0, 0); time.sleep(0.04)
    USER32.keybd_event(0x1B, 0, 2, 0); time.sleep(0.25)


def place_on_portrait(hwnd):
    mons = monitors()
    portrait = [m for m in mons if (m[3] - m[1]) > (m[2] - m[0])]
    target = portrait[0] if portrait else [m for m in mons if m[4] & 1][0]
    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE); time.sleep(0.4)
    win32gui.SetWindowPos(hwnd, 0, target[0], target[1],
                          target[2] - target[0], target[3] - target[1],
                          win32con.SWP_NOZORDER); time.sleep(0.3)
    win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE); time.sleep(0.8)


def grab(rect):
    l, t, r, b = rect
    return np.array(ImageGrab.grab(bbox=(l, t, r, b), all_screens=True).convert("RGB")).astype(int)


def save(rect, name):
    os.makedirs(SHOT_DIR, exist_ok=True)
    l, t, r, b = rect
    ImageGrab.grab(bbox=(l, t, r, b), all_screens=True).save(os.path.join(SHOT_DIR, name))


def find_dark_button(a):
    H, W = a.shape[:2]
    dark = (a.max(axis=2) < 70)
    y_from, y_to = int(H * 0.50), int(H * 0.90)
    x_to = int(W * 0.50)
    counts = dark[y_from:y_to, 0:x_to].sum(axis=1)
    rows = [y + y_from for y, c in enumerate(counts) if c > 100]
    if not rows:
        return None
    segs = []; s = rows[0]; prev = rows[0]
    for y in rows[1:]:
        if y - prev > 3:
            segs.append((s, prev)); s = y
        prev = y
    segs.append((s, prev))
    s, e = max(segs, key=lambda t: t[1] - t[0])
    if e - s < 15:
        return None
    mid = (s + e) // 2
    xs = np.where(dark[mid, 10:x_to])[0] + 10
    if len(xs) < 80:
        return None
    return (int(xs.min()), int(s), int(xs.max()), int(e))


def pill_box(btn):
    x0, y0, x1, y1 = btn
    return (x1 + PILL_DX0, y1 + PILL_DY0, x1 + PILL_DX1, y1 + PILL_DY1)


def pill_brightness(a, box):
    x0, y0, x1, y1 = box
    region = a[y0 + 6:y1 - 6, x0 + 8:x1 - 8]
    return float(np.median(region))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--launch", action="store_true")
    ap.add_argument("--quit", action="store_true")
    args = ap.parse_args()

    res = {"scheme": "ui", "ok": False, "action": "none", "reason": ""}
    launched = False

    if proc_count() == 0:
        if not args.launch:
            res["reason"] = "Trae 未运行且未指定 --launch"
            print(json.dumps(res, ensure_ascii=False)); return
        subprocess.Popen([find_exe()], close_fds=True); launched = True
        deadline = time.time() + 90
        while time.time() < deadline and proc_count() == 0:
            time.sleep(1)
        if proc_count() == 0:
            res["reason"] = "启动 Trae 超时"
            print(json.dumps(res, ensure_ascii=False)); return

    deadline = time.time() + 90
    found = None
    while time.time() < deadline:
        found = find_main_window()
        if found and found[2][2] - found[2][0] > 400:
            break
        time.sleep(1)
    if not found:
        res["reason"] = "未找到 Trae 主窗口"
        print(json.dumps(res, ensure_ascii=False)); return

    hwnd, area, rect = found
    res["hwnd"] = hwnd
    place_on_portrait(hwnd)
    if not robust_foreground(hwnd):
        res["reason"] = "无法将 Trae 前置，已放弃以免误点"
        print(json.dumps(res, ensure_ascii=False)); return

    L, T, R, B = win32gui.GetWindowRect(hwnd)
    W, H = R - L, B - T
    res["rect"] = [L, T, R, B]

    press_esc(); time.sleep(0.3)
    click(L + ACCOUNT_CLICK_DX, T + H - ACCOUNT_CLICK_FROM_BOTTOM)
    time.sleep(1.2)
    a = grab((L, T, R, B)); save((L, T, R, B), "ui_menu.png")

    btn = find_dark_button(a)
    if not btn:
        click(L + ACCOUNT_CLICK_DX, T + H - ACCOUNT_CLICK_FROM_BOTTOM)
        time.sleep(1.2)
        a = grab((L, T, R, B)); save((L, T, R, B), "ui_menu.png")
        btn = find_dark_button(a)

    if not btn:
        res["reason"] = "未识别到账号菜单（深色锚点未找到）"
        press_esc()
        print(json.dumps(res, ensure_ascii=False)); return

    res["anchor"] = list(btn)
    box = pill_box(btn)
    res["pill"] = list(box)
    bright = pill_brightness(a, box)
    res["pill_brightness"] = round(bright, 1)

    state = "claimable" if bright < 150 else ("signed" if bright > 195 else "unknown")
    res["state"] = state

    if state == "signed":
        res["ok"] = True; res["action"] = "already"; res["reason"] = "已签到"
    elif state == "unknown":
        res["reason"] = "胶囊亮度无法判定（%.1f）" % bright
    else:
        if args.dry_run:
            res["ok"] = True; res["action"] = "would_claim"; res["reason"] = "可签到（dry-run 未点击）"
        else:
            px = (box[0] + box[2]) // 2
            py = (box[1] + box[3]) // 2
            log("点击签到胶囊 (%d,%d)" % (px, py))
            click(L + px, T + py)
            time.sleep(2.0)
            save((L, T, R, B), "ui_after.png")
            res["ok"] = True; res["action"] = "claimed"; res["reason"] = "已点击签到"

    press_esc()
    if args.quit and launched:
        try:
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
            for _ in range(20):
                if proc_count() == 0:
                    break
                time.sleep(1)
            res["quit"] = proc_count() == 0
        except Exception as e:
            res["quit"] = False; res["quit_error"] = str(e)

    print(json.dumps(res, ensure_ascii=False))


if __name__ == "__main__":
    main()
