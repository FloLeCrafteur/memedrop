"""
Discord Overlay — app native Python/tkinter
Fenêtre transparente, always-on-top, click-through.
Reçoit les messages du bot via WebSocket et les affiche en overlay.

Dépendances  : pillow, websockets  (pip install pillow websockets)
OS supportés : Windows, macOS, Linux (X11)
"""

import asyncio
import json
import threading
import tkinter as tk
from tkinter import ttk
import time
import sys
import os
import io
import urllib.request
from PIL import Image, ImageTk, ImageDraw, ImageFont

import websockets

# ──────────────────────────────────────────────
#  CONFIG
# ──────────────────────────────────────────────
WS_URL          = "ws://localhost:8765"
OVERLAY_WIDTH   = 420          # largeur panneau (px)
MAX_TOASTS      = 5            # notifications simultanées max
TOAST_DURATION  = 7            # secondes avant disparition automatique
MARGIN          = 20           # marge bord écran
RECONNECT_DELAY = 3            # secondes entre tentatives de reconnexion

# Thème Discord Dark
BG_COLOR        = "#1e1f22"
BG_ALPHA        = 0.88         # transparence fenêtre (0-1)
ACCENT          = "#5865F2"    # bleu Discord
TEXT_MAIN       = "#dde1e7"
TEXT_SUB        = "#949ba4"
FONT_AUTHOR     = ("Segoe UI Semibold", 11) if sys.platform == "win32" else ("Helvetica", 11, "bold")
FONT_BODY       = ("Segoe UI", 10)          if sys.platform == "win32" else ("Helvetica", 10)
FONT_TIME       = ("Segoe UI", 8)           if sys.platform == "win32" else ("Helvetica", 8)
# ──────────────────────────────────────────────


def fetch_image_bytes(url: str, timeout: int = 5) -> bytes | None:
    """Télécharge une URL et retourne les bytes, ou None en cas d'erreur."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "DiscordOverlay/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except Exception:
        return None


def make_circle_avatar(img: Image.Image, size: int = 36) -> ImageTk.PhotoImage:
    """Découpe une image en cercle pour l'avatar."""
    img = img.resize((size, size), Image.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, size, size), fill=255)
    result = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    result.paste(img.convert("RGBA"), mask=mask)
    return ImageTk.PhotoImage(result)


class Toast(tk.Frame):
    """Un seul toast = une notification de message Discord."""

    def __init__(self, parent, payload: dict, on_close, **kwargs):
        super().__init__(parent, bg=BG_COLOR, **kwargs)
        self.on_close = on_close
        self._photo_refs = []   # garde les PhotoImage en vie
        self._build(payload)
        self._schedule_close()

    # ── construction UI ───────────────────────────────────────────────
    def _build(self, p: dict):
        self.configure(bd=0, relief="flat",
                        highlightthickness=1,
                        highlightbackground=ACCENT)

        # ── ligne du haut : avatar + auteur + timestamp ──
        top = tk.Frame(self, bg=BG_COLOR)
        top.pack(fill="x", padx=10, pady=(8, 4))

        # Avatar (chargé dans un thread séparé)
        self._avatar_label = tk.Label(top, bg=BG_COLOR)
        self._avatar_label.pack(side="left", padx=(0, 8))
        self._load_avatar_async(p.get("avatar", ""))

        # Nom + heure
        info = tk.Frame(top, bg=BG_COLOR)
        info.pack(side="left", fill="x", expand=True)
        tk.Label(info, text=p.get("author", "Inconnu"),
                 font=FONT_AUTHOR, fg=ACCENT, bg=BG_COLOR,
                 anchor="w").pack(fill="x")
        ts = p.get("timestamp", "")
        if ts:
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(ts)
                ts = dt.strftime("%H:%M")
            except Exception:
                pass
        tk.Label(info, text=ts, font=FONT_TIME, fg=TEXT_SUB,
                 bg=BG_COLOR, anchor="w").pack(fill="x")

        # Bouton ×
        close_btn = tk.Label(top, text="×", font=("Segoe UI", 14),
                             fg=TEXT_SUB, bg=BG_COLOR, cursor="hand2")
        close_btn.pack(side="right")
        close_btn.bind("<Button-1>", lambda _: self._close())

        # ── corps texte ──────────────────────────────────────────────
        content = p.get("content", "").strip()
        if content:
            tk.Label(self, text=content, font=FONT_BODY, fg=TEXT_MAIN,
                     bg=BG_COLOR, wraplength=OVERLAY_WIDTH - 40,
                     justify="left", anchor="w").pack(
                fill="x", padx=14, pady=(0, 6))

        # ── pièces jointes ───────────────────────────────────────────
        for att in p.get("attachments", []):
            self._add_attachment(att)

        # barre de progression (durée du toast)
        self._progress = tk.Frame(self, bg=ACCENT, height=2)
        self._progress.pack(fill="x", side="bottom")
        self._animate_progress()

    def _add_attachment(self, att: dict):
        kind = att.get("kind", "file")
        url  = att.get("url", "")
        name = att.get("filename", "fichier")

        if kind == "image":
            # Charger l'image dans un thread
            frame = tk.Frame(self, bg=BG_COLOR)
            frame.pack(fill="x", padx=10, pady=4)
            lbl = tk.Label(frame, text=f"🖼  Chargement…", fg=TEXT_SUB,
                           bg=BG_COLOR, font=FONT_BODY)
            lbl.pack(anchor="w")
            threading.Thread(target=self._load_image,
                             args=(url, lbl, frame), daemon=True).start()

        elif kind == "video":
            lbl = tk.Label(self, text=f"🎬  {name}  (vidéo)",
                           fg=TEXT_SUB, bg=BG_COLOR, font=FONT_BODY,
                           cursor="hand2")
            lbl.pack(anchor="w", padx=14, pady=2)
            lbl.bind("<Button-1>", lambda _, u=url: self._open_url(u))

        elif kind == "audio":
            row = tk.Frame(self, bg=BG_COLOR)
            row.pack(fill="x", padx=14, pady=4)
            tk.Label(row, text="🎵", bg=BG_COLOR, font=("Segoe UI", 18)).pack(side="left")
            tk.Label(row, text=name, fg=TEXT_MAIN, bg=BG_COLOR,
                     font=FONT_BODY).pack(side="left", padx=6)
            play_btn = tk.Label(row, text="▶ Ouvrir", fg=ACCENT,
                                bg=BG_COLOR, font=FONT_BODY, cursor="hand2")
            play_btn.pack(side="right")
            play_btn.bind("<Button-1>", lambda _, u=url: self._open_url(u))

        else:
            lbl = tk.Label(self, text=f"📎  {name}",
                           fg=TEXT_SUB, bg=BG_COLOR, font=FONT_BODY,
                           cursor="hand2")
            lbl.pack(anchor="w", padx=14, pady=2)
            lbl.bind("<Button-1>", lambda _, u=url: self._open_url(u))

    # ── chargements async ─────────────────────────────────────────────
    def _load_avatar_async(self, url: str):
        threading.Thread(target=self._fetch_avatar, args=(url,),
                         daemon=True).start()

    def _fetch_avatar(self, url: str):
        data = fetch_image_bytes(url)
        if not data:
            return
        try:
            img = Image.open(io.BytesIO(data))
            photo = make_circle_avatar(img, 36)
            self._photo_refs.append(photo)
            self._avatar_label.after(0, lambda: self._avatar_label.configure(image=photo))
        except Exception:
            pass

    def _load_image(self, url: str, placeholder: tk.Label, frame: tk.Frame):
        data = fetch_image_bytes(url)
        if not data:
            placeholder.after(0, lambda: placeholder.configure(text="❌ Image indisponible"))
            return
        try:
            img = Image.open(io.BytesIO(data))
            max_w = OVERLAY_WIDTH - 40
            ratio = max_w / img.width if img.width > max_w else 1
            new_size = (int(img.width * ratio), int(img.height * ratio))
            img = img.resize(new_size, Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            self._photo_refs.append(photo)
            def _show():
                placeholder.destroy()
                lbl = tk.Label(frame, image=photo, bg=BG_COLOR, cursor="hand2")
                lbl.pack(anchor="w")
                lbl.bind("<Button-1>", lambda _, u=url: self._open_url(u))
            frame.after(0, _show)
        except Exception as e:
            placeholder.after(0, lambda: placeholder.configure(text=f"❌ Erreur image"))

    # ── helpers ───────────────────────────────────────────────────────
    @staticmethod
    def _open_url(url: str):
        import webbrowser
        webbrowser.open(url)

    def _animate_progress(self):
        start = time.time()
        total = TOAST_DURATION * 1000  # ms

        def _step():
            elapsed = (time.time() - start) * 1000
            pct = max(0.0, 1.0 - elapsed / total)
            try:
                w = int((OVERLAY_WIDTH - 2) * pct)
                self._progress.configure(width=w)
            except tk.TclError:
                return
            if pct > 0:
                self.after(50, _step)
        _step()

    def _schedule_close(self):
        self.after(int(TOAST_DURATION * 1000), self._close)

    def _close(self):
        try:
            self.destroy()
        except tk.TclError:
            pass
        self.on_close(self)


# ─────────────────────────────────────────────────────────────────────
class OverlayApp:
    """Fenêtre principale transparente, always-on-top, click-through."""

    def __init__(self):
        self.root = tk.Tk()
        self._toasts: list[Toast] = []
        self._setup_window()
        self._setup_ws_thread()

    def _setup_window(self):
        root = self.root
        root.title("Discord Overlay")
        root.overrideredirect(True)   # pas de barre de titre
        root.attributes("-topmost", True)
        root.attributes("-alpha", BG_ALPHA)
        root.configure(bg=BG_COLOR)

        # Positionner en bas à droite
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        root.geometry(f"{OVERLAY_WIDTH}x1+{sw - OVERLAY_WIDTH - MARGIN}+{sh - 100}")

        # Click-through selon OS
        if sys.platform == "win32":
            import ctypes
            root.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
            style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
            ctypes.windll.user32.SetWindowLongW(hwnd, -20, style | 0x80000 | 0x20)
        elif sys.platform == "darwin":
            # macOS : niveau de fenêtre flottant
            root.attributes("-type", "dock")
        # Linux X11 : pas de click-through natif sans libs C, on passe

        root.resizable(False, False)

    # ── WebSocket ─────────────────────────────────────────────────────
    def _setup_ws_thread(self):
        self._loop = asyncio.new_event_loop()
        t = threading.Thread(target=self._run_ws_loop, daemon=True)
        t.start()

    def _run_ws_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._ws_listener())

    async def _ws_listener(self):
        while True:
            try:
                async with websockets.connect(WS_URL) as ws:
                    print(f"[Overlay] Connecté au bot sur {WS_URL}")
                    async for raw in ws:
                        try:
                            payload = json.loads(raw)
                            self.root.after(0, lambda p=payload: self._show_toast(p))
                        except json.JSONDecodeError:
                            pass
            except Exception as e:
                print(f"[Overlay] Déconnecté ({e}), reconnexion dans {RECONNECT_DELAY}s…")
                await asyncio.sleep(RECONNECT_DELAY)

    # ── Affichage des toasts ──────────────────────────────────────────
    def _show_toast(self, payload: dict):
        # Supprimer le plus ancien si on dépasse MAX_TOASTS
        if len(self._toasts) >= MAX_TOASTS:
            oldest = self._toasts[0]
            oldest._close()

        toast = Toast(self.root, payload, on_close=self._remove_toast)
        self._toasts.append(toast)
        self._reflow()

    def _remove_toast(self, toast: Toast):
        if toast in self._toasts:
            self._toasts.remove(toast)
        self._reflow()

    def _reflow(self):
        """Repositionne tous les toasts du bas vers le haut."""
        sw  = self.root.winfo_screenwidth()
        sh  = self.root.winfo_screenheight()
        y   = sh - MARGIN
        for toast in reversed(self._toasts):
            toast.update_idletasks()
            h = toast.winfo_reqheight()
            y -= h + 8
            toast.place(x=0, y=y, width=OVERLAY_WIDTH)

        # Redimensionner la fenêtre racine pour couvrir tous les toasts
        if self._toasts:
            total_h = sh - MARGIN - y + 10
            x = sw - OVERLAY_WIDTH - MARGIN
            self.root.geometry(f"{OVERLAY_WIDTH}x{total_h}+{x}+{y - 10}")
        else:
            self.root.geometry(f"{OVERLAY_WIDTH}x1")

    def run(self):
        print("[Overlay] Démarrage…")
        self.root.mainloop()


# ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = OverlayApp()
    app.run()
