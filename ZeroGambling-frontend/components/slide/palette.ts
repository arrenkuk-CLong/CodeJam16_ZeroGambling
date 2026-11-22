// Synthwave colours and the fixed numbers for the slide game's pseudo-3D camera.
// The canvas draws at a small fixed resolution (W x H) and CSS scales it up with crisp pixels.
// Gameplay numbers (steering, obstacle and ball sizes, speeds, checkpoints) are NOT here: they come with
// each run from the server (core/slide_balance.py), so the browser and the server's checks always agree.

export const PALETTE = {
  skyTop: '#0b0221',
  skyMid: '#2b0b4f',
  skyHorizon: '#ff3d81',
  sunTop: '#ffd319',
  sunBottom: '#ff2975',
  stars: '#f5e9ff',
  mountain: '#1a0533',
  mountainEdge: '#2de2e6',
  ground: '#140229',
  gridH: '#ff2bd6',            // horizontal grid lines that rush toward you
  gridV: '#7a2cff',            // grid lines running to the horizon
  borderA: '#ff3cac',          // neon border stripes (alternate = speed cue)
  borderB: '#7a2cff',
  edgeGlow: '#ff8fd0',
  trackA: '#1d0b35',
  trackB: '#24103f',
  laneMark: '#3ee8ff',
  finishA: '#f5e9ff',
  finishB: '#ff3cac',
  checkpoint: '#3ee8ff',
  shadow: 'rgba(0, 0, 0, 0.45)',
} as const;

export const W = 640;                 // internal canvas size (16:9)
export const H = 360;
export const HORIZON = 166;           // screen y of the horizon line
export const CAM_H = 4;               // camera height above the track (m)
export const Z_NEAR = 4.8;            // distance of the bottom screen edge from the camera (m)
export const FOCAL = ((H - HORIZON) * Z_NEAR) / CAM_H;
export const ROAD_HALF_M = 4.8;       // half the track width (m); positions on the track are in half-widths (-1..1)
export const SEG = 4;                 // one ground slice (m)
export const DRAW_SEGS = 150;         // slices drawn: 600 m of track
export const OBSTACLE_DRAW_M = 170;   // obstacles appear this far ahead (8-17 s at 20-10 m/s)
export const PLAYER_DZ = 5.6;         // the ball sits this far in front of the camera (m), near the bottom of the screen
export const BALL_PX = 32;            // the ball's sprite size, drawn 1:1 so it stays crisp (and small).
                                      // At the ball's depth that is 0.08 track half-widths = BALL_R on the server.
export const GRID_Z = 16;             // metres between horizontal grid lines
export const GRID_X = 10;             // metres between grid lines running to the horizon
export const IDLE_SPEED = 7;          // m/s while waiting for a run
