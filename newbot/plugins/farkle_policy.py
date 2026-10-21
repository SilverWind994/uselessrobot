"""Farkle 最优策略求解器（精确动态规划）。

模型
----
一次回合可以一直掷下去，直到玩家选择「入账」或「爆骰」。把「手里剩余骰子的
种类构成」记为 state、「本轮已累计的分数」记为 s，则

    D(state, s) = max(s, E[再掷一次])

其中 E[再掷一次] 按「所有可能掷出的点数组合 × 所有可锁定的计分子集」精确求和：
每个掷出结果下，玩家可以锁定任意一个能计分的子集，把它的分数计入 s，再用剩余
骰子进入下一个 state；若剩余骰子为空（热骰）则拿回整副骰组。掷出的骰子完全无法
计分即爆骰，本轮分数归零。

分数步长
--------
Farkle 的所有计分都是 50 的倍数，因此 s 以 50 分为一格精确离散，不存在近似。
s 从高到低递推（因为锁定后的分数一定比 s 大），O(状态数 × 分数格 × 结果分组)。

本模块不依赖 farkle.py：骰子概率表与计分函数都由调用方传入，避免循环导入，
也方便单独写脚本验证。
"""

import itertools
import math
from collections import Counter, defaultdict

STEP = 50              # 分数离散步长（Farkle 计分均为 50 的倍数）
_EPS = 1e-6            # 浮点比较容差
_MISS = object()


def _multiset_dists(count: int, probs) -> list:
    """count 颗同种骰子的点数多重集分布：[(每面颗数(6 元组), 概率)]"""
    out = []

    def rec(pos: int, left: int, counts: list, p: float) -> None:
        if pos == 5:
            counts[5] = left
            q = p * probs[5] ** left
            if q > 0:
                out.append((tuple(counts), q))
            return
        for k in range(left + 1):
            counts[pos] = k
            rec(pos + 1, left - k, counts, p * math.comb(left, k) * probs[pos] ** k)

    rec(0, count, [0] * 6, 1.0)
    return out


class Policy:
    """某一副骰组（6 颗）的最优策略表。

    典型用法：
        pol = build_policy(kinds, probs, score_counts, s_max, wild_kind="devil")
        pol.turn_ev                      # 空手开一轮的期望得分
        pol.bank_line(kinds)             # 该剩余骰型下的入账线
        pol.should_bank(kinds, s, T)     # s 分时是否该入账（T=离目标分还差多少）
        pol.best_lock(dice, s, T)        # 锁定哪些骰子最划算
    """

    def __init__(self, kinds, probs, score_counts, s_max, wild_kind=None, wild_value=1):
        self._probs = {}
        for k in set(kinds):
            dist = tuple(probs[k])
            if abs(sum(dist) - 1.0) > 1e-6:
                raise ValueError(f"骰型 {k} 的概率之和为 {sum(dist)}，应为 1")
            self._probs[k] = dist
        self.score_counts = score_counts
        self.wild_kind = wild_kind
        self.wild_value = wild_value
        self.step = STEP
        self.s_max = max(STEP, int(s_max) // STEP * STEP)
        self._score_cache = {}

        # 同分布的骰型合并（例如仙贝骰与普通骰完全一致），压缩状态空间。
        # 带万能面的骰型不参与合并：概率分布虽然可能相同，但掷出万能面时的计分
        # 规则不同，合并后会把手里的普通 1 也当成万能面，凭空多出顺子/三张。
        canon, seen = {}, {}
        for k in kinds:
            if k == wild_kind:
                canon[k] = k
                continue
            sig = tuple(round(p, 9) for p in probs[k])
            if sig in seen:
                canon[k] = seen[sig]
            else:
                seen[sig] = k
                canon[k] = k
        self.canon = canon
        self.full = tuple(sorted(canon[k] for k in kinds))

        self._build_states()
        self._build_groups()
        self._solve()

    # ==================== 状态与概率 ====================

    def _build_states(self) -> None:
        """枚举整副骰组的所有子多重集（按骰型计），即所有可能的剩余手牌构成"""
        items = sorted(Counter(self.full).items())
        states = []

        def rec(i, cur):
            if i == len(items):
                states.append(tuple(sorted(cur)))
                return
            kind, cnt = items[i]
            for k in range(cnt + 1):
                rec(i + 1, cur + [kind] * k)

        rec(0, [])
        self.states = states
        self.index = {st: i for i, st in enumerate(states)}
        self.full_index = self.index[self.full]

    def _state_key(self, kinds) -> tuple:
        """把任意骰型序列规整为状态键（空手 = 热骰 = 整副骰组）"""
        key = tuple(sorted(self.canon.get(k, k) for k in kinds))
        return key or self.full

    def _score(self, counts: tuple, wilds: int):
        """带缓存的子集计分（counts 为不含万能面的每面颗数）"""
        key = (counts, wilds)
        hit = self._score_cache.get(key, _MISS)
        if hit is _MISS:
            hit = self.score_counts(counts, wilds)
            self._score_cache[key] = hit
        return hit

    def _outcomes(self, state: tuple) -> list:
        """该状态下所有掷出结果：[(按骰型的每面颗数, 概率)]"""
        groups = sorted(Counter(state).items())
        dists = [(kind, _multiset_dists(cnt, self._probs_of(kind))) for kind, cnt in groups]
        out = []

        def rec(i, acc, p):
            if i == len(dists):
                out.append((tuple(acc), p))
                return
            kind, ds = dists[i]
            for counts, q in ds:
                acc.append((kind, counts))
                rec(i + 1, acc, p * q)
                acc.pop()

        rec(0, [], 1.0)
        return out

    def _probs_of(self, kind):
        return self._probs[kind]

    # ==================== 每个结果的锁定选项 ====================

    def _options(self, outcome: tuple, state_counts) -> dict:
        """一个掷出结果下，所有可锁定子集能带来的 (剩余状态编号 -> 最大得分)。

        同一个剩余骰型只保留得分最高的锁法：D 对 s 单调不减，分数越高一定不差。
        """
        buckets = []
        for kind, counts in outcome:
            for face in range(6):
                if counts[face]:
                    buckets.append((kind, face + 1, counts[face]))

        best = {}
        sel_faces = [0] * 6
        sel_kinds = defaultdict(int)
        state = {"wilds": 0, "total": 0}

        def dfs(i):
            if i == len(buckets):
                if state["total"] == 0:
                    return
                sc = self._score(tuple(sel_faces), state["wilds"])
                if sc is None:
                    return
                rem = []
                for kind, cnt in state_counts.items():
                    rem.extend([kind] * (cnt - sel_kinds[kind]))
                if rem:
                    rem_i = self.index[tuple(sorted(rem))]
                else:
                    rem_i = self.full_index      # 热骰：拿回整副骰组
                if sc > best.get(rem_i, -1):
                    best[rem_i] = sc
                return

            kind, face, cnt = buckets[i]
            wild = (kind == self.wild_kind and face == self.wild_value)
            for k in range(cnt + 1):
                if k:
                    sel_kinds[kind] += k
                    state["total"] += k
                    if wild:
                        state["wilds"] += k
                    else:
                        sel_faces[face - 1] += k
                dfs(i + 1)
                if k:
                    sel_kinds[kind] -= k
                    state["total"] -= k
                    if wild:
                        state["wilds"] -= k
                    else:
                        sel_faces[face - 1] -= k

        dfs(0)
        return best

    def _build_groups(self) -> None:
        """把结果按「锁定选项集合」合并，减少期望计算次数"""
        self.groups = []
        for state in self.states:
            state_counts = Counter(state)
            grouped = defaultdict(float)
            for outcome, p in self._outcomes(state):
                best = self._options(outcome, state_counts)
                key = tuple(sorted(best.items())) if best else ()
                grouped[key] += p
            self.groups.append([(p, key) for key, p in grouped.items()])

    # ==================== 动态规划 ====================

    def _solve(self) -> None:
        n = self.s_max // STEP + 1
        self.n = n
        D = [[0.0] * n for _ in self.states]
        groups = self.groups
        states_n = len(self.states)
        for i in range(n - 1, -1, -1):
            s = i * STEP
            for si in range(states_n):
                expect = 0.0
                for p, opts in groups[si]:
                    if not opts:
                        continue            # 爆骰：本轮分数归零
                    best = 0.0
                    for rem_i, sc in opts:
                        j = i + sc // STEP
                        v = s + sc if j >= n else D[rem_i][j]
                        if v > best:
                            best = v
                    expect += p * best
                D[si][i] = s if s >= expect else expect
        self.D = D

    # ==================== 查询接口 ====================

    def value(self, kinds, s: int) -> float:
        """剩余骰型 kinds、本轮已累计 s 分时，继续回合的期望最终得分（含立即入账）"""
        if s >= self.s_max:
            return float(s)
        i = self.index[self._state_key(kinds)]
        return self.D[i][s // STEP]

    def should_bank(self, kinds, s: int, target_remaining=None) -> bool:
        """是否应当入账：达到本轮目标分或继续掷的期望不如现在收手"""
        if target_remaining is not None and s >= target_remaining:
            return True
        if s >= self.s_max:
            return False
        i = self.index[self._state_key(kinds)]
        return self.D[i][s // STEP] <= s + _EPS

    def bank_line(self, kinds) -> int:
        """该剩余骰型的入账线：累计到多少分后收手最优（s_max 表示一直滚）"""
        i = self.index[self._state_key(kinds)]
        row = self.D[i]
        for j, v in enumerate(row):
            if v <= j * STEP + _EPS:
                return j * STEP
        return self.s_max

    @property
    def turn_ev(self) -> float:
        """空手开一轮（6 颗全掷）的期望最终得分"""
        return self.D[self.full_index][0]

    # ==================== 实战决策 ====================

    def _option_value(self, rem_kinds, s: int, target_remaining) -> float:
        """锁定后继续回合的价值：达到目标分就直接按入账算"""
        if target_remaining is not None and s >= target_remaining:
            return float(s)
        return self.value(rem_kinds, s)

    def best_lock(self, dice, s: int, target_remaining=None):
        """给定实际手牌（[(骰型, 点数)]），返回 (本次得分, 锁定下标列表)。

        无可计分子集（爆骰）返回 None。会枚举所有可锁定子集，按 DP 价值取最优。
        """
        dice = list(dice)
        hand_kinds = [self.canon.get(k, k) for k, _ in dice]
        hand_counts = Counter(hand_kinds)
        buckets = defaultdict(list)
        for idx, (kind, value) in enumerate(dice):
            buckets[(self.canon.get(kind, kind), value)].append(idx)
        keys = list(buckets)

        sel_faces = [0] * 6
        sel_kinds = defaultdict(int)
        chosen = []
        st = {"wilds": 0, "total": 0, "best": None}

        def dfs(i):
            if i == len(keys):
                if st["total"] == 0:
                    return
                sc = self._score(tuple(sel_faces), st["wilds"])
                if sc is None:
                    return
                rem = []
                for kind, cnt in hand_counts.items():
                    rem.extend([kind] * (cnt - sel_kinds[kind]))
                rem_kinds = rem or list(self.full)
                v = self._option_value(rem_kinds, s + sc, target_remaining)
                best = st["best"]
                # 价值相同则优先锁更少骰子（留更多骰子继续掷，后续更灵活）
                cand = (v, sc, -len(rem), list(chosen))
                if best is None or cand[:3] > best[:3]:
                    st["best"] = cand
                return

            kind, value = keys[i]
            idxs = buckets[keys[i]]
            wild = (kind == self.wild_kind and value == self.wild_value)
            for k in range(len(idxs) + 1):
                if k:
                    sel_kinds[kind] += k
                    st["total"] += k
                    chosen.extend(idxs[:k])
                    if wild:
                        st["wilds"] += k
                    else:
                        sel_faces[value - 1] += k
                dfs(i + 1)
                if k:
                    del chosen[-k:]
                    sel_kinds[kind] -= k
                    st["total"] -= k
                    if wild:
                        st["wilds"] -= k
                    else:
                        sel_faces[value - 1] -= k

        dfs(0)
        best = st["best"]
        if best is None:
            return None
        return best[1], best[3]


def build_policy(kinds, probs, score_counts, s_max, wild_kind=None, wild_value=1) -> Policy:
    """构造（并求解）一副骰组的最优策略。

    kinds        : 6 个骰型字符串
    probs        : {骰型: 6 元组，点数 1~6 的概率}
    score_counts : (每面颗数 6 元组, 万能面数量) -> 得分 / None
    s_max        : 分数格上限（建议 = 目标分 + 先手竞价上限）
    wild_kind    : 恶魔骰这类「掷出某点数即为万能面」的骰型
    """
    pol = Policy(kinds, probs, score_counts, s_max, wild_kind, wild_value)
    return pol
