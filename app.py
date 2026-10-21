# -*- coding: utf-8 -*-
"""
阅读模拟器 Reading Scroller v1.0

模拟人类阅读时的滚轮操作：以不规律的节奏缓慢下滑，读一段后小幅上翻回看，
再继续下滑，如此循环。滚动量、间隔、停顿都带随机性，不是匀速机械滚动。

热键：F9 暂停/继续   F10 停止   F8 隐藏窗口   F11/F12 切换速度
"""

import ctypes
import ctypes.wintypes as wt
import os
import random
import sys

# ─────────────────────────── 基本信息 ───────────────────────────
APP_NAME = "阅读模拟器"
APP_VERSION = "1.0"

# 三档速度：名称、每次滚动的基础间隔（秒）
SPEEDS = [("慢读", 1.7), ("正常", 1.1), ("快读", 0.7)]
DEFAULT_SPEED = 1

STEP_MIN, STEP_MAX = 1, 3     # 每次向下滚动的格数范围
REVIEW_RATIO = 0.25           # 回看幅度：上滑量 = 这段下滑量 × 该比例
REVIEW_EVERY = (18, 46)       # 每下滑多少格触发一次回看
JITTER = False                # True 则光标轻微抖动（更像真人，但会挪指针）
AUTO_START = 3                # 启动后几秒自动开始

# ─────────────────────────── Win32 ───────────────────────────
user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)

LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wt.UINT),
        ("style", wt.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wt.HINSTANCE),
        ("hIcon", wt.HICON),
        ("hCursor", wt.HANDLE),
        ("hbrBackground", wt.HBRUSH),
        ("lpszMenuName", wt.LPCWSTR),
        ("lpszClassName", wt.LPCWSTR),
        ("hIconSm", wt.HICON),
    ]


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wt.HWND),
        ("message", wt.UINT),
        ("wParam", wt.WPARAM),
        ("lParam", wt.LPARAM),
        ("time", wt.DWORD),
        ("pt", wt.POINT),
    ]


class PAINTSTRUCT(ctypes.Structure):
    _fields_ = [
        ("hdc", wt.HDC),
        ("fErase", wt.BOOL),
        ("rcPaint", wt.RECT),
        ("fRestore", wt.BOOL),
        ("fIncUpdate", wt.BOOL),
        ("rgbReserved", ctypes.c_byte * 32),
    ]


WM_DESTROY, WM_CLOSE = 0x0002, 0x0010
WM_PAINT, WM_ERASEBKGND, WM_TIMER = 0x000F, 0x0014, 0x0113
WM_LBUTTONDOWN, WM_NCHITTEST = 0x0201, 0x0084
WM_MOUSEMOVE = 0x0200
HTCLIENT, HTCAPTION = 1, 2

WS_POPUP, WS_VISIBLE = 0x80000000, 0x10000000
WS_EX_TOPMOST, WS_EX_APPWINDOW = 0x00000008, 0x00040000

DT_CENTER, DT_VCENTER, DT_SINGLELINE = 0x1, 0x4, 0x20
DT_LEFT, DT_RIGHT = 0x0, 0x2

PS_SOLID, TRANSPARENT, DEFAULT_CHARSET, CLEARTYPE = 0, 1, 1, 5
SPI_GETWORKAREA = 0x0030
LOGPIXELSX = 88

IMAGE_ICON = 1
LR_LOADFROMFILE, LR_DEFAULTSIZE = 0x0010, 0x0040

MOUSEEVENTF_WHEEL, MOUSEEVENTF_MOVE = 0x0800, 0x0001

TIMER_TICK, TIMER_KEYS = 1, 2

VK_F8, VK_F9, VK_F10, VK_F11, VK_F12 = 0x77, 0x78, 0x79, 0x7A, 0x7B

user32.CreateWindowExW.argtypes = (
    wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wt.HWND, wt.HMENU, wt.HINSTANCE, wt.LPVOID,
)
user32.CreateWindowExW.restype = wt.HWND
user32.DefWindowProcW.argtypes = (wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)
user32.DefWindowProcW.restype = LRESULT
user32.SetTimer.argtypes = (wt.HWND, ctypes.c_size_t, wt.UINT, ctypes.c_void_p)
user32.SetTimer.restype = ctypes.c_size_t
user32.KillTimer.argtypes = (wt.HWND, ctypes.c_size_t)
user32.BeginPaint.argtypes = (wt.HWND, ctypes.POINTER(PAINTSTRUCT))
user32.BeginPaint.restype = wt.HDC
user32.EndPaint.argtypes = (wt.HWND, ctypes.POINTER(PAINTSTRUCT))
user32.InvalidateRect.argtypes = (wt.HWND, ctypes.c_void_p, wt.BOOL)
user32.FillRect.argtypes = (wt.HDC, ctypes.POINTER(wt.RECT), wt.HBRUSH)
user32.FillRect.restype = ctypes.c_int
user32.DrawTextW.argtypes = (wt.HDC, wt.LPCWSTR, ctypes.c_int,
                             ctypes.POINTER(wt.RECT), wt.UINT)
user32.DrawTextW.restype = ctypes.c_int
user32.GetDC.argtypes = (wt.HWND,)
user32.GetDC.restype = wt.HDC
user32.ReleaseDC.argtypes = (wt.HWND, wt.HDC)
user32.ScreenToClient.argtypes = (wt.HWND, ctypes.POINTER(wt.POINT))
user32.GetSystemMetrics.argtypes = (ctypes.c_int,)
user32.GetSystemMetrics.restype = ctypes.c_int
user32.mouse_event.argtypes = (wt.DWORD, ctypes.c_int, ctypes.c_int,
                               wt.DWORD, ctypes.c_size_t)
user32.GetAsyncKeyState.argtypes = (ctypes.c_int,)
user32.GetAsyncKeyState.restype = ctypes.c_short
user32.DestroyWindow.argtypes = (wt.HWND,)
user32.PostMessageW.argtypes = (wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)
user32.PostQuitMessage.argtypes = (ctypes.c_int,)
user32.GetMessageW.argtypes = (ctypes.POINTER(MSG), wt.HWND, wt.UINT, wt.UINT)
user32.GetMessageW.restype = ctypes.c_int
user32.TranslateMessage.argtypes = (ctypes.POINTER(MSG),)
user32.DispatchMessageW.argtypes = (ctypes.POINTER(MSG),)
user32.DispatchMessageW.restype = LRESULT
user32.LoadCursorW.argtypes = (wt.HINSTANCE, ctypes.c_void_p)
user32.LoadCursorW.restype = wt.HANDLE
user32.LoadImageW.argtypes = (wt.HINSTANCE, wt.LPCWSTR, wt.UINT,
                              ctypes.c_int, ctypes.c_int, wt.UINT)
user32.LoadImageW.restype = wt.HANDLE
user32.SetWindowRgn.argtypes = (wt.HWND, wt.HRGN, wt.BOOL)
user32.ShowWindow.argtypes = (wt.HWND, ctypes.c_int)
user32.IsWindowVisible.argtypes = (wt.HWND,)
user32.IsWindowVisible.restype = wt.BOOL
user32.SystemParametersInfoW.argtypes = (wt.UINT, wt.UINT, ctypes.c_void_p, wt.UINT)
user32.RegisterClassExW.argtypes = (ctypes.POINTER(WNDCLASSEXW),)
user32.RegisterClassExW.restype = wt.ATOM

gdi32.CreateFontW.argtypes = (
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wt.DWORD, wt.DWORD, wt.DWORD, wt.DWORD, wt.DWORD, wt.DWORD, wt.DWORD,
    wt.DWORD, wt.LPCWSTR,
)
gdi32.CreateFontW.restype = wt.HFONT
gdi32.CreateSolidBrush.argtypes = (wt.DWORD,)
gdi32.CreateSolidBrush.restype = wt.HBRUSH
gdi32.CreatePen.argtypes = (ctypes.c_int, ctypes.c_int, wt.DWORD)
gdi32.CreatePen.restype = wt.HPEN
gdi32.SelectObject.argtypes = (wt.HDC, wt.HGDIOBJ)
gdi32.SelectObject.restype = wt.HGDIOBJ
gdi32.DeleteObject.argtypes = (wt.HGDIOBJ,)
gdi32.RoundRect.argtypes = (wt.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                            ctypes.c_int, ctypes.c_int, ctypes.c_int)
gdi32.GetDeviceCaps.argtypes = (wt.HDC, ctypes.c_int)
gdi32.SetTextColor.argtypes = (wt.HDC, wt.DWORD)
gdi32.SetBkMode.argtypes = (wt.HDC, ctypes.c_int)


def RGB(r, g, b):
    return r | (g << 8) | (b << 16)


C_BG = RGB(30, 30, 30)
C_PANEL = RGB(37, 37, 38)
C_LINE = RGB(60, 60, 60)
C_TEXT = RGB(212, 212, 212)
C_DIM = RGB(139, 139, 139)
C_FAINT = RGB(95, 95, 95)
C_ACCENT = RGB(78, 201, 176)
C_GOLD = RGB(215, 186, 125)
C_BLUE = RGB(86, 156, 214)
C_BTN = RGB(47, 47, 49)
C_BTN_HOVER = RGB(60, 60, 62)

# ─────────────────────────── 输入模拟 ───────────────────────────


def wheel(notches):
    """notches > 0 上滚，< 0 下滚"""
    if not notches:
        return
    delta = (notches * 120) & 0xFFFFFFFF
    user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, delta, 0)


def nudge(dx, dy):
    user32.mouse_event(MOUSEEVENTF_MOVE, dx, dy, 0, 0)


# ─────────────────────────── 路径与设置 ───────────────────────────


def base_dir():
    return os.path.dirname(os.path.abspath(__file__))


def settings_path():
    return os.path.join(base_dir(), "settings.ini")


def load_speed():
    try:
        with open(settings_path(), "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("speed"):
                    v = int(line.split("=", 1)[1].strip())
                    if 0 <= v < len(SPEEDS):
                        return v
    except Exception:
        pass
    return DEFAULT_SPEED


def save_speed(idx):
    try:
        with open(settings_path(), "w", encoding="utf-8") as f:
            f.write("[settings]\n")
            f.write("speed = {}\n".format(idx))
    except Exception:
        pass


# ─────────────────────────── 布局 / DPI ───────────────────────────
S = 1.0
W = H = 0


def sc(v):
    return int(round(v * S))


def layout():
    global W, H
    W, H = sc(340), sc(216)


def btn_toggle_rect():
    return (sc(16), sc(148), sc(196), sc(38))


def btn_close_rect():
    return (sc(224), sc(148), sc(100), sc(38))


def speed_rect(i):
    return (sc(16) + i * sc(105), sc(112), sc(98), sc(30))


def hit(rect, x, y):
    rx, ry, rw, rh = rect
    return rx <= x < rx + rw and ry <= y < ry + rh


# ─────────────────────────── 状态 ───────────────────────────
class State:
    def __init__(self):
        self.mode = "waiting"      # waiting | running | paused | stopped
        self.phase = "down"        # down | up
        self.speed = load_speed()
        self.total_down = 0
        self.total_up = 0
        self.reviews = 0
        self.since_review = 0
        self.next_review = random.randint(*REVIEW_EVERY)
        self.up_left = 0
        self.countdown = AUTO_START
        self.hover = None
        self.keys = {}

    @property
    def interval(self):
        return SPEEDS[self.speed][1]


st = State()


# ─────────────────────────── 绘制 ───────────────────────────


def make_font(px, weight=400):
    return gdi32.CreateFontW(
        -px, 0, 0, 0, weight, 0, 0, 0,
        DEFAULT_CHARSET, 0, 0, CLEARTYPE, 0, "Microsoft YaHei UI",
    )


def draw_text(hdc, s, x, y, w, h, px, color, weight=400, fmt=None):
    if fmt is None:
        fmt = DT_CENTER | DT_VCENTER | DT_SINGLELINE
    f = make_font(px, weight)
    old = gdi32.SelectObject(hdc, f)
    gdi32.SetTextColor(hdc, color)
    gdi32.SetBkMode(hdc, TRANSPARENT)
    r = wt.RECT(x, y, x + w, y + h)
    user32.DrawTextW(hdc, s, -1, ctypes.byref(r), fmt)
    gdi32.SelectObject(hdc, old)
    gdi32.DeleteObject(f)


def fill_rect(hdc, x, y, w, h, color):
    b = gdi32.CreateSolidBrush(color)
    r = wt.RECT(x, y, x + w, y + h)
    user32.FillRect(hdc, ctypes.byref(r), b)
    gdi32.DeleteObject(b)


def round_rect(hdc, x, y, w, h, rad, fill, border=None):
    br = gdi32.CreateSolidBrush(fill)
    pn = gdi32.CreatePen(PS_SOLID, 1, border if border is not None else fill)
    ob = gdi32.SelectObject(hdc, br)
    op = gdi32.SelectObject(hdc, pn)
    gdi32.RoundRect(hdc, x, y, x + w, y + h, rad, rad)
    gdi32.SelectObject(hdc, ob)
    gdi32.SelectObject(hdc, op)
    gdi32.DeleteObject(br)
    gdi32.DeleteObject(pn)


def status_text():
    if st.mode == "waiting":
        return ("待机", C_DIM,
                "{} 秒后自动开始 · 请把鼠标移到要阅读的窗口".format(st.countdown))
    if st.mode == "stopped":
        return ("已停止", C_DIM, "点击开始，或按 F9")
    if st.mode == "paused":
        return ("已暂停", C_GOLD, "按 F9 继续")
    if st.phase == "down":
        return ("下滑中 ↓", C_ACCENT, "跟随阅读节奏")
    return ("回看中 ↑", C_BLUE, "小幅上翻 {} 格".format(max(0, st.up_left)))


def paint(hwnd):
    ps = PAINTSTRUCT()
    hdc = user32.BeginPaint(hwnd, ctypes.byref(ps))
    try:
        fill_rect(hdc, 0, 0, W, H, C_BG)
        fill_rect(hdc, 0, 0, W, sc(96), C_PANEL)

        main, color, sub = status_text()
        draw_text(hdc, main, 0, sc(12), W, sc(34), sc(26), color, 700)
        draw_text(hdc, sub, 0, sc(48), W, sc(16), sc(12), C_DIM)

        stat = "已下滑 {} 格 · 回看 {} 次".format(st.total_down, st.reviews)
        draw_text(hdc, stat, 0, sc(68), W, sc(14), sc(11), C_FAINT)

        fill_rect(hdc, 0, sc(96), W, 1, C_LINE)

        # 速度档位
        draw_text(hdc, "阅读速度", sc(16), sc(96), sc(120), sc(16), sc(10),
                  C_FAINT, 400, DT_LEFT | DT_VCENTER | DT_SINGLELINE)
        for i, item in enumerate(SPEEDS):
            x, y, w, h = speed_rect(i)
            active = (i == st.speed)
            if active:
                fill = C_ACCENT
                fg = RGB(20, 20, 20)
            elif st.hover == ("speed", i):
                fill = C_BTN_HOVER
                fg = C_TEXT
            else:
                fill = C_BTN
                fg = C_DIM
            round_rect(hdc, x, y, w, h, sc(7), fill)
            draw_text(hdc, item[0], x, y, w, h, sc(12), fg, 700 if active else 400)

        # 主按钮
        x, y, w, h = btn_toggle_rect()
        if st.mode == "running":
            label, fill, hover_fill = "暂停", C_GOLD, RGB(232, 205, 148)
        else:
            label, fill, hover_fill = "开始", C_ACCENT, RGB(102, 218, 194)
        if st.hover == "toggle":
            fill = hover_fill
        round_rect(hdc, x, y, w, h, sc(8), fill)
        draw_text(hdc, label, x, y, w, h, sc(14), RGB(20, 20, 20), 700)

        # 退出按钮
        x, y, w, h = btn_close_rect()
        round_rect(hdc, x, y, w, h, sc(8),
                   C_BTN_HOVER if st.hover == "close" else C_BTN)
        draw_text(hdc, "退出", x, y, w, h, sc(13), C_TEXT)

        draw_text(hdc, "F9 暂停/继续   F10 停止   F8 隐藏窗口   F11 / F12 换速度",
                  0, sc(196), W, sc(14), sc(10), C_FAINT)
    finally:
        user32.EndPaint(hwnd, ctypes.byref(ps))


def invalidate(hwnd):
    user32.InvalidateRect(hwnd, None, False)


# ─────────────────────────── 节奏引擎 ───────────────────────────


def start_run(hwnd):
    st.mode = "running"
    st.phase = "down"
    st.since_review = 0
    st.next_review = random.randint(*REVIEW_EVERY)
    st.up_left = 0
    user32.SetTimer(hwnd, TIMER_TICK, 200, None)
    invalidate(hwnd)


def pause(hwnd):
    if st.mode != "running":
        return
    st.mode = "paused"
    user32.KillTimer(hwnd, TIMER_TICK)
    invalidate(hwnd)


def resume(hwnd):
    st.mode = "running"
    user32.SetTimer(hwnd, TIMER_TICK, 200, None)
    invalidate(hwnd)


def stop(hwnd):
    st.mode = "stopped"
    user32.KillTimer(hwnd, TIMER_TICK)
    st.phase = "down"
    st.up_left = 0
    st.since_review = 0
    invalidate(hwnd)


def toggle(hwnd):
    if st.mode == "running":
        pause(hwnd)
    elif st.mode == "paused":
        resume(hwnd)
    else:
        start_run(hwnd)


def set_speed(idx, hwnd):
    idx = max(0, min(len(SPEEDS) - 1, idx))
    if idx == st.speed:
        return
    st.speed = idx
    save_speed(idx)
    invalidate(hwnd)


def on_tick(hwnd):
    if st.mode == "waiting":
        st.countdown -= 1
        if st.countdown <= 0:
            start_run(hwnd)
        else:
            invalidate(hwnd)
        return

    if st.mode != "running":
        return

    interval = st.interval

    if st.phase == "down":
        n = random.randint(STEP_MIN, max(STEP_MIN, STEP_MAX))
        wheel(-n)
        st.total_down += n
        st.since_review += n

        # 阅读节奏本身就不规则，偶尔遇到长段落会停得久一些
        delay = interval * random.uniform(0.65, 1.6)
        if random.random() < 0.05:
            delay += random.uniform(1.2, 3.5)

        if st.since_review >= st.next_review:
            st.phase = "up"
            base = max(1, int(round(st.since_review * REVIEW_RATIO)))
            st.up_left = max(1, int(round(base * random.uniform(0.85, 1.2))))
            st.since_review = 0
            st.next_review = random.randint(*REVIEW_EVERY)
            st.reviews += 1
            delay = random.uniform(0.5, 1.4)      # 回看前先愣一下
    else:
        n = min(st.up_left, random.randint(1, 3))
        wheel(n)
        st.total_up += n
        st.up_left -= n
        delay = interval * random.uniform(0.9, 1.9)
        if st.up_left <= 0:
            st.phase = "down"
            delay = random.uniform(0.6, 1.6)

    if JITTER and random.random() < 0.35:
        nudge(random.choice((-1, 0, 1)), random.choice((-1, 0, 1)))

    invalidate(hwnd)
    user32.SetTimer(hwnd, TIMER_TICK, max(1, int(delay * 1000)), None)


def on_keys(hwnd):
    for vk, action in (
        (VK_F8, lambda: toggle_vis(hwnd)),
        (VK_F9, lambda: toggle(hwnd)),
        (VK_F10, lambda: stop(hwnd)),
        (VK_F11, lambda: set_speed(st.speed - 1, hwnd)),
        (VK_F12, lambda: set_speed(st.speed + 1, hwnd)),
    ):
        down = bool(user32.GetAsyncKeyState(vk) & 0x8000)
        if down and not st.keys.get(vk, False):
            action()
        st.keys[vk] = down


def toggle_vis(hwnd):
    if user32.IsWindowVisible(hwnd):
        user32.ShowWindow(hwnd, 0)   # SW_HIDE
    else:
        user32.ShowWindow(hwnd, 5)   # SW_SHOW


# ─────────────────────────── 窗口过程 ───────────────────────────


def _client_xy(lparam):
    return (ctypes.c_short(lparam & 0xFFFF).value,
            ctypes.c_short((lparam >> 16) & 0xFFFF).value)


def _hit_speed(x, y):
    for i in range(len(SPEEDS)):
        if hit(speed_rect(i), x, y):
            return i
    return None


@WNDPROC
def wndproc(hwnd, msg, wparam, lparam):
    try:
        if msg == WM_PAINT:
            paint(hwnd)
            return 0
        if msg == WM_ERASEBKGND:
            return 1
        if msg == WM_TIMER:
            if wparam == TIMER_TICK:
                on_tick(hwnd)
            elif wparam == TIMER_KEYS:
                on_keys(hwnd)
            return 0
        if msg == WM_NCHITTEST:
            x = lparam & 0xFFFF
            y = (lparam >> 16) & 0xFFFF
            x = x - 65536 if x >= 32768 else x
            y = y - 65536 if y >= 32768 else y
            pt = wt.POINT(x, y)
            user32.ScreenToClient(hwnd, ctypes.byref(pt))
            if (hit(btn_toggle_rect(), pt.x, pt.y)
                    or hit(btn_close_rect(), pt.x, pt.y)
                    or _hit_speed(pt.x, pt.y) is not None):
                return HTCLIENT
            return HTCAPTION
        if msg == WM_MOUSEMOVE:
            x, y = _client_xy(lparam)
            h = None
            if hit(btn_toggle_rect(), x, y):
                h = "toggle"
            elif hit(btn_close_rect(), x, y):
                h = "close"
            else:
                i = _hit_speed(x, y)
                if i is not None:
                    h = ("speed", i)
            if h != st.hover:
                st.hover = h
                invalidate(hwnd)
            return 0
        if msg == WM_LBUTTONDOWN:
            x, y = _client_xy(lparam)
            if hit(btn_toggle_rect(), x, y):
                toggle(hwnd)
            elif hit(btn_close_rect(), x, y):
                user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
            else:
                i = _hit_speed(x, y)
                if i is not None:
                    set_speed(i, hwnd)
            return 0
        if msg == WM_CLOSE:
            user32.DestroyWindow(hwnd)
            return 0
        if msg == 0x00A3:  # WM_NCLBUTTONDBLCLK：别让双击把窗口最大化
            return 0
        if msg == WM_DESTROY:
            user32.PostQuitMessage(0)
            return 0
    except Exception:
        pass
    return user32.DefWindowProcW(hwnd, msg, wparam, lparam)


# ─────────────────────────── 入口 ───────────────────────────


def main():
    global S
    try:
        user32.SetProcessDPIAware()
    except Exception:
        pass

    hdc = user32.GetDC(0)
    dpi = gdi32.GetDeviceCaps(hdc, LOGPIXELSX) or 96
    user32.ReleaseDC(0, hdc)
    S = dpi / 96.0
    layout()

    hinst = ctypes.windll.kernel32.GetModuleHandleW(None)
    cls_name = ctypes.create_unicode_buffer("ReadingScrollerWnd")

    icon = 0
    ico_path = os.path.join(base_dir(), "icon.ico")
    if os.path.exists(ico_path):
        try:
            icon = user32.LoadImageW(0, ico_path, IMAGE_ICON, 0, 0,
                                     LR_LOADFROMFILE | LR_DEFAULTSIZE)
        except Exception:
            icon = 0

    cls = WNDCLASSEXW()
    cls.cbSize = ctypes.sizeof(WNDCLASSEXW)
    cls.style = 0x00020000  # CS_DROPSHADOW
    cls.lpfnWndProc = wndproc
    cls.hInstance = hinst
    cls.hIcon = icon or 0
    cls.hIconSm = icon or 0
    cls.hCursor = user32.LoadCursorW(None, 32512)  # IDC_ARROW
    cls.hbrBackground = 0
    cls.lpszClassName = ctypes.cast(cls_name, wt.LPCWSTR)
    user32.RegisterClassExW(ctypes.byref(cls))

    wa = wt.RECT()
    user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(wa), 0)
    x = wa.right - W - sc(24)
    y = wa.bottom - H - sc(24)

    hwnd = user32.CreateWindowExW(
        WS_EX_TOPMOST | WS_EX_APPWINDOW,
        cls_name.value, APP_NAME,
        WS_POPUP | WS_VISIBLE,
        x, y, W, H,
        None, None, hinst, None,
    )
    if not hwnd:
        return

    # 圆角：Win11 交给系统处理，旧系统用窗口区域裁剪
    rounded = False
    try:
        dwm = ctypes.WinDLL("dwmapi")
        dwm.DwmSetWindowAttribute.argtypes = (wt.HWND, wt.DWORD, ctypes.c_void_p, wt.DWORD)
        pref = ctypes.c_int(2)  # DWMWCP_ROUND
        rounded = dwm.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(pref), 4) == 0
    except Exception:
        rounded = False
    if not rounded:
        gdi32.CreateRoundRectRgn.argtypes = (ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                             ctypes.c_int, ctypes.c_int, ctypes.c_int)
        gdi32.CreateRoundRectRgn.restype = wt.HRGN
        rgn = gdi32.CreateRoundRectRgn(0, 0, W + 1, H + 1, sc(14), sc(14))
        user32.SetWindowRgn(hwnd, rgn, True)

    user32.SetTimer(hwnd, TIMER_TICK, 1000, None)
    user32.SetTimer(hwnd, TIMER_KEYS, 70, None)

    if "--selftest" in sys.argv:
        user32.SetTimer(hwnd, 999, 15000, None)

    msg = MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        if msg.message == WM_TIMER and msg.wParam == 999:
            user32.DestroyWindow(hwnd)
            continue
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        try:
            log = os.path.join(base_dir(), "error.log")
            with open(log, "w", encoding="utf-8") as f:
                f.write("Reading Scroller {}\n\n".format(APP_VERSION))
                traceback.print_exc(file=f)
        except Exception:
            pass
