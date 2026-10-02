import os


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")


class Config:
    ONE_BOT_URL = "http://localhost:3000"
    BOT_HOST = "0.0.0.0"
    BOT_PORT = 8080

    DATABASE = {
        "name": "robot",
        "user": "postgres",
        "password": "",
        "host": "127.0.0.1",
        "port": "5432",
    }

    FILES = {
        "users_ids": os.path.join(BASE_DIR, "users_ids_re.txt"),
        "groups_ids": os.path.join(BASE_DIR, "groups_ids_re.txt"),
        "json_dir": os.path.join(ASSETS_DIR, "jsonFile"),
    }

    ASSETS = {
        "uefig": os.path.join(ASSETS_DIR, "uefig"),
        "hasfinfig": os.path.join(ASSETS_DIR, "hasfinfig"),
        "htfig": os.path.join(ASSETS_DIR, "htfig"),
        "meme": os.path.join(ASSETS_DIR, "meme"),
        "tale": os.path.join(ASSETS_DIR, "tale"),
        "tale_answer": os.path.join(ASSETS_DIR, "taleanswer"),
        "output": os.path.join(ASSETS_DIR, "output"),
        "vt": os.path.join(ASSETS_DIR, "vt"),
    }

    # 硅基流动 API 配置（密钥从 config_local.py 读取，请勿在此填写）
    SILICONFLOW_BASE_URL = "https://api.siliconflow.cn/v1"
    SILICONFLOW_API_KEY = ""

    AI_MODEL = {
        "chat": "deepseek-ai/DeepSeek-V4-Flash",       # AI对话
        "summarise": "deepseek-ai/DeepSeek-V4-Flash",  # 群聊总结
        "reply": "deepseek-ai/DeepSeek-V4-Flash",      # 群自动回复
    }

    SYSTEM_USER_IDS = []
    ADMIN_USER_IDS = []

    SPECIAL_GROUPS = []

    # Steam API Key (用于 dsc/dsc2 命令，从 config_local.py 读取)
    STEAM_API_KEY = ""

    AI_VOICE = ["你是一个年轻活力的女高中生"]

    # ==================== 猫猫远征队 ====================
    CAT_EXPEDITION_DIR = os.path.join(ASSETS_DIR, "cat_expedition")
    CAT_POOL_PATH = os.path.join(CAT_EXPEDITION_DIR, "cat_pool.json")
    CAT_PLAYERS_PATH = os.path.join(CAT_EXPEDITION_DIR, "players.json")

    # 图片素材目录（图鉴/详情卡片合成用）
    CAT_IMG_CATS_DIR = os.path.join(CAT_EXPEDITION_DIR, "cats")     # 猫名.png 专属立绘，缺则用最终职业肖像
    CAT_IMG_JOBS_DIR = os.path.join(CAT_EXPEDITION_DIR, "jobs")     # 职业图标
    CAT_IMG_ORIGINS_DIR = os.path.join(CAT_EXPEDITION_DIR, "origins")  # 国家旗帜
    CAT_CARD_TEMPLATE = os.path.join(CAT_EXPEDITION_DIR, "data", "队员表格.png")
    CAT_CARD_CACHE_DIR = os.path.join(CAT_EXPEDITION_DIR, "data", "cache")  # 合成图缓存
    CAT_MAP_PATH = os.path.join(CAT_EXPEDITION_DIR, "data", "地图.png")     # 世界地图

    # 抽卡概率
    CAT_RARITY_RATES = {"normal": 0.75, "rare": 0.20, "epic": 0.04, "legend": 0.01}
    CAT_RARITY_NAMES = {"normal": "普通", "rare": "稀有", "epic": "史诗", "legend": "传说"}

    # 鱼干价格
    CAT_SUMMON_COST = 100          # 单次抽卡
    CAT_SIGNIN_MIN = 80            # 签到鱼干下限
    CAT_SIGNIN_MAX = 120           # 签到鱼干上限
    CAT_SIGNIN_CRIT_CHANCE = 0.10  # 暴击概率（双倍）
    CAT_SIGNIN_SUPER_CHANCE = 0.01 # 超级暴击概率（四倍）
    CAT_SIGNIN_BONUS_INTERVAL = 10  # 每多少天触发累计奖励
    CAT_SIGNIN_BONUS_CAP = 2000    # 累计奖励上限
    CAT_WELCOME_FISH = 1000        # 新玩家初始
    CAT_DUP_REFUND_BY_RARITY = {"normal": 20, "rare": 50, "epic": 100, "legend": 500}

    # 猫眼石（抽卡积累，100换一只指定猫）
    CAT_EYE_STONE_PER_SUMMON = 1
    CAT_EYE_STONE_COST = 100

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

    CAT_ADMIN_QQ = 0                # 邮件功能（全服发放）仅管理员可用（真实值在 config_local.py）

    # ==================== 远征Boss系统 ====================
    CAT_EXPEDITION_DATA = os.path.join(CAT_EXPEDITION_DIR, "expedition.json")  # 全局远征状态
    CAT_EXPEDITION_IMG_DIR = os.path.join(CAT_EXPEDITION_DIR, "expedition")    # 剧情/Boss图文件夹
    CAT_EXPEDITION_ACTS_PATH = os.path.join(CAT_EXPEDITION_DIR, "expedition_acts.json")  # 关卡配置

    CAT_EXPEDITION_RANDOM_MIN = 0.8   # 伤害随机下限
    CAT_EXPEDITION_RANDOM_MAX = 1.2   # 伤害随机上限

    @classmethod
    def get_db_url(cls):
        db = cls.DATABASE
        return f"postgresql://{db['user']}:{db['password']}@{db['host']}:{db['port']}/{db['name']}"


# ==================== 本地私密配置覆盖（不入库） ====================
# config_local.py 中定义的全大写变量会自动覆盖上面的默认值，
# 模板见 config.example.py；config_local.py 已在 .gitignore 中忽略。
try:
    import config_local as _local
except ImportError:
    _local = None

if _local is not None:
    for _name in dir(_local):
        if _name.isupper():
            setattr(Config, _name, getattr(_local, _name))
    del _name
    del _local
