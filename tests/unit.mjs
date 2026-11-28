// Unit tests of the kit's engine-free parts (no browser): node tests/unit.mjs
// The browser side (templates, look gates, hero clipping, formats, video colour, audio levels): python tests/browser.py
import assert from 'node:assert/strict';

const LIB = new URL('../skills/papercraft/assets/lib/', import.meta.url);
const P2 = await import(new URL('paperkit-2d.js', LIB));
const PM = await import(new URL('paper-motion.js', LIB));
const PS = await import(new URL('paper-sound.js', LIB));
const PMU = await import(new URL('paper-music.js', LIB));

let passed = 0;
function test(name, fn) {
  fn();
  passed++;
  console.log(`  PASS  ${name}`);
}

function bandEnergyPct(buf, sr, cutoffHz) {
  // Exact radix-2 Cooley-Tukey FFT over the full buffer (power-of-2 zero-padded)
  let N = 1;
  while (N < buf.length && N < 16384) N <<= 1;
  const re = new Float64Array(N), im = new Float64Array(N);
  const len = Math.min(N, buf.length);
  for (let i = 0; i < len; i++) re[i] = buf[i];
  for (let i = 1, j = 0; i < N; i++) {
    let bit = N >> 1;
    for (; j & bit; bit >>= 1) j ^= bit;
    j ^= bit;
    if (i < j) { let t = re[i]; re[i] = re[j]; re[j] = t; }
  }
  for (let l = 2; l <= N; l <<= 1) {
    const ang = (-2 * Math.PI) / l, wr = Math.cos(ang), wi = Math.sin(ang);
    for (let i = 0; i < N; i += l) {
      let cr = 1, ci = 0;
      for (let j = 0; j < l / 2; j++) {
        const u = i + j, v = u + l / 2;
        const tr = re[v] * cr - im[v] * ci, ti = re[v] * ci + im[v] * cr;
        re[v] = re[u] - tr; im[v] = im[u] - ti;
        re[u] += tr; im[u] += ti;
        const nr = cr * wr - ci * wi; ci = cr * wi + ci * wr; cr = nr;
      }
    }
  }
  let tot = 0, low = 0;
  for (let k = 1; k <= N / 2; k++) {
    const p = re[k] * re[k] + im[k] * im[k];
    tot += p;
    if ((k * sr) / N <= cutoffHz) low += p;
  }
  return tot > 0 ? (100 * low) / tot : 100;
}

console.log('=== 1. paperkit-2d.js ===');
test('shape.ngon builds clean regular polygons', () => {
  const hex = P2.shape.ngon(6, 2.5);
  assert.equal(hex.length, 6);
  for (const [x, y] of hex) assert.ok(Math.abs(Math.hypot(x, y) - 2.5) < 1e-9);
  const v = P2.validateOutline(hex);
  assert.equal(v.ok, true, v.issues.join('; '));
  assert.ok(v.area > 15 && v.area < 17);
});

test('shape.roundedRect builds smooth rectangle resting on y=0', () => {
  const rr = P2.shape.roundedRect(4, 2, 0.4, 8);
  const v = P2.validateOutline(rr);
  assert.equal(v.ok, true, v.issues.join('; '));
  const b = P2.bbox(rr);
  assert.ok(Math.abs(b.x0 + 2) < 1e-6 && Math.abs(b.x1 - 2) < 1e-6);
  assert.ok(Math.abs(b.y0) < 1e-6 && Math.abs(b.y1 - 2) < 1e-6);
});

test('shape.cloud builds smooth round-puffed cloud on flat base (no spikes)', () => {
  const cl = P2.shape.cloud(P2.rng(7), { w: 4.4, h: 2.0, puffs: 5 });
  const cl2 = P2.shape.cloud({ w: 4.4, h: 2.0, puffs: 5 });
  for (const c of [cl, cl2]) {
    const v = P2.validateOutline(c);
    assert.equal(v.ok, true, v.issues.join('; '));
    const b = P2.bbox(c);
    assert.ok(b.y0 >= -1e-6, `cloud base should sit at y>=0, got ${b.y0}`);
    assert.ok(b.w > 3.5 && b.h > 1.5);
  }
});

test('validateOutline catches self-intersections, NaN, and degenerate polygons', () => {
  const bowtie = [[-1, 0], [1, 2], [1, 0], [-1, 2]];
  const v1 = P2.validateOutline(bowtie);
  assert.equal(v1.ok, false);
  assert.ok(v1.issues.some((s) => s.includes('self-intersect')));

  const nanPoly = [[0, 0], [1, NaN], [1, 1]];
  assert.equal(P2.validateOutline(nanPoly).ok, false);

  const linePoly = [[0, 0], [1, 0], [2, 0]];
  assert.equal(P2.validateOutline(linePoly).ok, false);
});

console.log('=== 2. paper-motion.js ===');
test('FlapSpring meets rise overshoot & settle acceptance bands', () => {
  const f = new PM.FlapSpring({ p: 0, size: 0.4 });
  f.set(1);
  let maxP = 0, tUp = null;
  for (let i = 1; i <= 120; i++) {
    const p = f.step(1 / 60);
    if (p > maxP) maxP = p;
    if (tUp === null && p >= 1) tUp = i / 60;
  }
  assert.ok(maxP >= 1.08 && maxP <= 1.16, `overshoot ${maxP}`);
  assert.ok(tUp >= 0.16 && tUp <= 0.34, `tUp ${tUp}`);
  assert.ok(Math.abs(f.p - 1) < 0.005, `settled p=${f.p}`);
});

test('smootherstep endpoints, midpoint, descending range, and monotonicity', () => {
  assert.equal(PM.smootherstep(0, 1, -0.5), 0);
  assert.equal(PM.smootherstep(0, 1, 0), 0);
  assert.equal(PM.smootherstep(0, 1, 0.5), 0.5);
  assert.equal(PM.smootherstep(0, 1, 1), 1);
  assert.equal(PM.smootherstep(0, 1, 2), 1);
  assert.equal(PM.smootherstep(-2, -10, 0), 0);
  assert.equal(PM.smootherstep(-2, -10, -6), 0.5);
  assert.equal(PM.smootherstep(-2, -10, -12), 1);
});

test('glideSchedule holds cleanly, slows at dips, and is strictly monotonic', () => {
  const g = PM.glideSchedule({
    duration: 10, fps: 60, holdStart: 1.0, easeIn: 1.0, easeOut: 1.2, holdEnd: 1.0,
    dips: [{ u: 0.5, width: 0.08, factor: 0.3 }],
  });
  assert.equal(g(0), 0);
  assert.equal(g(0.95), 0);
  assert.equal(g(9.1), 1);
  assert.equal(g(10), 1);
  let prev = 0;
  let speedAtDip = null, speedFast = null;
  for (let i = 1; i <= 600; i++) {
    const t = i / 60, u = g(t);
    assert.ok(u >= prev - 1e-12, `non-monotonic at t=${t}: ${prev} -> ${u}`);
    const du = u - prev;
    if (Math.abs(u - 0.5) < 0.01 && speedAtDip === null) speedAtDip = du;
    if (Math.abs(u - 0.25) < 0.01 && speedFast === null) speedFast = du;
    prev = u;
  }
  assert.ok(speedAtDip < speedFast * 0.65, `expected dip slowdown (${speedAtDip} vs ${speedFast})`);
});

test('polarCameraPos computes exact spherical coordinates', () => {
  const p = PM.polarCameraPos({ target: [1, 2, 3], azim: 0, pitchDeg: 45, dist: 20, time: 0, drift: 0 });
  const c = 20 * Math.SQRT1_2;
  assert.ok(Math.abs(p[0] - 1) < 1e-9);
  assert.ok(Math.abs(p[1] - (2 + c)) < 1e-9);
  assert.ok(Math.abs(p[2] - (3 + c)) < 1e-9);
});

test('checkContinuity passes smooth paths (incl. PI wrap) and catches teleports', () => {
  // Smooth continuous circular walk that wraps yaw across +/- PI
  const good = PM.checkContinuity((t) => {
    const a = -Math.PI + t * 1.2;
    const yaw = Math.atan2(Math.sin(a), Math.cos(a));
    return { pos: [Math.cos(a) * 3, 0, Math.sin(a) * 3], yaw, dist: 30 + Math.sin(t) * 2 };
  }, { duration: 4, fps: 60 });
  assert.equal(good.ok, true, JSON.stringify(good.issues));

  // Simulated fal 5.15s teleport & 5.4s camera distance jump
  const bad = PM.checkContinuity((t) => ({
    pos: [t < 2.0 ? -0.635 : 0.0, 0, 0],
    yaw: 0,
    dist: t < 2.5 ? 32.2 : 35.0,
  }), { duration: 3, fps: 60 });
  assert.equal(bad.ok, false);
  assert.ok(bad.issues.some((x) => x.kind === 'pos'));
  assert.ok(bad.issues.some((x) => x.kind === 'dist'));
});

test('checkContinuity skips the step across a cut and checks a loop seam', () => {
  // two shots: the camera jumps 40 units at t = 2 (a cut), and each shot is smooth
  const film = (t) => ({ pos: [t < 2 ? t : 40 + t, 0, 0], yaw: t < 2 ? 0 : 2, dist: 30 });
  assert.equal(PM.checkContinuity(film, { duration: 4, fps: 30 }).ok, false, 'an unmarked cut is a jump');
  assert.equal(PM.checkContinuity(film, { duration: 4, fps: 30, cuts: [2] }).ok, true, 'a marked cut is not');
  assert.equal(PM.checkContinuity(film, { duration: 4, fps: 30, cuts: [1] }).ok, false, 'a cut marked at the wrong time does not hide the jump');
  assert.equal(PM.checkContinuity(film, { duration: 4, fps: 30, cuts: 2 }).ok, true, 'one cut may be given as a number');
  // a cut that falls on a frame time, at every common rate: the step that carries the jump is the one skipped
  for (const fps of [24, 25, 30, 60]) {
    for (let j = 1; j < 5 * fps; j += 7) {
      const c = j / fps, shot = (t) => ({ pos: [t < c ? 0 : 50, 0, 0] });
      assert.equal(PM.checkContinuity(shot, { duration: 6, fps, cuts: [c] }).ok, true, `cut at ${c} s, ${fps} fps`);
    }
    for (const c of [0.1, 0.7, 1.8, 2.3, 4.9]) {
      const shot = (t) => ({ pos: [t < c ? 0 : 50, 0, 0] });
      assert.equal(PM.checkContinuity(shot, { duration: 6, fps, cuts: [c] }).ok, true, `cut at ${c} s, ${fps} fps`);
    }
  }
  // a loop: an orbit that closes, and one that stops a quarter turn short
  const orbit = (turns) => (t) => ({ pos: [Math.cos(t / 8 * turns * 2 * Math.PI) * 30, 20, Math.sin(t / 8 * turns * 2 * Math.PI) * 30], azim: t / 8 * turns * 2 * Math.PI });
  assert.equal(PM.checkContinuity(orbit(1), { duration: 8, fps: 30, loop: true }).ok, true, 'a full turn closes');
  const open = PM.checkContinuity(orbit(0.75), { duration: 8, fps: 30, loop: true });
  assert.equal(open.ok, false, 'three quarters of a turn does not close');
  assert.ok(open.issues.every((i) => i.seam && i.t === 8), 'the only issues are at the seam');
  assert.equal(PM.checkContinuity(orbit(0.75), { duration: 8, fps: 30 }).ok, true, 'without loop the open orbit is a fine one-way move');
});

test('checkContinuity flags non-finite values and pitch snaps', () => {
  const nan = PM.checkContinuity((t) => ({ pos: [t, t > 1 ? NaN : 0, 0], yaw: 0, dist: 30 }), { duration: 2, fps: 30 });
  assert.equal(nan.ok, false);
  assert.ok(nan.issues.some((x) => x.kind === 'nan' && x.field === 'pos.y'));
  const pitch = PM.checkContinuity((t) => ({ pos: [0, 0, 0], pitchDeg: t < 1 ? 44 : 80 }), { duration: 2, fps: 60 });
  assert.equal(pitch.ok, false);
  assert.ok(pitch.issues.some((x) => x.kind === 'pitch'));
  const calm = PM.checkContinuity((t) => ({ pos: [0, 0, 0], pitchDeg: 44 + 4 * Math.sin(t) }), { duration: 4, fps: 60 });
  assert.equal(calm.ok, true, JSON.stringify(calm.issues));
});

console.log('=== 3. paper-sound.js ===');
test('FLAP_PRESETS warm/crisp/soft exist and warm is default', () => {
  assert.equal(PS.FLAP, PS.FLAP_PRESETS.warm);
  assert.ok(PS.FLAP_PRESETS.soft.lpHz < PS.FLAP_PRESETS.warm.lpHz);
  assert.ok(PS.FLAP_PRESETS.warm.lpHz < PS.FLAP_PRESETS.crisp.lpHz);
});

test('synthFlap passes hygiene, determinism, and spectral warmth', () => {
  const sr = 48000;
  for (const [name, preset] of Object.entries(PS.FLAP_PRESETS)) {
    for (const size of [0.2, 0.75]) {
      for (const up of [true, false]) {
        const P = PS.flapParams({ size, up, seed: 42 }, preset);
        const buf = PS.synthFlap({ size, up, pitch: P.pitch, dur: P.dur, seed: P.synthSeed, sr }, preset);
        const buf2 = PS.synthFlap({ size, up, pitch: P.pitch, dur: P.dur, seed: P.synthSeed, sr }, preset);
        // Bit-identical determinism
        assert.equal(buf.length, buf2.length);
        for (let i = 0; i < buf.length; i++) {
          assert.ok(Number.isFinite(buf[i]), `${name} non-finite sample`);
          assert.equal(buf[i], buf2[i]);
        }
        let peak = 0, at = 0, tail = 0;
        for (let i = 0; i < buf.length; i++) {
          const a = Math.abs(buf[i]);
          if (a > peak) { peak = a; at = i; }
          if (i >= buf.length - sr / 1000) tail = Math.max(tail, a);
        }
        const attackMs = (at / sr) * 1000;
        const firstRel = Math.abs(buf[0]) / peak;
        const tailDb = 20 * Math.log10(tail / peak + 1e-12);
        assert.ok(attackMs <= 8.0, `${name} s=${size} up=${up} attackMs=${attackMs.toFixed(2)}`);
        assert.ok(firstRel < 0.02, `${name} firstRel=${firstRel}`);
        assert.ok(tailDb < -35, `${name} tailDb=${tailDb.toFixed(1)}`);
        if (name === 'warm' && up) {
          const e15 = bandEnergyPct(buf, sr, 1500);
          const e25 = bandEnergyPct(buf, sr, 2500);
          assert.ok(e15 >= 75, `warm s=${size} <1.5kHz was ${e15.toFixed(1)}%`);
          assert.ok(e25 >= 90, `warm s=${size} <2.5kHz was ${e25.toFixed(1)}%`);
        }
      }
    }
  }
});

test('encodeWav16 produces valid 16-bit PCM RIFF/WAVE bytes', () => {
  const ch0 = new Float32Array([0, 0.5, -0.5, 1.0]);
  const ch1 = new Float32Array([0, -0.25, 0.25, -1.0]);
  const wav = PS.encodeWav16({ numberOfChannels: 2, length: 4, sampleRate: 48000, channels: [ch0, ch1] });
  assert.equal(wav.byteLength, 44 + 4 * 2 * 2);
  const txt = (a, b) => String.fromCharCode(...wav.subarray(a, b));
  assert.equal(txt(0, 4), 'RIFF');
  assert.equal(txt(8, 12), 'WAVE');
  assert.equal(txt(12, 16), 'fmt ');
  assert.equal(txt(36, 40), 'data');
  const dv = new DataView(wav.buffer);
  assert.equal(dv.getUint16(20, true), 1); // PCM
  assert.equal(dv.getUint16(22, true), 2); // stereo
  assert.equal(dv.getUint32(24, true), 48000);
  assert.equal(dv.getInt16(44 + 4, true), Math.round(0.5 * 32767));
});

test('createFlapCollector picks nearest/largest single winner and deduplicates keys', () => {
  const fired = [];
  const col = PS.createFlapCollector((ev) => fired.push(ev), { falloff: 9, groupWindow: 0.5 });
  col.add({ key: 'far', size: 0.9, distance: 20 });
  col.add({ key: 'nearSmall', size: 0.2, distance: 1 });
  col.add({ key: 'nearBig', size: 0.85, distance: 1.2 });
  col.flush(1.0);
  assert.equal(fired.length, 1);
  assert.equal(fired[0].key, 'nearBig');
  // Same key within groupWindow is suppressed
  col.add({ key: 'nearBig', size: 0.85, distance: 1.2 });
  col.flush(1.2);
  assert.equal(fired.length, 1);
  // After groupWindow expires it fires again
  col.add({ key: 'nearBig', size: 0.85, distance: 1.2 });
  col.flush(1.7);
  assert.equal(fired.length, 2);
});

test('createFlapCollector still speaks after the clock restarts', () => {
  const fired = [];
  const col = PS.createFlapCollector((ev) => fired.push(ev), { groupWindow: 0.5 });
  col.add({ key: 'a', size: 0.6 }); col.flush(9.9);
  col.add({ key: 'a', size: 0.6 }); col.flush(0.6);        // restart(): the clock went back; 0.6 is far from 9.9
  assert.equal(fired.length, 2);
  col.reset();
  col.add({ key: 'a', size: 0.6 }); col.flush(0.7);        // reset() forgets the window
  assert.equal(fired.length, 3);
});

console.log('=== 4. paper-music.js ===');
test('synthFeltPiano generates clean, warm, click-free notes', () => {
  assert.equal(PMU.midiToHz(69), 440);
  assert.equal(PMU.midiToHz(57), 220);
  for (const midi of [48, 60, 76]) {
    const pcm = PMU.synthFeltPiano(midi, 7, 48000);
    assert.ok(pcm.length > 48000);
    let peak = 0;
    for (let i = 0; i < pcm.length; i++) {
      assert.ok(Number.isFinite(pcm[i]));
      peak = Math.max(peak, Math.abs(pcm[i]));
    }
    assert.ok(peak > 0.85 && peak <= 0.96, `midi ${midi} peak=${peak}`);
    assert.ok(Math.abs(pcm[0]) < 0.01, `onset click on midi ${midi}`);
    assert.ok(Math.abs(pcm[pcm.length - 1]) < 0.01, `tail click on midi ${midi}`);
    const warmPct = bandEnergyPct(pcm.subarray(1000, 3048), 48000, 2500);
    assert.ok(warmPct >= 88, `midi ${midi} <2.5kHz was ${warmPct.toFixed(1)}%`);
  }
});

console.log(`\nALL ${passed} UNIT TESTS PASSED!`);
