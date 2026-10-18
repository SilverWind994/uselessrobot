"""运行时图片清理：删除各插件生成目录中超过指定时长的图片，避免堆积。

设计原则：
- 只清理「运行时生成」的图片（合成图、缓存图、题目图等），不碰原始素材
- 素材目录（猫立绘、麻将牌面）始终保留
- 各插件的 state.json 等数据文件不删
"""
import os
import time

# 运行时会生成图片的目录（相对 newbot/assets）
_RUNTIME_IMAGE_DIRS = [
    "mahjong17",          # 17步麻将：tiles_/view_/table_/end_/result_*.png
    "yahtzee",            # 快艇骰子：board_/dice_*.png
    "farkle",             # Farkle：board_*.png
    "tournament",         # 锦标赛：bracket_*.png
    "avalon",             # 何切阿瓦隆：question_*.png
    "cat_expedition/data/cache",  # 猫猫图鉴卡片缓存
]

# 这些扩展名的文件才会被清理（避免误删 state.json 等）
_IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp")

DEFAULT_MAX_AGE_SECONDS = 12 * 60 * 60   # 12 小时


def cleanup_old_images(assets_dir: str,
                       max_age: int = DEFAULT_MAX_AGE_SECONDS) -> int:
    """删除运行时图片目录中早于 max_age 秒的图片，返回删除数量。

    每个目录内部只删文件，不递归子目录（素材都放在别的地方）。
    """
    now = time.time()
    removed = 0
    for sub in _RUNTIME_IMAGE_DIRS:
        folder = os.path.join(assets_dir, sub)
        if not os.path.isdir(folder):
            continue
        try:
            entries = os.listdir(folder)
        except OSError:
            continue
        for name in entries:
            path = os.path.join(folder, name)
            if not os.path.isfile(path):
                continue
            if not name.lower().endswith(_IMAGE_EXTS):
                continue
            try:
                if now - os.path.getmtime(path) > max_age:
                    os.remove(path)
                    removed += 1
            except OSError:
                continue
    return removed
