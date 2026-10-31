/**
 * SETS Open-Source Free WhatsApp HTTP API Bridge
 * Powered by @whiskeysockets/baileys (Open-Source Multi-Device WhatsApp Library)
 * Dispatches WhatsApp alerts to user-configured recipient numbers dynamically.
 *
 * Endpoints:
 *   GET  http://127.0.0.1:3001/        -> Web UI showing QR Code & Connection Status
 *   GET  http://127.0.0.1:3001/status  -> JSON status { connected, qrDataUrl }
 *   POST http://127.0.0.1:3001/send    -> { "phone": "+97150...", "message": "Hello..." }
 */

const http = require("http");
const fs = require("fs");
const path = require("path");
const pino = require("pino");
const QRCode = require("qrcode");
const {
  default: makeWASocket,
  useMultiFileAuthState,
  DisconnectReason,
  fetchLatestBaileysVersion,
} = require("@whiskeysockets/baileys");

const PORT = process.env.WA_BRIDGE_PORT || 3001;
const DEFAULT_NUMBER = process.env.DEFAULT_WA_RECIPIENT || "";
const AUTH_DIR = path.join(__dirname, "auth_info_baileys");

let sock = null;
let isConnected = false;
let latestQrDataUrl = "";
let connectedUser = null;

function formatJid(phone) {
  const digits = String(phone || DEFAULT_NUMBER).replace(/[^0-9]/g, "");
  if (!digits) return null;
  return `${digits}@s.whatsapp.net`;
}

async function startWhatsAppSocket() {
  fs.mkdirSync(AUTH_DIR, { recursive: true });
  const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
  const { version } = await fetchLatestBaileysVersion();

  sock = makeWASocket({
    version,
    logger: pino({ level: "silent" }),
    printQRInTerminal: true,
    auth: state,
  });

  sock.ev.on("creds.update", saveCreds);

  sock.ev.on("connection.update", async (update) => {
    const { connection, lastDisconnect, qr } = update;
    if (qr) {
      latestQrDataUrl = await QRCode.toDataURL(qr);
      console.log("[SETS WhatsApp Bridge] New QR Code generated. Open http://127.0.0.1:" + PORT + " to scan.");
    }
    if (connection === "close") {
      isConnected = false;
      const statusCode =
        lastDisconnect &&
        lastDisconnect.error &&
        lastDisconnect.error.output &&
        lastDisconnect.error.output.statusCode;
      const shouldReconnect = statusCode !== DisconnectReason.loggedOut;
      console.log("[SETS WhatsApp Bridge] Connection closed. Reconnecting:", shouldReconnect);
      if (shouldReconnect) {
        setTimeout(startWhatsAppSocket, 3000);
      }
    } else if (connection === "open") {
      isConnected = true;
      latestQrDataUrl = "";
      connectedUser = sock.user || { id: DEFAULT_NUMBER };
      console.log("[SETS WhatsApp Bridge] Connected! Ready to send alerts to " + DEFAULT_NUMBER);
    }
  });
}

const server = http.createServer(async (req, res) => {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");

  if (req.method === "OPTIONS") {
    res.writeHead(204);
    return res.end();
  }

  if (req.method === "GET" && req.url === "/status") {
    res.writeHead(200, { "Content-Type": "application/json" });
    return res.end(
      JSON.stringify({
        ok: true,
        connected: isConnected,
        user: connectedUser,
        default_recipient: DEFAULT_NUMBER,
        qr_data_url: latestQrDataUrl,
      })
    );
  }

  if (req.method === "GET" && req.url === "/") {
    res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
    return res.end(`
      <!DOCTYPE html>
      <html>
      <head>
        <title>SETS Open-Source WhatsApp Bridge</title>
        <meta http-equiv="refresh" content="6" />
        <style>
          body { font-family: system-ui, sans-serif; background: #0f172a; color: #f8fafc; text-align: center; padding: 40px; }
          .card { max-width: 480px; margin: 0 auto; background: #1e293b; padding: 28px; border-radius: 12px; border: 1px solid #334155; }
          .badge { display: inline-block; padding: 6px 14px; border-radius: 99px; font-weight: 700; background: ${isConnected ? "#10b981" : "#f59e0b"}; color: #052e16; }
          img { margin-top: 16px; border-radius: 8px; background: #fff; padding: 10px; }
        </style>
      </head>
      <body>
        <div class="card">
          <h2>SETS Open-Source WhatsApp Bridge</h2>
          <p><span class="badge">${isConnected ? "CONNECTED & READY" : "WAITING FOR QR SCAN"}</span></p>
          ${
            !isConnected && latestQrDataUrl
              ? `<p>Open WhatsApp on your phone &rarr; Linked Devices &rarr; Link a Device, and scan:</p><img src="${latestQrDataUrl}" width="260" />`
              : isConnected
              ? `<p style="color:#6ee7b7;">Your WhatsApp session is active! SETS AI Lead Watcher can now send instant free alerts to all user-configured team numbers.</p>`
              : `<p>Generating QR code... page refreshes automatically.</p>`
          }
        </div>
      </body>
      </html>
    `);
  }

  if (req.method === "POST" && req.url === "/send") {
    let body = "";
    req.on("data", (chunk) => (body += chunk));
    req.on("end", async () => {
      try {
        const data = JSON.parse(body || "{}");
        const phone = data.phone || DEFAULT_NUMBER;
        const message = data.message || "";
        if (!message) {
          res.writeHead(400, { "Content-Type": "application/json" });
          return res.end(JSON.stringify({ ok: false, error: "Message is required" }));
        }
        if (!isConnected || !sock) {
          res.writeHead(503, { "Content-Type": "application/json" });
          return res.end(
            JSON.stringify({
              ok: false,
              error: "WhatsApp Bridge not linked yet. Open http://127.0.0.1:3001 to scan QR code.",
            })
          );
        }
        const jid = formatJid(phone);
        if (!jid) {
          res.writeHead(400, { "Content-Type": "application/json" });
          return res.end(JSON.stringify({ ok: false, error: "Recipient phone number is required" }));
        }
        await sock.sendMessage(jid, { text: message });
        res.writeHead(200, { "Content-Type": "application/json" });
        return res.end(JSON.stringify({ ok: true, recipient: phone, jid }));
      } catch (err) {
        res.writeHead(500, { "Content-Type": "application/json" });
        return res.end(JSON.stringify({ ok: false, error: err.message }));
      }
    });
    return;
  }

  res.writeHead(404, { "Content-Type": "application/json" });
  res.end(JSON.stringify({ error: "Not found" }));
});

server.listen(PORT, "127.0.0.1", () => {
  console.log("====================================================================");
  console.log("  SETS Open-Source WhatsApp Bridge running at http://127.0.0.1:" + PORT);
  console.log("  Ready to dispatch alerts to configured recipient numbers");
  console.log("====================================================================");
  startWhatsAppSocket();
});

