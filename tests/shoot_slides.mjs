#!/usr/bin/env node
/**
 * 合格条件 10：E2E のスライドを Playwright で 1 枚ずつ撮影し、はみ出した枚数が 0 であることを確かめる。
 *
 * 撮影と測定は、複製したスキルの capture.mjs（assets/scripts）に任せる。ここでは結果を判定する。
 * 判定: 撮影が終了コード 0、overflowSlides が空、撮影した画像の数がスライド数と一致、画像が実在する。
 * 画像は作業フォルダに残るので、開いて目で確かめる（パスを標準出力に出す）。
 *
 * 使い方: node tests/shoot_slides.mjs <slides.html>
 * 終了コード: 0＝合格、1＝不合格、2＝引数の誤り、3＝Playwright が使えない
 */
import { spawnSync } from 'node:child_process';
import { existsSync, mkdtempSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const repo = path.resolve(here, '..');
const capture = path.join(repo, 'plugins/ced-skills/skills/ced-websearch-slide-ja/assets/scripts/capture.mjs');

const html = process.argv[2];
if (!html || !existsSync(html)) {
  console.error('使い方: node tests/shoot_slides.mjs <slides.html>');
  process.exit(2);
}
const out = mkdtempSync(path.join(os.tmpdir(), 'ced-shoot-'));
const r = spawnSync(process.execPath, [capture, path.resolve(html), '--out', out], { encoding: 'utf8' });

if (r.status === 3) {
  console.error('Playwright が使えない（撮影できない）。合格条件 10 は未検証');
  process.exit(3);
}
if (r.status !== 0) {
  console.error(`FAIL: 撮影が終了コード ${r.status}\n${r.stderr}`);
  process.exit(1);
}
let rep;
try {
  rep = JSON.parse(r.stdout);
} catch {
  console.error('FAIL: 撮影の報告を読めない');
  process.exit(1);
}

const problems = [];
if (!(rep.total > 0)) problems.push('スライドが 0 枚');
if (rep.overflowSlides.length !== 0) problems.push(`はみ出したスライド: ${rep.overflowSlides.join(', ')}`);
const files = rep.slides.map((s) => path.join(rep.outDir, s.file));
const missing = files.filter((f) => !existsSync(f));
if (missing.length) problems.push(`撮影できていない画像: ${missing.map((f) => path.basename(f)).join(', ')}`);
if (rep.slides.length !== rep.total) problems.push(`撮影数 ${rep.slides.length} ≠ スライド数 ${rep.total}`);

console.log(`撮影: ${rep.slides.length} 枚（スライド ${rep.total} 枚）、はみ出し ${rep.overflowSlides.length} 枚`);
console.log(`画像の場所（開いて確かめる）: ${rep.outDir}`);
if (problems.length) {
  for (const p of problems) console.log('FAIL:', p);
  process.exit(1);
}
console.log('PASS: 合格条件 10（はみ出し 0・全枚撮影）');
