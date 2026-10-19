"""网页端玩家身份：密码哈希与登录令牌签名。

机器人（私聊里设置密码）与网页服务共用这里的哈希/校验逻辑，保证两边算法一致。
密码只以「随机盐 + PBKDF2 哈希」形式存档，不可逆，因此任何地方都无法回显明文。
"""

import base64
import hashlib
import hmac
import os
import time

PBKDF2_ITERATIONS = 120000   # 迭代次数：够慢到难以爆破，又不会拖慢设置密码
SALT_BYTES = 16
PASSWORD_MIN = 6             # 密码长度下限
PASSWORD_MAX = 32            # 密码长度上限
TOKEN_TTL = 7 * 24 * 60 * 60  # 登录令牌有效期：7 天


def make_salt() -> str:
    """生成随机盐（hex）"""
    return os.urandom(SALT_BYTES).hex()


def hash_password(password: str, salt: str) -> str:
    """按盐计算密码哈希（hex）"""
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                               salt.encode("utf-8"), PBKDF2_ITERATIONS).hex()


def verify_password(password: str, salt: str, pwd_hash: str) -> bool:
    """校验密码；盐或哈希为空表示尚未设置密码，一律不通过"""
    if not salt or not pwd_hash:
        return False
    return hmac.compare_digest(hash_password(password, salt), pwd_hash)


def check_password_text(password: str) -> str:
    """校验新密码是否合法，返回错误提示（合法时返回空串）"""
    if not password:
        return "密码不能为空喵"
    if len(password) < PASSWORD_MIN or len(password) > PASSWORD_MAX:
        return f"密码长度需为 {PASSWORD_MIN}~{PASSWORD_MAX} 位喵"
    if any(c.isspace() for c in password):
        return "密码不能包含空格喵"
    return ""


def _sign(payload: bytes, secret: bytes) -> str:
    return hmac.new(secret, payload, hashlib.sha256).hexdigest()


def make_token(qq: int, secret: bytes, ttl: int = TOKEN_TTL) -> str:
    """签发登录令牌：base64(QQ|过期时间) + HMAC 签名"""
    payload = f"{qq}|{int(time.time()) + ttl}".encode("utf-8")
    body = base64.urlsafe_b64encode(payload).decode("ascii")
    return f"{body}.{_sign(payload, secret)}"


def parse_token(token: str, secret: bytes):
    """校验登录令牌，返回其中的 QQ；无效或已过期返回 None"""
    if not token or "." not in token:
        return None
    body, _, sig = token.partition(".")
    try:
        payload = base64.urlsafe_b64decode(body.encode("ascii"))
    except Exception:
        return None
    if not hmac.compare_digest(_sign(payload, secret), sig):
        return None
    try:
        qq_text, expire_text = payload.decode("utf-8").split("|")
        qq, expire = int(qq_text), int(expire_text)
    except ValueError:
        return None
    if expire < time.time():
        return None
    return qq
