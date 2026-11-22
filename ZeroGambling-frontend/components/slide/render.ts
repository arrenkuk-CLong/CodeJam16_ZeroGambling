// Pseudo-3D renderer for the slide game. No 3D engine: the ground is ~160 thin slices, each projected
// with perspective (scale = FOCAL / distance), so slices near the camera are wide and low on screen and
// far ones are thin and close to the horizon. Everything is painted far → near (painter's algorithm).
//
// Motion: the slices never move on screen. Their colours come from their position in the *world*, so as
// the camera's distance grows the stripes and grid lines slide toward you.

import type { SlideRun } from '@/lib/world-types';
import {
  CAM_H, DRAW_SEGS, FOCAL, GRID_X, GRID_Z, H, HORIZON, OBSTACLE_DRAW_M, PALETTE, PLAYER_DZ,
  ROAD_HALF_M, SEG, W,
} from './palette';

/** Small seeded random generator, so the same run always has the same stars and bends. */
export function mulberry32(seed: number) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Gentle left/right bends. Purely visual: collisions use positions across the track, not the screen. */
export function makeCurve(seed: number) {
  const rnd = mulberry32(seed ^ 0x9e3779b9);
  const p1 = rnd() * Math.PI * 2, p2 = rnd() * Math.PI * 2;
  return (z: number) => z < 120 ? 0 : 0.012 * (Math.sin(z / 700 + p1) + 0.6 * Math.sin(z / 300 + p2));
}

/** Sky, striped sun, stars and mountains never move, so they are drawn once into their own canvas. */
export function makeBackground(seed: number): HTMLCanvasElement {
  const c = document.createElement('canvas');
  c.width = W; c.height = H;
  const ctx = c.getContext('2d')!;
  const rnd = mulberry32(seed);
  const sky = ctx.createLinearGradient(0, 0, 0, HORIZON);
  sky.addColorStop(0, PALETTE.skyTop);
  sky.addColorStop(0.6, PALETTE.skyMid);
  sky.addColorStop(1, PALETTE.skyHorizon);
  ctx.fillStyle = sky;
  ctx.fillRect(0, 0, W, HORIZON);

  ctx.fillStyle = PALETTE.stars;
  for (let i = 0; i < 70; i++) {
    ctx.globalAlpha = 0.3 + rnd() * 0.7;
    ctx.fillRect(Math.floor(rnd() * W), Math.floor(rnd() * HORIZON * 0.6), 1, 1);
  }
  ctx.globalAlpha = 1;

  // Sun: a gradient disc with horizontal cut-outs that get thicker toward the bottom.
  const r = 62, cx = W / 2, cy = HORIZON - 46;
  const sun = ctx.createLinearGradient(0, cy - r, 0, cy + r);
  sun.addColorStop(0, PALETTE.sunTop);
  sun.addColorStop(1, PALETTE.sunBottom);
  ctx.fillStyle = sun;
  ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = sky;
  for (let i = 0; i < 7; i++) ctx.fillRect(cx - r, cy - 6 + i * 9, r * 2, 1 + i * 0.9);

  // Mountain silhouette sitting on the horizon, with a neon rim.
  ctx.beginPath();
  ctx.moveTo(0, HORIZON);
  for (let x = 0; x <= W; x += 16) {
    const valley = Math.abs(x - cx) < 90 ? 0.35 : 1; // keep the sun visible in the middle
    ctx.lineTo(x, HORIZON - (6 + rnd() * 34) * valley);
  }
  ctx.lineTo(W, HORIZON);
  ctx.closePath();
  ctx.fillStyle = PALETTE.mountain;
  ctx.fill();
  ctx.strokeStyle = PALETTE.mountainEdge;
  ctx.globalAlpha = 0.6;
  ctx.lineWidth = 1;
  ctx.stroke();
  ctx.globalAlpha = 1;
  return c;
}

interface Slice { zw: number; cz: number; xoff: number; y: number; scale: number; }
const MIN_CZ = 1.6; // nearest distance ever projected (well below the bottom of the screen)

/** Projects one world point. u = position across the track in half-widths (-1 left edge, 1 right edge). */
function sx(s: Slice, u: number) { return W / 2 + (s.xoff + u * ROAD_HALF_M) * s.scale; }

/** Fills the band between a far slice and the next nearer one, between track positions u0 and u1. */
function band(ctx: CanvasRenderingContext2D, far: Slice, near: Slice, u0: number, u1: number, color: string) {
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.moveTo(sx(far, u0), far.y);
  ctx.lineTo(sx(far, u1), far.y);
  ctx.lineTo(sx(near, u1), near.y);
  ctx.lineTo(sx(near, u0), near.y);
  ctx.closePath();
  ctx.fill();
}

export interface Frame {
  distance: number;          // how far the ball has travelled (m)
  u: number;                 // ball position across the track
  run: SlideRun | null;      // null = idle preview, no obstacles
  sprites: Record<string, HTMLImageElement>;
  curve: (z: number) => number;
  background: HTMLCanvasElement;
}

/** Draws one frame and returns where the ball should be drawn (internal canvas pixels). */
export function drawFrame(ctx: CanvasRenderingContext2D, f: Frame) {
  ctx.drawImage(f.background, 0, 0);
  ctx.fillStyle = PALETTE.ground;
  ctx.fillRect(0, HORIZON, W, H - HORIZON);

  // 1. Project the slices. The camera sits PLAYER_DZ behind the ball. Bends accumulate slice by slice.
  const camW = f.distance - PLAYER_DZ;
  const base = Math.floor(camW / SEG);
  const frac = camW / SEG - base;
  const slices: Slice[] = [];
  let xoff = 0, dx = -f.curve(base * SEG) * frac;
  for (let n = 0; n <= DRAW_SEGS; n++) {
    const zw = (base + n) * SEG;
    const cz = Math.max(zw - camW, MIN_CZ); // slices just behind the camera are clamped below the screen
    const scale = FOCAL / cz;
    slices.push({ zw, cz, xoff, y: HORIZON + CAM_H * scale, scale });
    xoff += dx;
    dx += f.curve(zw);
  }
  const at = (zw: number): Slice => { // interpolated slice at any world distance
    const i = Math.min(Math.max((zw - base * SEG) / SEG, 0), DRAW_SEGS - 1);
    const n = Math.floor(i), t = i - n, a = slices[n]!, b = slices[n + 1]!;
    const cz = Math.max(zw - camW, MIN_CZ), scale = FOCAL / cz;
    return { zw, cz, xoff: a.xoff + (b.xoff - a.xoff) * t, y: HORIZON + CAM_H * scale, scale };
  };

  // 2. Grid lines running to the horizon (drawn before the track, which covers the middle ones).
  ctx.lineWidth = 1;
  ctx.strokeStyle = PALETTE.gridV;
  ctx.globalAlpha = 0.55;
  for (let k = -16; k <= 16; k++) {
    ctx.beginPath();
    for (let n = DRAW_SEGS; n >= 0; n--) {
      const s = slices[n]!;
      const x = W / 2 + (s.xoff + k * GRID_X) * s.scale;
      if (n === DRAW_SEGS) ctx.moveTo(x, s.y); else ctx.lineTo(x, s.y);
    }
    ctx.stroke();
  }
  ctx.globalAlpha = 1;

  // 3. Horizontal grid lines, the neon border, the track, lane marks and the finish line. Far → near.
  const length = f.run?.lengthM ?? Infinity;
  for (let n = DRAW_SEGS; n > 0; n--) {
    const far = slices[n]!, near = slices[n - 1]!;
    if (near.zw % GRID_Z === 0) {
      ctx.globalAlpha = Math.max(0, Math.min(1, 1 - near.cz / 600));
      ctx.fillStyle = PALETTE.gridH;
      ctx.fillRect(0, Math.floor(near.y), W, Math.max(1, Math.min(4, Math.round(near.scale * 0.025))));
      ctx.globalAlpha = 1;
    }
    const light = Math.floor(near.zw / (SEG * 2)) % 2 === 0; // stripe every 2 slices (8 m)
    band(ctx, far, near, -1.16, -1, light ? PALETTE.borderA : PALETTE.borderB);
    band(ctx, far, near, 1, 1.16, light ? PALETTE.borderA : PALETTE.borderB);
    band(ctx, far, near, -1, 1, light ? PALETTE.trackA : PALETTE.trackB);
    if (light) for (const u of [-0.31, 0.31]) band(ctx, far, near, u - 0.012, u + 0.012, PALETTE.laneMark);
    if (length >= near.zw && length < far.zw + SEG) { // checkered finish band
      for (let c = 0; c < 10; c++) {
        const u0 = -1 + c * 0.2;
        band(ctx, far, near, u0, u0 + 0.2, (c + Math.floor(near.zw / SEG)) % 2 ? PALETTE.finishA : PALETTE.finishB);
      }
    }
  }

  // 3b. Checkpoint lines every 50 m (only the highest one you pass pays), drawn 1 m deep.
  if (f.run) {
    const every = f.run.checkpointEveryM;
    ctx.globalAlpha = 0.85;
    for (let c = Math.ceil(Math.max(camW + MIN_CZ * 2, every) / every) * every; c < Math.min(length, camW + SEG * DRAW_SEGS); c += every) {
      const a = at(c), b = at(c + 1);
      ctx.fillStyle = PALETTE.checkpoint;
      ctx.beginPath();
      ctx.moveTo(sx(b, -1), b.y); ctx.lineTo(sx(b, 1), b.y); ctx.lineTo(sx(a, 1), a.y); ctx.lineTo(sx(a, -1), a.y);
      ctx.closePath(); ctx.fill();
    }
    ctx.globalAlpha = 1;
  }

  // 4. Neon glow along both track edges.
  ctx.save();
  ctx.shadowColor = PALETTE.borderA;
  ctx.shadowBlur = 8;
  ctx.strokeStyle = PALETTE.edgeGlow;
  ctx.lineWidth = 1.5;
  for (const u of [-1.16, 1.16]) {
    ctx.beginPath();
    for (let n = DRAW_SEGS; n >= 0; n--) {
      const s = slices[n]!;
      if (n === DRAW_SEGS) ctx.moveTo(sx(s, u), s.y); else ctx.lineTo(sx(s, u), s.y);
    }
    ctx.stroke();
  }
  ctx.restore();

  // 5. Haze on the horizon so far objects fade in instead of popping.
  const haze = ctx.createLinearGradient(0, HORIZON, 0, HORIZON + 26);
  haze.addColorStop(0, 'rgba(255, 61, 129, 0.45)');
  haze.addColorStop(1, 'rgba(255, 61, 129, 0)');
  ctx.fillStyle = haze;
  ctx.fillRect(0, HORIZON, W, 26);

  // 6. Obstacles ahead of the camera, far → near, anchored bottom-centre on the track.
  const ball = at(f.distance);
  const ballX = sx(ball, f.u);
  if (f.run) {
    const rows = f.run.rows;
    for (let i = rows.length - 1; i >= 0; i--) {
      const row = rows[i]!;
      const cz = row.z - camW;
      if (cz > OBSTACLE_DRAW_M || cz < MIN_CZ * 2) continue;
      const s = at(row.z);
      const size = f.run.hit.obstacleHalf * 2 * ROAD_HALF_M * s.scale;
      ctx.globalAlpha = Math.min(1, (OBSTACLE_DRAW_M - cz) / 40);
      for (const ob of row.obstacles) {
        const x = sx(s, f.run.lanes[ob.lane] ?? 0);
        ctx.fillStyle = PALETTE.shadow;
        ctx.beginPath(); ctx.ellipse(x, s.y, size * 0.45, size * 0.1, 0, 0, Math.PI * 2); ctx.fill();
        const img = f.sprites[ob.kind];
        if (img?.complete && img.naturalWidth) ctx.drawImage(img, Math.round(x - size / 2), Math.round(s.y - size), Math.round(size), Math.round(size));
      }
      ctx.globalAlpha = 1;
    }
  }

  // 7. The ball's shadow (the ball itself is an animated GIF layered over the canvas).
  ctx.fillStyle = PALETTE.shadow;
  ctx.beginPath(); ctx.ellipse(ballX, ball.y, 14, 4, 0, 0, Math.PI * 2); ctx.fill();
  return { ballX, ballY: ball.y };
}
