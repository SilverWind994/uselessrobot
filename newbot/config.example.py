# 本地配置模板
# 使用方法：复制本文件为 config_local.py，填入真实值后保存。
# config_local.py 已在 .gitignore 中忽略，不会被提交到 GitHub。

# PostgreSQL 数据库连接配置
DATABASE = {
    "name": "robot",
    "user": "postgres",
    "password": "你的数据库密码",
    "host": "127.0.0.1",
    "port": "5432",
}

# 硅基流动 API Key（AI 对话 / 总结 / 自动回复 / TTS）
# 申请地址：https://cloud.siliconflow.cn/
SILICONFLOW_API_KEY = "sk-你的key"

# Steam API Key（dsc/dsc2 命令查询战绩用）
# 申请地址：https://steamcommunity.com/dev/apikey
STEAM_API_KEY = "你的steam_api_key"

# 系统级 QQ（这些号的消息机器人不响应）
SYSTEM_USER_IDS = [123456789]

# 管理员 QQ（可使用管理命令）
ADMIN_USER_IDS = [123456789]

# 开启自动聊天回复的群号列表
SPECIAL_GROUPS = [123456789, 987654321]

# 猫猫远征队：全服邮件功能的管理员 QQ
CAT_ADMIN_QQ = 123456789
