"""
Discord Overlay Client - Version Webview
Supporte GIFs, Vidéos, Sons et reconnexion automatique.
"""

import asyncio
import json
import threading
import webview
import sys

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────
# REMPLACEZ par l'adresse générée par Railway (ex: "wss://mon-bot.up.railway.app")
WS_URL = "wss://memedrop-production-80af.up.railway.app" 
# ─────────────────────────────────────────────

HTML_CONTENT = """
<!DOCTYPE html>
<html>
<head>
    <style>
        body {
            font-family: 'Segoe UI', Helvetica, Arial, sans-serif;
            margin: 0;
            padding: 10px;
            overflow: hidden;
            background-color: rgba(0, 0, 0, 0); /* Fenêtre transparente */
            display: flex;
            flex-direction: column;
            justify-content: flex-end;
            height: 100vh;
            box-sizing: border-box;
        }
        .toast {
            background: rgba(30, 31, 34, 0.95);
            border: 1px solid #5865F2;
            border-radius: 8px;
            color: #dde1e7;
            padding: 12px;
            margin-top: 8px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.6);
            animation: slideIn 0.3s cubic-bezier(0.18, 0.89, 0.32, 1.28) forwards;
            max-width: 380px;
            position: relative;
        }
        @keyframes slideIn {
            from { transform: translateX(110%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        @keyframes slideOut {
            from { transform: translateX(0); opacity: 1; }
            to { transform: translateX(110%); opacity: 0; }
        }
        .header { display: flex; align-items: center; margin-bottom: 6px; }
        .avatar { width: 36px; height: 36px; border-radius: 50%; margin-right: 10px; border: 1px solid #2b2d31; }
        .author { color: #5865F2; font-weight: bold; font-size: 14px; }
        .content { font-size: 13px; word-break: break-word; line-height: 1.4; color: #dbdee1; }
        .media { max-width: 100%; max-height: 180px; border-radius: 4px; margin-top: 8px; display: block; }
        .progress-bar {
            position: absolute; bottom: 0; left: 0; height: 3px; background: #5865F2; width: 100%;
            animation: shrink 7s linear forwards; border-bottom-left-radius: 8px; border-bottom-right-radius: 8px;
        }
        @keyframes shrink { from { width: 100%; } to { width: 0%; } }
    </style>
</head>
<body>
    <div id="container"></div>

    <script>
        const container = document.getElementById('container');

        function createToast(data) {
            // Limiter à 4 notifications max à l'écran pour éviter d'envahir l'espace
            if (container.children.length >= 4) {
                container.children[0].remove();
            }

            const toast = document.createElement('div');
            toast.className = 'toast';

            let mediaHtml = '';
            if (data.attachments && data.attachments.length > 0) {
                const att = data.attachments[0];
                if (att.kind === 'image') {
                    // Les GIFs fonctionnent nativement ici !
                    mediaHtml = `<img class="media" src="${att.url}">`;
                } else if (att.kind === 'video') {
                    // Vidéo avec son activé (autoplay)
                    mediaHtml = `<video class="media" src="${att.url}" autoplay controls></video>`;
                } else if (att.kind === 'audio') {
                    mediaHtml = `<audio class="media" src="${att.url}" autoplay controls style="width:100%; height:30px;"></audio>`;
                }
            }

            toast.innerHTML = `
                <div class="header">
                    <img class="avatar" src="${data.avatar || 'https://discord.com/assets/c09a1f2c4bfac614e857.png'}">
                    <span class="author">${data.author}</span>
                </div>
                <div class="content">${data.content}</div>
                ${mediaHtml}
                <div class="progress-bar"></div>
            `;

            container.appendChild(toast);

            // Disparition automatique après 7 secondes
            setTimeout(() => {
                toast.style.animation = 'slideOut 0.3s ease forwards';
                setTimeout(() => { toast.remove(); }, 300);
            }, 7000);
        }
    </script>
</body>
</html>
"""

async def ws_listener(window):
    """Écoute le serveur Railway en continu avec reconnexion automatique."""
    while True:
        try:
            print(f"[Overlay] Connexion à {WS_URL}...")
            async with websockets.connect(WS_URL, ping_interval=20, ping_timeout=20) as ws:
                print("[Overlay] Connecté avec succès ! En attente de messages...")
                async for raw in ws:
                    try:
                        payload = json.loads(raw)
                        # Injecte le message directement dans la fenêtre Web
                        window.evaluate_js(f"createToast({json.dumps(payload)})")
                    except Exception as e:
                        print(f"Erreur traitement message: {e}")
        except Exception as e:
            print(f"[Overlay] Déconnecté ou serveur inaccessible. Réémission dans 4s... ({e})")
            await asyncio.sleep(4)

def start_ws_thread(window):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(ws_listener(window))

if __name__ == "__main__":
    # Configuration de la fenêtre transparente
    window = webview.create_window(
        'Discord Overlay Client',
        html=HTML_CONTENT,
        transparent=True,
        on_top=True,      # Reste au-dessus des jeux / fenêtres
        frameless=True,   # Pas de bordures Windows
        width=400,
        height=700
    )

    # Lancement du thread de communication en arrière-plan
    threading.Thread(target=start_ws_thread, args=(window,), daemon=True).start()

    # Positionne automatiquement la fenêtre en bas à droite de l'écran principal
    # (easy_drag=False empêche l'utilisateur de déplacer la zone transparente par erreur)
    webview.start(easy_drag=False)