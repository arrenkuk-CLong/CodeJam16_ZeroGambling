"""Prints the slide game's tuning table from core/slide_balance.py.

    python manage.py slide_table              # markdown table, 300 simulated runs per level
    python manage.py slide_table --json       # the same rows as JSON
"""
import json

from django.core.management.base import BaseCommand

from core import slide_balance as sb


class Command(BaseCommand):
    help = "Print the slide game's balance table (steering, expected reach, checkpoint pay, upgrade costs)."

    def add_arguments(self, parser):
        parser.add_argument("--samples", type=int, default=300, help="simulated runs per level")
        parser.add_argument("--json", action="store_true")

    def handle(self, *args, samples, json: bool = False, **kw):
        rows = sb.table(samples)
        if json:
            self.stdout.write(_json(rows, sb.checkpoints()))
            return
        w = self.stdout.write
        w("| Glider | Steering /s | % of top | Target reach | Flawless reach p10 / median / p90 | "
          "Expected checkpoint | Pay | Upgrade to next | Runs per upgrade | Total invested |")
        w("|---|---|---|---|---|---|---|---|---|---|")
        for r in rows:
            lvl = "none" if r["level"] is None else str(r["level"])
            up = "buy: %d" % sb.GLIDER_PRICE if r["level"] is None else ("max" if r["upgrade_cost"] is None else str(r["upgrade_cost"]))
            runs = "" if r["runs_to_upgrade"] is None else "%.1f" % r["runs_to_upgrade"]
            w(f"| {lvl} | {r['steer']:.2f} | {round(100 * r['steer'] / sb.STEER_MAX)}% | {r['reach']:.0f} m | "
              f"{r['perfect_p10']:.0f} / {r['perfect_median']:.0f} / {r['perfect_p90']:.0f} m | "
              f"{r['expected_checkpoint']} m | {r['expected_gems']} | {up} | {runs} | "
              f"{'' if r['level'] is None else r['invested']} |")
        w("")
        w("Checkpoint pay (only the highest one passed counts): " +
          ", ".join(f"{c['m']} m = {c['gems']}" for c in sb.checkpoints()))


def _json(rows, checkpoints):
    return json.dumps({"levels": rows, "checkpoints": checkpoints}, indent=2)
