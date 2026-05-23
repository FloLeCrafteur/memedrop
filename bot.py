"""
Discord Overlay Bot - Version Stable pour Railway
Lit un salon Discord et diffuse via WebSocket sécurisé.
"""

import discord
import asyncio
import websockets
import json
import os
from datetime import datetime

# ─────────────────────────────────────────────
#  CONFIG — Via variables d'environnement sur Railway
# ─────────────────────────────────────────────
# Sur Railway, configurez ces variables dans l'onglet "Variables"
BOT_TOKEN  = os.environ.get("TOKEN", "VOTRE_TOKEN_LOCAL_SI_TEST")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", 1507734070535258154))
PORT       = int(os.environ.get("PORT", 8765)) # Railway fournit le port automatiquement
# ─────────────────────────────────────────────

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# Liste des overlays connectés (vos amis)
connected_clients = set()

async def broadcast(payload: dict):
    """Envoie le message à tous les amis connectés en même temps."""
    if not connected_clients:
        return
    data = json.dumps(payload, ensure_ascii=False)
    # asyncio.gather envoie à tout le monde en parallèle
    await asyncio.gather(
        *[ws.send(data) for ws in connected_clients],
        return_exceptions=True,
    )

async def ws_handler(websocket):
    """Gère la connexion de l'overlay d'un ami."""
    connected_clients.add(websocket)
    print(f"[WS] Un ami s'est connecté. Total : {len(connected_clients)}")
    try:
        # Attend que le client se déconnecte, sans bloquer
        await websocket.wait_closed()
    finally:
        connected_clients.discard(websocket)
        print(f"[WS] Un ami s'est déconnecté. Restants : {len(connected_clients)}")

@client.event
async def on_ready():
    ch = client.get_channel(CHANNEL_ID)
    name = ch.name if ch else "introuvable"
    print(f"[Discord] Bot en ligne : {client.user}")
    print(f"[Discord] Surveillance du salon : #{name} ({CHANNEL_ID})")

@client.event
async def on_message(message: discord.Message):
    if message.channel.id != CHANNEL_ID or message.author == client.user:
        return

    attachments = []
    for att in message.attachments:
        mime = att.content_type or ""
        if mime.startswith("image/"):
            kind = "image"
        elif mime.startswith("video/"):
            kind = "video"
        elif mime.startswith("audio/"):
            kind = "audio"
        else:
            kind = "file"
        
        attachments.append({
            "url": att.url,
            "filename": att.filename,
            "kind": kind
        })

    payload = {
        "id": str(message.id),
        "author": message.author.display_name,
        "avatar": str(message.author.display_avatar.url),
        "content": message.content,
        "timestamp": datetime.utcnow().isoformat(),
        "attachments": attachments,
    }

    print(f"[Discord] Nouveau message de {payload['author']}")
    await broadcast(payload)

async def main():
    # ping_interval=20 et ping_timeout=20 empêchent Railway de couper la connexion
    async with websockets.serve(ws_handler, "0.0.0.0", PORT, ping_interval=20, ping_timeout=20):
        print(f"[WS] Serveur WebSocket prêt sur le port {PORT}")
        await client.start(BOT_TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Arrêt du bot.")