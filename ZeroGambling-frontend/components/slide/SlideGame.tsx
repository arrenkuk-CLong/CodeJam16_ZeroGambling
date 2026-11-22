'use client';
// The playable slide: a canvas for the world plus the roulette-ball GIF layered on top (a canvas can only
// draw a GIF's first frame, an <img> keeps it animated). A/D steer. The run comes from Django: obstacle
// rows, this glider's steering speed and the hit sizes. This component plays it and reports a finish or a
// crash through onEnd; the server pays the highest checkpoint passed.

import { useEffect, useRef } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import type { SlideRun } from '@/lib/world-types';
import { BALL_PX, H, IDLE_SPEED, W } from './palette';
import { drawFrame, makeBackground, makeCurve } from './render';

export interface SlideEnd { runId: string; result: 'survived' | 'crashed'; distanceM: number; }

const COUNTDOWN_S = 3;
const SPRITES = { cards: '/slide/cards.png', token: '/slide/Token.png', dice: '/slide/dice.png' };
const BALL_GIF = '/slide/roulette_ball.gif';
const BALL_CRASH = '/slide/roulette_ball_crash.png';

function speedAt(run: SlideRun, d: number) {
  const t = Math.min(1, d / run.speed.rampM);
  return run.speed.start + (run.speed.max - run.speed.start) * t;
}

export function SlideGame({ run, checkpoints, onEnd }: {
  run: SlideRun | null; checkpoints: { m: number; gems: number }[]; onEnd: (e: SlideEnd) => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const ballRef = useRef<HTMLImageElement>(null);
  const frameRef = useRef<HTMLDivElement>(null);
  const hudDistance = useRef<HTMLSpanElement>(null);
  const hudSpeed = useRef<HTMLSpanElement>(null);
  const hudBar = useRef<HTMLDivElement>(null);
  const hudCheckpoint = useRef<HTMLSpanElement>(null);
  const checkpointsRef = useRef(checkpoints);
  useEffect(() => { checkpointsRef.current = checkpoints; });
  const banner = useRef<HTMLParagraphElement>(null);
  const input = useRef({ left: false, right: false });
  const onEndRef = useRef(onEnd);
  useEffect(() => { onEndRef.current = onEnd; });

  // Keyboard: A / D only move the ball left and right.
  useEffect(() => {
    const set = (e: KeyboardEvent, down: boolean) => {
      if (e.target instanceof HTMLElement && e.target.closest('input, textarea, select, [contenteditable]')) return;
      const k = e.key.toLowerCase();
      if (k === 'a') input.current.left = down;
      if (k === 'd') input.current.right = down;
    };
    const down = (e: KeyboardEvent) => set(e, true), up = (e: KeyboardEvent) => set(e, false);
    const clear = () => { input.current.left = input.current.right = false; };
    window.addEventListener('keydown', down);
    window.addEventListener('keyup', up);
    window.addEventListener('blur', clear);
    return () => { window.removeEventListener('keydown', down); window.removeEventListener('keyup', up); window.removeEventListener('blur', clear); };
  }, []);

  // The game loop. Restarts whenever a new run arrives (or returns to the idle preview).
  useEffect(() => {
    const canvas = canvasRef.current, ballImg = ballRef.current;
    if (!canvas || !ballImg) return;
    const ctx = canvas.getContext('2d')!;
    ctx.imageSmoothingEnabled = false; // crisp pixels
    const seed = run?.seed ?? 7;
    const background = makeBackground(seed);
    const curve = makeCurve(seed);
    const sprites = Object.fromEntries(Object.entries(SPRITES).map(([k, src]) => {
      const img = new Image(); img.src = src; return [k, img];
    }));
    ballImg.src = BALL_GIF;
    frameRef.current?.classList.remove('animate-[slide-shake_0.35s_ease-in-out]');

    let distance = 0, u = 0, raf = 0, last = performance.now(), countdown = run ? COUNTDOWN_S : 0, done = false;
    let nextRow = 0; // first obstacle row the ball hasn't passed yet
    let checkpoint = 0; // highest checkpoint passed (only this one pays)
    const showBanner = (text: string) => { if (banner.current) { banner.current.textContent = text; banner.current.hidden = !text; } };
    showBanner(run ? String(COUNTDOWN_S) : '');

    const placeBall = (x: number, y: number) => {
      ballImg.style.left = `${((x - BALL_PX / 2) / W) * 100}%`;
      ballImg.style.top = `${((y - BALL_PX + 2) / H) * 100}%`;
    };
    const hud = (d: number, v: number) => {
      if (!run) return;
      if (hudDistance.current) hudDistance.current.textContent = `${Math.floor(d)} / ${run.lengthM} m`;
      if (hudSpeed.current) hudSpeed.current.textContent = `${Math.round(v * 3.6)} km/h`;
      if (hudBar.current) hudBar.current.style.width = `${Math.min(100, (d / run.lengthM) * 100)}%`;
      const c = Math.min(run.lengthM, Math.floor(d / run.checkpointEveryM) * run.checkpointEveryM);
      if (c !== checkpoint || d === 0) {
        checkpoint = c;
        const gems = checkpointsRef.current.find(x => x.m === c)?.gems ?? 0;
        const el = hudCheckpoint.current;
        if (el) {
          el.textContent = c ? `Checkpoint ${c} m · ${gems} gem${gems === 1 ? '' : 's'}` : `First checkpoint at ${run.checkpointEveryM} m`;
          if (c) el.animate([{ color: '#3ee8ff', transform: 'scale(1.15)' }, { color: '', transform: 'scale(1)' }], { duration: 500 });
        }
      }
    };
    const finish = (result: SlideEnd['result'], d: number) => {
      done = true;
      if (result === 'crashed') {
        ballImg.src = BALL_CRASH;
        frameRef.current?.classList.add('animate-[slide-shake_0.35s_ease-in-out]');
        showBanner('Crashed');
      } else showBanner('Finished!');
      onEndRef.current({ runId: run!.id, result, distanceM: Math.floor(d) });
    };

    const tick = (now: number) => {
      const dt = Math.min(0.05, (now - last) / 1000); // a hidden tab never jumps ahead
      last = now;
      if (!run) {
        distance += IDLE_SPEED * dt;
      } else if (countdown > 0) {
        countdown -= dt;
        showBanner(countdown > 0 ? String(Math.ceil(countdown)) : 'Go!');
        if (countdown <= 0) setTimeout(() => { if (!done) showBanner(''); }, 600);
      } else if (!done) {
        const steer = (input.current.right ? 1 : 0) - (input.current.left ? 1 : 0);
        const { hitR, wallU, depthM } = run.hit;
        u = Math.max(-wallU, Math.min(wallU, u + steer * run.steer * dt)); // a better glider steers faster
        const before = distance;
        distance = Math.min(run.lengthM, distance + speedAt(run, distance) * dt);
        // Hit test every row the ball swept past this frame, so a fast frame can't skip through one.
        const rows = run.rows;
        while (nextRow < rows.length && rows[nextRow]!.z + depthM < before) nextRow++;
        for (let i = nextRow; i < rows.length && rows[i]!.z - depthM <= distance; i++) {
          if (rows[i]!.obstacles.some(o => Math.abs((run.lanes[o.lane] ?? 0) - u) < hitR)) {
            distance = Math.max(before, rows[i]!.z - depthM);
            finish('crashed', distance);
            break;
          }
        }
        if (!done && distance >= run.lengthM) finish('survived', distance);
        hud(distance, speedAt(run, distance));
      }
      const { ballX, ballY } = drawFrame(ctx, { distance, u, run, sprites, curve, background });
      placeBall(ballX, ballY);
      if (!done || !run) raf = requestAnimationFrame(tick);
    };
    hud(0, run ? run.speed.start : 0);
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [run]);

  return <div className="space-y-3">
    {run && <div className="flex items-center gap-3 font-mono text-xs text-muted-foreground">
      <span ref={hudDistance} className="tabular-nums text-foreground">0 / {run.lengthM} m</span>
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-primary/20"><div ref={hudBar} className="h-full w-0 bg-primary"/></div>
      <span ref={hudSpeed} className="tabular-nums">0 km/h</span>
    </div>}
    {run && <p className="font-mono text-xs"><span ref={hudCheckpoint} className="inline-block origin-left tabular-nums text-foreground">First checkpoint at {run.checkpointEveryM} m</span></p>}
    <div ref={frameRef} className="relative aspect-video w-full overflow-hidden rounded-lg border border-border/30 bg-black">
      <canvas ref={canvasRef} width={W} height={H} className="block h-full w-full [image-rendering:pixelated]"
        role="img" aria-label="Synthwave downhill slide. Steer the roulette ball with A and D to dodge cards, tokens and dice."/>
      {/* eslint-disable-next-line @next/next/no-img-element -- a plain <img> keeps the GIF animating; next/image adds nothing for a 7 KB sprite */}
      <img ref={ballRef} src={BALL_GIF} alt="" aria-hidden width={BALL_PX} height={BALL_PX}
        className="pointer-events-none absolute [image-rendering:pixelated]" style={{ width: `${(BALL_PX / W) * 100}%`, left: '47.5%', top: '64%' }}/>
      <p ref={banner} hidden role="status" aria-live="assertive"
        className="pointer-events-none absolute inset-x-0 top-[22%] text-center font-mono text-4xl font-bold tracking-widest text-[#ffd319] [text-shadow:0_0_12px_#ff2975] md:text-6xl"/>
    </div>
    <div className="flex items-center justify-between gap-3 text-xs text-muted-foreground">
      <p>Steer with <kbd className="rounded border border-border/50 px-1.5 py-0.5 font-mono">A</kbd> and <kbd className="rounded border border-border/50 px-1.5 py-0.5 font-mono">D</kbd>.</p>
      <div className="flex gap-2 md:hidden">
        <button type="button" aria-label="Steer left" className="touch-none rounded-lg border border-border/50 p-3 active:bg-primary/20"
          onPointerDown={() => { input.current.left = true; }} onPointerUp={() => { input.current.left = false; }}
          onPointerLeave={() => { input.current.left = false; }} onPointerCancel={() => { input.current.left = false; }}><ChevronLeft/></button>
        <button type="button" aria-label="Steer right" className="touch-none rounded-lg border border-border/50 p-3 active:bg-primary/20"
          onPointerDown={() => { input.current.right = true; }} onPointerUp={() => { input.current.right = false; }}
          onPointerLeave={() => { input.current.right = false; }} onPointerCancel={() => { input.current.right = false; }}><ChevronRight/></button>
      </div>
    </div>
  </div>;
}
