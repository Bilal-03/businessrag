import { access, mkdir, readdir, rm, stat } from 'node:fs/promises';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const webDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const repoDir = path.resolve(webDir, '..');
const rawDir = path.join(repoDir, 'artifacts', 'portfolio-demo-raw');
const outputDir = path.join(repoDir, 'artifacts');
const outputPath = path.join(outputDir, 'bizguide-ai-portfolio-demo.mp4');

async function findFiles(directory, extension) {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = [];

  for (const entry of entries) {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      files.push(...await findFiles(entryPath, extension));
    } else if (entry.name.endsWith(extension)) {
      files.push(entryPath);
    }
  }

  return files;
}

async function run(command, args) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { stdio: ['ignore', 'pipe', 'pipe'] });
    let stdout = '';
    let stderr = '';
    child.stdout.on('data', chunk => { stdout += chunk; });
    child.stderr.on('data', chunk => { stderr += chunk; });
    child.once('error', reject);
    child.once('exit', code => resolve({ code: code ?? 1, stdout, stderr }));
  });
}

try {
  await access(rawDir);
} catch {
  throw new Error('No raw recording found. Run `npm run demo:record` from web/ first.');
}

const sources = await findFiles(rawDir, '.webm');
if (sources.length !== 1) {
  throw new Error(`Expected exactly one raw WebM recording, found ${sources.length}.`);
}

await mkdir(outputDir, { recursive: true });
await rm(outputPath, { force: true });

const converter = '/usr/bin/avconvert';
try {
  await access(converter);
} catch {
  throw new Error('macOS avconvert was not found; MP4 conversion cannot continue.');
}

const conversionArgs = [
  '--source', sources[0],
  '--preset', 'Preset1280x720',
  '--output', outputPath,
  '--replace',
  '--disableFastStart',
];

const conversion = await run(converter, conversionArgs);
let conversionTool = 'avconvert';

if (conversion.code !== 0) {
  const ffmpegCandidates = ['/usr/local/bin/ffmpeg', '/opt/homebrew/bin/ffmpeg'];
  const ffmpeg = (await Promise.all(ffmpegCandidates.map(async candidate => {
    try {
      await access(candidate);
      return candidate;
    } catch {
      return null;
    }
  }))).find(Boolean);

  if (!ffmpeg) {
    throw new Error(
      `avconvert could not convert the browser recording and no FFmpeg fallback was found.\n${conversion.stderr || conversion.stdout}\nRaw recording: ${sources[0]}`,
    );
  }

  console.warn('avconvert does not accept Playwright WebM input; using the explicit FFmpeg MP4 fallback.');
  const fallback = await run(ffmpeg, [
    '-y',
    '-i', sources[0],
    '-c:v', 'libx264',
    '-pix_fmt', 'yuv420p',
    '-movflags', '+faststart',
    '-an',
    outputPath,
  ]);

  if (fallback.code !== 0) {
    throw new Error(
      `FFmpeg could not convert the browser recording.\n${fallback.stderr || fallback.stdout}\nRaw recording: ${sources[0]}`,
    );
  }
  conversionTool = 'ffmpeg fallback';
}

const outputStats = await stat(outputPath);
if (outputStats.size === 0) {
  throw new Error('The MP4 conversion completed with an empty output file.');
}

const description = await run('file', ['--brief', outputPath]);
if (!/ISO Media|MPEG-4|QuickTime/i.test(description.stdout)) {
  throw new Error(`The output is not recognized as an MP4-compatible movie: ${description.stdout}`);
}

console.log(`Portfolio demo ready: ${path.relative(repoDir, outputPath)}`);
console.log(`Source recording: ${path.relative(repoDir, sources[0])}`);
console.log(`Conversion tool: ${conversionTool}`);
console.log('The capture is silent; no microphone or browser audio is enabled.');
