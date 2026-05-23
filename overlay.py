"""
Discord Overlay — app native Python/tkinter
Fenêtre transparente, always-on-top, click-through.

Dépendances : pillow websockets
  pip install pillow websockets
"""

import asyncio, json, threading, time, sys, io, urllib.request, webbrowser
import tkinter as tk
from PIL import Image, ImageTk, ImageDraw

# ─── CONFIG ────────────────────────────────────────────────────────────────────
WS_URL          = "ws://memedrop-production-80af.up.railway.app"
OVERLAY_WIDTH   = 400
MAX_TOASTS      = 5
TOAST_DURATION  = 7          # secondes
MARGIN_RIGHT    = 20
MARGIN_BOTTOM   = 40
GAP             = 8
RECONNECT_DELAY = 3

BG_COLOR   = "#1e1f22"
BG_ALPHA   = 0.92
ACCENT     = "#5865F2"
TEXT_MAIN  = "#dde1e7"
TEXT_SUB   = "#949ba4"

if sys.platform == "win32":
    F_AUTHOR = ("Segoe UI", 11, "bold")
    F_BODY   = ("Segoe UI", 10)
    F_TIME   = ("Segoe UI", 8)
    F_CLOSE  = ("Segoe UI", 13, "bold")
else:
    F_AUTHOR = ("Helvetica", 11, "bold")
    F_BODY   = ("Helvetica", 10)
    F_TIME   = ("Helvetica", 8)
    F_CLOSE  = ("Helvetica", 13, "bold")
# ───────────────────────────────────────────────────────────────────────────────


def fetch_bytes(url, timeout=6):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "DiscordOverlay/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except Exception:
        return None


def circle_avatar(data: bytes, size=36) -> ImageTk.PhotoImage:
    img = Image.open(io.BytesIO(data)).convert("RGBA").resize((size, size), Image.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(img, mask=mask)
    return ImageTk.PhotoImage(out)


# ─── TOAST ─────────────────────────────────────────────────────────────────────
class Toast(tk.Frame):
    def __init__(self, parent, payload: dict, on_close):
        super().__init__(parent, bg=BG_COLOR,
                         highlightthickness=1, highlightbackground=ACCENT)
        self._refs    = []
        self._closed  = False
        self.on_close = on_close
        self._build(payload)
        # forcer le calcul de taille AVANT que reflow soit appelé
        self.update_idletasks()
        self.after(int(TOAST_DURATION * 1000), self._close)

    # ── construction ──────────────────────────────────────────────────────────
    def _build(self, p):
        pad = dict(padx=12)

        # ── EN-TÊTE ──
        header = tk.Frame(self, bg=BG_COLOR)
        header.pack(fill="x", **pad, pady=(10, 4))

        # placeholder avatar
        self._av_lbl = tk.Label(header, bg=BG_COLOR, width=2)
        self._av_lbl.pack(side="left", padx=(0, 8))
        threading.Thread(target=self._load_avatar, args=(p.get("avatar",""),), daemon=True).start()

        # auteur + heure
        col = tk.Frame(header, bg=BG_COLOR)
        col.pack(side="left", fill="x", expand=True)

        author = p.get("author") or "Inconnu"
        tk.Label(col, text=author, font=F_AUTHOR, fg=ACCENT,
                 bg=BG_COLOR, anchor="w").pack(fill="x")

        ts = p.get("timestamp", "")
        try:
            from datetime import datetime
            ts = datetime.fromisoformat(ts).strftime("%H:%M")
        except Exception:
            pass
        tk.Label(col, text=ts, font=F_TIME, fg=TEXT_SUB,
                 bg=BG_COLOR, anchor="w").pack(fill="x")

        # bouton ×
        x_btn = tk.Label(header, text="✕", font=F_CLOSE, fg=TEXT_SUB,
                         bg=BG_COLOR, cursor="hand2")
        x_btn.pack(side="right", padx=(4, 0))
        x_btn.bind("<Button-1>", lambda _e: self._close())

        # ── TEXTE ──
        content = (p.get("content") or "").strip()
        if content:
            tk.Label(self, text=content, font=F_BODY, fg=TEXT_MAIN,
                     bg=BG_COLOR, anchor="w", justify="left",
                     wraplength=OVERLAY_WIDTH - 32).pack(
                fill="x", **pad, pady=(0, 8))

        # ── PIÈCES JOINTES ──
        for att in p.get("attachments", []):
            self._add_att(att, pad)

        # ── BARRE PROGRESSION ──
        bar_bg = tk.Frame(self, bg="#2b2d31", height=3)
        bar_bg.pack(fill="x", side="bottom")
        self._bar = tk.Frame(bar_bg, bg=ACCENT, height=3)
        self._bar.place(relx=0, rely=0, relwidth=1.0, relheight=1.0)
        self._bar_start = time.time()
        self._tick_bar()

    def _add_att(self, att, pad):
        kind = att.get("kind","file")
        url  = att.get("url","")
        name = att.get("filename","fichier")

        if kind == "image":
            frm = tk.Frame(self, bg=BG_COLOR)
            frm.pack(fill="x", **pad, pady=(0, 6))
            ph  = tk.Label(frm, text="⏳ Chargement image…", font=F_BODY,
                           fg=TEXT_SUB, bg=BG_COLOR, anchor="w")
            ph.pack(fill="x")
            threading.Thread(target=self._load_img, args=(url, ph, frm), daemon=True).start()

        elif kind == "video":
            lbl = tk.Label(self, text=f"🎬  {name}", font=F_BODY,
                           fg=TEXT_SUB, bg=BG_COLOR, cursor="hand2", anchor="w")
            lbl.pack(fill="x", **pad, pady=(0, 4))
            lbl.bind("<Button-1>", lambda _e, u=url: webbrowser.open(u))

        elif kind == "audio":
            row = tk.Frame(self, bg=BG_COLOR)
            row.pack(fill="x", **pad, pady=(0, 4))
            tk.Label(row, text="🎵", font=("Segoe UI", 16) if sys.platform=="win32" else ("Helvetica",16),
                     bg=BG_COLOR).pack(side="left")
            tk.Label(row, text=name, font=F_BODY, fg=TEXT_MAIN,
                     bg=BG_COLOR).pack(side="left", padx=6)
            btn = tk.Label(row, text="▶ Ouvrir", font=F_BODY,
                           fg=ACCENT, bg=BG_COLOR, cursor="hand2")
            btn.pack(side="right")
            btn.bind("<Button-1>", lambda _e, u=url: webbrowser.open(u))

        else:
            lbl = tk.Label(self, text=f"📎  {name}", font=F_BODY,
                           fg=TEXT_SUB, bg=BG_COLOR, cursor="hand2", anchor="w")
            lbl.pack(fill="x", **pad, pady=(0, 4))
            lbl.bind("<Button-1>", lambda _e, u=url: webbrowser.open(u))

    # ── chargements réseau ────────────────────────────────────────────────────
    def _load_avatar(self, url):
        if not url:
            return
        data = fetch_bytes(url)
        if not data:
            return
        try:
            photo = circle_avatar(data, 36)
            self._refs.append(photo)
            self._av_lbl.after(0, lambda: self._av_lbl.configure(image=photo))
        except Exception:
            pass

    def _load_img(self, url, ph: tk.Label, frm: tk.Frame):
        data = fetch_bytes(url)
        if not data:
            ph.after(0, lambda: ph.configure(text="❌ Image indisponible"))
            return
        try:
            img   = Image.open(io.BytesIO(data))
            max_w = OVERLAY_WIDTH - 32
            if img.width > max_w:
                img = img.resize((max_w, int(img.height * max_w / img.width)), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            self._refs.append(photo)
            def _show():
                ph.destroy()
                lbl = tk.Label(frm, image=photo, bg=BG_COLOR, cursor="hand2")
                lbl.pack(anchor="w")
                lbl.bind("<Button-1>", lambda _e, u=url: webbrowser.open(u))
                # redéclencher un reflow pour intégrer la nouvelle hauteur
                self.event_generate("<<ToastResized>>")
            frm.after(0, _show)
        except Exception:
            ph.after(0, lambda: ph.configure(text="❌ Erreur image"))

    # ── barre de progression ──────────────────────────────────────────────────
    def _tick_bar(self):
        if self._closed:
            return
        elapsed = time.time() - self._bar_start
        pct     = max(0.0, 1.0 - elapsed / TOAST_DURATION)
        try:
            self._bar.place(relwidth=pct)
        except tk.TclError:
            return
        if pct > 0:
            self.after(50, self._tick_bar)

    # ── fermeture ─────────────────────────────────────────────────────────────
    def _close(self):
        if self._closed:
            return
        self._closed = True
        try:
            self.destroy()
        except tk.TclError:
            pass
        self.on_close(self)


# ─── OVERLAY APP ───────────────────────────────────────────────────────────────
class OverlayApp:
    def __init__(self):
        self.root   = tk.Tk()
        self._toasts: list[Toast] = []
        self._setup_window()
        self._setup_ws_thread()

    def _setup_window(self):
        r = self.root
        r.title("Discord Overlay")
        r.overrideredirect(True)
        r.attributes("-topmost", True)
        r.attributes("-alpha", BG_ALPHA)
        r.configure(bg=BG_COLOR)
        r.resizable(False, False)

        sw, sh = r.winfo_screenwidth(), r.winfo_screenheight()
        # fenêtre initiale 1px invisible en bas à droite
        r.geometry(f"1x1+{sw - OVERLAY_WIDTH - MARGIN_RIGHT}+{sh - 2}")

        # click-through Windows
        if sys.platform == "win32":
            try:
                import ctypes
                r.update_idletasks()
                hwnd  = ctypes.windll.user32.GetParent(r.winfo_id())
                style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
                ctypes.windll.user32.SetWindowLongW(hwnd, -20, style | 0x80000 | 0x20)
            except Exception as e:
                print(f"[click-through] {e}")
        elif sys.platform == "darwin":
            try:
                r.attributes("-transparent", True)
            except Exception:
                pass

    # ── WebSocket ──────────────────────────────────────────────────────────────
    def _setup_ws_thread(self):
        self._loop = asyncio.new_event_loop()
        threading.Thread(target=self._run_ws, daemon=True).start()

    def _run_ws(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._ws_listener())

    async def _ws_listener(self):
        while True:
            try:
                async with websockets.connect(WS_URL) as ws:
                    print(f"[Overlay] Connecté → {WS_URL}")
                    async for raw in ws:
                        try:
                            p = json.loads(raw)
                            self.root.after(0, lambda payload=p: self._show_toast(payload))
                        except json.JSONDecodeError:
                            pass
            except Exception as e:
                print(f"[Overlay] ✗ {e}  — reconnexion dans {RECONNECT_DELAY}s")
                await asyncio.sleep(RECONNECT_DELAY)

    # ── toasts ─────────────────────────────────────────────────────────────────
    def _show_toast(self, payload):
        if len(self._toasts) >= MAX_TOASTS:
            self._toasts[0]._close()

        t = Toast(self.root, payload, on_close=self._remove_toast)
        # écouter les redimensionnements (image chargée a posteriori)
        t.bind("<<ToastResized>>", lambda _e: self._reflow())
        self._toasts.append(t)
        self._reflow()

    def _remove_toast(self, toast):
        if toast in self._toasts:
            self._toasts.remove(toast)
        self._reflow()

    def _reflow(self):
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()

        if not self._toasts:
            self.root.geometry(f"1x1+{sw}+{sh}")
            return

        # calculer la hauteur totale nécessaire
        heights = []
        for t in self._toasts:
            t.update_idletasks()
            h = t.winfo_reqheight()
            heights.append(max(h, 60))   # plancher 60px au cas où

        total_h = sum(heights) + GAP * (len(heights) - 1)

        win_x = sw - OVERLAY_WIDTH - MARGIN_RIGHT
        win_y = sh - MARGIN_BOTTOM - total_h

        self.root.geometry(f"{OVERLAY_WIDTH}x{total_h}+{win_x}+{win_y}")

        # placer chaque toast dans la fenêtre
        y = 0
        for t, h in zip(self._toasts, heights):
            t.place(x=0, y=y, width=OVERLAY_WIDTH, height=h)
            y += h + GAP

    def run(self):
        import websockets as _ws   # import tardif pour valider
        print("[Overlay] Démarrage — en attente de messages…")
        self.root.mainloop()


# ───────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import websockets
    app = OverlayApp()
    app.run()