"""玩家头像：保存上传图片、生成可访问地址。

头像统一裁成方形 PNG 存在 assets/cat_expedition/avatars/{qq}.png，
网页端用圆形边框显示；没有头像时前端回退到昵称首字。
"""

import base64
import io
import os

from PIL import Image

from plugins.cat_config import CatConfig

AVATAR_DIR = CatConfig.CAT_AVATAR_DIR
AVATAR_SIZE = 128                 # 保存尺寸（正方形）
MAX_UPLOAD_BYTES = 4 * 1024 * 1024  # 原始图片上限 4MB
MIN_SIDE = 16                     # 太小的图不接收

os.makedirs(AVATAR_DIR, exist_ok=True)


def _path(qq) -> str:
    return os.path.join(AVATAR_DIR, f"{int(qq)}.png")


def avatar_url(qq) -> str:
    """返回头像地址；没有上传过时返回空串"""
    try:
        path = _path(qq)
    except (TypeError, ValueError):
        return ""
    if not os.path.exists(path):
        return ""
    try:
        version = int(os.path.getmtime(path))
    except OSError:
        version = 0
    return f"/avatars/{int(qq)}.png?v={version}"


def save_avatar(qq, data_url: str) -> str:
    """保存 base64 图片，成功返回空串，失败返回提示文案。"""
    text = str(data_url or "")
    if text.startswith("data:"):
        if "," not in text:
            return "图片格式不对喵"
        text = text.split(",", 1)[1]
    text = text.strip()
    if not text:
        return "请先选择一张图片喵"
    try:
        raw = base64.b64decode(text, validate=True)
    except Exception:
        return "图片解析失败，请重新选择喵"
    if not raw:
        return "图片是空的喵"
    if len(raw) > MAX_UPLOAD_BYTES:
        return "图片太大喵（最多 4MB）"

    try:
        image = Image.open(io.BytesIO(raw))
        image.load()
    except Exception:
        return "只能上传图片文件喵"

    if min(image.size) < MIN_SIDE:
        return "图片太小喵，至少需要 16×16"
    if image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGBA")

    # 居中裁成正方形，再缩放成统一尺寸
    side = min(image.size)
    left = (image.width - side) // 2
    top = (image.height - side) // 2
    image = image.crop((left, top, left + side, top + side))
    image = image.resize((AVATAR_SIZE, AVATAR_SIZE), Image.LANCZOS)

    path = _path(qq)
    tmp = path + ".tmp"
    try:
        image.save(tmp, "PNG")
        os.replace(tmp, path)
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass
        return "头像保存失败喵，稍后再试"
    return ""
