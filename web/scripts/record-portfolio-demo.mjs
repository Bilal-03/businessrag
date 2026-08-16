import { mkdir, rm } from 'node:fs/promises';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const webDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const repoDir = path.resolve(webDir, '..');
const rawDir = path.join(repoDir, 'artifacts', 'portfolio-demo-raw');

await rm(rawDir, { recursive: true, force: true });
await mkdir(rawDir, { recursive: true });

const npmCommand = process.platform === 'win32' ? 'npx.cmd' : 'npx';
const child = spawn(
  npmCommand,
  ['--no-install', 'playwright', 'test', '--config=playwright.demo.config.js'],
  { cwd: webDir, env: process.env, stdio: 'inherit' },
);

const exitCode = await new Promise((resolve, reject) => {
  child.once('error', reject);
  child.once('exit', code => resolve(code ?? 1));
});

if (exitCode !== 0) {
  process.exit(exitCode);
}

console.log(`Raw portfolio recording written under ${path.relative(repoDir, rawDir)}/`);
console.log('Run `npm run demo:convert` from web/ to create the MP4 artifact.');
