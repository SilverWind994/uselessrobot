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

胜率模型
--------
Policy 求的是「单回合」的最优策略。实战里 Farkle 是双人赛跑，赢在谁先到目标分，
所以本模块另外提供两层：
  · RaceModel：由双方的「单回合得分分布」算出双人赛跑胜率表 V(双方剩余分)；
  · WinTurn：给定双方剩余分后，本回合的锁骰/入账改按胜率最大化求解。
这样机器人在离目标很近时会及时收手，在对手快赢时会主动冒险。

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
        self._turn_stats_cache = {}

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

    def turn_stats(self, r=None):
        """按 EV 最优策略打完一轮时，两种结束方式的概率分布。

        返回 (bank, bust)：
          bank[x] = 本回合以「入账 x 分」结束的概率（x > 0）；
          bust[s] = 在已累计 s 分时爆骰的概率（本轮得分归零）。

        r 给定时，本回合累计分一旦达到 r 就立即入账：比赛中先达标即锁定胜局，
        再掷只会白白承担爆骰风险；r 为 None 则按 EV 最优策略一直打到 s_max。
        """
        n = self.n
        cut = n - 1 if r is None else min(n - 1, -(-int(r) // STEP))
        hit = self._turn_stats_cache.get(cut)
        if hit is not None:
            return hit
        layers = [dict() for _ in range(n)]      # 分数档 -> {状态编号: 概率}
        layers[0][self.full_index] = 1.0
        bank, bust = defaultdict(float), defaultdict(float)
        for i in range(n):
            layer = layers[i]
            if not layer:
                continue
            s = i * self.step
            for si, mass in layer.items():
                if i >= cut or self.D[si][i] <= s + _EPS:
                    bank[s] += mass               # 入账（达标或策略主动收手）
                    continue
                for p, opts in self.groups[si]:
                    if not opts:
                        bust[s] += mass * p       # 爆骰，本轮归零
                        continue
                    # 与 _solve 一致：选 D 值最大的锁定方式
                    best = None
                    for rem_i, sc in opts:
                        j = i + sc // self.step
                        v = s + sc if j >= n else self.D[rem_i][j]
                        if best is None or v > best[0]:
                            best = (v, rem_i, sc)
                    gain = mass * p
                    j = i + best[2] // self.step
                    if j >= n:
                        bank[s + best[2]] += gain
                    else:
                        layers[j][best[1]] = layers[j].get(best[1], 0.0) + gain
        self._turn_stats_cache[cut] = (dict(bank), dict(bust))
        return self._turn_stats_cache[cut]

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

    def best_lock(self, dice, s: int, target_remaining=None, value_fn=None):
        """给定实际手牌（[(骰型, 点数)]），返回 (本次得分, 锁定下标列表)。

        无可计分子集（爆骰）返回 None。会枚举所有可锁定子集，按 DP 价值取最优。
        value_fn(剩余骰型, 新累计分) 可替换估值方式（胜率模型传入自己的价值表）。
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
                if value_fn is not None:
                    v = value_fn(rem_kinds, s + sc)
                else:
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


def _dist_of(stats, step: int = STEP) -> list:
    """把 turn_stats 的 (bank, bust) 合并成「单回合最终得分」分布（爆骰记 0）。

    bank[x] 是一轮以入账 x 分结束的概率；bust 是一轮以爆骰结束的概率，无论爆骰时
    本轮已累计多少分，最终入账都是 0，所以全部并入 0 分这一档。
    step 是赛跑表的分数格；大于 50 时把得分按最近的格归并（目标分很大时用来
    控制表规模）。
    """
    bank, bust = stats
    agg = defaultdict(float)
    for x, p in bank.items():
        if x > 0 and p > 1e-12:
            agg[int(round(int(x) / step))] += float(p)
    p0 = sum(float(p) for p in bust.values())
    if p0 > 0:
        agg[0] += p0
    return sorted((u, p) for u, p in agg.items() if p > 1e-12)


class RaceModel:
    """双人赛跑的胜率表（先到目标分者获胜）。

    V_me[r][rp]  = 轮到我行动、我剩余 r 分、对手剩余 rp 分时，我最终获胜的概率；
    V_opp[r][rp] = 轮到对手行动时的同一概率。

    双方每回合的得分分布由 Policy.turn_stats 给出（爆骰记 0，且累计分达到目标
    即入账），之后双方都按这张参考分布推进；本回合的锁骰/入账由 WinTurn 依据 V
    做胜率最大化。

    同一剩余分下双方都爆骰会形成 V_me ↔ V_opp 的循环，这里用代数求解：
        V_me = B + f0 * V_opp
        V_opp = D + g0 * V_me
    """

    def __init__(self, my_stats, opp_stats, r_max, step: int = STEP):
        step = max(STEP, int(step))
        size = max(2, int(r_max) // step + 1)
        self.step = step
        self.size = size
        f = _dist_of(my_stats, step)
        g = _dist_of(opp_stats, step)
        self.f0 = sum(p for x, p in f if x == 0)
        self.g0 = sum(p for x, p in g if x == 0)
        # 每个剩余分档（以分数格为单位）预先切出「0 < x < 剩余格」的部分，以及达标概率
        self._f_mid = []
        self._tail_f = []
        self._g_mid = []
        for i in range(size):
            self._f_mid.append([(x, p) for x, p in f if 0 < x < i])
            self._tail_f.append(sum(p for x, p in f if x >= i))
            self._g_mid.append([(x, p) for x, p in g if 0 < x < i])

        v_me = [[0.0] * size for _ in range(size)]
        v_opp = [[0.0] * size for _ in range(size)]
        for j in range(size):
            v_me[0][j] = 1.0            # 我已经达标
            v_opp[0][j] = 1.0
        for i in range(1, size):
            v_me[i][0] = 0.0            # 对手已经达标
            v_opp[i][0] = 0.0
        denom = 1.0 - self.f0 * self.g0
        for i in range(1, size):
            row_me = v_me[i]
            f_mid = self._f_mid[i]
            tail_f = self._tail_f[i]
            for j in range(1, size):
                b = tail_f
                for x, p in f_mid:
                    b += p * v_opp[i - x][j]
                d = 0.0
                for y, p in self._g_mid[j]:
                    d += p * row_me[j - y]
                v = (b + self.f0 * d) / denom
                row_me[j] = v
                v_opp[i][j] = d + self.g0 * v
        self.v_me = v_me
        self.v_opp = v_opp

    def _idx(self, remaining_points: int) -> int:
        """剩余分数 -> 赛跑表下标（向上取整到分数格）"""
        return max(0, min(self.size - 1,
                          -(-max(0, int(remaining_points)) // self.step)))

    def win_prob_my_turn(self, my_points: int, opp_points: int) -> float:
        """轮到我行动时的胜率（参数为双方还差的分数）"""
        return self.v_me[self._idx(my_points)][self._idx(opp_points)]

    def win_prob_opp_turn(self, my_points: int, opp_points: int) -> float:
        """轮到对手行动时的胜率（参数为双方还差的分数）"""
        return self.v_opp[self._idx(my_points)][self._idx(opp_points)]


class WinTurn:
    """本回合的胜率最优策略表。

    给定双方剩余分，把「入账」的价值定义为 V_opp(入账后的剩余, 对手剩余)（即换手
    后我的胜率），把「继续掷」的价值按所有掷出结果与可锁定子集精确求和，取较大者。
    这样：
      · 已达到剩余分 → 立即入账（赢）；
      · 越接近目标，溢出分越不值钱，会及时收手；
      · 对手越接近胜利，入账的保守收益越低，会主动提高风险去搏。
    """

    def __init__(self, policy: Policy, race: RaceModel, my_units: int, opp_units: int):
        self.pol = policy
        self.race = race
        self.my_units = max(1, int(my_units))
        self.opp_units = max(0, int(opp_units))
        self.step = policy.step
        self._build()

    def _build(self) -> None:
        pol = self.pol
        n = self.my_units                     # 只用得到 s < 剩余分的部分
        self.n = n
        self.bust_value = self.race.win_prob_opp_turn(self.my_units * self.step,
                                                      self.opp_units * self.step)
        W = [[0.0] * n for _ in pol.states]
        bank = [[False] * n for _ in pol.states]
        for i in range(n - 1, -1, -1):
            bank_v = self.race.win_prob_opp_turn((self.my_units - i) * self.step,
                                                 self.opp_units * self.step)
            for si in range(len(pol.states)):
                cont = 0.0
                for p, opts in pol.groups[si]:
                    if not opts:
                        cont += p * self.bust_value
                        continue
                    best = -1.0
                    for rem_i, sc in opts:
                        j = i + sc // self.step
                        v = 1.0 if j >= n else W[rem_i][j]
                        if v > best:
                            best = v
                    cont += p * best
                if bank_v >= cont - _EPS:
                    W[si][i] = bank_v
                    bank[si][i] = True
                else:
                    W[si][i] = cont
        self.W = W
        self._bank = bank

    def _lock_value(self, rem_kinds, s: int) -> float:
        if s >= self.my_units * self.step:
            return 1.0
        si = self.pol.index[self.pol._state_key(rem_kinds)]
        return self.W[si][s // self.step]

    def should_bank(self, kinds, s: int) -> bool:
        """剩余骰型 kinds、本回合已累计 s 分时是否应当入账"""
        if s >= self.my_units * self.step:
            return True
        si = self.pol.index[self.pol._state_key(kinds)]
        return self._bank[si][s // self.step]

    def best_lock(self, dice, s: int):
        """按胜率最大化选择本次锁定的骰子；无解返回 None"""
        return self.pol.best_lock(dice, s, value_fn=self._lock_value)


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
