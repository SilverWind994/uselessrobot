import os
import random
import threading
import time
from typing import Optional

from core.command_router import CommandContext, CommandRouter
from core.message_sender import Target
from plugins.cat_stock import _load_json, _save_json

# 喵红包：QQ 群里发鱼干 / 猫眼石 / 猫薄荷，随机分成不等的份数，用红包 id 抢。
# 猫薄荷走喵股市账本；红包转入转出都会计入充提流水，因此不会改变股市盈亏排行的结果。

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # newbot/
PACKET_DIR = os.path.join(_BASE_DIR, "assets", "red_packet")
PACKET_PATH = os.path.join(PACKET_DIR, "packets.json")

PACKET_MAX_SHARES = 50          # 单个红包最多分多少份
PACKET_KEEP_SECONDS = 7 * 3600 * 24  # 抢完的红包保留 7 天后清理
PACKET_EXPIRE_SECONDS = 24 * 3600    # 24 小时没抢完，剩余金额自动退回发送者

_KIND_NAMES = {"fish": "鱼干", "eye_stones": "猫眼石", "catnip": "猫薄荷"}


def _parse_kind(token: str) -> Optional[str]:
    token = token.lower()
    if token in ("鱼干", "鱼", "fish"):
        return "fish"
    if token in ("猫眼石", "猫眼", "石头", "stone", "eye", "eyestone"):
        return "eye_stones"
    if token in ("猫薄荷", "薄荷", "catnip", "nip"):
        return "catnip"
    return None


class RedPacketPlugin:
    """喵红包：发红包、抢红包、查看红包"""

    def __init__(self, sender, cat_game, stock_plugin):
        self._sender = sender
        self._cat = cat_game
        self._stock = stock_plugin
        self._lock = threading.Lock()
        os.makedirs(PACKET_DIR, exist_ok=True)

    def register(self, router: CommandRouter) -> None:
        router.register(
            ["喵红包", "红包", "redpacket", ".redpacket"],
            self.cmd_packet,
            description="喵红包·发鱼干/猫眼石/猫薄荷，随机分成不等份数，用红包 id 抢"
        )

    # ==================== 存档 ====================

    def _load(self) -> dict:
        return _load_json(PACKET_PATH)

    def _save(self, packets: dict) -> None:
        _save_json(PACKET_PATH, packets)

    @staticmethod
    def _scope(target: Target) -> str:
        return f"g{target.group_id}" if target.is_group else f"p{target.user_id}"

    def _nick(self, qq: int) -> str:
        player = self._cat._peek_player(qq) or {}
        return player.get("nick") or str(qq)

    @staticmethod
    def _remaining(pkt: dict) -> int:
        return int(pkt["total"]) - sum(int(c["amount"]) for c in pkt.get("claims", []))

    def _load_and_clean(self) -> dict:
        """读红包存档，顺便把到期没抢完的剩余金额退回发送者"""
        packets = self._load()
        now = int(time.time())
        changed = False
        for pkt in packets.values():
            if self._remaining(pkt) <= 0:
                continue
            if now < int(pkt.get("expires_at", pkt.get("created_at", now))):
                continue
            remaining = self._remaining(pkt)
            self._refund(pkt, remaining)
            pkt.setdefault("claims", []).append({
                "qq": int(pkt["sender"]), "amount": remaining,
                "ts": now, "refund": True,
            })
            changed = True
        if changed:
            self._save(packets)
        return packets

    def _refund(self, pkt: dict, amount: int) -> None:
        sender = int(pkt["sender"])
        kind = pkt["kind"]
        if kind == "catnip":
            self._stock.catnip_transfer_in(sender, amount)
        elif kind == "fish":
            self._cat.add_fish(sender, amount)
        else:
            self._cat.add_eye_stones(sender, amount)

    # ==================== 命令入口 ====================

    def cmd_packet(self, ctx: CommandContext) -> None:
        target = Target.from_data(ctx.raw_data)
        args = (ctx.get_args() or "").strip()
        if not args:
            self._list(target)
            return
        parts = args.split()
        sub = parts[0].lower()
        if sub in ("发", "发红包", "create", "send"):
            self._create(target, ctx.user_id, parts[1:])
        elif sub in ("抢", "领", "领取", "grab"):
            if not parts[1:]:
                self._sender.send_text(target, "用法：喵红包 抢 <红包id>")
                return
            self._grab(target, ctx.user_id, parts[1])
        elif sub in ("查", "查看", "状态", "info"):
            if not parts[1:]:
                self._sender.send_text(target, "用法：喵红包 查 <红包id>")
                return
            self._info(target, parts[1])
        elif sub.isdigit():
            self._grab(target, ctx.user_id, sub)
        else:
            self._sender.send_text(target, self._usage())

    @staticmethod
    def _usage() -> str:
        return ("【喵红包】\n"
                "发：喵红包 发 <总金额> <份数> <类型>\n"
                "　例：喵红包 发 1000 5 鱼干\n"
                "　类型可选：鱼干 / 猫眼石 / 猫薄荷\n"
                "抢：喵红包 抢 <红包id>\n"
                "查：喵红包 查 <红包id>\n"
                "不带参数：查看本群还在抢的红包\n"
                "不收手续费，随机分成不等金额，每份至少 1\n"
                "24 小时内没抢完，剩余金额自动退回发送者")

    # ==================== 发红包 ====================

    def _create(self, target: Target, qq: int, args: list) -> None:
        kind = None
        nums = []
        for token in args:
            k = _parse_kind(token)
            if k:
                kind = k
            elif token.isdigit():
                nums.append(int(token))
        if kind is None or len(nums) < 2:
            self._sender.send_text(target, self._usage())
            return
        total, count = nums[0], nums[1]
        name = _KIND_NAMES[kind]

        if total <= 0 or count <= 0:
            self._sender.send_text(target, "金额和份数都要大于 0 喵～")
            return
        if count > PACKET_MAX_SHARES:
            self._sender.send_text(target, f"一个红包最多分 {PACKET_MAX_SHARES} 份喵～")
            return
        if total < count:
            self._sender.send_text(target, f"每份至少 1 {name}，总金额不能少于份数喵～")
            return

        with self._lock:
            packets = self._load_and_clean()
            # 清理很久以前就抢完的红包
            now = int(time.time())
            for pid in list(packets):
                pkt = packets[pid]
                if (self._remaining(pkt) <= 0
                        and now - int(pkt.get("created_at", now)) > PACKET_KEEP_SECONDS):
                    del packets[pid]

            # 扣款（失败时立即返回，不产生红包记录）
            if kind == "catnip":
                ok, balance = self._stock.catnip_transfer_out(qq, total)
                if not ok:
                    self._sender.send_text(
                        target, f"猫薄荷不够啦！你现在有 {balance} 猫薄荷，红包不能发成负债喵")
                    return
            else:
                player = self._cat._get_player(qq)
                balance = int(player.get(kind, 0))
                if balance < total:
                    self._sender.send_text(
                        target, f"{name}不够啦！你现在有 {balance} {name}，红包不能发成负债喵")
                    return
                player[kind] = balance - total
                self._cat._update_player(qq, player)

            pid = self._new_id(packets)
            packets[pid] = {
                "id": pid,
                "sender": qq,
                "sender_nick": self._nick(qq),
                "scope": self._scope(target),
                "kind": kind,
                "total": total,
                "count": count,
                "claims": [],
                "created_at": now,
                "expires_at": now + PACKET_EXPIRE_SECONDS,
            }
            self._save(packets)

        self._sender.send_text(
            target,
            f"🧧 红包已发出！\n"
            f"红包 id：{pid}｜{total} {name} 分 {count} 份\n"
            f"发送「喵红包 抢 {pid}」开抢，先到先得喵～\n"
            f"（24 小时内没抢完，剩余会自动退回给你）"
        )

    def _new_id(self, packets: dict) -> str:
        while True:
            pid = str(random.randint(100000, 999999))
            if pid not in packets:
                return pid

    # ==================== 抢红包 ====================

    def _grab(self, target: Target, qq: int, pid: str) -> None:
        with self._lock:
            packets = self._load_and_clean()
            pkt = packets.get(pid.strip())
            if pkt is None:
                self._sender.send_text(target, f"没有找到红包 {pid} 喵～")
                return
            if pkt.get("scope") != self._scope(target):
                self._sender.send_text(target, "这个红包不在当前聊天里喵～")
                return
            if self._remaining(pkt) <= 0:
                self._sender.send_text(target, "这个红包已经被抢光了喵～")
                return
            if any(int(c["qq"]) == qq for c in pkt.get("claims", [])):
                self._sender.send_text(target, "你已经抢过这个红包了喵～")
                return

            amount = self._next_share(pkt)
            kind = pkt["kind"]
            name = _KIND_NAMES[kind]
            pkt.setdefault("claims", []).append({
                "qq": qq, "amount": amount, "ts": int(time.time()),
            })
            self._save(packets)

        # 发放奖励放在锁外，避免跨存档文件长时间持锁
        if kind == "catnip":
            balance = self._stock.catnip_transfer_in(qq, amount)
            self._sender.send_text(
                target, f"🧧 抢到 {amount} 猫薄荷！当前共 {balance} 猫薄荷")
        elif kind == "fish":
            self._cat.add_fish(qq, amount)
        else:
            self._cat.add_eye_stones(qq, amount)
        if kind != "catnip":
            left_count = pkt["count"] - len(pkt["claims"])
            left_amount = self._remaining(pkt)
            if left_count <= 0:
                self._sender.send_text(target, f"🧧 抢到 {amount} {name}！红包已抢光")
            else:
                self._sender.send_text(
                    target,
                    f"🧧 抢到 {amount} {name}！"
                    f"红包还剩 {left_count} 份 / {left_amount} {name}")

    @staticmethod
    def _next_share(pkt: dict) -> int:
        """随机分一份：保证每份至少 1，且留够后面每人至少 1"""
        claims = pkt.get("claims", [])
        left_count = int(pkt["count"]) - len(claims)
        left_amount = RedPacketPlugin._remaining(pkt)
        if left_count <= 1:
            return left_amount
        max_share = left_amount - (left_count - 1)
        cap = max(1, min(max_share, int(left_amount / left_count * 2) + 1))
        return random.randint(1, cap)

    # ==================== 查看 ====================

    def _list(self, target: Target) -> None:
        scope = self._scope(target)
        with self._lock:
            packets = self._load_and_clean()
        opened = [p for p in packets.values()
                  if p.get("scope") == scope and self._remaining(p) > 0]
        if not opened:
            self._sender.send_text(
                target, "当前聊天没有还在抢的红包喵～\n" + self._usage())
            return
        opened.sort(key=lambda p: p.get("created_at", 0), reverse=True)
        lines = ["【喵红包 · 还在抢】"]
        for pkt in opened[:5]:
            name = _KIND_NAMES.get(pkt["kind"], pkt["kind"])
            left_count = int(pkt["count"]) - len(pkt.get("claims", []))
            lines.append(
                f"  {pkt['id']}｜{pkt['sender_nick']} 的 {name}，"
                f"还剩 {left_count}/{pkt['count']} 份 / {self._remaining(pkt)} {name}")
        lines.append("")
        lines.append("发送「喵红包 抢 <红包id>」开抢")
        self._sender.send_text(target, "\n".join(lines))

    def _info(self, target: Target, pid: str) -> None:
        with self._lock:
            packets = self._load_and_clean()
        pkt = packets.get(pid.strip())
        if pkt is None:
            self._sender.send_text(target, f"没有找到红包 {pid} 喵～")
            return
        if pkt.get("scope") != self._scope(target):
            self._sender.send_text(target, "这个红包不在当前聊天里喵～")
            return
        name = _KIND_NAMES.get(pkt["kind"], pkt["kind"])
        claims = [c for c in pkt.get("claims", []) if not c.get("refund")]
        refunds = [c for c in pkt.get("claims", []) if c.get("refund")]
        lines = [f"【喵红包 {pkt['id']}】{pkt['sender_nick']} 发出",
                 f"总额 {pkt['total']} {name} / {pkt['count']} 份，"
                 f"已抢 {len(claims)} 份，剩余 {self._remaining(pkt)} {name}"]
        for c in claims:
            lines.append(f"  {self._nick(int(c['qq']))}：{c['amount']} {name}")
        for c in refunds:
            lines.append(f"  （到期未抢完，{c['amount']} {name} 已退回发送者）")
        if self._remaining(pkt) <= 0:
            lines.append("（已到期）" if refunds else "（已抢光）")
        self._sender.send_text(target, "\n".join(lines))
