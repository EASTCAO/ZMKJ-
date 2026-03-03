"""
prompt_db.py — SQLite 提示词 CRUD + 海马体摄影风格预设
"""
import sqlite3
import os
from config import DB_PATH

PRESETS = [
    {
        "name": "清新自然风",
        "prompt_zh": "柔和自然光，清新淡雅，浅色系背景，轻盈氛围",
        "prompt_en": (
            "Hamaya studio portrait style, soft natural light, fresh and elegant, "
            "light pastel background, airy atmosphere, gentle smile, "
            "high-end photography, skin retouching, bokeh background, photorealistic"
        ),
        "negative": "harsh lighting, dark background, oversaturated",
        "category": "自然",
    },
    {
        "name": "高级灰调",
        "prompt_zh": "高级灰色调，低饱和度，时尚杂志风，精致妆容",
        "prompt_en": (
            "Hamaya studio portrait, premium gray tone, desaturated elegant palette, "
            "fashion magazine style, refined makeup, sophisticated expression, "
            "soft studio lighting, high-end retouching, photorealistic"
        ),
        "negative": "bright colors, casual look, harsh shadows",
        "category": "时尚",
    },
    {
        "name": "暖调复古",
        "prompt_zh": "暖橙色调，胶片质感，复古氛围，柔和光晕",
        "prompt_en": (
            "Hamaya studio portrait, warm amber tone, film grain texture, "
            "vintage atmosphere, soft light halo, retro color grading, "
            "intimate expression, high-end photography, photorealistic"
        ),
        "negative": "cold tones, modern harsh lighting, oversaturated",
        "category": "复古",
    },
    {
        "name": "纯白极简",
        "prompt_zh": "纯白背景，极简风格，高调布光，干净通透",
        "prompt_en": (
            "Hamaya studio portrait, pure white background, minimalist style, "
            "high-key lighting, clean and bright, simple elegant outfit, "
            "professional retouching, sharp focus on face, photorealistic"
        ),
        "negative": "cluttered background, dark tones, heavy makeup",
        "category": "极简",
    },
    {
        "name": "森系小清新",
        "prompt_zh": "绿植背景，自然光，森系氛围，清新文艺",
        "prompt_en": (
            "Hamaya studio portrait, green botanical background, dappled natural light, "
            "forest fairy aesthetic, fresh literary style, floral or linen outfit, "
            "soft dreamy bokeh, high-end photography, photorealistic"
        ),
        "negative": "urban background, harsh flash, heavy makeup",
        "category": "自然",
    },
    {
        "name": "商务精英",
        "prompt_zh": "深色渐变背景，西装正装，自信气场，专业形象",
        "prompt_en": (
            "Hamaya studio portrait, dark gradient background, business suit, "
            "confident powerful expression, professional corporate image, "
            "dramatic studio lighting, sharp details, high-end retouching, photorealistic"
        ),
        "negative": "casual clothing, bright background, soft lighting",
        "category": "商务",
    },
    {
        "name": "梦幻粉调",
        "prompt_zh": "粉紫色调，梦幻氛围，少女感，柔光",
        "prompt_en": (
            "Hamaya studio portrait, soft pink and lavender tones, dreamy romantic atmosphere, "
            "feminine aesthetic, delicate makeup, soft diffused lighting, "
            "flower or tulle elements, high-end photography, photorealistic"
        ),
        "negative": "dark tones, masculine style, harsh lighting",
        "category": "梦幻",
    },
    {
        "name": "国风古典",
        "prompt_zh": "中国传统服饰，古典意境，水墨背景，东方美学",
        "prompt_en": (
            "Hamaya studio portrait, traditional Chinese hanfu or qipao, "
            "classical oriental aesthetic, ink wash painting background, "
            "elegant ancient beauty, soft warm lighting, high-end photography, photorealistic"
        ),
        "negative": "modern clothing, western style, harsh lighting",
        "category": "国风",
    },
]


def _conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_db() -> None:
    with _conn() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS prompts (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL UNIQUE,
                prompt_zh   TEXT NOT NULL,
                prompt_en   TEXT NOT NULL,
                negative    TEXT DEFAULT '',
                category    TEXT DEFAULT '通用',
                is_preset   INTEGER DEFAULT 0,
                created_at  TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        for p in PRESETS:
            con.execute(
                "INSERT OR IGNORE INTO prompts (name, prompt_zh, prompt_en, negative, category, is_preset) VALUES (?, ?, ?, ?, ?, 1)",
                (p["name"], p["prompt_zh"], p["prompt_en"], p["negative"], p["category"]),
            )


def get_all_prompts() -> list[dict]:
    with _conn() as con:
        con.row_factory = sqlite3.Row
        rows = con.execute("SELECT * FROM prompts ORDER BY is_preset DESC, id ASC").fetchall()
    return [dict(r) for r in rows]


def get_prompt_names() -> list[tuple[int, str]]:
    with _conn() as con:
        rows = con.execute("SELECT id, name FROM prompts ORDER BY is_preset DESC, id ASC").fetchall()
    return [(r[0], r[1]) for r in rows]


def get_prompt_by_id(pid: int) -> dict | None:
    with _conn() as con:
        con.row_factory = sqlite3.Row
        row = con.execute("SELECT * FROM prompts WHERE id=?", (pid,)).fetchone()
    return dict(row) if row else None


def get_prompt_by_name(name: str) -> dict | None:
    with _conn() as con:
        con.row_factory = sqlite3.Row
        row = con.execute("SELECT * FROM prompts WHERE name=?", (name,)).fetchone()
    return dict(row) if row else None


def upsert_prompt(name, prompt_zh, prompt_en, negative, category, pid=None):
    name = name.strip()
    prompt_en = prompt_en.strip()
    if not name or not prompt_en:
        return False, "名称和英文提示词不能为空"
    with _conn() as con:
        if pid is not None:
            row = con.execute("SELECT is_preset FROM prompts WHERE id=?", (pid,)).fetchone()
            con.execute(
                "UPDATE prompts SET name=?, prompt_zh=?, prompt_en=?, negative=?, category=? WHERE id=?",
                (name, prompt_zh, prompt_en, negative, category, pid),
            )
        else:
            try:
                con.execute(
                    "INSERT INTO prompts (name, prompt_zh, prompt_en, negative, category) VALUES (?, ?, ?, ?, ?)",
                    (name, prompt_zh, prompt_en, negative, category),
                )
            except sqlite3.IntegrityError:
                return False, f"名称「{name}」已存在"
    return True, "保存成功"


def delete_prompt(pid: int):
    with _conn() as con:
        row = con.execute("SELECT is_preset FROM prompts WHERE id=?", (pid,)).fetchone()
        if not row:
            return False, "未找到该提示词"
        if row[0] == 1:
            return False, "内置预设不可删除"
        con.execute("DELETE FROM prompts WHERE id=?", (pid,))
    return True, "删除成功"
