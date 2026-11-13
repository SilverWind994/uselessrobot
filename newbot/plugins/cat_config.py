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
    CAT_RARITY_NAMES = {"normal": "普通", "rare": "稀有", "epic": "史诗",
                        "legend": "传说", "hidden": "隐秘"}

    # 抽卡幸运：单抽有 1% 概率直接变成十连（仍只按 1 抽扣费）
    CAT_SUMMON_LUCKY_CHANCE = 0.01
    CAT_SUMMON_LUCKY_COUNT = 10

    # ==================== 鱼干经济 ====================
    CAT_SUMMON_COST = 100          # 单次抽卡
    CAT_SIGNIN_MIN = 80            # 签到鱼干下限
    CAT_SIGNIN_MAX = 120           # 签到鱼干上限
    CAT_SIGNIN_CRIT_CHANCE = 0.10  # 暴击概率（双倍）；超级暴击概率为其平方（四倍）
    CAT_SIGNIN_LOW_FISH = 2500     # 签到暴击提升的鱼干阈值（低于此值且非全服战力第一时生效）
    CAT_SIGNIN_BONUS_INTERVAL = 10  # 每多少天触发累计奖励
    CAT_SIGNIN_BONUS_CAP = 2000    # 累计奖励上限
    CAT_SIGNIN_HIDDEN_MILESTONES = (50, 70, 90, 110, 130)  # 累计签到送隐秘喵喵的天数
    CAT_SIGNIN_HIDDEN_CAT_ID = "mah01"                    # 隐秘喵喵「优衣喵(H)」
    CAT_WELCOME_FISH = 1000        # 新玩家初始
    CAT_DUP_REFUND_BY_RARITY = {"normal": 20, "rare": 50, "epic": 100,
                                "legend": 500, "hidden": 1000}

    # 猫眼石（抽卡积累，100换一只指定猫。仅由抽卡动作产生）
    CAT_EYE_STONE_PER_SUMMON = 1
    CAT_EYE_STONE_COST = 100

    # ==================== 喵保险 ====================
    # 购买后，接下来 10 次付费抽卡全部为普通（normal）才触发赔付；
    # 欧气「一抽变十连」不消耗进度；出现稀有及以上立即失效（保费不退）。
    CAT_INSURANCE_WINDOW = 10
    CAT_INSURANCE_PAYOUT_FISH = 1000      # 鱼干档赔付的鱼干数
    CAT_INSURANCE_PAYOUT_EYE = 10         # 鱼干档赔付的猫眼石数
    CAT_INSURANCE_PAYOUT_EYE_ONLY = 88    # 猫眼石档赔付的猫眼石数
    # 档位：price 为购买消耗（fish/eye），payout 为赔付类型
    CAT_INSURANCE_TIERS = {
        "fish66": {"name": "鱼干基础保", "cost_fish": 66, "cost_eye": 0,
                   "payout": "ten_pull", "payout_text": "赔付一次全卡池十连"},
        "fish88": {"name": "鱼干豪华保", "cost_fish": 88, "cost_eye": 0,
                   "payout": "fish_eye", "payout_text": "赔付 1000 鱼干 + 10 猫眼石"},
        "eye8": {"name": "猫眼石基础保", "cost_fish": 0, "cost_eye": 8,
                 "payout": "eye", "payout_text": "赔付 88 猫眼石"},
        "eye16": {"name": "猫眼石豪华保", "cost_fish": 0, "cost_eye": 16,
                  "payout": "legends", "payout_text": "赔付随机卡池全部传说各一只"},
    }

    # ==================== 养成与战斗 ====================
    CAT_MAX_STAR = 5              # 星级上限

    # 猫猫基础战力（按稀有度，1星基准）
    CAT_BASE_POWER_BY_RARITY = {"normal": 20, "rare": 30, "epic": 40, "legend": 50,
                                "hidden": 80}

    # 星级战力倍率：2星两倍兵力、3星转职、4星三倍兵力、5星转职
    CAT_STAR_POWER_MULT = {1: 1, 2: 2, 3: 2, 4: 3, 5: 3}

    # 特性适性加成：战斗类型/天气/地形每匹配一项的基础加成（按稀有度）
    # 3星×2、5星×3；仅出阵队员生效
    CAT_TRAIT_BONUS_BY_RARITY = {"normal": 0.02, "rare": 0.03, "epic": 0.04,
                                 "legend": 0.05, "hidden": 0.08}
    CAT_TRAIT_MULT_BY_STAR = {1: 1, 2: 1, 3: 2, 4: 2, 5: 3}

    # 战况枚举（特性适性的两个维度，猫的适性以后在 cat_pool.json 分配）
    CAT_WEATHER_TYPES = ["晴", "阴", "雨", "暴雨", "雪", "雾", "雷暴", "沙暴",
                         "大风", "冰雹", "酷暑", "严寒",
                         "血月", "月蚀", "星陨", "极光", "魔力风暴", "元素乱流",
                         "圣光降临"]
    CAT_TERRAIN_TYPES = ["平原", "山地", "森林", "水域", "沼泽", "沙漠", "雪原", "火山", "洞窟", "遗迹", "天空", "深海",
                         "龙巢", "神殿", "古战场", "深渊裂隙", "水晶矿脉", "诅咒之地", "妖精之森"]

    # ==================== 遗物研究（全服共享） ====================
    CAT_RELIC_RESEARCH_PATH = os.path.join(CAT_EXPEDITION_DIR, "relics.json")
    CAT_RELIC_IMG_DIR = os.path.join(CAT_EXPEDITION_DIR, "relics")

    # 研究力 = 基础值 + 该国猫猫稀有度折算（普通2/稀有3/史诗4/传说5）
    CAT_RELIC_BASE_SCORE = 10
    CAT_RELIC_RARITY_SCORE = {"normal": 2, "rare": 3, "epic": 4, "legend": 5}
    # 成功率 = 研究力 ÷ 除数；进度进入当阶段最后 10% 时除数改为 10000
    CAT_RELIC_DIVISOR = 1000
    CAT_RELIC_FINAL_DIVISOR = 10000
    CAT_RELIC_CRIT_CHANCE = 0.01      # 研究成功时的暴击概率
    CAT_RELIC_CRIT_GAIN = 5           # 暴击额外进度
    # 每个国家四件遗物，依次累计到以下进度随机解锁一件
    CAT_RELIC_REQUIREMENTS = (100, 200, 400, 800)

    # 遗物效果参数
    CAT_RELIC_CODEX_REFUND_CHANCE = 0.01    # 光典誓言之匣：每次抽卡返还鱼干
    CAT_RELIC_LENS_EYE_CHANCE = 0.01        # 月辉聚光镜：抽卡后额外获得 1 猫眼石
    CAT_RELIC_SHIELD_CHANCE = 0.0001        # 曦座日轮圣盾：远征后不消耗当日次数
    CAT_RELIC_SWORD_BONUS = 0.01            # 圣辉誓约长剑：远征战力额外 +1%

    # 国家代码 -> 该国遗物（目前只开放圣辉教国）
    CAT_RELICS = {
        "au": [
            {"id": "au_codex", "name": "光典誓言之匣", "icon": "光典誓言之匣",
             "effect": "每次抽卡时 1% 概率返还该次抽卡的鱼干"},
            {"id": "au_sword", "name": "圣辉誓约长剑", "icon": "圣辉誓约长剑",
             "effect": "远征战力计算完毕后额外增加 1%"},
            {"id": "au_shield", "name": "曦座日轮圣盾", "icon": "曦座日轮圣盾",
             "effect": "万分之一概率远征后不消耗当日远征次数"},
            {"id": "au_lens", "name": "月辉聚光镜", "icon": "月辉聚光镜",
             "effect": "抽卡后 1% 概率额外获得 1 猫眼石"},
        ],
    }

    # ==================== 远征Boss系统 ====================
    CAT_EXPEDITION_DATA = os.path.join(CAT_EXPEDITION_DIR, "expedition.json")  # 全局远征状态
    CAT_EXPEDITION_IMG_DIR = os.path.join(CAT_EXPEDITION_DIR, "expedition")    # 剧情/Boss图文件夹
    CAT_EXPEDITION_ACTS_PATH = os.path.join(CAT_EXPEDITION_DIR, "expedition_acts.json")  # 关卡配置

    CAT_EXPEDITION_RANDOM_MIN = 0.8   # 伤害随机下限
    CAT_EXPEDITION_RANDOM_MAX = 1.2   # 伤害随机上限

    CAT_EXPEDITION_CRIT_CHANCE = 0.10  # 远征暴击概率
    CAT_EXPEDITION_CRIT_MULT = 1.5     # 远征暴击伤害倍率
