"""Farkle 骰组期望模拟（临时脚本）。

关键建模：一轮（回合）= 从该玩家首掷开始，到「入账」或「爆骰」换手为止。
热骰（6 颗全部计分用完）拿回全部骰子继续掷，仍属于**同一轮**，不另计一轮。
每轮开始时手牌重置为该玩家的骰组（DICE_NUM 颗），爆骰则本轮入账 0 分并换手。

掷骰、计分、爆骰判定全部复用 plugins/farkle.py；选骰口径与 web/farkle_web.py 一致。
"""
import bisect
import itertools
import os
import random
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "newbot"))

from plugins.farkle import (  # noqa: E402
    DICE_DEVIL, DICE_LOADOUTS, DICE_NORMAL, DICE_NUM, _is_wild, _roll_die,
    _score_selection,
)

TARGET = 4000
BANK_LINE = 400


def _die(kind, value):
    return {"kind": kind, "value": value}


def _subset_score(pairs):
    """一组骰子（(kind, value) 序列）的得分；万能面必须参与三张/顺子。"""
    dice = [_die(k, v) for k, v in pairs]
    wilds = sum(1 for d in dice if _is_wild(d))
    reals = Counter(d["value"] for d in dice if not _is_wild(d))
    if wilds == 0:
        return _score_selection(reals)
    best = None
    for combo in itertools.combinations_with_replacement(range(1, 7), wilds):
        merged = Counter(reals)
        merged.update(Counter(combo))
        score = _score_selection(merged)
        if score is None:
            continue
        if all(merged[f] >= 3 or len(merged) >= 5 for f in combo):
            if best is None or score > best:
                best = score
    return best


_DECIDE = {}


def decide(roll):
    """roll: [(kind, value)]；返回 (本轮得分, 被锁定的骰子种类列表)。

    贪心：分数最高；同分锁得少（留更多骰子继续掷，爆骰风险更低）。
    """
    key = tuple(sorted(roll))
    hit = _DECIDE.get(key)
    if hit is not None:
        return hit
    n = len(roll)
    best_score, best_keep = 0, None
    for r in range(1, n + 1):
        for combo in itertools.combinations(range(n), r):
            s = _subset_score([roll[i] for i in combo])
            if not s or s <= 0:
                continue
            if s > best_score or (s == best_score and r < len(best_keep)):
                best_score, best_keep = s, combo
    out = (best_score, [roll[i][0] for i in best_keep] if best_keep else [])
    _DECIDE[key] = out
    return out


def play_turn(kinds, bank_at, hot_out=None):
    """走完一轮，返回本轮入账分数（爆骰为 0）。热骰在同一轮内延续。"""
    base = list(kinds)
    hand = list(kinds)
    turn_score = 0
    while True:
        roll = [(k, _roll_die(k)) for k in hand]
        gained, locked = decide(roll)
        if gained <= 0:
            return 0                       # 爆骰：本轮累计分作废
        turn_score += gained
        rest = list(hand)
        for k in locked:
            rest.remove(k)
        if not rest:                       # 热骰：同一轮内取回全部骰子
            if hot_out is not None:
                hot_out[0] += 1
            rest = list(base)
        hand = rest
        if turn_score >= bank_at:
            return turn_score


def turn_histogram(kinds, bank_at=BANK_LINE, trials=200000):
    """返回 (分数列表, 每轮热骰次数)。"""
    hot = [0]
    scores = []
    for _ in range(trials):
        scores.append(play_turn(kinds, bank_at, hot))
    return scores, hot[0] / trials


def race(scores_a, scores_b, target=TARGET, a_first=True):
    """两人轮流抽每轮得分，先到目标者胜。a_first 指定本局谁先掷。"""
    a, b, turns = 0, 0, 0
    while True:
        if a_first:
            a += random.choice(scores_a)
            turns += 1
            if a >= target:
                return 0, turns
            b += random.choice(scores_b)
            turns += 1
            if b >= target:
                return 1, turns
        else:
            b += random.choice(scores_b)
            turns += 1
            if b >= target:
                return 1, turns
            a += random.choice(scores_a)
            turns += 1
            if a >= target:
                return 0, turns


def duel(scores_x, scores_y, trials=15000):
    """先手逐局交替，剥离先手优势，只比骰组强度；返回 x 的胜率。"""
    wins = 0
    for i in range(trials):
        w, _ = race(scores_x, scores_y, a_first=(i % 2 == 0))
        wins += 1 if w == 0 else 0
    return wins / trials


if __name__ == "__main__":
    random.seed(20261020)

    # --- 校准 1：单骰只掷一次就收，解析期望 (100+50)/6 = 25 ---
    ev1 = turn_histogram([DICE_NORMAL], bank_at=1, trials=100000)[0]
    print(f"[校准1] 单骰掷一次即收 EV={sum(ev1) / len(ev1):.3f}（解析值 25.000）")

    # --- 校准 2：单骰连续掷（银行线 50），应命中「掷到 1/5 就收」→ 1 或 5 的期望 ---
    #   继续掷单骰爆骰概率 4/6；最优就是掷到计分就收 → EV = (100+50)/6 = 25；
    #   银行线 50 时，掷出 5(50) 已达标，掷出 1(100) 也达标 → 同样 25
    ev2 = turn_histogram([DICE_NORMAL], bank_at=50, trials=100000)[0]
    print(f"[校准2] 单骰银行线 50  EV={sum(ev2) / len(ev2):.3f}（解析值 25.000）\n")

    names = list(DICE_LOADOUTS.keys())
    base = DICE_LOADOUTS["normal6"]

    print("=== 每轮期望得分（入账线 400）· 8 骰组 ===")
    print(f"{'骰组':<9}{'EV/轮':>9}{'热骰/轮':>10}{'到4000轮数':>12}")
    hist = {}
    evs = {}
    for name in names:
        scores, hot_rate = turn_histogram(DICE_LOADOUTS[name])
        hist[name] = scores
        ev = sum(scores) / len(scores)
        evs[name] = ev
        print(f"{name:<9}{ev:>9.1f}{hot_rate:>10.2f}{TARGET / ev:>12.1f}")

    print("\n=== 相对普通骰组 strength（EV 比值）===")
    for name in names:
        print(f"{name:<9} EV比 {evs[name] / evs['normal6']:>6.3f}"
              f"   强度差 {(evs[name] / evs['normal6'] - 1) * 100:>+7.1f}%")

    print("\n=== 单挑普通骰组 4000 分目标（先手逐局交替 · 15000 局）===")
    print(f"[校准3] normal6 自对自 {duel(hist['normal6'], hist['normal6']) * 100:.2f}%（应≈50%）")
    for name in names:
        wr = duel(hist[name], hist["normal6"])
        print(f"{name:<9} 胜率 {wr * 100:6.2f}%")

    print("\n=== 换入账线的稳健性（EV 比 normal6）===")
    print(f"{'骰组':<9}{'300':>8}{'500':>8}{'750':>8}")
    for name in names:
        row = []
        for bank in (300, 500, 750):
            s = turn_histogram(DICE_LOADOUTS[name], bank_at=bank, trials=40000)[0]
            row.append(sum(s) / len(s))
        b = []
        for bank in (300, 500, 750):
            s = turn_histogram(base, bank_at=bank, trials=40000)[0]
            b.append(sum(s) / len(s))
        print(f"{name:<9}" + "".join(f"{row[i] / b[i]:>8.3f}" for i in range(3)))
