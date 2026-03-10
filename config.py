import os
import math
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

ARK_API_KEY  = os.getenv("ARK_API_KEY", "")
ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
ARK_MODEL_ID    = os.getenv("ARK_MODEL_ID",    "doubao-seedream-4-5-251128")
ARK_MODEL_ID_V5 = os.getenv("ARK_MODEL_ID_V5", "doubao-seedream-5-0-260128")
ARK_CHAT_MODEL  = os.getenv("ARK_CHAT_MODEL",  "doubao-seed-2-0-pro-260215")

DB_PATH = "data/prompts.db"

# 输出尺寸（API 支持：WIDTHxHEIGHT、1k、2k、4k）
IMAGE_SIZES = {
    "2K":   "2k",
    "4K":   "4k",
}

# 画面比例
ASPECT_RATIOS = ["1:1", "4:3", "3:4", "16:9", "9:16", "3:2", "2:3", "21:9"]

# 根据比例 + 画质计算 WxH
_QUALITY_BASE = {"2K": 2048, "4K": 3072}

_MIN_PIXELS = 3_686_400  # API 最低像素要求 (~1920x1920)

def compute_size(ratio_label: str, quality_label: str) -> str:
    w_r, h_r = map(int, ratio_label.split(":"))
    base = _QUALITY_BASE.get(quality_label, 1440)
    if w_r >= h_r:
        w = base
        h = int(base * h_r / w_r)
    else:
        h = base
        w = int(base * w_r / h_r)
    # 确保总像素不低于 API 最低要求，缩放后向上取整到 8 的倍数
    if w * h < _MIN_PIXELS:
        scale = (_MIN_PIXELS / (w * h)) ** 0.5
        w = math.ceil(w * scale / 8) * 8
        h = math.ceil(h * scale / 8) * 8
    else:
        w = math.ceil(w / 8) * 8
        h = math.ceil(h / 8) * 8
    return f"{w}x{h}"

# 生成后不再强制缩放，保持 API 原始输出尺寸
TARGET_SIZES: dict[str, tuple[int, int]] = {}

GLOBAL_NEGATIVE_PROMPT = (
    "blurry, low quality, distorted face, watermark, cartoon, "
    "noise, grain, ugly, deformed"
)

MAX_REF_IMAGE_PX = 1024
REQUEST_TIMEOUT  = 120

# ── 造梦 AI 服务平台（yswg.love）──────────────────────────────────────────────
YSWG_BASE_URL   = os.getenv("YSWG_BASE_URL",   "http://yswg.love:15091")
YSWG_APP_KEY    = os.getenv("YSWG_APP_KEY",    "")
YSWG_APP_SECRET = os.getenv("YSWG_APP_SECRET", "")

# ── 内部访问鉴权 ───────────────────────────────────────────────────────────────
API_TOKEN      = os.getenv("API_TOKEN",      "")
SECRET_KEY     = os.getenv("SECRET_KEY",     "change-me-in-production")
LOGIN_USERNAME = os.getenv("LOGIN_USERNAME", "admin")
LOGIN_PASSWORD = os.getenv("LOGIN_PASSWORD", "")
