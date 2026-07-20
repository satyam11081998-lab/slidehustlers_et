/**
 * Contract test for the offline demo payload.
 *
 *   node scripts/check-offline-payload.mjs
 *
 * The control room falls back to `public/demo/*.json` whenever the API is
 * unreachable. Those files are produced by `backend/export_static.py`, which
 * means two separate pieces of code have to agree on a shape — and when they
 * silently disagreed once, the board crashed on
 * `rs.zones[hero]` with "Cannot read properties of undefined".
 *
 * This asserts every field the board actually dereferences, so the offline path
 * cannot rot without the build failing first.
 */
import { readFileSync, existsSync } from "node:fs";

const DIR = new URL("../public/demo/", import.meta.url);
let failures = 0;

const ok = (cond, label, detail = "") => {
  console.log(`  [${cond ? "PASS" : "FAIL"}] ${label}${detail ? " — " + detail : ""}`);
  if (!cond) failures++;
};
const isArr = (v) => Array.isArray(v) && v.length > 0;

const index = JSON.parse(readFileSync(new URL("index.json", DIR)));
ok(isArr(index), "index.json lists scenarios", `${index.length} found`);

for (const { id } of index) {
  const f = new URL(`${id}.json`, DIR);
  console.log(`\n== ${id} ==`);
  if (!existsSync(f)) { ok(false, "payload exists"); continue; }
  const d = JSON.parse(readFileSync(f));

  ok(typeof d.duration === "number" && d.duration > 0, "duration present", String(d.duration));
  ok(isArr(d.frames) && d.frames.length === d.duration + 1,
     "one frame per simulated minute", `${d.frames?.length} frames`);

  // --- the exact expressions the hero chart evaluates -------------------
  const rs = d.risk_series;
  ok(!!rs, "risk_series present");
  ok(isArr(rs?.t), "risk_series.t is a non-empty array");
  ok(typeof rs?.hero === "string" && rs.hero.length > 0, "risk_series.hero is a zone id", rs?.hero);
  ok(!!rs?.zones && isArr(rs.zones[rs.hero]),
     "risk_series.zones[hero] resolves (the crash that started this test)");
  ok(isArr(rs?.baseline), "risk_series.baseline is a non-empty array");
  ok(rs?.t?.length === rs?.baseline?.length && rs?.t?.length === rs?.zones?.[rs.hero]?.length,
     "series lengths agree", `t=${rs?.t?.length} base=${rs?.baseline?.length}`);

  // --- frame shape (must match the WebSocket payload) -------------------
  const mid = d.frames[Math.floor(d.frames.length / 2)];
  ok(!!mid?.state && !!mid?.risk, "frames carry {state, risk}");
  for (const k of ["clock", "duration", "sensors", "t"]) {
    ok(mid.state?.[k] !== undefined, `frame.state.${k} present`);
  }
  ok(typeof mid.risk?.top_band_name === "string", "frame.risk.top_band_name present");
  ok(!!mid.risk?.zones, "frame.risk.zones present");

  // --- metrics fields the verdict card reads ---------------------------
  const m = d.metrics;
  ok(!!m, "metrics present");
  for (const p of [["kavach", "detection_clock"], ["kavach", "false_negatives"],
                   ["kavach", "false_positives"], ["baseline", "first_uncleared_clock"],
                   ["baseline", "first_uncleared_t"]]) {
    ok(m?.[p[0]]?.[p[1]] !== undefined, `metrics.${p[0]}.${p[1]} present`);
  }

  // --- sparkline series -------------------------------------------------
  const sids = Object.keys(d.series || {});
  ok(sids.length > 0, "sparkline series present", sids.join(", "));
  for (const sid of sids) {
    ok(isArr(d.series[sid].values), `series.${sid}.values is populated`);
  }
  ok(Array.isArray(d.alerts), "alerts array present", `${d.alerts?.length ?? 0}`);
}

console.log(failures === 0
  ? "\nOFFLINE PAYLOAD CONTRACT OK\n"
  : `\n${failures} CONTRACT CHECK(S) FAILED\n`);
process.exit(failures === 0 ? 0 : 1);
