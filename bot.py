"""
Discord Overlay Bot
Lit un salon Discord et diffuse les messages via WebSocket vers l'overlay desktop.
"""

import discord
import asyncio
import websockets
import json
import os
from datetime import datetime

# ─────────────────────────────────────────────
#  CONFIG — modifier ces valeurs
# ─────────────────────────────────────────────
BOT_TOKEN      = "TOKEN"          # Token du bot Discord
CHANNEL_ID     = 1507734070535258154        # ID du salon à surveiller (int)
WS_HOST        = "ws://memedrop-production-80af.up.railway.app"
WS_PORT        = 8765
# ─────────────────────────────────────────────

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# Ensemble des clients WebSocket connectés
connected_clients: set = set()


async def broadcast(payload: dict):
    """Envoie le message à tous les clients overlay connectés."""
    if not connected_clients:
        return
    data = json.dumps(payload, ensure_ascii=False)
    await asyncio.gather(
        *[ws.send(data) for ws in connected_clients],
        return_exceptions=True,
    )


async def ws_handler(websocket):
    """Gère une connexion WebSocket entrante (depuis l'overlay)."""
    connected_clients.add(websocket)
    print(f"[WS] Client connecté ({len(connected_clients)} total)")
    try:
        await websocket.wait_closed()
    finally:
        connected_clients.discard(websocket)
        print(f"[WS] Client déconnecté ({len(connected_clients)} restants)")


@client.event
async def on_ready():
    ch = client.get_channel(CHANNEL_ID)
    name = ch.name if ch else "introuvable"
    print(f"[Discord] Connecté en tant que {client.user}")
    print(f"[Discord] Surveillance du salon : #{name} ({CHANNEL_ID})")


@client.event
async def on_message(message: discord.Message):
    # Filtrer uniquement le salon configuré
    if message.channel.id != CHANNEL_ID:
        return
    # Ignorer les messages du bot lui-même
    if message.author == client.user:
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
            "url":      att.url,
            "filename": att.filename,
            "kind":     kind,
            "size":     att.size,
        })

    payload = {
        "id":          str(message.id),
        "author":      message.author.display_name,
        "avatar":      str(message.author.display_avatar.url),
        "content":     message.content,
        "timestamp":   datetime.utcnow().isoformat(),
        "attachments": attachments,
    }

    print(f"[Discord] Message de {payload['author']}: {payload['content'][:60]}")
    await broadcast(payload)


async def main():
    # Railway injecte automatiquement le port dans la variable d'environnement PORT
    # Si on est en local (et que PORT n'existe pas), on garde 8765 par défaut
    port = int(os.environ.get("PORT", 8765))
    
    # On écoute sur "0.0.0.0" pour accepter les connexions externes sur Railway
    async with websockets.serve(ws_handler, "0.0.0.0", port):
        print(f"[WS] Serveur démarré sur le port {port}")
        await client.start(BOT_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
