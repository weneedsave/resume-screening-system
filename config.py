import logging
import os
import sys

#获取绝对路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Windows 中文环境下 stdout/stderr 默认用系统区域编码（cp936），
# 日志里的中文会变成一堆乱码，等于白加日志。这里统一切到 UTF-8。
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

# 统一日志配置：各模块用 logging.getLogger(__name__) 取 logger 即可
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


def _load_env():
    """从项目根目录的 .env 文件加载环境变量（不覆盖已存在的系统环境变量）。"""
    env_path = os.path.join(BASE_DIR, ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            # 跳过空行和注释行
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


_load_env()

UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
DB_PATH = os.path.join(BASE_DIR, "resume_ai.db")
MAX_CONTENT_LENGTH = 20 * 1024 * 1024  # 20MB

# DashScope（可选）
# DeepSeek（对话与视觉解析共用同一个模型）

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")

# 大模型接口超时（秒）。SDK 不给超时会用很长的默认值，一份简历卡住就能拖垮整批筛选。
AI_TIMEOUT = float(os.getenv("AI_TIMEOUT", "30"))

# 本机 Tesseract（可选）
TESSERACT_EXE = os.getenv("TESSERACT_EXE", r"E:\OCR\tesseract.exe")
TESSDATA_DIR = os.getenv("TESSDATA_DIR", r"E:\OCR\tessdata")

# 是否处理后删除上传文件
AUTO_DELETE_AFTER_PROCESS = False

# 调试模式：默认关闭（debug 模式会暴露堆栈与调试器，不能用于对外提供服务）。
# 本地开发想开热重载，设置环境变量 FLASK_DEBUG=1 再启动。
DEBUG = os.getenv("FLASK_DEBUG", "0") == "1"
