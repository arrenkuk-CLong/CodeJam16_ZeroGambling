"""Port of Lovable's test suites (engine, expanded, casino-rules, collectibles, accounts) plus API tests
for the Django services that replaced the Postgres functions. Run: venv\\Scripts\\python manage.py test core"""
import random
from datetime import timedelta

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from . import casino_engine as ce
from . import challenge_catalog as catalog
from . import slide_balance as sb
from .accounts import USERNAME_RE
from .casino_rules import (CASINO_GAMES, CASINO_VARIANTS, crash_target_step, expected_value, find_option, format_cents, parse_cents,
                           roulette_bets, roulette_wins)
from .challenges import MODULES, circular_error, lights_press, mastermind_score, wordle_feedback
from .economy import (compute_reward, equipment_stake_value, glider_stake_value, log_stake_value, next_level, skill_stake_value,
                      skill_value)
from .jscompat import Rng, to_base
from .models import (CasinoSession, ChallengeMastery, InventoryItem, LossLedger, Player, SlideRun, Trophy, WalletLedger)
from .services import can_claim
from .shop_catalog import COLLECTIBLE_TIERS, draw_collectibles
from .slide import settle_report

BASE = dict(passed=True, is_void=False, level=3, peak_before=3, hints=0, recent_same_game_passes=0, repeated_task=False)


def reward(**kw):
    return compute_reward(**{**BASE, **kw})


def correct_submission(game_id, g):
    a = g["answer"]
    return {
        1: lambda: {"answer": str(a["value"])},
        2: lambda: {"answers": [str(v) for v in a["answers"]]},
        3: lambda: {"answer": a["plain"].lower()},
        5: lambda: {"answers": a["correct"]},
        6: lambda: {"text": a["passage"], "elapsedMs": 1000, "pasted": False},
        8: lambda: {"moves": a["presses"]},
        10: lambda: {"answer": str(a["value"]) if a["kind"] == "units" else to_base(a["value"], a["toBase"])},
        11: lambda: {"cells": a["target"]},
        12: lambda: {"answers": [i["correct"] for i in a["items"]]},
        13: lambda: {"answers": a["odd"]},
        14: lambda: {"answer": str(a["count"])},
        15: lambda: {"answers": a["landing"]},
        16: lambda: {"answers": a["targets"]},
        17: lambda: {"taps": [i * 60000 / a["bpm"] for i in range(a["audible"] + a["silent"])]},
        18: lambda: {"answers": a["targets"]},
        19: lambda: {"elapsedMs": a["target"]},
        20: lambda: {"hz": a["target"]},
    }[game_id]()


class GameDifficultyAndSpeed(SimpleTestCase):
    def test_harder_games_pay_more_at_the_same_level(self):
        easy, medium, hard = reward(game_id=14)["gems"], reward(game_id=4)["gems"], reward(game_id=8)["gems"]
        self.assertEqual(easy, 11)  # 5 + 2*3, no change for easy games
        self.assertLess(easy, medium)
        self.assertLess(medium, hard)

    def test_levels_still_raise_pay_within_a_game(self):
        self.assertLess(reward(game_id=8, level=3)["gems"], reward(game_id=8, level=4)["gems"])

    def test_faster_solves_pay_more(self):
        slow, quick, fast = (reward(game_id=14, elapsed_sec=t)["gems"] for t in (60, 15, 5))
        self.assertLess(slow, quick)
        self.assertLess(quick, fast)

    def test_fixed_length_games_have_no_speed_bonus(self):
        self.assertEqual(reward(game_id=17, elapsed_sec=1)["gems"], reward(game_id=17)["gems"])

    def test_fails_still_pay_nothing(self):
        self.assertEqual(reward(passed=False, game_id=8, elapsed_sec=1)["gems"], 0)

    def test_wordle_accepts_any_real_word(self):
        from .challenges import GUESS_WORDS
        self.assertTrue({"crane", "glyph", "fjord"} <= GUESS_WORDS[5])


class Catalog(SimpleTestCase):
    def test_exactly_the_19_active_ids(self):
        self.assertEqual(catalog.ACTIVE_IDS, [1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20])

    def test_rejects_retracted_id_9(self):
        self.assertIsNone(catalog.get_entry(9))
        self.assertNotIn(9, MODULES)

    def test_a_module_for_every_active_id(self):
        for gid in catalog.ACTIVE_IDS:
            self.assertIn(gid, MODULES)


class Generators(SimpleTestCase):
    def test_reproducible_and_accept_their_own_answer(self):
        for gid in [i for i in catalog.ACTIVE_IDS if i not in (4, 7)]:
            for level in (1, 12, 30):
                g1 = MODULES[gid].generate(Rng(f"seed-{level}"), level)
                g2 = MODULES[gid].generate(Rng(f"seed-{level}"), level)
                self.assertEqual(g1, g2, f"#{gid} level {level}")
                server = g1["answer"]["target"] if gid == 19 else 1000
                ev = MODULES[gid].evaluate(g1, correct_submission(gid, g1), {"level": level, "serverElapsedMs": server})
                self.assertTrue(ev["passed"], f"#{gid} level {level}: {' '.join(ev['feedback'])}")

    def test_math_chain_accepts_fractions(self):
        g = {"answer": {"value": 0.5, "steps": []}}
        self.assertTrue(MODULES[1].evaluate(g, {"answer": "1/2"}, {})["passed"])
        self.assertFalse(MODULES[1].evaluate(g, {"answer": "0.4"}, {})["passed"])

    def test_wordle_repeated_letters(self):
        self.assertEqual(wordle_feedback("LLAMA", "HELLO"), ["y", "y", "x", "x", "x"])
        self.assertEqual(wordle_feedback("ALLOT", "HELLO"), ["x", "y", "g", "y", "x"])

    def test_wordle_and_mastermind_guesses(self):
        g = MODULES[4].generate(Rng("w"), 1)
        out = MODULES[4].guess(g, {}, {"guess": g["answer"]["word"]}, 0, g["maxAttempts"])
        self.assertTrue(out["done"]["passed"])
        self.assertIn("error", MODULES[4].guess(g, {}, {"guess": "zzzz"}, 0, 7))
        m = MODULES[7].generate(Rng("m"), 1)
        self.assertTrue(MODULES[7].guess(m, {}, {"guess": m["answer"]["code"]}, 0, m["maxAttempts"])["done"]["passed"])

    def test_mastermind_exact_before_misplaced(self):
        self.assertEqual(mastermind_score([0, 0, 1, 1], [0, 1, 0, 2]), {"exact": 1, "misplaced": 2})

    def test_angle_error_is_circular(self):
        self.assertEqual(circular_error(359, 1), 2)

    def test_lights_out_replays_to_solved(self):
        g = MODULES[8].generate(Rng("x"), 3)
        b = g["stimulus"]["board"]
        for p in g["answer"]["presses"]:
            b = lights_press(b, g["stimulus"]["n"], p, g["stimulus"]["wrap"])
        self.assertTrue(all(x == 0 for x in b))

    def test_sequence_memory_is_shown_once(self):
        self.assertTrue(MODULES[11].generate(Rng("s"), 1)["ephemeral"])

    def test_tempo_reports_late_taps_in_ms(self):
        g = MODULES[17].generate(Rng("t"), 1)
        iv = 60000 / g["answer"]["bpm"]
        ev = MODULES[17].evaluate(g, {"taps": [i * iv + 80 for i in range(g["answer"]["audible"] + g["answer"]["silent"])]}, {})
        self.assertEqual(ev["metrics"]["meanErrMs"], 80)
        self.assertIn("80 ms late", ev["feedback"][0])

    def test_many_seeds_generate(self):
        for gid, mod in MODULES.items():
            for s in range(15):
                for level in (1, 5, 10, 15, 25, 40):
                    mod.generate(Rng(f"{gid}-{s}-{level}"), level)


class Economy(SimpleTestCase):
    def test_pays_5_plus_2_per_level(self):
        self.assertEqual(reward()["gems"], 11)

    def test_half_when_rebuilding(self):
        self.assertEqual(reward(peak_before=8)["gems"], 6)

    def test_zero_for_fail_or_repeat(self):
        self.assertEqual(reward(passed=False)["gems"], 0)
        self.assertEqual(reward(repeated_task=True)["gems"], 0)

    def test_hint_halves(self):
        self.assertEqual(reward(level=10, peak_before=10, hints=1)["gems"], 13)

    def test_repeat_decays_to_40_percent(self):
        self.assertEqual(reward(level=10, peak_before=10, recent_same_game_passes=10)["gems"], 10)

    def test_band_floor(self):
        self.assertEqual(next_level(10, 12, False, False), 10)
        self.assertEqual(next_level(5, 5, True, False), 6)
        self.assertEqual(next_level(5, 5, False, True), 5)

    def test_every_casino_bet_is_negative(self):
        for g in CASINO_GAMES:
            for o in g["options"]:
                self.assertLess(expected_value(o), 0, f"{g['id']}/{o['id']}")
        self.assertEqual(find_option("roulette", "red")["profitMultiplier"], 1)


def cards(ranks, flush=False):
    return [{"r": r, "s": 1 if flush else s % 4} for s, r in enumerate(ranks)]


def hand(ranks, stake=1000, split=False):
    return {"cards": cards(ranks), "stakeCents": stake, "fromSplit": split, "splitAces": split and ranks[0] == 1, "doubled": False, "done": False, "bust": False}


def bj(player, dealer, deck=(), variant="classic"):
    return {"variant": variant, "dealer": cards(dealer), "deck": cards(list(deck)), "hands": [hand(player)], "activeHand": 0, "phase": "player",
            "insuranceCents": 0, "stakeCents": 1000}


class CasinoCatalog(SimpleTestCase):
    def test_seven_games(self):
        self.assertEqual([g["id"] for g in CASINO_GAMES], ["roulette", "blackjack", "slots", "baccarat", "crash", "sixdraw", "poker"])

    def test_payouts(self):
        self.assertEqual(find_option("baccarat", "banker")["profitMultiplier"], 0.95)
        self.assertEqual(find_option("sixdraw", "survive")["profitMultiplier"], 0.8)
        self.assertEqual(find_option("sixdraw", "survive")["p"], 0.5)

    def test_start_each_game(self):
        for game in CASINO_GAMES:
            result = ce.start_game(game["id"], game["options"][0]["id"])
            if game["id"] == "blackjack":
                self.assertEqual(len(result["state"]["hands"][0]["cards"]), 2)
            elif game["id"] in ("poker", "sixdraw"):
                self.assertIsNone(result.get("settlement"))
            else:
                self.assertIsNotNone(result.get("settlement"))

    def test_fifteen_tables(self):
        self.assertEqual(len(CASINO_VARIANTS), 15)
        self.assertEqual(len({v["game"] for v in CASINO_VARIANTS}), 7)
        self.assertTrue(all(v["rulesVersion"] == 2 and v["exposureLimitCents"] == 100000 for v in CASINO_VARIANTS))

    def test_exact_money(self):
        self.assertEqual(parse_cents("10.50"), 1050)
        self.assertEqual(parse_cents("0.01"), 1)
        self.assertIsNone(parse_cents("1.001"))
        self.assertIsNone(parse_cents("-1"))
        self.assertEqual(format_cents(-12345), "-123.45")

    def test_six_draw_labels(self):
        target = next(v for v in CASINO_VARIANTS if v["id"] == "target" and v["game"] == "sixdraw")
        self.assertEqual([o["label"] for o in target["options"]], ["1 safe · 1.08×", "2 safe · 1.35×", "3 safe · 1.80×", "4 safe · 2.70×", "5 safe · 5.40×"])


class CardRules(SimpleTestCase):
    def test_soft_17(self):
        self.assertEqual(ce.hand_value(cards([1, 6])), {"total": 17, "soft": True})

    def test_flush_beats_straight(self):
        straight, flush = cards([2, 3, 4, 5, 6]), cards([2, 5, 8, 11, 13], True)
        self.assertEqual(ce.poker_name(ce.evaluate_poker(straight)[0]), "Straight")
        self.assertEqual(ce.poker_name(ce.evaluate_poker(flush)[0]), "Flush")
        self.assertGreater(ce.compare_poker(flush, straight), 0)

    def test_ace_low_straight(self):
        self.assertEqual(ce.evaluate_poker(cards([1, 2, 3, 4, 5]))[0], 4)


class AssetValuation(SimpleTestCase):
    def test_skill_value_formula(self):
        self.assertAlmostEqual(skill_value(2, 20), 1.1)

    def test_level_2_rollback_is_one_gem(self):
        self.assertEqual(skill_stake_value(2, 1), 1)

    def test_equipment_half_price(self):
        self.assertEqual(equipment_stake_value(80), 40)

    def test_glider_levels_half_of_cost(self):
        self.assertEqual(glider_stake_value(1, 1), sb.upgrade_cost(0) // 2)
        self.assertEqual(glider_stake_value(2, 3), 0)
        self.assertEqual(glider_stake_value(0, 1), 0)

    def test_log_journal_cap(self):
        self.assertEqual(log_stake_value([2], 60), 51)


class Roulette(SimpleTestCase):
    def test_even_bet(self):
        self.assertTrue(roulette_wins("even", 2))
        self.assertTrue(roulette_wins("even", 36))
        self.assertFalse(roulette_wins("even", 0))
        self.assertFalse(roulette_wins("even", 17))
        self.assertAlmostEqual(find_option("roulette", "even")["p"], 18 / 37)

    def test_pockets_and_ticket_sizes(self):
        for variant in ("european", "french", "american"):
            size = 38 if variant == "american" else 37
            for bet in roulette_bets(variant):
                self.assertAlmostEqual(bet["p"] * size, len(bet["covered"]), msg=f"{variant}/{bet['id']}")

    def test_rtp(self):
        self.assertTrue(all(abs(b["p"] * (1 + b["profitMultiplier"]) - 36 / 37) < 1e-10 for b in roulette_bets("european") if b["id"] != "straight:0"))
        self.assertTrue(all(abs(b["p"] * (1 + b["profitMultiplier"]) - 36 / 38) < 1e-10 for b in roulette_bets("american") if b["id"] != "topline"))
        top = next(b for b in roulette_bets("american") if b["id"] == "topline")
        self.assertEqual(top["covered"], ["0", "00", "1", "2", "3"])
        red = next(o for o in next(v for v in CASINO_VARIANTS if v["id"] == "american")["options"] if o["id"] == "red")
        self.assertEqual(red["p"], 18 / 38)

    def test_la_partage(self):
        for id_ in ("red", "black", "odd", "even", "low", "high"):
            self.assertIn("la partage", next(b for b in roulette_bets("french") if b["id"] == id_)["label"])

    def test_stacked_tickets(self):
        r = ce.start_game("roulette", "straight:17", {"variant": "european", "stakeCents": 700,
                                                       "tickets": [{"betId": "straight:17", "stakeCents": 500}, {"betId": "straight:23", "stakeCents": 200}]})
        self.assertEqual([ln["committedCents"] for ln in r["settlement"]["lines"]], [500, 200])


class SlotsAndSixDraw(SimpleTestCase):
    def test_all_trap_positions(self):
        for trap in range(6):
            state = {"variant": "classic", "trap": trap, "draws": [], "target": 3, "stakeCents": 500, "phase": "draw"}
            result = None
            for tile in [n for n in range(6) if n != trap][:3]:
                result = ce.six_draw_action(state, tile)
                state = result["state"]
            self.assertEqual(result["settlement"]["returnCents"], 900)
            self.assertEqual(result["settlement"]["status"], "win")
            lost = ce.six_draw_action({"variant": "classic", "trap": trap, "draws": [], "target": 3, "stakeCents": 500, "phase": "draw"}, trap)
            self.assertEqual(lost["settlement"]["returnCents"], 0)

    def test_open_tile_rejected(self):
        state = {"variant": "classic", "trap": 5, "draws": [0], "target": 3, "stakeCents": 500, "phase": "draw"}
        with self.assertRaisesMessage(ce.EngineError, "already open"):
            ce.six_draw_action(state, 0)
        self.assertEqual(state["draws"], [0])

    def test_sanitized_view(self):
        view = ce.sanitize_active_view({"variant": "classic", "trap": 5, "draws": [0, 2], "target": 3, "stakeCents": 500, "phase": "draw"})
        self.assertEqual(view["draws"], [0, 2])
        self.assertNotIn("trap", view)
        self.assertEqual(view["nextSafeChance"], 0.75)


class Baccarat(SimpleTestCase):
    def test_tableau(self):
        for banker in range(8):
            for third in range(10):
                expected = (banker <= 2 or (banker == 3 and third != 8) or (banker == 4 and 2 <= third <= 7) or (banker == 5 and 4 <= third <= 7)
                            or (banker == 6 and 6 <= third <= 7))
                self.assertEqual(ce.banker_draws(banker, third), expected)
        self.assertTrue(ce.banker_draws(5, None))
        self.assertFalse(ce.banker_draws(6, None))

    def test_stacked_bets(self):
        r = ce.start_game("baccarat", "player", {"variant": "commission", "stakeCents": 600,
                                                 "tickets": [{"betId": "player", "stakeCents": 500}, {"betId": "tie", "stakeCents": 100}]})
        self.assertEqual([[ln["id"], ln["committedCents"]] for ln in r["settlement"]["lines"]], [["player", 500], ["tie", 100]])


class Blackjack(SimpleTestCase):
    def test_natural_after_declining_insurance(self):
        result = ce.blackjack_action({**bj([1, 13], [1, 9]), "phase": "insurance"}, "declineInsurance")
        self.assertEqual(result["settlement"]["returnCents"], 2500)
        self.assertIn("3:2", result["settlement"]["lines"][0]["reason"])

    def test_insurance(self):
        result = ce.blackjack_action({**bj([10, 7], [1, 10]), "phase": "insurance"}, "insurance", {"insuranceCents": 500})
        self.assertEqual(result["additionalCents"], 500)
        self.assertEqual(result["settlement"]["committedCents"], 1500)
        self.assertEqual(next(ln for ln in result["settlement"]["lines"] if ln["id"] == "insurance")["returnCents"], 1500)
        self.assertEqual(result["settlement"]["status"], "push")

    def test_stands_on_soft_17(self):
        result = ce.blackjack_action(bj([10, 8], [1, 6]), "stand")
        self.assertEqual(result["view"]["dealerTotal"], 17)
        self.assertTrue(result["view"]["dealerSoft"])
        self.assertEqual(result["settlement"]["returnCents"], 2000)

    def test_split(self):
        result = ce.blackjack_action(bj([8, 8], [10, 7], [3, 2]), "split")
        self.assertEqual(result["additionalCents"], 1000)
        self.assertEqual(len(result["state"]["hands"]), 2)
        self.assertEqual(len(result["state"]["hands"][0]["cards"]), 2)
        self.assertEqual(len(result["state"]["hands"][1]["cards"]), 1)
        result = ce.blackjack_action(result["state"], "stand")
        self.assertEqual(len(result["state"]["hands"][1]["cards"]), 2)
        result = ce.blackjack_action(result["state"], "stand")
        self.assertEqual(result["settlement"]["committedCents"], 2000)

    def test_split_aces(self):
        result = ce.blackjack_action(bj([1, 1], [10, 7], [13, 12]), "split")
        self.assertTrue(all(len(h["cards"]) == 2 and h["done"] for h in result["state"]["hands"]))
        self.assertTrue(all(ln["returnCents"] == 2000 for ln in result["settlement"]["lines"]))

    def test_double(self):
        result = ce.blackjack_action(bj([5, 6], [10, 6], [10, 10]), "double")
        self.assertEqual(result["additionalCents"], 1000)
        self.assertEqual(len(result["state"]["hands"][0]["cards"]), 3)
        self.assertEqual(result["state"]["hands"][0]["stakeCents"], 2000)
        self.assertEqual(result["settlement"]["committedCents"], 2000)

    def test_active_view_hides_hole_card(self):
        view = ce.blackjack_view(bj([10, 7], [9, 8]), False)
        self.assertEqual(len(view["dealer"]), 1)
        self.assertNotIn("dealerTotal", view)


class Crash(SimpleTestCase):
    def test_integer_model(self):
        self.assertEqual(ce.crash_k_from_r(9_007_199_254_740_992), 97)
        self.assertEqual(ce.crash_k_from_r(1), 10000)
        self.assertEqual(crash_target_step(150), 2)
        self.assertEqual(crash_target_step(200), 1)

    def test_auto_target_boundary(self):
        state = {"variant": "live", "crashK": 200, "target": 200, "autoTarget": 200, "launchedAt": 0, "stakeCents": 1000, "phase": "live"}
        result = ce.crash_action(state, "tick", 2500)
        self.assertEqual(result["settlement"]["returnCents"], 2000)
        self.assertEqual(result["view"]["payableTick"], 200)

    def test_cashout_at_k(self):
        base = {"variant": "live", "crashK": 200, "target": 200, "launchedAt": 0, "stakeCents": 1001, "phase": "live"}
        self.assertEqual(ce.crash_action(dict(base), "cashout", 2500)["settlement"]["returnCents"], 2002)
        crashed = ce.crash_action(dict(base), "cashout", 2525)
        self.assertEqual(crashed["settlement"]["returnCents"], 0)
        self.assertEqual(crashed["view"]["firstFailedTick"], 201)
        self.assertEqual(crashed["view"]["lastPayableTick"], 200)


class Poker(SimpleTestCase):
    def test_comparisons(self):
        self.assertEqual(ce.evaluate_poker(cards([1, 2, 3, 4, 5])), [4, 5])
        self.assertGreater(ce.compare_poker(cards([2, 3, 4, 5, 6]), cards([1, 2, 3, 4, 5])), 0)
        self.assertGreater(ce.compare_poker(cards([1, 1, 13, 8, 3]), cards([1, 1, 12, 8, 3])), 0)
        self.assertEqual(ce.compare_poker(cards([1, 1, 13, 8, 3]), cards([1, 1, 13, 8, 3])), 0)

    def test_high_pair_returns_stake(self):
        result = ce.poker_action({"variant": "jacks", "player": cards([11, 11, 2, 5, 9]), "deck": [], "phase": "draw", "stakeCents": 100}, [0, 1, 2, 3, 4])
        self.assertEqual(result["settlement"]["returnCents"], 100)
        self.assertEqual(result["settlement"]["status"], "push")
        self.assertEqual(result["view"]["award"], "high-pair")

    def test_royal_at_minimum_stake(self):
        royal = [{"r": r, "s": 1} for r in (1, 10, 11, 12, 13)]
        result = ce.poker_action({"variant": "jacks", "player": royal, "deck": [], "phase": "draw", "stakeCents": 1}, [0, 1, 2, 3, 4])
        self.assertEqual(result["settlement"]["returnCents"], 800)
        self.assertEqual(result["view"]["playerRank"], "Royal flush")

    def test_dealer_holds_two_highest(self):
        state = {"variant": "showdown", "player": cards([11, 11, 2, 5, 9]), "dealer": cards([2, 5, 9, 11, 1]), "deck": cards([2, 3, 4]), "phase": "draw", "stakeCents": 500}
        self.assertEqual(ce.poker_action(state, [0, 1, 2, 3, 4])["view"]["dealerKeep"], [3, 4])


class SlideBalance(SimpleTestCase):
    def test_costs_rise_and_checkpoints_pay(self):
        costs = [sb.upgrade_cost(level) for level in range(20)]
        self.assertEqual(costs, sorted(set(costs)))
        self.assertEqual([c["gems"] for c in sb.checkpoints()], list(range(1, 21)))
        self.assertEqual((round(sb.reach_m(2)), round(sb.reach_m(20))), (100, 1000))
        self.assertEqual(sb.GLIDER_PRICE, 30)

    def test_only_the_highest_checkpoint_pays(self):
        self.assertEqual([sb.checkpoint_m(d) for d in (0, 49, 50, 237, 999, 1000, 1200)], [0, 0, 50, 200, 950, 1000, 1000])
        self.assertEqual(sb.checkpoint_gems(200), 4)

    def test_level_20_always_finishes(self):
        rng = random.Random(4)
        for _ in range(20):
            rows = sb.make_rows(rng)
            reaches = [sb.perfect_reach(rows, sb.steer(level)) for level in (None, 2, 10, 20)]
            self.assertEqual(reaches, sorted(reaches))
            self.assertEqual(reaches[-1], sb.TRACK_M)


class SlideSettlement(SimpleTestCase):
    RUN = {"length_m": 1000, "limit_m": 420.7}

    def test_crash_pays_highest_checkpoint(self):
        self.assertEqual(settle_report(self.RUN, "crashed", 237, 600), {"status": "crashed", "distance": 237, "checkpoint": 200, "gems": 4})

    def test_capped_report(self):
        self.assertEqual(settle_report(self.RUN, "survived", 1000, 600), {"status": "crashed", "distance": 420, "checkpoint": 400, "gems": 8})

    def test_finish_pays_top(self):
        s = settle_report({"length_m": 1000, "limit_m": 1000}, "survived", 3, 600)
        self.assertEqual((s["distance"], s["checkpoint"], s["gems"]), (1000, 1000, 20))

    def test_short_crash_and_impossible_speed(self):
        self.assertEqual(settle_report(self.RUN, "crashed", 40, 60)["gems"], 0)
        with self.assertRaises(Exception):
            settle_report(self.RUN, "crashed", 400, 2)


class Collectibles(SimpleTestCase):
    @staticmethod
    def lcg(seed):
        x = [seed]

        def rng(n):
            x[0] = (x[0] * 1103515245 + 12345) % 2147483648
            return x[0] % n
        return rng

    def test_seven_tiers(self):
        self.assertEqual(len(COLLECTIBLE_TIERS), 7)
        self.assertEqual(COLLECTIBLE_TIERS[-1]["max"], 30000)

    def test_budget_respected(self):
        for s in range(1, 6):
            r = draw_collectibles(50000, self.lcg(s))
            self.assertLessEqual(r["spent"], 50000)
            self.assertEqual(r["spent"], sum(i["price"] for i in r["items"]))
            self.assertGreater(len(r["items"]), 1)

    def test_can_be_all_common(self):
        r = draw_collectibles(1000, lambda n: 0)
        self.assertTrue(all(i["rarity"] == "Common" for i in r["items"]))
        self.assertEqual(len(r["items"]), 20)


class AccountRules(SimpleTestCase):
    def test_usernames(self):
        self.assertFalse(USERNAME_RE.match("ab"))
        self.assertTrue(USERNAME_RE.match("abc"))
        self.assertTrue(USERNAME_RE.match("a" * 30))
        self.assertFalse(USERNAME_RE.match("a" * 31))
        self.assertFalse(USERNAME_RE.match("bad name!"))

    def test_only_unlinked_non_demo_guests_can_be_adopted(self):
        self.assertTrue(can_claim(Player(account_id=None, is_demo=False)))
        self.assertFalse(can_claim(Player(account_id=1, is_demo=False)))
        self.assertFalse(can_claim(Player(account_id=None, is_demo=True)))


# ---------- API: the Django replacements for Lovable's server functions and Postgres functions ----------
TOKEN = "t" * 40
DEMO = "d" * 40


class Api(TestCase):
    def post(self, path, body=None, status=200, bearer=None):
        headers = {"HTTP_AUTHORIZATION": f"Bearer {bearer}"} if bearer else {}
        r = self.client.post(f"/api/{path}", body or {}, content_type="application/json", **headers)
        self.assertEqual(r.status_code, status, r.content)
        return r.json()

    def rid(self):
        return f"req-{random.random():.12f}"

    def player(self, token=TOKEN):
        self.post("summary", {"token": token})
        from .services import sha256
        return Player.objects.get(token_hash=sha256(token))

    def fund(self, gems, token=TOKEN):
        p = self.player(token)
        p.gem_cents = gems * 100
        p.save()
        return p

    def test_guest_and_demo_profiles(self):
        s = self.post("summary", {"token": TOKEN})
        self.assertEqual((s["player"]["gems"], s["player"]["isDemo"]), (0, False))
        d = self.post("summary", {"token": DEMO, "demo": True})
        self.assertEqual((d["player"]["gems"], d["player"]["gemCents"], d["player"]["isDemo"]), (42, 4200, True))
        self.assertEqual(d["ledger"][0]["reason"], "Seeded judge demo profile")
        self.post("summary", {"token": "short"}, status=400)

    def test_world_shape(self):
        w = self.post("world", {"token": TOKEN})
        self.assertEqual(set(w), {"inventory", "game", "trophies", "losses", "preferences", "manifest", "activeSession", "rounds", "traderOffers"})
        self.assertEqual(len(w["manifest"]), 15)
        self.assertIsNone(w["game"]["gliderLevel"])

    def solve(self, game_id=1, token=TOKEN, fresh=False):
        run = self.post("challenges/issue", {"token": token, "gameId": game_id, "fresh": fresh})
        started = self.post("challenges/action", {"token": token, "runId": run["id"], "requestId": self.rid(), "action": "start"})["run"]
        self.assertIsNotNone(started["stimulus"])
        from .models import ChallengeRun
        answer = ChallengeRun.objects.get(id=run["id"]).private_data["answer"]
        return self.post("challenges/action", {"token": token, "runId": run["id"], "requestId": self.rid(), "action": "submit",
                                               "payload": {"answer": str(answer["value"])}})["run"]

    def test_challenge_pass_pays_once_and_levels_up(self):
        done = self.solve()
        self.assertEqual(done["status"], "passed")
        self.assertEqual(done["result"]["receipt"]["gemsAwarded"], 16)  # (5 + 2 x level 1) x 1.5 hard x 1.5 fast solve
        self.assertEqual(done["result"]["receipt"]["newLevel"], 2)
        self.assertEqual(done["result"]["receipt"]["balance"], 16)
        again = self.post("challenges/issue", {"token": TOKEN, "gameId": 1})
        self.assertEqual(again["id"], done["id"])  # returning shows the receipt, not a new puzzle
        retry = self.post("challenges/action", {"token": TOKEN, "runId": done["id"], "requestId": self.rid(), "action": "submit", "payload": {"answer": "0"}})
        self.assertEqual(retry["error"], "This challenge is already finished.")
        self.assertEqual(self.post("summary", {"token": TOKEN})["player"]["gems"], 16)
        second = self.solve(fresh=True)
        self.assertEqual(second["level"], 2)
        self.assertEqual(second["result"]["reward"]["lines"][0]["label"], "Same game ×2 this hour (rotate to restore)")

    def test_ephemeral_stimulus_is_sent_once(self):
        run = self.post("challenges/issue", {"token": TOKEN, "gameId": 11})
        self.assertIsNone(run["stimulus"])
        started = self.post("challenges/action", {"token": TOKEN, "runId": run["id"], "requestId": self.rid(), "action": "start"})["run"]
        self.assertIsNotNone(started["stimulus"])
        self.assertIsNone(self.post("challenges/issue", {"token": TOKEN, "gameId": 11})["stimulus"])

    def test_same_request_id_is_not_counted_twice(self):
        run = self.post("challenges/issue", {"token": TOKEN, "gameId": 4})
        self.post("challenges/action", {"token": TOKEN, "runId": run["id"], "requestId": self.rid(), "action": "start"})
        rid = self.rid()
        a = self.post("challenges/action", {"token": TOKEN, "runId": run["id"], "requestId": rid, "action": "guess", "payload": {"guess": "ABLE"}})["run"]
        b = self.post("challenges/action", {"token": TOKEN, "runId": run["id"], "requestId": rid, "action": "guess", "payload": {"guess": "ABLE"}})["run"]
        self.assertEqual(a["attempts"], 1)
        self.assertEqual(b["attempts"], 1)

    def test_trophy_at_level_10(self):
        p = self.player()
        ChallengeMastery.objects.create(player=p, game_id=1, level=9, peak_level=9)
        self.solve()
        self.assertEqual(list(Trophy.objects.filter(player=p).values_list("milestone", flat=True)), [10])

    def test_reset_keeps_peak(self):
        self.solve()
        self.post("challenges/reset", {"token": TOKEN, "gameId": 1})
        m = self.post("summary", {"token": TOKEN})["mastery"][0]
        self.assertEqual((m["level"], m["peak"]), (1, 2))

    def test_roulette_gem_round_settles_exactly(self):
        self.fund(10)
        s = self.post("casino/start", {"token": TOKEN, "requestId": self.rid(), "game": "roulette", "option": "red",
                                       "asset": {"type": "gems", "amount": "2.50"}, "config": {"variant": "european", "tickets": [{"betId": "red", "stakeCents": 250}]}})
        self.assertEqual(s["status"], "settled")
        won = s["result"]["returnCents"] == 500
        self.assertEqual(s["result"]["balanceCents"], 1000 - 250 + (500 if won else 0))
        self.assertEqual(self.post("summary", {"token": TOKEN})["player"]["gemCents"], s["result"]["balanceCents"])
        self.assertEqual(len(self.post("world", {"token": TOKEN})["rounds"]), 1)

    def test_insufficient_gems_and_one_open_round(self):
        self.post("casino/start", {"token": TOKEN, "requestId": self.rid(), "game": "roulette", "option": "red", "asset": {"type": "gems", "amount": "1.00"}}, status=400)
        self.fund(50)
        s = self.post("casino/start", {"token": TOKEN, "requestId": self.rid(), "game": "sixdraw", "option": "survive", "asset": {"type": "gems", "amount": "5.00"}})
        self.assertEqual(s["status"], "active")
        self.assertNotIn("trap", s["view"])
        err = self.post("casino/start", {"token": TOKEN, "requestId": self.rid(), "game": "roulette", "option": "red", "asset": {"type": "gems", "amount": "1.00"}}, status=400)
        self.assertIn("Finish your active hand", err["detail"])
        for tile in range(6):
            s = self.post("casino/act", {"token": TOKEN, "requestId": self.rid(), "sessionId": s["id"], "action": "reveal", "tile": tile})
            if s["status"] == "settled":
                break
        self.assertIn(s["result"]["returnCents"], (0, 900))

    def test_blackjack_double_charges_more_gems(self):
        self.fund(100)
        for _ in range(30):
            s = self.post("casino/start", {"token": TOKEN, "requestId": self.rid(), "game": "blackjack", "option": "standard",
                                           "asset": {"type": "gems", "amount": "10.00"}, "config": {"variant": "classic"}})
            if s["status"] == "active" and s["view"]["phase"] == "player":
                before = self.post("summary", {"token": TOKEN})["player"]["gemCents"]
                s = self.post("casino/act", {"token": TOKEN, "requestId": self.rid(), "sessionId": s["id"], "action": "double"})
                self.assertEqual(s["status"], "settled")
                self.assertEqual(s["totalCommittedCents"], 2000)
                self.assertEqual(s["result"]["balanceCents"], before - 1000 + s["result"]["returnCents"])
                return
            if s["status"] == "active":
                self.post("casino/act", {"token": TOKEN, "requestId": self.rid(), "sessionId": s["id"], "action": "declineInsurance"})
                s = CasinoSession.objects.get(id=s["id"])
                if s.status == "active":
                    self.post("casino/act", {"token": TOKEN, "requestId": self.rid(), "sessionId": str(s.id), "action": "stand"})
        self.fail("never dealt a playable hand")

    def test_glider_shop_upgrade_and_level_stake(self):
        self.fund(200)
        self.post("shop/buy", {"token": TOKEN, "requestId": self.rid(), "productKey": "glider"})
        err = self.post("shop/buy", {"token": TOKEN, "requestId": self.rid(), "productKey": "glider"}, status=400)
        self.assertIn("already own a glider", err["detail"])
        rid = self.rid()
        self.assertEqual(self.post("slide/glider/upgrade", {"token": TOKEN, "requestId": rid})["level"], 1)
        self.assertEqual(self.post("slide/glider/upgrade", {"token": TOKEN, "requestId": rid})["level"], 1)  # retried, charged once
        self.post("slide/glider/upgrade", {"token": TOKEN, "requestId": self.rid()})
        g = self.post("world", {"token": TOKEN})["game"]
        self.assertEqual(g["gliderLevel"], 2)
        self.assertEqual(self.post("summary", {"token": TOKEN})["player"]["gems"], 200 - 30 - sb.upgrade_cost(0) - sb.upgrade_cost(1))
        # stake both levels on six-draw and lose on purpose
        s = self.post("casino/start", {"token": TOKEN, "requestId": self.rid(), "game": "sixdraw", "option": "survive", "asset": {"type": "glider", "levels": 2}})
        self.assertIn("Glider Lv 2 → 0", s["assetLabel"])
        self.assertTrue(self.post("world", {"token": TOKEN})["game"]["reserved"])
        self.post("slide/glider/upgrade", {"token": TOKEN, "requestId": self.rid()}, status=400)
        trap = CasinoSession.objects.get(id=s["id"]).state["trap"]
        s = self.post("casino/act", {"token": TOKEN, "requestId": self.rid(), "sessionId": s["id"], "action": "reveal", "tile": trap})
        self.assertEqual(s["result"]["status"], "loss")
        self.assertEqual(self.post("world", {"token": TOKEN})["game"]["gliderLevel"], 0)
        self.assertTrue(LossLedger.objects.filter(description__startswith="Lost Glider levels").exists())

    def test_collectible_batch_and_trade(self):
        self.fund(5000)
        r = self.post("shop/collectibles", {"token": TOKEN, "requestId": "batch-0001", "budget": 2500})
        self.assertLessEqual(r["spent"], 2500)
        self.assertEqual(r["spent"], sum(i["price"] for i in r["items"]))
        self.assertEqual(self.post("summary", {"token": TOKEN})["player"]["gems"], 5000 - r["spent"])
        again = self.post("shop/collectibles", {"token": TOKEN, "requestId": "batch-0001", "budget": 2500})
        self.assertEqual(again["spent"], r["spent"])  # retry is free
        p = self.player()
        cheap = InventoryItem.objects.filter(player=p).order_by("price").first()
        if cheap.price < 96:
            self.assertIn("Alex needs", self.post("shop/trade", {"token": TOKEN, "requestId": self.rid(), "itemId": str(cheap.id), "offerKey": "alex-orbit"}, status=400)["detail"])
        item = InventoryItem.objects.create(player=p, kind="collectible", item_key="x", name="Test Prism", price=500, symbol="◈")
        got = self.post("shop/trade", {"token": TOKEN, "requestId": self.rid(), "itemId": str(item.id), "offerKey": "alex-relic"})
        self.assertEqual(got["name"], "Alex's Ancient Relic")
        self.assertTrue(LossLedger.objects.filter(game="trade").exists())

    def test_slide_run_pays_highest_checkpoint_three_times_a_day(self):
        for n in range(4):
            run = self.post("slide/start", {"token": TOKEN, "requestId": self.rid()})
            self.assertEqual(run["lengthM"], 1000)
            SlideRun.objects.filter(id=run["id"]).update(created_at=timezone.now() - timedelta(seconds=60), limit_m=1000)
            out = self.post("slide/finish", {"token": TOKEN, "runId": run["id"], "result": "crashed", "distanceM": 237})
            self.assertEqual((out["checkpointM"], out["gems"]), (200, 4 if n < 3 else 0))
        self.assertEqual(self.post("summary", {"token": TOKEN})["player"]["gems"], 12)
        g = self.post("world", {"token": TOKEN})["game"]
        self.assertEqual((g["rewardedRunsToday"], g["best"], len(g["runs"])), (3, 237, 4))

    def test_starting_a_run_abandons_the_open_one(self):
        first = self.post("slide/start", {"token": TOKEN, "requestId": self.rid()})
        self.post("slide/start", {"token": TOKEN, "requestId": self.rid()})
        self.assertEqual(SlideRun.objects.get(id=first["id"]).status, "abandoned")

    def test_preferences_gate_stakes(self):
        prefs = self.post("world", {"token": TOKEN})["preferences"]
        self.post("preferences", {"token": TOKEN, "preferences": {**prefs, "allowSkillStakes": False}})
        self.solve()
        err = self.post("casino/start", {"token": TOKEN, "requestId": self.rid(), "game": "roulette", "option": "red",
                                         "asset": {"type": "skill", "gameId": 1, "rollbackLevel": 1}}, status=400)
        self.assertIn("switched off", err["detail"])

    def test_accounts_adopt_guest_progress(self):
        self.solve()
        session = self.post("auth/signup", {"email": "a@example.com", "password": "password123", "username": "alice"})
        self.assertEqual(session["profile"]["username"], "alice")
        bearer = session["token"]
        claim = self.post("account/claim", {"guestToken": TOKEN}, bearer=bearer)
        self.assertTrue(claim["adoptedGuest"])
        self.assertEqual(self.post("summary", {"token": "z" * 40}, bearer=bearer)["player"]["gems"], 16)
        # signed out, the adopted guest token no longer opens the account's data
        self.assertIn("belongs to an account", self.post("summary", {"token": TOKEN}, status=400)["detail"])
        self.post("auth/signup", {"email": "A@example.com", "password": "password123", "username": "alice2"}, status=400)
        self.post("auth/signin", {"email": "a@example.com", "password": "wrong-pass"}, status=400)
        again = self.post("auth/signin", {"email": "a@example.com", "password": "password123"})
        self.assertEqual(again["profile"]["username"], "alice")
        other = self.post("auth/signup", {"email": "b@example.com", "password": "password123", "username": "bob"})
        taken = self.post("auth/profile", {"username": "ALICE"}, status=400, bearer=other["token"])
        self.assertEqual(taken["code"], "23505")
        self.post("auth/user", {"password": "newpassword1", "currentPassword": "nope"}, status=400, bearer=bearer)
        self.post("auth/user", {"password": "newpassword1", "currentPassword": "password123"}, bearer=bearer)
        self.post("auth/signin", {"email": "a@example.com", "password": "newpassword1"})
        self.post("account/delete", {}, bearer=bearer)
        self.assertFalse(WalletLedger.objects.filter(player__account__email="a@example.com").exists())
        self.post("auth/signin", {"email": "a@example.com", "password": "newpassword1"}, status=400)

    def test_password_reset(self):
        from django.core import mail
        self.post("auth/signup", {"email": "c@example.com", "password": "password123", "username": "carol"})
        self.post("auth/recover", {"email": "c@example.com", "redirectTo": "https://evil.example/steal"})
        self.post("auth/recover", {"email": "nobody@example.com"})
        self.assertEqual(len(mail.outbox), 1)
        link = mail.outbox[0].body.split("\n")[2]
        self.assertTrue(link.startswith("http://localhost:3000/reset-password#type=recovery"))
        params = dict(kv.split("=") for kv in link.split("#")[1].split("&"))
        session = self.post("auth/recover/confirm", {"uid": params["uid"], "token": params["token"], "password": "brandnew99"})
        self.assertTrue(session["token"])
        self.post("auth/signin", {"email": "c@example.com", "password": "brandnew99"})
        self.post("auth/recover/confirm", {"uid": params["uid"], "token": params["token"], "password": "another99"}, status=400)
