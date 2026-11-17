// Dependency-free publication check. Findings show locations, never matched values.
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { createHash } from 'node:crypto';

const mode = process.argv[2] ?? '--staged';
if (!['--staged', '--worktree'].includes(mode)) {
  throw new Error('Usage: node tools/check_git_secrets.mjs [--staged|--worktree]');
}
const git = (...args) => execFileSync('git', args, { maxBuffer: 64 * 1024 * 1024 });
const root = git('rev-parse', '--show-toplevel').toString().trim();
const list = (...args) => git(...args).toString().split('\0').filter(Boolean);
const files = [...new Set(mode === '--staged'
  ? list('ls-files', '-z')
  : [...list('ls-files', '-z'), ...list('ls-files', '--others', '--exclude-standard', '-z')])];
const staged = new Map();
if (mode === '--staged') {
  const entries = list('ls-files', '--stage', '-z').map(entry => {
    const match = /^(\d+) ([a-f0-9]+) (\d)\t([\s\S]+)$/.exec(entry);
    if (!match || match[3] !== '0') throw new Error('Unmerged or invalid Git index');
    return { oid: match[2], name: match[4] };
  });
  const batch = execFileSync('git', ['cat-file', '--batch'], {
    input: entries.map(entry => entry.oid + '\n').join(''), maxBuffer: 64 * 1024 * 1024,
  });
  let cursor = 0;
  for (const entry of entries) {
    const end = batch.indexOf(10, cursor);
    const header = batch.subarray(cursor, end).toString();
    const match = /^([a-f0-9]+) blob (\d+)$/.exec(header);
    if (end < 0 || !match || match[1] !== entry.oid) throw new Error(`Cannot inspect index blob: ${entry.name}`);
    const size = Number(match[2]);
    const start = end + 1;
    if (start + size >= batch.length || batch[start + size] !== 10) throw new Error('Truncated Git blob batch');
    staged.set(entry.name, batch.subarray(start, start + size));
    cursor = start + size + 1;
  }
}
const placeholder = value => /^(?:|none|null|false|true|demo|test|example|placeholder|changeme|your[-_ ].*|replace[-_ ].*|<.*>|\$\{.*\})$/i.test(value)
  || /^(?:test|fake|dummy|example|mock|demo|not-a-real|replace-with)[-_]/i.test(value);
const rules = [
  ['private-key', /-----BEGIN (?:RSA |EC |OPENSSH |DSA |ENCRYPTED )?PRIVATE KEY-----/g],
  ['provider-token', /\b(?:sk-(?:proj-|ant-api\d\d-)?[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|AKIA[0-9A-Z]{16}|xox[baprs]-[A-Za-z0-9-]{20,}|AIza[A-Za-z0-9_-]{30,})\b/g],
  ['jwt', /\beyJ[A-Za-z0-9_-]{15,}\.eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{16,}/g],
  ['url-credentials', /https?:\/\/[^\s/:"'<>]+:[^\s/@"'<>]{8,}@/g],
  ['literal-credential', /(?<![\w-])(?:["']?(?:[A-Za-z][A-Za-z0-9]*_)*(?:api[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret|service[_-]?token|smtp[_-]?password|password|secret[_-]?key)["']?\s*[:=]\s*["'])([^\s"']{12,})(?:["'])/gi],
  ['literal-bearer', /\bBearer\s+([A-Za-z0-9_.-]{24,})/g],
];
// Compare against actual local configuration without displaying its contents.
const localSecrets = new Set();
for (const name of ['configs/models.local.yaml', 'product_v1/.env', 'product_v1/.env.network', '.env']) {
  let data;
  try { data = readFileSync(path.join(root, name), 'utf8'); } catch (error) {
    if (error.code === 'ENOENT') continue;
    throw error;
  }
  const pattern = /^\s*["']?((?:[A-Z_]*_)?(?:API_KEY|ACCESS_TOKEN|AUTH_TOKEN|CLIENT_SECRET|SERVICE_TOKEN|SMTP_PASSWORD|PASSWORD|SECRET_KEY))["']?\s*[:=]\s*["']?([^\s"'#]{8,})/gim;
  for (const match of data.matchAll(pattern)) {
    if (!placeholder(match[2]) && !/^env:/.test(match[2])) localSecrets.add(match[2]);
  }
}
const findings = [];
const allowlistPath = 'tools/secret_scan_allowlist.json';
let allowlist = [];
try {
  const config = mode === '--staged' ? (staged.get(allowlistPath)?.toString() ?? '[]') : readFileSync(path.join(root, allowlistPath), 'utf8');
  allowlist = JSON.parse(config);
} catch (error) {
  // Only a missing initial allowlist is acceptable. Invalid JSON always fails.
  if (error.code !== 'ENOENT' && error.status !== 128) throw error;
}
let reviewed = 0;
let bytes = 0;
let binaries = 0;
for (const name of files) {
  let buffer;
  try {
    buffer = mode === '--staged' ? staged.get(name) : readFileSync(path.join(root, name));
    if (!buffer) throw new Error('Missing index blob');
  }
  catch (error) { throw new Error(`Cannot inspect ${name}: ${error.code ?? 'git read failed'}`); }
  bytes += buffer.length;
  if (/(?:^|\/)(?:\.env(?:\..*)?|credentials\.json|token\.json|id_rsa|id_ed25519)$|\.(?:pem|key|p12|pfx|sqlite3?|db)$/i.test(name)
      && !/\.example$/.test(name)) findings.push({ file: name, rule: 'sensitive-path' });
  if (buffer.includes(0)) {
    binaries++;
    if (!/^product_v1\/fixtures\/demo_private_lending\/chat-[12]\.png$/.test(name)) {
      findings.push({ file: name, rule: 'unreviewed-binary' });
    }
    continue;
  }
  const data = buffer.toString('utf8');
  const add = (rule, index) => {
    const line = data.slice(0, index).split('\n').length;
    const lineHash = createHash('sha256').update(data.split('\n')[line - 1].replace(/\r$/, '')).digest('hex');
    if (rule !== 'local-credential-copy' && allowlist.some(item => item.file === name && item.rule === rule && item.line_sha256 === lineHash)) {
      reviewed++;
      return;
    }
    findings.push({ file: name, line, rule });
  };
  for (const [rule, pattern] of rules) {
    for (const match of data.matchAll(pattern)) {
      const value = match[1] ?? match[0];
      if (!placeholder(value)) add(rule, match.index);
    }
  }
  for (const value of localSecrets) {
    const index = data.indexOf(value);
    if (index >= 0) add('local-credential-copy', index);
  }
}
console.log(JSON.stringify({ mode, files: files.length, bytes, binaries, reviewed, findings }, null, 2));
process.exitCode = findings.length ? 1 : 0;
