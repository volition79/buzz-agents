// The cryptography is @noble/secp256k1. This file only validates Nostr event shape.
import { schnorr } from '@noble/secp256k1';
import { createHash } from 'node:crypto';

const isHex = (v, n) => typeof v === 'string' && new RegExp(`^[0-9a-f]{${n}}$`).test(v);
const hex = (v) => Buffer.from(v).toString('hex');
const bytes = (v) => new Uint8Array(Buffer.from(v, 'hex'));

async function verify(e) {
  if (!e || !isHex(e.id, 64) || !isHex(e.pubkey, 64) || !isHex(e.sig, 128) ||
      !Number.isSafeInteger(e.created_at) || e.created_at < 0 ||
      !Number.isSafeInteger(e.kind) || e.kind < 0 || typeof e.content !== 'string' ||
      Buffer.byteLength(e.content) > 65536 || !Array.isArray(e.tags) ||
      e.tags.length > 1000 || !e.tags.every(t => Array.isArray(t) &&
        t.length <= 100 && t.every(s => typeof s === 'string' && s.length <= 8192))) return false;
  const canonical = JSON.stringify([0, e.pubkey, e.created_at, e.kind, e.tags, e.content]);
  const id = createHash('sha256').update(canonical).digest('hex');
  if (id !== e.id) return false;
  try { return await schnorr.verifyAsync(bytes(e.sig), bytes(id), bytes(e.pubkey)); }
  catch { return false; }
}

try {
  let data = '';
  process.stdin.setEncoding('utf8');
  for await (const chunk of process.stdin) {
    data += chunk;
    if (Buffer.byteLength(data) > 8 * 1024 * 1024) throw new Error('input_limit');
  }
  const input = JSON.parse(data || 'null');
  let result;
  if (process.argv[2] === 'keygen') {
    const { secretKey, publicKey } = schnorr.keygen();
    result = { private_key: hex(secretKey), public_key: hex(publicKey) };
  } else if (process.argv[2] === 'public' && isHex(input, 64)) {
    result = hex(schnorr.getPublicKey(bytes(input)));
  } else if (process.argv[2] === 'verify' && Array.isArray(input) && input.length <= 200) {
    result = await Promise.all(input.map(verify));
  } else throw new Error('operation_invalid');
  process.stdout.write(JSON.stringify(result) + '\n');
} catch {
  process.stderr.write('nostr_helper_failed\n');
  process.exitCode = 1;
}
