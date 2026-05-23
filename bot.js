const { Client, GatewayIntentBits } = require("discord.js");
const WebSocket = require("ws");
const http = require("http");
const fs = require("fs");
const path = require("path");

// ─── CONFIG ─────────────────────────────────────────────────────────────────
const DISCORD_TOKEN = process.env.DISCORD_TOKEN || "TON_TOKEN_ICI";
const CHANNEL_ID = process.env.CHANNEL_ID || "1507734070535258154";
const WS_PORT = process.env.WS_PORT || 8765;
const HTTP_PORT = process.env.HTTP_PORT || 8766;
// ────────────────────────────────────────────────────────────────────────────

// Serveur HTTP pour servir l'app display
const httpServer = http.createServer((req, res) => {
  const displayPath = path.join(__dirname, "../display/index.html");
  if (req.url === "/" || req.url === "/index.html") {
    fs.readFile(displayPath, (err, data) => {
      if (err) {
        res.writeHead(404);
        res.end("Display app not found. Place index.html in /display/");
        return;
      }
      res.writeHead(200, { "Content-Type": "text/html" });
      res.end(data);
    });
  } else {
    res.writeHead(404);
    res.end("Not found");
  }
});

httpServer.listen(HTTP_PORT, () => {
  console.log(`📺 Display app accessible sur http://localhost:${HTTP_PORT}`);
});

// Serveur WebSocket
const wss = new WebSocket.Server({ server: httpServer });
const clients = new Set();

wss.on("connection", (ws) => {
  clients.add(ws);
  console.log(`✅ Nouveau client connecté (${clients.size} total)`);

  ws.on("close", () => {
    clients.delete(ws);
    console.log(`❌ Client déconnecté (${clients.size} restants)`);
  });
});

function broadcast(data) {
  const payload = JSON.stringify(data);
  clients.forEach((client) => {
    if (client.readyState === WebSocket.OPEN) {
      client.send(payload);
    }
  });
  console.log(`📡 Diffusé à ${clients.size} client(s)`);
}

// Bot Discord
const discord = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMessages,
    GatewayIntentBits.MessageContent,
  ],
});

discord.once("ready", () => {
  console.log(`🤖 Bot connecté en tant que ${discord.user.tag}`);
  console.log(`👂 Écoute du salon: ${CHANNEL_ID}`);
});

discord.on("messageCreate", async (message) => {
  // Ignorer les bots et les autres salons
  if (message.bot) return;
  if (message.channel.id !== CHANNEL_ID) return;

  const payload = {
    type: "notification",
    author: message.author.username,
    avatar: message.author.displayAvatarURL({ size: 128 }),
    text: message.content || "",
    images: [],
    timestamp: Date.now(),
  };

  // Récupérer les images attachées
  message.attachments.forEach((attachment) => {
    if (attachment.contentType?.startsWith("image/")) {
      payload.images.push(attachment.url);
    }
  });

  // Récupérer les images dans les embeds
  message.embeds.forEach((embed) => {
    if (embed.image?.url) payload.images.push(embed.image.url);
    if (embed.thumbnail?.url) payload.images.push(embed.thumbnail.url);
  });

  // Ignorer les messages vides (ni texte ni image)
  if (!payload.text && payload.images.length === 0) return;

  console.log(
    `📨 Message de ${payload.author}: "${payload.text}" (${payload.images.length} image(s))`
  );
  broadcast(payload);
});

discord.login(DISCORD_TOKEN).catch((err) => {
  console.error("❌ Impossible de se connecter à Discord:", err.message);
  process.exit(1);
});
