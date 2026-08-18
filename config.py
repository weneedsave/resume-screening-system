import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


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
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
DASHSCOPE_MODEL = os.getenv("DASHSCOPE_MODEL", "qwen3.6-plus")

# 本机 Tesseract（可选）
TESSERACT_EXE = os.getenv("TESSERACT_EXE", r"E:\OCR\tesseract.exe")
TESSDATA_DIR = os.getenv("TESSDATA_DIR", r"E:\OCR\tessdata")

# 是否处理后删除上传文件
AUTO_DELETE_AFTER_PROCESS = False
