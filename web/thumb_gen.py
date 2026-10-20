# -*- coding: utf-8 -*-
"""喵喵远征队素材缩略图批量生成。

把原图（1~7MB 的 PNG 立绘/图标/插画）缩到网页端实际需要的尺寸，
输出到原目录的同名子目录下，格式统一为 WebP（体积约为原 PNG 的 5%~15%）。

用法：
    python -m web.thumb_gen           # 生成全部缺失的缩略图
    python -m web.thumb_gen --force   # 强制重新生成
"""
import argparse
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO, "newbot"))
from PIL import Image

from plugins.cat_config import CatConfig

# 源目录 → (缩略图子目录名, 最长边像素)
# 列表/卡片小图与旗帜只需 256；章节插画、世界地图等大图留 1024
_TARGETS = [
    (CatConfig.CAT_IMG_CATS_DIR,      ("thumb", 256)),
    (CatConfig.CAT_IMG_JOBS_DIR,      ("thumb", 256)),
    (CatConfig.CAT_IMG_ORIGINS_DIR,   ("thumb", 256)),
    (CatConfig.CAT_EXPEDITION_IMG_DIR, ("large", 1024)),
    (os.path.join(CatConfig.CAT_EXPEDITION_DIR, "data"), ("large", 1024)),
]

_WEBP_KW = dict(format="WEBP", quality=82, method=4)


def _make(src: str, dst: str, max_side: int) -> None:
    img = Image.open(src)
    img.thumbnail((max_side, max_side), Image.LANCZOS)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    img.save(dst, **_WEBP_KW)


def run(force: bool = False) -> None:
    total = made = 0
    for src_dir, (sub, side) in _TARGETS:
        if not os.path.isdir(src_dir):
            continue
        out_dir = os.path.join(src_dir, sub)
        for name in os.listdir(src_dir):
            src = os.path.join(src_dir, name)
            if not os.path.isfile(src) or not name.lower().endswith(".png"):
                continue
            dst = os.path.join(out_dir, os.path.splitext(name)[0] + ".webp")
            total += 1
            if not force and os.path.exists(dst) and os.path.getmtime(dst) >= os.path.getmtime(src):
                continue
            try:
                _make(src, dst, side)
                made += 1
                print(f"[{side:>4}px] {name} -> {os.path.getsize(dst)//1024} KB "
                      f"(原 {os.path.getsize(src)//1024} KB)")
            except Exception as e:
                print(f"[失败] {name}: {e}")
    print(f"完成：{made} 张新生成 / 共 {total} 张")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="强制重新生成")
    run(force=ap.parse_args().force)
