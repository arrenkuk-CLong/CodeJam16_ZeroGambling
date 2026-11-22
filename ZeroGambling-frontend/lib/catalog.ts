// Fixed demo catalog: exactly 19 active challenges. ID 9 is permanently retracted.
export type GameGroup = "logic" | "memory" | "perception";

export interface CatalogEntry {
  id: number;
  name: string;
  group: GameGroup;
  version: number;
  measures: string;
  example: string;
  depth: string;
  width: string;
  input: "number" | "text" | "choice" | "grid" | "svg" | "audio" | "timer";
  scoring: string;
}

export const RETRACTED_IDS = [9] as const;

export const GROUPS: { id: GameGroup; label: string; blurb: string }[] = [
  { id: "logic", label: "Logic & language", blurb: "Answers checked exactly by code." },
  { id: "memory", label: "Memory & visual", blurb: "Hold, transform and spot what you saw." },
  { id: "perception", label: "Perception", blurb: "Your error becomes a 0–100 score." },
];

export const CATALOG: CatalogEntry[] = [
  { id: 1, name: "Mental math chains", group: "logic", version: 1, input: "number",
    measures: "Working-memory arithmetic under a timer", example: "((7 + 3) × 4) − 5 = ?",
    depth: "More operations, bigger numbers, shorter timer", width: "Negatives, exact division",
    scoring: "Exact. Fractions such as 1/2 and decimals such as 0.5 are equivalent." },
  { id: 2, name: "Pattern completion", group: "logic", version: 1, input: "number",
    measures: "Inferring a rule from examples", example: "3, 7, 11, 15, __",
    depth: "Longer sequences, more missing terms", width: "Quadratic, interleaved and Fibonacci-style rules",
    scoring: "Every missing term must be exact. Ambiguous puzzles are rejected at generation." },
  { id: 3, name: "Cipher decoding", group: "logic", version: 1, input: "text",
    measures: "Systematic symbol substitution", example: "KHOOR → HELLO (shift 3)",
    depth: "Longer text, fewer hints", width: "Caesar → Atbash → Vigenère, missing spaces",
    scoring: "Letters only, case-insensitive; spaces and punctuation ignored. 95% letters correct passes." },
  { id: 4, name: "Wordle-style", group: "logic", version: 1, input: "text",
    measures: "Deduction from letter feedback", example: "CRANE → 🟩⬜🟨⬜⬜",
    depth: "Word length 4 → 6, fewer guesses", width: "Hard mode (revealed hints must be reused)",
    scoring: "Solve within the guess budget. Fewer guesses score higher." },
  { id: 5, name: "Vocabulary", group: "logic", version: 1, input: "choice",
    measures: "Word knowledge across frequency tiers", example: "‘Ephemeral’ means…",
    depth: "Rarer words", width: "Definition → word, then synonyms",
    scoring: "Five items from a curated lexicon; 4 of 5 passes." },
  { id: 6, name: "Typing gauntlet", group: "logic", version: 1, input: "text",
    measures: "Speed and accuracy on a passage", example: "Type 20 words at ≥ 90% accuracy",
    depth: "Longer passages, higher accuracy and speed", width: "Numbers and symbols",
    scoring: "Edit-distance accuracy plus words per minute. Pasted text scores 0." },
  { id: 7, name: "Mastermind", group: "logic", version: 1, input: "grid",
    measures: "Hypothesis testing with partial feedback", example: "4 pegs, 6 colors, 10 tries",
    depth: "More positions and colors, fewer tries", width: "Duplicate colors allowed",
    scoring: "Exact matches counted first, then misplaced colors. Fewer guesses score higher." },
  { id: 8, name: "Lights Out", group: "logic", version: 1, input: "grid",
    measures: "Planning in a puzzle with coupled moves", example: "3×3 board, turn every light off",
    depth: "Bigger grid, longer scrambles", width: "Wraparound edges",
    scoring: "Moves are replayed on the server. Solve within the move limit." },
  { id: 10, name: "Base conversion / units", group: "logic", version: 1, input: "text",
    measures: "Number representation fluency", example: "45 (decimal) → binary",
    depth: "Bigger numbers, more steps", width: "Binary ↔ hex ↔ decimal, chained units",
    scoring: "Exact for bases; ±0.5% for unit chains. Prefixes 0b / 0x are accepted." },
  { id: 11, name: "Sequence memory", group: "memory", version: 1, input: "grid",
    measures: "Short-term ordered recall", example: "Watch 5 flashes, repeat them",
    depth: "Longer sequence, faster playback", width: "Reverse order recall, 4×4 grid",
    scoring: "Shown once. A refresh during recall does not replay it." },
  { id: 12, name: "Mental rotation", group: "memory", version: 1, input: "svg",
    measures: "Rotating shapes in your head", example: "Which one is the same shape, rotated?",
    depth: "Bigger shapes, less time", width: "Mirror images as distractors",
    scoring: "Symmetric shapes are rejected so exactly one answer fits. 4 of 5 passes." },
  { id: 13, name: "Odd-one-out (color)", group: "memory", version: 1, input: "grid",
    measures: "Fine lightness discrimination", example: "Find the slightly lighter tile",
    depth: "Smaller difference, bigger grid", width: "Lightness-only differences (color-blind safe)",
    scoring: "Five boards; 4 of 5 passes." },
  { id: 14, name: "Dot count", group: "perception", version: 1, input: "number",
    measures: "Rapid numerosity estimation", example: "≈ 40 dots for 1.2 s",
    depth: "More dots, shorter flash", width: "Two colors, count one",
    scoring: "Score = 100 × (1 − 2 × relative error). 75 passes." },
  { id: 15, name: "Trajectory landing", group: "perception", version: 1, input: "svg",
    measures: "Intuitive physics prediction", example: "Where will the ball land?",
    depth: "Shorter visible arc", width: "Wind",
    scoring: "Distance in scene widths. Score = 100 × (1 − error / 0.2). Average 70 passes." },
  { id: 16, name: "Angle matching", group: "perception", version: 1, input: "svg",
    measures: "Orientation judgement", example: "Rotate the dial to 37°",
    depth: "Tighter tolerance", width: "Target hidden before you answer",
    scoring: "Shortest circular error, so 359° vs 1° is 2°. Pass if mean error ≤ tolerance." },
  { id: 17, name: "Tempo keeping", group: "perception", version: 1, input: "audio",
    measures: "Internal timing through silence", example: "4 beats at 90 BPM, keep tapping",
    depth: "Faster tempo, longer silence", width: "—",
    scoring: "Mean early/late error on silent beats vs. ¼ beat; missed beats count against you. 60 passes." },
  { id: 18, name: "Line splitting", group: "perception", version: 1, input: "svg",
    measures: "Proportional spatial judgement", example: "Mark 3/7 of the way along",
    depth: "Harder fractions (halves → eighths)", width: "Measure from the far end, percentages",
    scoring: "Error in line lengths. Pass if mean error is within tolerance." },
  { id: 19, name: "Time estimation", group: "perception", version: 1, input: "timer",
    measures: "Interval timing", example: "Stop at exactly 4.5 s",
    depth: "Longer intervals, tighter tolerance", width: "On-screen distraction",
    scoring: "Relative error. A hidden tab voids the run without penalty." },
  { id: 20, name: "Pitch matching", group: "perception", version: 1, input: "audio",
    measures: "Pitch discrimination", example: "Tune to the reference tone",
    depth: "Narrower tolerance (cents)", width: "Reference plays once",
    scoring: "Error = |1200 × log₂(yours / target)| cents. Pass if within tolerance." },
];

export const ACTIVE_IDS = CATALOG.map((g) => g.id);

export function getEntry(id: number): CatalogEntry | undefined {
  if ((RETRACTED_IDS as readonly number[]).includes(id)) return undefined;
  return CATALOG.find((g) => g.id === id);
}

export function bandFor(level: number): { name: string; maxModifiers: number } {
  if (level < 10) return { name: "Depth only", maxModifiers: 0 };
  if (level < 25) return { name: "One modifier", maxModifiers: 1 };
  if (level < 40) return { name: "Up to two modifiers", maxModifiers: 2 };
  return { name: "Chained modifiers", maxModifiers: 3 };
}
