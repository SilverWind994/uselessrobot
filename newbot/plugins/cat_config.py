import os

# 猫猫远征队插件专属配置：游戏数值、路径等实现细节随插件走。
# 框架级/密钥类配置（如 CAT_ADMIN_QQ）仍在新bot根目录的 config.py 中。

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # newbot/
_ASSETS_DIR = os.path.join(_BASE_DIR, "assets")


class CatConfig:
    # ==================== 路径 ====================
    CAT_EXPEDITION_DIR = os.path.join(_ASSETS_DIR, "cat_expedition")
    CAT_POOL_PATH = os.path.join(CAT_EXPEDITION_DIR, "cat_pool.json")
    CAT_PLAYERS_PATH = os.path.join(CAT_EXPEDITION_DIR, "players.json")

    # 图片素材目录（图鉴/详情卡片合成用）
    CAT_IMG_CATS_DIR = os.path.join(CAT_EXPEDITION_DIR, "cats")     # 猫名.png 专属立绘，缺则用最终职业肖像
    CAT_IMG_JOBS_DIR = os.path.join(CAT_EXPEDITION_DIR, "jobs")     # 职业图标
    CAT_IMG_ORIGINS_DIR = os.path.join(CAT_EXPEDITION_DIR, "origins")  # 国家旗帜
    CAT_CARD_TEMPLATE = os.path.join(CAT_EXPEDITION_DIR, "data", "队员表格.png")
    CAT_CARD_CACHE_DIR = os.path.join(CAT_EXPEDITION_DIR, "data", "cache")  # 合成图缓存
    CAT_MAP_PATH = os.path.join(CAT_EXPEDITION_DIR, "data", "地图.png")     # 世界地图

    # ==================== 抽卡 ====================
    CAT_RARITY_RATES = {"normal": 0.75, "rare": 0.20, "epic": 0.04, "legend": 0.01}
    CAT_RARITY_NAMES = {"normal": "普通", "rare": "稀有", "epic": "史诗", "legend": "传说"}

    # 抽卡幸运：单抽有 1% 概率直接变成十连（仍只按 1 抽扣费）
    CAT_SUMMON_LUCKY_CHANCE = 0.01
    CAT_SUMMON_LUCKY_COUNT = 10

    # ==================== 鱼干经济 ====================
    CAT_SUMMON_COST = 100          # 单次抽卡
    CAT_SIGNIN_MIN = 80            # 签到鱼干下限
    CAT_SIGNIN_MAX = 120           # 签到鱼干上限
    CAT_SIGNIN_CRIT_CHANCE = 0.10  # 暴击概率（双倍）
    CAT_SIGNIN_SUPER_CHANCE = 0.01 # 超级暴击概率（四倍）
    CAT_SIGNIN_LOW_FISH = 1000     # 签到暴击提升的鱼干阈值（低于此值且非全服战力第一时生效）
    CAT_SIGNIN_BONUS_INTERVAL = 10  # 每多少天触发累计奖励
    CAT_SIGNIN_BONUS_CAP = 2000    # 累计奖励上限
    CAT_WELCOME_FISH = 1000        # 新玩家初始
    CAT_DUP_REFUND_BY_RARITY = {"normal": 20, "rare": 50, "epic": 100, "legend": 500}

    # 猫眼石（抽卡积累，100换一只指定猫）
    CAT_EYE_STONE_PER_SUMMON = 1
    CAT_EYE_STONE_COST = 100

    # ==================== 养成与战斗 ====================
    CAT_MAX_STAR = 5              # 星级上限

    # 猫猫基础战力（按稀有度，1星基准）
    CAT_BASE_POWER_BY_RARITY = {"normal": 20, "rare": 30, "epic": 40, "legend": 50}

    # 星级战力倍率：2星两倍兵力、3星转职、4星三倍兵力、5星转职
    CAT_STAR_POWER_MULT = {1: 1, 2: 2, 3: 2, 4: 3, 5: 3}

    # 特性适性加成：战斗类型/天气/地形每匹配一项的基础加成（按稀有度）
    # 3星×2、5星×3；仅出阵队员生效
    CAT_TRAIT_BONUS_BY_RARITY = {"normal": 0.02, "rare": 0.03, "epic": 0.04, "legend": 0.05}
    CAT_TRAIT_MULT_BY_STAR = {1: 1, 2: 1, 3: 2, 4: 2, 5: 3}

    # 战况枚举（特性适性的两个维度，猫的适性以后在 cat_pool.json 分配）
    CAT_WEATHER_TYPES = ["晴", "阴", "雨", "暴雨", "雪", "雾", "雷暴", "沙暴",
                         "大风", "冰雹", "酷暑", "严寒",
                         "血月", "月蚀", "星陨", "极光", "魔力风暴", "元素乱流"]
    CAT_TERRAIN_TYPES = ["平原", "山地", "森林", "水域", "沼泽", "沙漠", "雪原", "火山", "洞窟", "遗迹", "天空", "深海",
                         "龙巢", "神殿", "古战场", "深渊裂隙", "水晶矿脉", "诅咒之地", "妖精之森"]

    # 远征队位置上限（初始值，可通过游戏内成长提升，实际值存在玩家存档）
    CAT_INITIAL_DEPLOY_LIMIT = 3    # 出阵猫猫上限初始值
    CAT_INITIAL_RESEARCH_LIMIT = 3  # 研究猫猫上限初始值

    # ==================== 远征Boss系统 ====================
    CAT_EXPEDITION_DATA = os.path.join(CAT_EXPEDITION_DIR, "expedition.json")  # 全局远征状态
    CAT_EXPEDITION_IMG_DIR = os.path.join(CAT_EXPEDITION_DIR, "expedition")    # 剧情/Boss图文件夹
    CAT_EXPEDITION_ACTS_PATH = os.path.join(CAT_EXPEDITION_DIR, "expedition_acts.json")  # 关卡配置

    CAT_EXPEDITION_RANDOM_MIN = 0.8   # 伤害随机下限
    CAT_EXPEDITION_RANDOM_MAX = 1.2   # 伤害随机上限

    CAT_EXPEDITION_CRIT_CHANCE = 0.10  # 远征暴击概率
    CAT_EXPEDITION_CRIT_MULT = 1.5     # 远征暴击伤害倍率
