import fs from 'node:fs';
import path from 'node:path';
import { execFileSync, spawnSync } from 'node:child_process';
import { createHash, randomBytes } from 'node:crypto';
const source = path.resolve('tools/check_git_secrets.mjs');
const scratchRoot = path.resolve('tmp');
fs.mkdirSync(scratchRoot, { recursive: true });
const cwd = fs.mkdtempSync(path.join(scratchRoot, 'secret-scanner-test-'));
const git = (...args) => execFileSync('git', args, { cwd, stdio: 'pipe' });
const write = (name, value) => {
  const target = path.join(cwd, name);
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, value);
};
const scan = (mode, expected, rule) => {
  const result = spawnSync(process.execPath, [source, mode], { cwd, encoding: 'utf8' });
  if (result.status !== expected) throw new Error(`Unexpected status for ${mode}: ${result.status}`);
  const output = JSON.parse(result.stdout);
  if (rule && !output.findings.some(item => item.rule === rule)) throw new Error(`Missing ${rule}`);
  checks++;
};
let checks = 0;
try {
  git('init', '-q');
  write('tools/secret_scan_allowlist.json', '[]');
  write('safe.txt', 'Only source documentation.\n');
  git('add', 'safe.txt', 'tools/secret_scan_allowlist.json');
  scan('--staged', 0);
  const token = ['sk', 'proj', randomBytes(24).toString('hex')].join('-');
  const line = `value=${token}`;
  write('candidate.txt', line + '\n');
  scan('--worktree', 1, 'provider-token');
  scan('--staged', 0);
  git('add', 'candidate.txt');
  write('candidate.txt', 'The worktree is now clean, but the index still contains the sentinel.\n');
  scan('--staged', 1, 'provider-token');
  write('tools/secret_scan_allowlist.json', JSON.stringify([{ file: 'candidate.txt', rule: 'provider-token',
    line_sha256: createHash('sha256').update(line).digest('hex') }]));
  git('add', 'tools/secret_scan_allowlist.json');
  scan('--staged', 0);
  write('candidate.txt', line + ' changed\n');
  git('add', 'candidate.txt');
  scan('--staged', 1, 'provider-token');
  const opaque = randomBytes(32).toString('hex');
  const localLine = `opaque=${opaque}`;
  write('candidate.txt', localLine + '\n');
  write('configs/models.local.yaml', `api_key: ${opaque}\n`);
  write('tools/secret_scan_allowlist.json', JSON.stringify([{ file: 'candidate.txt', rule: 'local-credential-copy',
    line_sha256: createHash('sha256').update(localLine).digest('hex') }]));
  git('add', 'candidate.txt', 'tools/secret_scan_allowlist.json');
  scan('--staged', 1, 'local-credential-copy');
  fs.rmSync(path.join(cwd, 'configs/models.local.yaml'));
  write('candidate.txt', 'Safe again.\n');
  write('unexpected.bin', Buffer.from([0, 1, 2, 3]));
  git('add', 'candidate.txt', 'unexpected.bin');
  scan('--staged', 1, 'unreviewed-binary');
  console.log(JSON.stringify({ scannerChecksPassed: checks }));
} finally {
  const resolved = path.resolve(cwd);
  if (!resolved.startsWith(scratchRoot + path.sep)) throw new Error('Unsafe cleanup path');
  fs.rmSync(resolved, { recursive: true, force: true });
}
