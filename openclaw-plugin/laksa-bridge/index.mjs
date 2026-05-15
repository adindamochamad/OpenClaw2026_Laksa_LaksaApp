/**
 * Plugin OpenClaw: arahkan perintah WhatsApp ke Laksa (FastAPI).
 * Tanpa LLM — balasan hanya dari router Laksa.
 */

import fs from "node:fs";
import os from "node:os";
import path from "node:path";

import { definePluginEntry } from "/usr/lib/node_modules/openclaw/dist/plugin-sdk/plugin-entry.js";
import { requestPluginConversationBinding } from "/usr/lib/node_modules/openclaw/dist/plugin-sdk/conversation-runtime.js";

const SESI_SUDAH_DIBALAS = new Map();
const TTL_MS = 180_000;

/** Pola teks error LLM yang jangan dikirim ke pengguna WhatsApp */
const POLA_BALASAN_DIBLOKIR = [
  /HTTP\s*401/i,
  /invalid access token/i,
  /token expired/i,
  /authentication error/i,
  /unauthorized/i,
];

function kunci_sesi(kanal, identitas) {
  return `${kanal}:${identitas}`;
}

function tandai_dibalas(kunci) {
  SESI_SUDAH_DIBALAS.set(kunci, Date.now());
  for (const [k, waktu] of SESI_SUDAH_DIBALAS) {
    if (Date.now() - waktu > TTL_MS) SESI_SUDAH_DIBALAS.delete(k);
  }
}

function sudah_dibalas_baru_ini(kunci) {
  const waktu = SESI_SUDAH_DIBALAS.get(kunci);
  return waktu != null && Date.now() - waktu < TTL_MS;
}

function harus_blokir_balasan_agent(teks) {
  if (!teks) return false;
  return POLA_BALASAN_DIBLOKIR.some((pola) => pola.test(teks));
}

function ekstrak_teks_pengguna(teks) {
  const mentah = (teks || "").trim();
  if (!mentah) return "";
  const baris = mentah.split("\n").map((b) => b.trim()).filter(Boolean);
  if (baris.length === 0) return mentah;
  const terakhir = baris[baris.length - 1];
  if (terakhir.startsWith("```") || terakhir.startsWith("{")) {
    const cocokJson = mentah.match(/"sender_id"\s*:\s*"([^"]+)"/);
    const cocokMenu = mentah.match(/\n(menu|status|laporan|mingguan|masuk|keluar|[+\-]\s*\d)/i);
    if (cocokMenu) return cocokMenu[1].trim();
    if (cocokJson) {
      const idx = mentah.toLowerCase().lastIndexOf("\nmenu");
      if (idx >= 0) return mentah.slice(idx + 1).trim();
    }
  }
  return terakhir;
}

function ekstrak_peer_dari_session(sessionKey) {
  const kunci = (sessionKey || "").trim();
  const cocok = kunci.match(/whatsapp:direct:(\+?\d+)/i);
  return cocok?.[1] || "";
}

function daftar_nomor_allowlist(cfg) {
  const akar = cfg?.channels?.whatsapp;
  const dariUtama = Array.isArray(akar?.allowFrom) ? akar.allowFrom : [];
  const dariAkun = Object.values(akar?.accounts || {}).flatMap((a) =>
    Array.isArray(a?.allowFrom) ? a.allowFrom : [],
  );
  const gabung = [...dariUtama, ...dariAkun]
    .map((n) => String(n).trim())
    .filter((n) => n.startsWith("+"));
  return [...new Set(gabung)];
}

async function pastikan_persetujuan_binding(akarPlugin) {
  const berkas = path.join(os.homedir(), ".openclaw", "plugin-binding-approvals.json");
  let isi = { version: 1, approvals: [] };
  try {
    if (fs.existsSync(berkas)) {
      isi = JSON.parse(fs.readFileSync(berkas, "utf8"));
    }
  } catch {
    /* pakai default kosong */
  }
  const sudah = (isi.approvals || []).some(
    (e) =>
      e.pluginRoot === akarPlugin &&
      e.channel === "whatsapp" &&
      (e.accountId || "default") === "default",
  );
  if (sudah) return;
  isi.approvals = isi.approvals || [];
  isi.approvals.push({
    pluginRoot: akarPlugin,
    pluginId: "laksa-bridge",
    pluginName: "Laksa Bridge",
    channel: "whatsapp",
    accountId: "default",
    approvedAt: Date.now(),
  });
  fs.mkdirSync(path.dirname(berkas), { recursive: true });
  fs.writeFileSync(berkas, `${JSON.stringify(isi, null, 2)}\n`, "utf8");
}

async function panggil_laksa(url, secret, peer, text) {
  const header = { "Content-Type": "application/json" };
  if (secret) header["X-OpenClaw-Secret"] = secret;
  const res = await fetch(url, {
    method: "POST",
    headers: header,
    body: JSON.stringify({ channel: "whatsapp", peer, text }),
    signal: AbortSignal.timeout(120_000),
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Laksa HTTP ${res.status}: ${body.slice(0, 300)}`);
  }
  return res.json();
}

async function kirim_balasan_whatsapp(api, peer, teks, accountId = "default") {
  await api.runtime.channel.whatsapp.sendMessageWhatsApp(peer, teks, {
    verbose: false,
    accountId,
  });
}

export default definePluginEntry({
  id: "laksa-bridge",
  name: "Laksa Bridge",
  description: "WhatsApp → Laksa webhook",
  register(api) {
    const cfg = api.pluginConfig || {};
    const urlLaksa =
      cfg.laksaWebhookUrl ||
      process.env.LAKSA_WEBHOOK_URL ||
      "http://127.0.0.1:8000/webhook/openclaw";
    const rahasia =
      cfg.laksaWebhookSecret || process.env.LAKSA_WEBHOOK_SECRET || "";
    const akarPlugin = api.rootDir || path.dirname(api.source || "");

    async function tangani_lewat_laksa(peer, text) {
      if (!peer || !text) return null;
      const teksBersih = ekstrak_teks_pengguna(text);
      if (!teksBersih || teksBersih.startsWith("/")) return null;
      const data = await panggil_laksa(urlLaksa, rahasia, peer, teksBersih);
      if (!data.handled || !data.reply) return null;
      return data.reply;
    }

    async function proses_pesan_wa(peer, text, accountId = "default") {
      const kunci = kunci_sesi("whatsapp", peer);
      try {
        const balasan = await tangani_lewat_laksa(peer, text);
        if (!balasan) return false;
        await kirim_balasan_whatsapp(api, peer, balasan, accountId);
        tandai_dibalas(kunci);
        api.logger.info?.(
          `laksa-bridge: balas ke ${peer}: ${ekstrak_teks_pengguna(text).slice(0, 40)}`,
        );
        return true;
      } catch (err) {
        api.logger.warn?.(`laksa-bridge: ${String(err)}`);
        return false;
      }
    }

    async function ikat_percakapan_wa(nomor, accountId = "default") {
      if (!akarPlugin || !nomor) return;
      try {
        const hasil = await requestPluginConversationBinding({
          pluginId: api.id,
          pluginName: api.name,
          pluginRoot: akarPlugin,
          conversation: {
            channel: "whatsapp",
            accountId,
            conversationId: nomor,
          },
          binding: {
            summary: "Percakapan WhatsApp diarahkan ke Laksa",
            detachHint: "/laksa-lepas",
          },
        });
        api.logger.info?.(
          `laksa-bridge: binding ${nomor} → ${hasil.status}`,
        );
      } catch (err) {
        api.logger.warn?.(`laksa-bridge: binding ${nomor} gagal: ${String(err)}`);
      }
    }

    // Persetujuan binding (untuk inbound_claim jika adapter WA sudah siap)
    api.on("gateway_start", async () => {
      if (!akarPlugin) return;
      try {
        await pastikan_persetujuan_binding(akarPlugin);
        api.logger.info?.("laksa-bridge: siap (WhatsApp → Laksa, tanpa agent LLM)");
      } catch (err) {
        api.logger.warn?.(`laksa-bridge: gateway_start ${String(err)}`);
      }
    });

    // Klaim pesan sebelum agent (jika binding aktif)
    api.on(
      "inbound_claim",
      async (event, ctx) => {
        if ((ctx.channelId || event.channel || "").toLowerCase() !== "whatsapp") {
          return;
        }
        const peer =
          event.senderId ||
          ctx.senderId ||
          event.conversationId ||
          ctx.conversationId ||
          "";
        const text =
          event.content || event.bodyForAgent || event.body || "";
        if (!peer || !text.trim()) return;

        const berhasil = await proses_pesan_wa(
          peer,
          text,
          ctx.accountId || event.accountId || "default",
        );
        if (berhasil) return { handled: true };
      },
      { priority: 400 },
    );

    // Cadangan jika binding belum aktif (mis. nomor baru)
    api.on(
      "message_received",
      async (event, ctx) => {
        if ((ctx.channelId || "").toLowerCase() !== "whatsapp") return;
        const peer = (event.from || "").trim();
        const text = (event.content || "").trim();
        if (!peer || !text) return;

        const berhasil = await proses_pesan_wa(
          peer,
          text,
          ctx.accountId || "default",
        );
        if (berhasil && akarPlugin) {
          await ikat_percakapan_wa(peer, ctx.accountId || "default");
        }
      },
      { priority: 400 },
    );

    // Blokir pesan error API (jalur yang memakai message_sending)
    api.on(
      "message_sending",
      async (event, ctx) => {
        if ((ctx.channelId || "").toLowerCase() !== "whatsapp") return;
        const isi = (event.content || "").trim();
        const kunci = kunci_sesi(
          ctx.channelId,
          ctx.conversationId || event.to || "?",
        );

        if (harus_blokir_balasan_agent(isi)) {
          api.logger.info?.(`laksa-bridge: blokir error API ke WA`);
          return { cancel: true };
        }

        if (sudah_dibalas_baru_ini(kunci) && isi && isi !== "NO_REPLY") {
          api.logger.info?.(
            `laksa-bridge: blokir balasan ganda (${isi.slice(0, 50)})`,
          );
          return { cancel: true };
        }
      },
      { priority: 400 },
    );

    const daftarPerintah = [
      ["menu", "Menu Laksa", false],
      ["laporan", "Laporan harian Laksa", false],
      ["laksa-status", "Status skor kesehatan Laksa", false],
      ["mingguan", "Ringkasan 7 hari", false],
      ["masuk", "Catat pemasukan", true],
      ["keluar", "Catat pengeluaran", true],
    ];

    for (const [nama, deskripsi, terimaArg] of daftarPerintah) {
      api.registerCommand({
        name: nama,
        description: deskripsi,
        acceptsArgs: terimaArg,
        requireAuth: false,
        async handler(ctx) {
          const peer = ctx.from || ctx.senderId || "";
          const teks =
            nama === "laksa-status"
              ? "status"
              : ctx.args && terimaArg
                ? `${nama} ${ctx.args}`.trim()
                : nama;
          api.logger.info?.(`laksa-bridge: /${nama} dari ${peer}`);
          try {
            const balasan = await tangani_lewat_laksa(peer, teks);
            if (!balasan) {
              return { text: "⚠️ Laksa tidak merespons. Cek laksa.service." };
            }
            tandai_dibalas(kunci_sesi("whatsapp", peer));
            return { text: balasan };
          } catch (err) {
            return { text: `⚠️ Laksa error: ${String(err)}` };
          }
        },
      });
    }
  },
});
