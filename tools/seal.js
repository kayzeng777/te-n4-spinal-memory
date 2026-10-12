#!/usr/bin/env node
// Seals the Reading Room: tools/reading-room.json (plaintext, git-ignored) ->
// tools/reading-room.sealed.json (ciphertext, committed). Each lecture is
// encrypted under its own password: PBKDF2-SHA256 -> AES-256-GCM, the same
// scheme the page decrypts with (WebCrypto). Run, then tools/build.py.
//
//   reading-room.json: {"0": {"password": "...", "replay": "<YouTube id>",
//                             "links": [{"label": "...", "url": "https://..."}],
//                             "note": "..."}, "1": {...}}   (key = lecture index)
//
// A lecture left out of the file shows as "soon" in the Reading Room.
const crypto = require('crypto'), fs = require('fs'), path = require('path');
const ITER = 600000;
const src = path.join(__dirname, 'reading-room.json');
const out = path.join(__dirname, 'reading-room.sealed.json');
const rooms = JSON.parse(fs.readFileSync(src, 'utf8'));
const sealed = {v: 1, iter: ITER, rooms: {}};
for (const [i, r] of Object.entries(rooms)) {
  if (!r.password) throw new Error(`lecture ${i}: no password`);
  const {password, ...body} = r;
  for (const l of body.links || [])
    if (!/^https:\/\//.test(l.url)) throw new Error(`lecture ${i}: link must be https: ${l.url}`);
  const salt = crypto.randomBytes(16), iv = crypto.randomBytes(12);
  const key = crypto.pbkdf2Sync(password.normalize('NFKC'), salt, ITER, 32, 'sha256');
  const c = crypto.createCipheriv('aes-256-gcm', key, iv);
  const ct = Buffer.concat([c.update(JSON.stringify(body), 'utf8'), c.final(), c.getAuthTag()]);
  sealed.rooms[i] = {salt: salt.toString('base64'), iv: iv.toString('base64'), ct: ct.toString('base64')};
}
fs.writeFileSync(out, JSON.stringify(sealed, null, 1) + '\n');
console.log(`sealed ${Object.keys(sealed.rooms).length} lecture(s) -> tools/reading-room.sealed.json`);
