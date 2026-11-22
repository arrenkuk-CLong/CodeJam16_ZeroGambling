"""Procedural generators and evaluators for the 19 active challenges (port of Lovable's games.server.ts).
Server-only: answers never reach the browser. Every module has generate(rng, level) and either
evaluate(g, submission, ctx) (one submission) or guess(g, state, payload, used, max) (several guesses)."""
import json
import math
import re
from pathlib import Path

from .jscompat import js_round, js_str, to_base, to_fixed

_DATA = json.loads((Path(__file__).with_name("challenge_data.json")).read_text(encoding="utf-8"))
WORDS = {int(k): v for k, v in _DATA["WORDS"].items()}
LEXICON = _DATA["LEXICON"]
PHRASES = _DATA["PHRASES"]
TYPING_WORDS = _DATA["TYPING_WORDS"]
# Wordle answers come from WORDS (common words); any real English word of the right length counts as a guess.
_GUESSES = json.loads((Path(__file__).with_name("wordle_guesses.json")).read_text(encoding="utf-8"))
GUESS_WORDS = {int(k): set(v) | set(WORDS[int(k)]) for k, v in _GUESSES.items()}


def clamp(v, a, b):
    return max(a, min(b, v))


def r1(v):
    return js_round(v * 10) / 10


def fail(feedback, metrics=None):
    return {"score": 0, "passed": False, "feedback": feedback, "metrics": metrics or {}}


def _get(d, key, default=None):
    return d.get(key, default) if isinstance(d, dict) else default


def js_number(x) -> float:
    """Number(x): undefined -> NaN, null -> 0, numeric strings -> their value, anything else -> NaN."""
    if x is None:
        return 0.0
    if isinstance(x, bool):
        return 1.0 if x else 0.0
    if isinstance(x, (int, float)):
        return float(x)
    if isinstance(x, str):
        s = x.strip()
        if not s:
            return 0.0
        try:
            return float(s)
        except ValueError:
            return math.nan
    return math.nan


def finite(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def is_integer(x) -> bool:
    return finite(x) and float(x).is_integer()


_FRAC = re.compile(r"^(-?\d+)\s*/\s*(-?\d+)$", re.ASCII)
_NUM = re.compile(r"^-?\d*\.?\d+(e-?\d+)?$", re.ASCII | re.IGNORECASE)


def parse_number(raw):
    s = js_str(raw) if isinstance(raw, (int, float)) and not isinstance(raw, bool) else str("" if raw is None else raw)
    s = s.strip().replace("−", "-").replace(",", "")
    if not s:
        return None
    m = _FRAC.match(s)
    if m:
        d = float(m.group(2))
        return None if d == 0 else float(m.group(1)) / d
    return float(s) if _NUM.match(s) else None


def near(a, b):
    return abs(a - b) < 1e-9 * max(1, abs(b))


def same(a, b) -> bool:
    """JavaScript ===, for the numbers in a JSON submission."""
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    return a == b


def at(arr, i, default=None):
    return arr[i] if 0 <= i < len(arr) else default


# ---------- 1. Mental math chains ----------
class Math1:
    id, version = 1, 1

    @staticmethod
    def generate(rng, level):
        ops = min(2 + (level - 1) // 2, 9)
        max_n = min(6 + level * 2, 60)
        negatives = level >= 10
        division = level >= 6
        mods = ["Negatives"] if negatives else []
        value = rng.int(2, max_n)
        expr = str(value)
        steps = []
        for i in range(ops):
            choices = ["+", "−", "×"] + (["÷"] if division else [])
            op = rng.pick(choices)
            n = rng.int(2, min(12, 3 + level) if op == "×" else max_n)
            if negatives and rng.chance(0.3):
                n = -n
            if op == "×" and abs(value * n) > 5000:
                op = "+"
            if op == "÷":
                divisors = [d for d in (2, 3, 4, 5, 6, 7, 8, 9) if value % d == 0 and value != 0]
                if not divisors:
                    op = "−"
                else:
                    d = rng.pick(divisors)
                    n = d * (-1 if negatives and rng.chance(0.3) else 1)
            prev = value
            value = value + n if op == "+" else value - n if op == "−" else value * n if op == "×" else value // n
            shown = f"({n})" if n < 0 else str(n)
            expr = f"{expr} {op} {shown}" if i == 0 else f"({expr}) {op} {shown}"
            steps.append(f"{prev} {op} {shown} = {value}")
        time_limit = max(20, 75 - level * 2)
        return {
            "publicData": {"prompt": "Evaluate the expression. Innermost parentheses first.", "operations": ops, "timeLimitSec": time_limit},
            "stimulus": {"expression": expr.replace("-", "−")},
            "answer": {"value": value, "steps": steps}, "maxAttempts": 1, "modifiers": mods, "timeLimitSec": time_limit,
            "answerReveal": str(value),
        }

    @staticmethod
    def evaluate(g, sub, ctx):
        v = parse_number(_get(sub, "answer"))
        value, steps = g["answer"]["value"], g["answer"]["steps"]
        if v is None:
            return fail(["That isn't a number. Use digits, a decimal or a fraction like 1/2.", *steps], {"expected": value})
        if near(v, value):
            return {"score": 100, "passed": True, "feedback": [f"Exactly {js_str(value)}."], "metrics": {"expected": value, "entered": v}}
        off = r1(v - value)
        return fail([f"Expected {js_str(value)}; you entered {js_str(v)} ({'+' if off > 0 else ''}{js_str(off)}).", "Working:", *steps],
                    {"expected": value, "entered": v, "error": off})

    @staticmethod
    def hint(g, used):
        return f"First step: {g['answer']['steps'][0]}" if used == 0 else None


# ---------- 2. Pattern completion ----------
def fit_families(known):
    fits = []

    def check(name, f):
        try:
            return {"name": name, "f": f} if all(near(f(i), v) for i, v in known) else None
        except (ZeroDivisionError, OverflowError):
            return None

    a = at(known, 0)
    b = at(known, 1)
    c = at(known, 2)
    if a and b:
        d = (b[1] - a[1]) / (b[0] - a[0])
        fits.append(check("arithmetic", lambda n: a[1] + (n - a[0]) * d))
        if a[1] != 0 and b[0] - a[0] == 1:
            r = b[1] / a[1]
            fits.append(check("geometric", lambda n: a[1] * r ** (n - a[0])))
    if a and b and c:
        def lagrange(n):
            return (a[1] * ((n - b[0]) * (n - c[0])) / ((a[0] - b[0]) * (a[0] - c[0]))
                    + b[1] * ((n - a[0]) * (n - c[0])) / ((b[0] - a[0]) * (b[0] - c[0]))
                    + c[1] * ((n - a[0]) * (n - b[0])) / ((c[0] - a[0]) * (c[0] - b[0])))
        fits.append(check("quadratic", lagrange))
    m = dict(known)
    if 0 in m and 1 in m:
        def seq(n):
            x, y = m[0], m[1]
            if n == 0:
                return x
            for _ in range(1, n):
                x, y = y, x + y
            return y
        fits.append(check("fibonacci", seq))
    ev = [k for k in known if k[0] % 2 == 0]
    od = [k for k in known if k[0] % 2 == 1]
    if len(ev) >= 2 and len(od) >= 2:
        def mk(k):
            d = (k[1][1] - k[0][1]) / (k[1][0] - k[0][0])
            return lambda n: k[0][1] + (n - k[0][0]) * d
        fe, fo = mk(ev), mk(od)
        fits.append(check("interleaved", lambda n: fe(n) if n % 2 == 0 else fo(n)))
    return [f for f in fits if f]


class Pattern:
    id, version = 2, 1

    @staticmethod
    def generate(rng, level):
        for _ in range(50):
            length = min(5 + level // 6, 9)
            missing_count = min(1 + level // 12, 3)
            fams = ["arithmetic", "geometric"] + (["quadratic"] if level >= 4 else []) + (["interleaved"] if level >= 10 else []) + (["fibonacci"] if level >= 15 else [])
            fam = rng.pick(fams)
            neg = level >= 10
            if fam == "arithmetic":
                s = rng.int(1, 20)
                d = rng.int(2, 6 + level) * (-1 if neg and rng.chance(0.4) else 1)
                f = lambda n, s=s, d=d: s + n * d  # noqa: E731
            elif fam == "geometric":
                s = rng.int(1, 5)
                r = rng.pick([2, 3, -2] if neg else [2, 3])
                f = lambda n, s=s, r=r: s * r ** n  # noqa: E731
            elif fam == "quadratic":
                s, bq, cq = rng.int(0, 9), rng.int(0, 4), rng.int(1, 3)
                f = lambda n, s=s, bq=bq, cq=cq: s + bq * n + cq * n * n  # noqa: E731
            elif fam == "interleaved":
                s1, d1, s2, d2 = rng.int(1, 9), rng.int(2, 7), rng.int(20, 40), -rng.int(1, 5)
                f = lambda n, s1=s1, d1=d1, s2=s2, d2=d2: s1 + (n // 2) * d1 if n % 2 == 0 else s2 + ((n - 1) // 2) * d2  # noqa: E731
            else:
                x0, y0 = rng.int(1, 5), rng.int(1, 6)

                def f(n, x0=x0, y0=y0):
                    p, q = x0, y0
                    if n == 0:
                        return p
                    for _ in range(1, n):
                        p, q = q, p + q
                    return q
            terms = [f(i) for i in range(length)]
            if any(abs(t) > 100000 for t in terms):
                continue
            missing = []  # a JS Set: insertion order, no duplicates
            if level >= 8 and missing_count > 1:
                missing.append(rng.int(2, length - 2))
            i = length - 1
            while len(missing) < missing_count:
                if i not in missing:
                    missing.append(i)
                i -= 1
            known = [(i, t) for i, t in enumerate(terms) if i not in missing]
            fits = fit_families(known)
            order = sorted(missing, key=str)
            preds = {",".join(js_str(r1(ft["f"](i))) for i in order) for ft in fits}
            if len(preds) != 1:
                continue  # ambiguous or unfittable
            shown = [None if i in missing else t for i, t in enumerate(terms)]
            answers = [terms[i] for i in sorted(missing)]
            return {
                "publicData": {"prompt": "Fill in the missing terms.", "length": length, "missingCount": len(missing)},
                "stimulus": {"terms": shown}, "answer": {"answers": answers, "family": fam}, "maxAttempts": 1,
                "modifiers": ["New rule families"] if level >= 10 else [], "answerReveal": ", ".join(js_str(a) for a in answers), "timeLimitSec": 120,
            }
        raise RuntimeError("Could not generate an unambiguous pattern")

    @staticmethod
    def evaluate(g, sub, ctx):
        given = _get(sub, "answers")
        given = given if isinstance(given, list) else []
        exp = g["answer"]["answers"]
        right = 0
        for i, v in enumerate(exp):
            p = parse_number(at(given, i))
            if p is not None and near(p, v):
                right += 1
        score = js_round(right / len(exp) * 100)
        fam = g["answer"]["family"]
        return {
            "score": score, "passed": right == len(exp),
            "feedback": [f"All {len(exp)} correct — a {fam} rule."] if right == len(exp) else [f"{right}/{len(exp)} correct. Expected {', '.join(js_str(v) for v in exp)} ({fam} rule)."],
            "metrics": {"correct": right, "total": len(exp)},
        }

    @staticmethod
    def hint(g, used):
        return f"The rule family is {g['answer']['family']}." if used == 0 else None


# ---------- 3. Cipher decoding ----------
ALPHA = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def caesar(s, k):
    return re.sub("[A-Z]", lambda m: ALPHA[(ALPHA.index(m.group()) + k + 26) % 26], s)


def atbash(s):
    return re.sub("[A-Z]", lambda m: ALPHA[25 - ALPHA.index(m.group())], s)


def vigenere(s, key, direction=1):
    j = [0]

    def sub(m):
        out = ALPHA[(ALPHA.index(m.group()) + direction * ALPHA.index(key[j[0] % len(key)]) + 26) % 26]
        j[0] += 1
        return out
    return re.sub("[A-Z]", sub, s)


def normalize_letters(s):
    return re.sub("[^A-Z]", "", s.upper())


class Cipher:
    id, version = 3, 1

    @staticmethod
    def generate(rng, level):
        n = min(1 + level // 6, 3)
        plain = " ".join(rng.pick(PHRASES) for _ in range(n)).upper()
        if level < 8:
            k = rng.int(1, 25)
            kind, cipher_text = "Caesar shift", caesar(plain, k)
            key_info = f"Each letter was shifted forward by {k}." if level <= 3 else "Shift unknown — look for short words."
        elif level < 15:
            kind, cipher_text, key_info = "Atbash", atbash(plain), "A↔Z, B↔Y, C↔X …"
        else:
            key = rng.pick(["SKILL", "FOCUS", "LOGIC", "TEMPO", "GEMS"])
            kind, cipher_text, key_info = "Vigenère", vigenere(plain, key), f"Keyword: {key}"
        no_spaces = level >= 12
        if no_spaces:
            cipher_text = cipher_text.replace(" ", "")
        return {
            "publicData": {"prompt": "Decode the message.", "cipher": kind, "normalization": "Letters only; case, spaces and punctuation ignored. 95% passes."},
            "stimulus": {"cipherText": cipher_text, "keyInfo": key_info, "cipher": kind}, "answer": {"plain": plain}, "maxAttempts": 1,
            "modifiers": ["Missing spaces"] if no_spaces else [], "answerReveal": plain, "timeLimitSec": 240,
        }

    @staticmethod
    def evaluate(g, sub, ctx):
        exp = normalize_letters(g["answer"]["plain"])
        raw = _get(sub, "answer")
        got = normalize_letters("" if raw is None else str(raw))
        same_count = sum(1 for i, ch in enumerate(exp) if i < len(got) and got[i] == ch)
        pct = same_count / max(len(exp), len(got)) if exp else 0
        score = js_round(pct * 100)
        return {"score": score, "passed": pct >= 0.95,
                "feedback": [f"{score}% of letters correct."] if pct >= 0.95 else [f"{score}% of letters in the right place (95% needed)."],
                "metrics": {"letterAccuracy": score}}

    @staticmethod
    def hint(g, used):
        return f"The first word is “{g['answer']['plain'].split(' ')[0]}”." if used == 0 else None


# ---------- 4. Wordle-style ----------
def wordle_feedback(guess, target):
    res = ["x"] * len(target)
    counts = {}
    for i, ch in enumerate(target):
        if at(guess, i) == ch:
            res[i] = "g"
        else:
            counts[ch] = counts.get(ch, 0) + 1
    for i in range(len(target)):
        g = at(guess, i)
        if res[i] != "g" and counts.get(g, 0) > 0:
            res[i] = "y"
            counts[g] -= 1
    return res


class Wordle:
    id, version = 4, 1

    @staticmethod
    def generate(rng, level):
        length = 4 if level < 6 else 5 if level < 15 else 6
        mx = 7 if level < 6 else 6
        hard = level >= 10
        word = rng.pick(WORDS[length]).upper()
        return {"publicData": {"prompt": f"Guess the {length}-letter word.", "length": length, "hardMode": hard},
                "stimulus": {"length": length}, "answer": {"word": word}, "maxAttempts": mx,
                "modifiers": ["Hard mode"] if hard else [], "answerReveal": word}

    @staticmethod
    def guess(g, state, payload, used, mx):
        raw = _get(payload, "guess")
        guess = ("" if raw is None else str(raw)).upper().strip()
        word = g["answer"]["word"]
        history = state.get("history") or []
        if len(guess) != len(word) or not re.fullmatch("[A-Z]+", guess):
            return {"state": state, "error": f"Enter {len(word)} letters."}
        if guess.lower() not in GUESS_WORDS[len(word)]:
            return {"state": state, "error": "Not in the word list — that guess wasn't counted."}
        if g["publicData"].get("hardMode"):
            for h in history:
                for i, ch in enumerate(h["guess"]):
                    if h["marks"][i] == "g" and guess[i] != ch:
                        return {"state": state, "error": f"Hard mode: position {i + 1} must be {ch}."}
                    if h["marks"][i] == "y" and ch not in guess:
                        return {"state": state, "error": f"Hard mode: your guess must contain {ch}."}
        marks = wordle_feedback(guess, word)
        nxt = {**state, "history": [*history, {"guess": guess, "marks": marks}]}
        n = used + 1
        if guess == word:
            return {"state": nxt, "done": {"score": js_round((mx - n + 1) / mx * 100), "passed": True, "feedback": [f"Solved in {n}/{mx}."], "metrics": {"guesses": n}}}
        if n >= mx:
            return {"state": nxt, "done": fail([f"Out of guesses. The word was {word}."], {"guesses": n})}
        return {"state": nxt}

    @staticmethod
    def hint(g, used):
        w = g["answer"]["word"]
        return f"The word contains the letter {w[len(w) // 2]}." if used == 0 else None


# ---------- 5. Vocabulary ----------
class Vocab:
    id, version = 5, 1

    @staticmethod
    def generate(rng, level):
        tier = 1 if level < 6 else 2 if level < 15 else 3
        synonyms = level >= 10
        pool = [e for e in LEXICON if e["tier"] == tier]
        items = []
        for e in rng.shuffle(pool)[:5]:
            others = rng.shuffle([o for o in pool if o["word"] != e["word"]])[:3]
            opts = rng.shuffle([e, *others])
            if synonyms and rng.chance(0.5):
                items.append({"q": f"Closest synonym of “{e['word']}”", "options": [o["syn"] for o in opts], "correct": opts.index(e)})
            else:
                items.append({"q": f"Which word means: “{e['def']}”?", "options": [o["word"] for o in opts], "correct": opts.index(e)})
        return {
            "publicData": {"prompt": "Five items. 4 correct passes.", "tier": tier, "count": 5},
            "stimulus": {"items": [{"q": i["q"], "options": i["options"]} for i in items]},
            "answer": {"correct": [i["correct"] for i in items], "items": items}, "maxAttempts": 1,
            "modifiers": ["Synonyms"] if synonyms else [], "timeLimitSec": 120,
        }

    @staticmethod
    def evaluate(g, sub, ctx):
        ans = _get(sub, "answers")
        ans = ans if isinstance(ans, list) else []
        items = g["answer"]["items"]
        right = sum(1 for i, it in enumerate(items) if same(at(ans, i), it["correct"]))
        wrong = [f"{it['q']} → {it['options'][it['correct']]}" for i, it in enumerate(items) if not same(at(ans, i), it["correct"])]
        return {"score": right * 20, "passed": right >= 4, "feedback": [f"{right}/5 correct.", *wrong], "metrics": {"correct": right}}


# ---------- 6. Typing gauntlet ----------
def levenshtein(a, b):
    dp = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, len(b) + 1):
            tmp = dp[j]
            dp[j] = min(dp[j] + 1, dp[j - 1] + 1, prev + (0 if a[i - 1] == b[j - 1] else 1))
            prev = tmp
    return dp[len(b)]


class Typing:
    id, version = 6, 1

    @staticmethod
    def generate(rng, level):
        n = min(10 + level, 50)
        symbols = level >= 10
        words = []
        for _ in range(n):
            if symbols and rng.chance(0.15):
                words.append(rng.pick(["42", "3.14", "#7", "$20", "x+y", "(ok)", "a/b", "99%", "@home"]))
            else:
                words.append(rng.pick(TYPING_WORDS))
        passage = " ".join(words)
        min_accuracy = min(0.98, 0.9 + level * 0.004)
        min_wpm = min(70, 18 + level * 1.5)
        return {
            "publicData": {"prompt": "Type the passage exactly. Paste is disabled and pasted runs score 0. Backspace is allowed.", "words": n, "minAccuracy": min_accuracy, "minWpm": min_wpm},
            "stimulus": {"passage": passage}, "answer": {"passage": passage}, "maxAttempts": 1,
            "modifiers": ["Numbers & symbols"] if symbols else [], "timeLimitSec": 300,
        }

    @staticmethod
    def evaluate(g, sub, ctx):
        raw = _get(sub, "text")
        typed = "" if raw is None else str(raw)
        if _get(sub, "pasted"):
            return fail(["Paste was detected, so this run scores 0. Type it to earn credit."])
        passage = g["answer"]["passage"]
        ms = js_number(_get(sub, "elapsedMs")) if isinstance(sub, dict) and "elapsedMs" in sub else math.nan
        server = ctx.get("serverElapsedMs")
        if not math.isfinite(ms) or ms <= 0 or (server is not None and ms > server + 1500):
            ms = server if server is not None else 60000
        dist = levenshtein(typed, passage)
        accuracy = max(0, 1 - dist / len(passage))
        wpm = len(passage) / 5 / (ms / 60000)
        min_accuracy, min_wpm = g["publicData"]["minAccuracy"], g["publicData"]["minWpm"]
        passed = accuracy >= min_accuracy and wpm >= min_wpm
        score = js_round(100 * accuracy ** 3 * min(1, wpm / min_wpm))
        return {
            "score": score, "passed": passed,
            "feedback": [f"{to_fixed(accuracy * 100, 1)}% accuracy ({dist} edits) at {to_fixed(wpm, 0)} WPM.",
                         f"Needed ≥ {to_fixed(min_accuracy * 100, 1)}% and ≥ {to_fixed(min_wpm, 0)} WPM."],
            "metrics": {"accuracyPct": r1(accuracy * 100), "wpm": js_round(wpm), "edits": dist},
        }


# ---------- 7. Mastermind ----------
def mastermind_score(guess, code):
    exact = 0
    cg, cc = {}, {}
    for i, c in enumerate(code):
        g = at(guess, i)
        if g == c:
            exact += 1
        else:
            cc[c] = cc.get(c, 0) + 1
            cg[g] = cg.get(g, 0) + 1
    misplaced = sum(min(v, cc.get(k, 0)) for k, v in cg.items())
    return {"exact": exact, "misplaced": misplaced}


class Mastermind:
    id, version = 7, 1

    @staticmethod
    def generate(rng, level):
        positions = 4 if level < 8 else 5 if level < 16 else 6
        symbols = 6 if level < 8 else 7 if level < 16 else 8
        mx = 10 if level < 8 else 9 if level < 16 else 8
        dup = level >= 6
        if dup:
            code = [rng.int(0, symbols - 1) for _ in range(positions)]
        else:
            code = rng.shuffle(list(range(symbols)))[:positions]
        return {"publicData": {"prompt": "Crack the hidden code.", "positions": positions, "symbols": symbols, "duplicates": dup},
                "stimulus": {"positions": positions, "symbols": symbols}, "answer": {"code": code}, "maxAttempts": mx,
                "modifiers": ["Duplicates allowed"] if dup else []}

    @staticmethod
    def guess(g, state, payload, used, mx):
        raw = _get(payload, "guess")
        guess = [js_number(x) for x in raw] if isinstance(raw, list) else []
        positions, symbols = g["publicData"]["positions"], g["publicData"]["symbols"]
        if len(guess) != positions or any(not is_integer(x) or x < 0 or x >= symbols for x in guess):
            return {"state": state, "error": f"Pick {positions} colors."}
        guess = [int(x) for x in guess]
        fb = mastermind_score(guess, g["answer"]["code"])
        history = [*(state.get("history") or []), {"guess": guess, **fb}]
        n = used + 1
        if fb["exact"] == positions:
            return {"state": {"history": history}, "done": {"score": js_round((mx - n + 1) / mx * 100), "passed": True, "feedback": [f"Cracked in {n}/{mx}."], "metrics": {"guesses": n}}}
        if n >= mx:
            return {"state": {"history": history}, "done": fail(["Out of tries."], {"guesses": n})}
        return {"state": {"history": history}}


# ---------- 8. Lights Out ----------
def lights_press(board, n, idx, wrap):
    b = list(board)
    r, c = idx // n, idx % n
    for rr, cc in ((r, c), (r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
        if wrap:
            rr, cc = (rr + n) % n, (cc + n) % n
        elif rr < 0 or cc < 0 or rr >= n or cc >= n:
            continue
        k = rr * n + cc
        b[k] = 0 if b[k] else 1
    return b


class Lights:
    id, version = 8, 1

    @staticmethod
    def generate(rng, level):
        n = 3 if level < 5 else 4 if level < 12 else 5
        wrap = level >= 10
        k = min(n * n - 1, 2 + level // 2)
        while True:
            board = [0] * (n * n)
            presses = rng.shuffle(list(range(n * n)))[:k]
            for p in presses:
                board = lights_press(board, n, p, wrap)
            if any(board):
                break
        move_limit = k + 3
        return {"publicData": {"prompt": "Turn every light off. Each press flips a cell and its neighbours.", "n": n, "wrap": wrap, "moveLimit": move_limit},
                "stimulus": {"n": n, "board": board, "wrap": wrap, "moveLimit": move_limit}, "answer": {"presses": presses}, "maxAttempts": 1,
                "modifiers": ["Wraparound edges"] if wrap else []}

    @staticmethod
    def evaluate(g, sub, ctx):
        raw = _get(sub, "moves")
        moves = [js_number(m) for m in raw] if isinstance(raw, list) else []
        s = g["stimulus"]
        n, board, wrap, move_limit = s["n"], s["board"], s["wrap"], s["moveLimit"]
        if any(not is_integer(m) or m < 0 or m >= n * n for m in moves):
            return fail(["Illegal move submitted."])
        b = board
        for m in moves:
            b = lights_press(b, n, int(m), wrap)
        lit = sum(1 for x in b if x)
        par = len(g["answer"]["presses"])
        if lit:
            return fail([f"{lit} light{'' if lit == 1 else 's'} still on after {len(moves)} moves.", f"A {par}-move solution existed."], {"moves": len(moves)})
        if len(moves) > move_limit:
            return fail([f"Solved, but in {len(moves)} moves (limit {move_limit})."], {"moves": len(moves)})
        score = 100 if len(moves) <= par else js_round(100 - ((len(moves) - par) / 3) * 40)
        return {"score": score, "passed": True, "feedback": [f"Solved in {len(moves)} moves (par {par})."], "metrics": {"moves": len(moves), "par": par}}


# ---------- 10. Base conversion / units ----------
UNIT_CHAINS = [
    {"from": "km", "to": "cm", "f": 100000}, {"from": "h", "to": "s", "f": 3600}, {"from": "ft", "to": "in", "f": 12},
    {"from": "mi", "to": "ft", "f": 5280}, {"from": "kg", "to": "g", "f": 1000}, {"from": "day", "to": "min", "f": 1440},
    {"from": "L", "to": "mL", "f": 1000}, {"from": "yd", "to": "in", "f": 36}, {"from": "m²", "to": "cm²", "f": 10000},
]
BASE_NAMES = {2: "binary", 16: "hexadecimal", 10: "decimal"}


class Base:
    id, version = 10, 1

    @staticmethod
    def generate(rng, level):
        if level >= 15:
            u = rng.pick(UNIT_CHAINS)
            v = rng.int(2, 40) / 4
            value = v * u["f"]
            return {"publicData": {"prompt": "Convert the quantity. ±0.5% tolerance.", "kind": "units"},
                    "stimulus": {"question": f"{js_str(v)} {u['from']} = ? {u['to']}", "target": u["to"], "kind": "units"},
                    "answer": {"value": value, "kind": "units"}, "maxAttempts": 1, "modifiers": ["Unit chains"],
                    "answerReveal": f"{js_str(value)} {u['to']}", "timeLimitSec": 90}
        mx = 15 + level * 25
        v = rng.int(5, mx)
        pairs = [(10, 2)] if level < 4 else [(2, 10)] if level < 7 else [(10, 16), (16, 10)] if level < 10 else [(2, 16), (16, 2), (10, 16), (16, 10)]
        from_b, to_b = rng.pick(pairs)
        shown = to_base(v, from_b).upper()
        return {
            "publicData": {"prompt": "Convert the number.", "kind": "base"},
            "stimulus": {"question": f"{shown} ({BASE_NAMES[from_b]}) → {BASE_NAMES[to_b]}", "target": BASE_NAMES[to_b], "toBase": to_b, "kind": "base"},
            "answer": {"value": v, "toBase": to_b, "kind": "base"}, "maxAttempts": 1, "modifiers": ["Binary ↔ hex"] if level >= 10 else [],
            "answerReveal": to_base(v, to_b).upper(), "timeLimitSec": 90,
        }

    @staticmethod
    def evaluate(g, sub, ctx):
        raw_in = _get(sub, "answer")
        raw = re.sub(r"\s+", "", ("" if raw_in is None else str(raw_in)).strip())
        a = g["answer"]
        if a["kind"] == "units":
            v = parse_number(re.sub("[a-zA-Z²]+$", "", raw))
            if v is None:
                return fail([f"Enter a number. Expected {js_str(a['value'])}."])
            rel = abs(v - a["value"]) / a["value"]
            if rel <= 0.005:
                return {"score": 100, "passed": True, "feedback": [f"Correct: {js_str(a['value'])}."], "metrics": {"relErrPct": r1(rel * 100)}}
            return fail([f"Expected {js_str(a['value'])}; you were {js_str(r1(rel * 100))}% off."], {"relErrPct": r1(rel * 100)})
        patterns = {2: r"^(0b)?[01]+$", 10: r"^\d+$", 16: r"^(0x)?[0-9a-f]+$"}
        expected = to_base(a["value"], a["toBase"]).upper()
        if not re.match(patterns[a["toBase"]], raw, re.IGNORECASE | re.ASCII):
            return fail([f"That isn't valid {BASE_NAMES[a['toBase']]}. Expected {expected}."])
        v = int(re.sub("^0[bx]", "", raw, flags=re.IGNORECASE) or "0", a["toBase"])
        if v == a["value"]:
            return {"score": 100, "passed": True, "feedback": [f"Correct: {expected}."], "metrics": {}}
        return fail([f"Expected {expected}; yours equals {v} in decimal (target {a['value']})."])


# ---------- 11. Sequence memory ----------
class Sequence:
    id, version = 11, 1

    @staticmethod
    def generate(rng, level):
        size = 4 if level >= 15 else 3
        length = min(3 + level // 2, 14)
        step_ms = max(320, 800 - level * 20)
        reverse = level >= 10 and rng.chance(0.5)
        seq = []
        while len(seq) < length:
            c = rng.int(0, size * size - 1)
            if not seq or c != seq[-1]:
                seq.append(c)
        return {
            "publicData": {"prompt": "Watch, then tap the cells in REVERSE order." if reverse else "Watch, then tap the cells in the same order.",
                           "size": size, "length": length, "stepMs": step_ms, "reverse": reverse, "showOnce": True},
            "stimulus": {"sequence": seq, "stepMs": step_ms, "size": size}, "answer": {"target": list(reversed(seq)) if reverse else seq},
            "maxAttempts": 1, "modifiers": ["Reverse order"] if reverse else [], "ephemeral": True,
        }

    @staticmethod
    def evaluate(g, sub, ctx):
        raw = _get(sub, "cells")
        inp = [js_number(x) for x in raw] if isinstance(raw, list) else []
        t = g["answer"]["target"]
        prefix = 0
        while prefix < len(t) and prefix < len(inp) and inp[prefix] == t[prefix]:
            prefix += 1
        ok = prefix == len(t) and len(inp) == len(t)
        step = js_str(t[prefix] + 1) if prefix < len(t) else "NaN"
        return {"score": js_round(prefix / len(t) * 100), "passed": ok,
                "feedback": [f"All {len(t)} in order."] if ok else [f"First {prefix} of {len(t)} correct; step {prefix + 1} was cell {step}."],
                "metrics": {"recalled": prefix, "length": len(t)}}


# ---------- 12. Mental rotation ----------
def norm(cells):
    mx = min(c[0] for c in cells)
    my = min(c[1] for c in cells)
    return sorted(([x - mx, y - my] for x, y in cells), key=lambda c: (c[0], c[1]))


def shape_key(cells):
    return json.dumps(norm(cells))


def rot(cells, k):
    c = cells
    for _ in range(k):
        c = [[y, -x] for x, y in c]
    return norm(c)


def mirror(cells):
    return norm([[-x, y] for x, y in cells])


class Rotation:
    id, version = 12, 1

    @staticmethod
    def generate(rng, level):
        size = min(5 + level // 8, 8)
        items, seen = [], set()
        dirs = [[1, 0], [-1, 0], [0, 1], [0, -1]]
        while len(items) < 5:
            cells = [[0, 0]]
            while len(cells) < size:
                x, y = rng.pick(cells)
                dx, dy = rng.pick(dirs)
                n = [x + dx, y + dy]
                if n not in cells:
                    cells.append(n)
            cells = norm(cells)
            variants = set()
            for k in range(4):
                variants.add(shape_key(rot(cells, k)))
                variants.add(shape_key(rot(mirror(cells), k)))
            if len(variants) != 8 or shape_key(cells) in seen:
                continue  # reject any symmetry -> exactly one answer
            seen.add(shape_key(cells))
            k = rng.int(1, 3)
            right = {"c": rot(cells, k), "ok": True}
            wrong = [{"c": rot(mirror(cells), j), "ok": False} for j in rng.shuffle([0, 1, 2, 3])[:3]]
            opts = rng.shuffle([right, *wrong])
            items.append({"shape": cells, "options": [o["c"] for o in opts], "correct": next(i for i, o in enumerate(opts) if o["ok"]), "angle": k * 90})
        return {
            "publicData": {"prompt": "Pick the option that is the same shape rotated (not mirrored). 4 of 5 passes.", "count": 5},
            "stimulus": {"items": [{"shape": i["shape"], "options": i["options"]} for i in items]}, "answer": {"items": items}, "maxAttempts": 1,
            "modifiers": ["Larger shapes"] if level >= 10 else [], "timeLimitSec": max(30, 90 - level * 2),
        }

    @staticmethod
    def evaluate(g, sub, ctx):
        ans = _get(sub, "answers")
        ans = ans if isinstance(ans, list) else []
        items = g["answer"]["items"]
        right = sum(1 for i, it in enumerate(items) if same(at(ans, i), it["correct"]))
        misses = [f"Item {i + 1}: option {it['correct'] + 1} (rotated {it['angle']}°); the others are mirror images."
                  for i, it in enumerate(items) if not same(at(ans, i), it["correct"])]
        return {"score": right * 20, "passed": right >= 4, "feedback": [f"{right}/5 correct.", *misses], "metrics": {"correct": right}}


# ---------- 13. Odd-one-out (color) ----------
class OddColor:
    id, version = 13, 1

    @staticmethod
    def generate(rng, level):
        n = min(8, 3 + level // 3)
        delta = max(2.5, 16 - level * 0.9)
        rounds = []
        for _ in range(5):
            h, s, l = rng.int(0, 359), rng.int(45, 75), rng.int(38, 58)
            odd = rng.int(0, n * n - 1)
            rounds.append({"n": n, "base": {"h": h, "s": s, "l": l}, "oddColor": {"h": h, "s": s, "l": l + delta}, "odd": odd})
        return {
            "publicData": {"prompt": "Each board has one tile that is slightly lighter. Tap it. 4 of 5 passes.", "n": n, "deltaPct": r1(delta)},
            "stimulus": {"rounds": [{"n": r["n"], "cells": [r["oddColor"] if i == r["odd"] else r["base"] for i in range(r["n"] * r["n"])]} for r in rounds]},
            "answer": {"odd": [r["odd"] for r in rounds]}, "maxAttempts": 1, "modifiers": [], "timeLimitSec": 90,
        }

    @staticmethod
    def evaluate(g, sub, ctx):
        ans = _get(sub, "answers")
        ans = ans if isinstance(ans, list) else []
        right = sum(1 for i, o in enumerate(g["answer"]["odd"]) if same(at(ans, i), o))
        delta = g["publicData"]["deltaPct"]
        return {"score": right * 20, "passed": right >= 4, "feedback": [f"{right}/5 found at a {js_str(delta)}% lightness difference."],
                "metrics": {"correct": right, "deltaPct": delta}}


# ---------- 14. Dot count ----------
class Dots:
    id, version = 14, 1

    @staticmethod
    def generate(rng, level):
        two_color = level >= 10
        count = min(8 + level * 3, 150)
        flash_ms = max(350, 1600 - level * 50)
        pts = []
        min_d = 0.6 / math.sqrt(count + (count / 2 if two_color else 0))
        total = count + js_round(count * rng.int(3, 7) / 10) if two_color else count
        guard = 0
        while len(pts) < total and guard < 20000:
            guard += 1
            p = {"x": rng.next() * 0.94 + 0.03, "y": rng.next() * 0.94 + 0.03, "c": 0 if len(pts) < count else 1}
            if all(math.hypot(q["x"] - p["x"], q["y"] - p["y"]) > min_d for q in pts):
                pts.append(p)
        real = sum(1 for p in pts if p["c"] == 0)
        return {
            "publicData": {"prompt": "Count only the GOLD dots. Shown once." if two_color else "Estimate how many dots flash. Shown once.",
                           "flashMs": flash_ms, "twoColor": two_color, "showOnce": True},
            "stimulus": {"dots": rng.shuffle(pts), "flashMs": flash_ms}, "answer": {"count": real}, "maxAttempts": 1,
            "modifiers": ["Two colors"] if two_color else [], "ephemeral": True, "answerReveal": str(real),
        }

    @staticmethod
    def evaluate(g, sub, ctx):
        guess = parse_number(_get(sub, "answer"))
        n = g["answer"]["count"]
        if guess is None:
            return fail([f"There were {n}."])
        rel = abs(guess - n) / n
        score = js_round(100 * clamp(1 - 2 * rel, 0, 1))
        how = "over" if guess > n else "under" if guess < n else "exact"
        return {"score": score, "passed": score >= 75,
                "feedback": [f"There were {n}; you said {js_str(guess)} ({how} by {js_str(abs(guess - n))}, {js_str(r1(rel * 100))}%)."],
                "metrics": {"error": guess - n, "relErrPct": r1(rel * 100)}}


# ---------- 15. Trajectory landing ----------
class Trajectory:
    id, version = 15, 1

    @staticmethod
    def generate(rng, level):
        wind = level >= 10
        visible = max(0.2, 0.6 - level * 0.02)
        rounds = []
        while len(rounds) < 3:
            y0 = 0.1 + rng.next() * 0.4
            vx = 0.25 + rng.next() * 0.35
            vy = 0.3 + rng.next() * 0.6
            g = 0.9 + rng.next() * 0.6
            ax = (rng.next() - 0.5) * 0.3 if wind else 0
            T = (vy + math.sqrt(vy * vy + 2 * g * y0)) / g
            landing = 0.05 + vx * T + 0.5 * ax * T * T
            peak = y0 + (vy * vy) / (2 * g)
            if landing < 0.4 or landing > 0.95 or peak > 0.95:
                continue
            pts = []
            for i in range(24):
                t = (i / 23) * T * visible
                x, y = 0.05 + vx * t + 0.5 * ax * t * t, y0 + vy * t - 0.5 * g * t * t
                pts.append([js_round(x * 1000) / 1000, js_round(y * 1000) / 1000])
            rounds.append({"points": pts, "landing": landing, "windAccel": js_round(ax * 100) / 100})
        return {
            "publicData": {"prompt": "The ball's flight is cut off. Click where it will hit the ground. 3 throws; average 70 passes.", "visibleFraction": r1(visible), "wind": wind},
            "stimulus": {"rounds": [{"points": r["points"], "wind": (("→" if r["windAccel"] > 0 else "←") + " wind") if wind else None} for r in rounds]},
            "answer": {"landing": [r["landing"] for r in rounds]}, "maxAttempts": 1, "modifiers": ["Wind"] if wind else [], "timeLimitSec": 90,
        }

    @staticmethod
    def evaluate(g, sub, ctx):
        raw = _get(sub, "answers")
        xs = [js_number(x) for x in raw] if isinstance(raw, list) else []
        lands = g["answer"]["landing"]
        errs = [at(xs, i) - l if finite(at(xs, i, math.nan)) else 1 for i, l in enumerate(lands)]
        scores = [100 * clamp(1 - abs(e) / 0.2, 0, 1) for e in errs]
        score = js_round(sum(scores) / len(scores))
        return {"score": score, "passed": score >= 70,
                "feedback": [f"Throw {i + 1}: {to_fixed(abs(e * 100), 1)}% of the width {'too far' if e > 0 else 'too short'}." for i, e in enumerate(errs)],
                "metrics": {"meanErrPct": r1(sum(abs(e) for e in errs) / len(errs) * 100)}}


# ---------- 16. Angle matching ----------
def circular_error(a, b):
    d = (((a - b) % 360) + 540) % 360 - 180
    return abs(d)


class Angle:
    id, version = 16, 1

    @staticmethod
    def generate(rng, level):
        tol = max(3, 15 - level // 2)
        hidden = level >= 10
        targets = [rng.int(0, 359), rng.int(0, 359), rng.int(0, 359)]
        starts = [rng.int(0, 359) for _ in targets]
        return {
            "publicData": {"prompt": "Memorise the target angle — it hides before you rotate the dial." if hidden else "Rotate the dial to the target angle. 0° points straight up and angles grow clockwise.",
                           "toleranceDeg": tol, "hidden": hidden},
            "stimulus": {"rounds": [{"target": t, "start": starts[i]} for i, t in enumerate(targets)], "hideAfterMs": 1500 if hidden else None},
            "answer": {"targets": targets}, "maxAttempts": 1, "modifiers": ["Target hides"] if hidden else [], "timeLimitSec": 90,
        }

    @staticmethod
    def evaluate(g, sub, ctx):
        raw = _get(sub, "answers")
        ans = [js_number(x) for x in raw] if isinstance(raw, list) else []
        t = g["answer"]["targets"]
        tol = g["publicData"]["toleranceDeg"]
        signed = []
        for i, x in enumerate(t):
            v = at(ans, i)
            v = x + 180 if v is None or not math.isfinite(v) else v
            signed.append((((v - x) % 360) + 540) % 360 - 180)
        errs = [abs(d) for d in signed]
        mean = sum(errs) / len(errs)
        score = js_round(100 * clamp(1 - mean / (3 * tol), 0, 1))

        def side(d):
            return "clockwise" if d > 0 else "counter-clockwise" if d < 0 else ""
        return {"score": score, "passed": mean <= tol,
                "feedback": [f"Mean error {js_str(r1(mean))}° (tolerance {tol}°).", *[f"Round {i + 1}: {js_str(r1(abs(d)))}° {side(d)} of target." for i, d in enumerate(signed)]],
                "metrics": {"meanErrDeg": r1(mean)}}


# ---------- 17. Tempo keeping ----------
class Tempo:
    id, version = 17, 1

    @staticmethod
    def generate(rng, level):
        bpm = min(70 + level * 4 + rng.int(0, 6), 180)
        audible = 4
        silent = min(4 + level // 2, 16)
        return {
            "publicData": {"prompt": f"Tap (space or button) on every beat. {audible} beats play, then keep tapping through {silent} silent beats.",
                           "bpm": bpm, "audibleBeats": audible, "silentBeats": silent},
            "stimulus": {"bpm": bpm, "audibleBeats": audible, "silentBeats": silent}, "answer": {"bpm": bpm, "audible": audible, "silent": silent},
            "maxAttempts": 1, "modifiers": [],
        }

    @staticmethod
    def evaluate(g, sub, ctx):
        if _get(sub, "interrupted"):
            return {"score": 0, "passed": False, "void": True, "feedback": ["The tab was hidden or audio stopped, so the run was voided — no penalty."], "metrics": {}}
        raw = _get(sub, "taps")
        taps = sorted(x for x in ([js_number(t) for t in raw] if isinstance(raw, list) else []) if math.isfinite(x))
        bpm, audible, silent = g["answer"]["bpm"], g["answer"]["audible"], g["answer"]["silent"]
        iv = 60000 / bpm
        used, errs = set(), []
        for j in range(silent):
            t = (audible + j) * iv
            best, best_d = -1, math.inf
            for i, x in enumerate(taps):
                d = abs(x - t)
                if i not in used and d < best_d and d <= iv / 2:
                    best, best_d = i, d
            if best >= 0:
                used.add(best)
                errs.append(taps[best] - t)
            else:
                errs.append(None)
        hit = [e for e in errs if e is not None]
        missed = silent - len(hit)
        if not hit:
            return fail([f"No taps matched the {silent} silent beats."], {"missed": missed})
        mean_signed = sum(hit) / len(hit)
        mean_abs = sum(abs(e) for e in hit) / len(hit)
        half = len(hit) // 2
        drift = (sum(hit[-half:]) / half - sum(hit[:half]) / half) if half else 0
        score = js_round(100 * clamp(1 - mean_abs / (iv * 0.25), 0, 1) * (len(hit) / silent))
        trend = " — you slowed down" if drift > 15 else " — you sped up" if drift < -15 else ""
        return {
            "score": score, "passed": score >= 60,
            "feedback": [f"Your taps averaged {abs(js_round(mean_signed))} ms {'early' if mean_signed < 0 else 'late'} (mean |error| {js_round(mean_abs)} ms at {js_round(iv)} ms per beat).",
                         f"Drift: {'+' if drift > 0 else ''}{js_round(drift)} ms from first to second half{trend}.",
                         f"Missed {missed} beat{'s' if missed > 1 else ''}." if missed else "No missed beats."],
            "metrics": {"meanErrMs": js_round(mean_signed), "meanAbsMs": js_round(mean_abs), "driftMs": js_round(drift), "missed": missed},
        }


# ---------- 18. Line splitting ----------
class Line:
    id, version = 18, 1

    @staticmethod
    def generate(rng, level):
        denoms = [2, 4] if level < 4 else [3, 5] if level < 7 else [6, 7, 8]
        from_end = level >= 10
        pct = level >= 25
        tol = max(0.015, 0.05 - level * 0.002)
        rounds = []
        for _ in range(3):
            q = rng.pick(denoms)
            p = rng.int(1, q - 1)
            right = from_end and rng.chance(0.5)
            v = js_round(p / q * 100) / 100 if pct else p / q
            rounds.append({"label": f"{js_round(v * 100)}%" if pct else f"{p}/{q}", "origin": "right" if right else "left", "target": 1 - v if right else v})
        return {
            "publicData": {"prompt": "Click the point that splits the line at the given fraction, measured from the marked end.", "tolerance": r1(tol * 1000) / 1000},
            "stimulus": {"rounds": [{"label": r["label"], "origin": r["origin"]} for r in rounds]},
            "answer": {"targets": [r["target"] for r in rounds], "tol": tol}, "maxAttempts": 1, "modifiers": ["Far-end origin"] if from_end else [], "timeLimitSec": 60,
        }

    @staticmethod
    def evaluate(g, sub, ctx):
        raw = _get(sub, "answers")
        xs = [js_number(x) for x in raw] if isinstance(raw, list) else []
        targets, tol = g["answer"]["targets"], g["answer"]["tol"]
        errs = [at(xs, i) - t if finite(at(xs, i, math.nan)) else 1 for i, t in enumerate(targets)]
        mean = sum(abs(e) for e in errs) / len(errs)
        score = js_round(100 * clamp(1 - mean / (tol * 4), 0, 1))
        return {"score": score, "passed": mean <= tol,
                "feedback": [f"Mean error {js_str(r1(mean * 100))}% of the line (tolerance {js_str(r1(tol * 100))}%).",
                             *[f"Line {i + 1}: {js_str(r1(abs(e) * 100))}% {'right' if e > 0 else 'left'} of target." for i, e in enumerate(errs)]],
                "metrics": {"meanErrPct": r1(mean * 100)}}


# ---------- 19. Time estimation ----------
class TimeEstimate:
    id, version = 19, 1

    @staticmethod
    def generate(rng, level):
        target = min(2000 + level * 500 + rng.int(0, 4) * 100, 20000)
        tol = max(0.03, 0.12 - level * 0.004)
        distraction = level >= 10
        return {
            "publicData": {"prompt": f"Press Ready, then press Stop when exactly {to_fixed(target / 1000, 1)} s have passed. No clock is shown.",
                           "targetMs": target, "tolerancePct": r1(tol * 100), "distraction": distraction},
            "stimulus": {"targetMs": target, "distraction": distraction}, "answer": {"target": target, "tol": tol}, "maxAttempts": 1,
            "modifiers": ["Distraction"] if distraction else [],
        }

    @staticmethod
    def evaluate(g, sub, ctx):
        if _get(sub, "hidden"):
            return {"score": 0, "passed": False, "void": True, "feedback": ["The tab was hidden during timing, so the run was voided — no penalty."], "metrics": {}}
        ms = js_number(_get(sub, "elapsedMs")) if isinstance(sub, dict) and "elapsedMs" in sub else math.nan
        if not math.isfinite(ms) or ms <= 0:
            return fail(["No timing received."])
        server = ctx.get("serverElapsedMs")
        if server is not None and abs(ms - server) > 3000:
            return {"score": 0, "passed": False, "void": True, "feedback": ["Device timing and server timing disagreed by more than 3 s, so the run was voided."], "metrics": {}}
        target, tol = g["answer"]["target"], g["answer"]["tol"]
        rel = (ms - target) / target
        score = js_round(100 * clamp(1 - abs(rel) / 0.25, 0, 1))
        return {"score": score, "passed": abs(rel) <= tol,
                "feedback": [f"You stopped at {to_fixed(ms / 1000, 2)} s — {abs(js_round(ms - target))} ms {'late' if rel > 0 else 'early'} ({js_str(r1(abs(rel) * 100))}%, tolerance {js_str(r1(tol * 100))}%)."],
                "metrics": {"errorMs": js_round(ms - target), "relErrPct": r1(rel * 100)}}


# ---------- 20. Pitch matching ----------
class Pitch:
    id, version = 20, 1

    @staticmethod
    def generate(rng, level):
        semis = rng.int(0, 24)
        target = 220 * 2 ** (semis / 12 + (rng.next() - 0.5) / 12)
        tol = max(5, 50 - level * 3)
        once = level >= 10
        below = 0.25 + rng.next() * 0.5  # slider spans one octave around target, offset randomly
        return {
            "publicData": {"prompt": "The reference plays once. Tune your tone to match it." if once else "Tune your tone to match the reference.",
                           "toleranceCents": tol, "playOnce": once},
            "stimulus": {"refHz": js_round(target * 100) / 100, "minHz": js_round(target * 2 ** (-below) * 100) / 100,
                         "maxHz": js_round(target * 2 ** (1 - below) * 100) / 100, "playOnce": once},
            "answer": {"target": target, "tol": tol}, "maxAttempts": 1, "modifiers": ["Reference plays once"] if once else [],
        }

    @staticmethod
    def evaluate(g, sub, ctx):
        hz = js_number(_get(sub, "hz")) if isinstance(sub, dict) and "hz" in sub else math.nan
        if not math.isfinite(hz) or hz <= 0:
            return fail(["No tone submitted."])
        target, tol = g["answer"]["target"], g["answer"]["tol"]
        c = 1200 * math.log2(hz / target)
        a = abs(c)
        score = js_round(100 * clamp(1 - a / (3 * tol), 0, 1))
        return {"score": score, "passed": a <= tol, "feedback": [f"{js_round(a)} cents {'sharp' if c > 0 else 'flat'} (tolerance {tol})."],
                "metrics": {"cents": js_round(c)}}


MODULES = {m.id: m for m in (Math1, Pattern, Cipher, Wordle, Vocab, Typing, Mastermind, Lights, Base, Sequence, Rotation, OddColor,
                             Dots, Trajectory, Angle, Tempo, Line, TimeEstimate, Pitch)}
