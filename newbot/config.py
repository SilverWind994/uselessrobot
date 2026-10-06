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

    # ==================== 猫猫远征队（密钥/身份类，真实值在 config_local.py） ====================
    # 游戏数值与路径等插件配置在 plugins/cat_config.py 的 CatConfig 中
    CAT_ADMIN_QQ = 0                # 邮件功能（全服发放）仅管理员可用

    # ==================== 何切阿瓦隆问答 ====================
    AVALON_DIR = os.path.join(ASSETS_DIR, "avalon")
    AVALON_DATA_PATH = os.path.join(AVALON_DIR, "avalon_data.json")
    AVALON_QUESTION_IMG = os.path.join(AVALON_DIR, "question.png")  # 当前题目图片（每次出题覆盖）
    AVALON_SETTERS = [3187638890, 2544910201]  # 出题人白名单

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
