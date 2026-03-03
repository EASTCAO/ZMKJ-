"""
app.py — 造梦空间 (Flask 版)
"""
import os
import io
import base64
from concurrent.futures import ThreadPoolExecutor
from PIL import Image

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from flask import Flask, request, jsonify
from math import gcd

from config import IMAGE_SIZES, ASPECT_RATIOS, compute_size, _QUALITY_BASE, _MIN_PIXELS, ARK_MODEL_ID, ARK_MODEL_ID_V5
from api_client import generate_id_photo, optimize_prompt

app = Flask(__name__)


def gcd_ceil(x: float) -> int:
    """向上取整到最近的 8 的倍数。"""
    import math
    return math.ceil(x / 8) * 8


def pil_to_data_uri(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/png;base64,{b64}"


@app.route("/")
def index():
    def _thumb(r):
        w, h = map(int, r.split(":"))
        mx = 30
        if w >= h:
            tw, th = mx, max(8, int(mx * h / w))
        else:
            th, tw = mx, max(8, int(mx * w / h))
        return f"width:{tw}px;height:{th}px"

    ratios_grid = (
        '<div class="ratio-opt" data-v="AUTO">'
        '<div class="ratio-thumb ratio-thumb-auto">AUTO</div>'
        '</div>'
    ) + "".join(
        f'<div class="ratio-opt" data-v="{r}">'
        f'<div class="ratio-thumb" style="{_thumb(r)}"></div>'
        f'<span>{r}</span></div>'
        for r in ASPECT_RATIOS
    )
    _size_labels = {"2K": "2K 高清", "4K": "4K 超清"}
    sizes_opts = "".join(f'<option value="{k}">{_size_labels.get(k, k)}</option>' for k in IMAGE_SIZES.keys())

    return f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>造梦空间</title>
<link rel="icon" type="image/svg+xml" href="/static/favicon.svg">
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
    font-family: 'SimHei', 'STHeiti', 'Microsoft YaHei', 'PingFang SC', sans-serif;
    font-weight: 500;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    background: linear-gradient(160deg, #dce8f0 0%, #e8efe6 20%, #f8f0e0 45%, #e6eef4 70%, #f0ece4 100%);
    background-size: 400% 400%;
    animation: gradShift 25s ease infinite;
    color: #3a3530;
    position: relative;
    overflow-x: hidden;
    overflow-y: auto;
}}
@keyframes gradShift {{
    0% {{ background-position: 0% 50%; }}
    50% {{ background-position: 100% 50%; }}
    100% {{ background-position: 0% 50%; }}
}}

/* 光影光斑 — 模拟阳光透窗 */
body::before, body::after {{
    content: '';
    position: fixed;
    border-radius: 50%;
    filter: blur(100px);
    z-index: 0;
    pointer-events: none;
}}
body::before {{
    width: 800px; height: 800px;
    background: radial-gradient(circle, rgba(255,220,130,0.4), rgba(255,200,80,0.1) 50%, transparent 70%);
    top: -200px; left: -100px;
    opacity: 0.7;
    animation: float1 14s ease-in-out infinite;
}}
body::after {{
    width: 600px; height: 600px;
    background: radial-gradient(circle, rgba(180,230,200,0.25), transparent 70%);
    bottom: -100px; right: -80px;
    opacity: 0.5;
    animation: float2 12s ease-in-out infinite;
}}
@keyframes float1 {{
    0%, 100% {{ transform: translate(0, 0) scale(1); }}
    50% {{ transform: translate(60px, 40px) scale(1.05); }}
}}
@keyframes float2 {{
    0%, 100% {{ transform: translate(0, 0) scale(1); }}
    50% {{ transform: translate(-50px, -30px) scale(1.08); }}
}}

/* 多层光斑 */
.glow {{
    position: fixed;
    border-radius: 50%;
    filter: blur(90px);
    z-index: 0;
    pointer-events: none;
}}
.glow-1 {{
    width: 500px; height: 500px;
    background: radial-gradient(circle, rgba(255,200,100,0.3), transparent 70%);
    top: 30%; right: 0%;
    opacity: 0.6;
    animation: float1 16s ease-in-out infinite reverse;
}}
.glow-2 {{
    width: 400px; height: 400px;
    background: radial-gradient(circle, rgba(180,220,180,0.2), transparent 70%);
    bottom: 20%; left: 5%;
    opacity: 0.4;
    animation: float2 18s ease-in-out infinite reverse;
}}
.glow-3 {{
    width: 350px; height: 350px;
    background: radial-gradient(circle, rgba(255,180,140,0.2), transparent 70%);
    top: 10%; left: 40%;
    opacity: 0.35;
    animation: float1 20s ease-in-out infinite;
}}

/* 光束 — 从左上角斜射 */
.light-beams {{
    position: fixed;
    top: 0; left: 0;
    width: 100%; height: 100%;
    z-index: 0;
    pointer-events: none;
    overflow: hidden;
}}
.beam {{
    position: absolute;
    top: -20%;
    background: linear-gradient(180deg, rgba(255,230,160,0.15), rgba(255,220,130,0.05) 60%, transparent);
    transform-origin: top center;
    filter: blur(2px);
}}
.beam-1 {{ left: 5%; width: 120px; height: 130%; transform: rotate(15deg); opacity: 0.6; animation: beamPulse 8s ease-in-out infinite; }}
.beam-2 {{ left: 18%; width: 80px; height: 120%; transform: rotate(20deg); opacity: 0.4; animation: beamPulse 10s ease-in-out infinite 2s; }}
.beam-3 {{ left: 35%; width: 100px; height: 125%; transform: rotate(12deg); opacity: 0.35; animation: beamPulse 12s ease-in-out infinite 4s; }}
.beam-4 {{ right: 15%; width: 70px; height: 115%; transform: rotate(-10deg); opacity: 0.25; animation: beamPulse 9s ease-in-out infinite 1s; }}
@keyframes beamPulse {{
    0%, 100% {{ opacity: 0.2; }}
    50% {{ opacity: 0.5; }}
}}

/* 金色光粒子 */
.sparkles {{
    position: fixed;
    top: 0; left: 0;
    width: 100%; height: 100%;
    z-index: 0;
    pointer-events: none;
    overflow: hidden;
}}
.sparkle {{
    position: absolute;
    background: radial-gradient(circle, rgba(255,215,100,0.95), rgba(255,190,60,0.3), transparent);
    border-radius: 50%;
    animation: sparkleFloat linear infinite;
}}
@keyframes sparkleFloat {{
    0% {{ transform: translateY(100vh) scale(0); opacity: 0; }}
    10% {{ opacity: 1; }}
    50% {{ opacity: 0.9; }}
    90% {{ opacity: 0.6; }}
    100% {{ transform: translateY(-10vh) scale(1); opacity: 0; }}
}}

/* 飘落花瓣 */
.petals {{
    position: fixed;
    top: 0; left: 0;
    width: 100%; height: 100%;
    z-index: 0;
    pointer-events: none;
    overflow: hidden;
}}
.petal {{
    position: absolute;
    top: -30px;
    width: 12px; height: 16px;
    background: radial-gradient(ellipse, rgba(255,200,180,0.7), rgba(255,180,160,0.2));
    border-radius: 50% 50% 50% 0;
    animation: petalFall linear infinite;
    filter: blur(0.5px);
}}
.petal.white {{
    background: radial-gradient(ellipse, rgba(255,255,240,0.8), rgba(255,250,220,0.2));
}}
.petal.gold {{
    background: radial-gradient(ellipse, rgba(255,220,130,0.7), rgba(255,200,80,0.2));
}}
@keyframes petalFall {{
    0% {{ transform: translateY(-5vh) rotate(0deg) translateX(0); opacity: 0; }}
    10% {{ opacity: 0.8; }}
    100% {{ transform: translateY(105vh) rotate(360deg) translateX(80px); opacity: 0.2; }}
}}

/* 装饰藤蔓 — 顶部角落 */
.vine {{
    position: fixed;
    z-index: 0;
    pointer-events: none;
    opacity: 0.15;
}}
.vine-tl {{
    top: 0; left: 0;
    width: 280px; height: 200px;
    background: radial-gradient(ellipse at top left, rgba(120,160,80,0.4), transparent 70%);
    border-radius: 0 0 100% 0;
}}
.vine-tr {{
    top: 0; right: 0;
    width: 220px; height: 180px;
    background: radial-gradient(ellipse at top right, rgba(100,150,90,0.35), transparent 70%);
    border-radius: 0 0 0 100%;
}}

/* 内容层 */
.page {{ position: relative; z-index: 1; display: flex; flex-direction: column; height: 100vh; overflow: hidden; }}

/* ── 导航 ── */
.brand {{
    position: fixed;
    top: 18px;
    left: 28px;
    z-index: 10;
    display: flex;
    align-items: baseline;
    gap: 3px;
    text-decoration: none;
    user-select: none;
}}
.brand-letters {{
    font-size: 1.55rem;
    font-weight: 900;
    letter-spacing: 4px;
    background: linear-gradient(135deg, #a07030 0%, #e0b850 45%, #c89040 70%, #7a5020 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    line-height: 1;
}}
.brand-sub {{
    font-size: 0.52rem;
    font-weight: 600;
    letter-spacing: 2.5px;
    color: rgba(140,110,55,0.55);
    padding-bottom: 2px;
    text-transform: uppercase;
}}
    -webkit-text-fill-color: transparent;
    background-clip: text;
}}

/* ── 英雄区 ── */
.hero.collapsed {{
    flex: 1;
    min-height: 0;
    overflow: hidden;
    pointer-events: none;
}}
.hero.collapsed > * {{ display: none; }}
.hero {{
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    padding: 0 24px;
    min-height: 300px;
    gap: 14px;
}}
.hero-deco-line {{
    width: 60px;
    height: 1px;
    background: linear-gradient(90deg, transparent, #c8a45a, transparent);
}}
.hero-label {{
    font-size: 0.78rem;
    letter-spacing: 6px;
    color: rgba(160,130,70,0.7);
    text-transform: uppercase;
}}
.hero-title {{
    font-size: 4rem;
    font-weight: 900;
    letter-spacing: 12px;
    line-height: 1.1;
    background: linear-gradient(135deg, #a07030 0%, #e0b850 40%, #c89040 60%, #7a5020 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    filter: drop-shadow(0 2px 20px rgba(200,160,60,0.3));
}}
.hero-sub {{
    font-size: 0.85rem;
    color: rgba(90,75,50,0.5);
    letter-spacing: 2px;
}}
.hero-svg {{
    width: 320px;
    max-width: 80vw;
    height: auto;
    filter: drop-shadow(0 8px 32px rgba(200,160,60,0.25));
}}

/* ── 结果容器 ── */
/* ── 滚动区域 ── */
.scroll-area {{
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    align-items: center;
}}
.results-spacer {{ flex: 1; }}
.results-container {{
    max-width: 900px;
    width: 100%;
    padding: 0 28px;
    display: flex;
    flex-direction: column;
    gap: 16px;
}}
.result-card {{
    width: 100%;
    padding-bottom: 4px;
    animation: rcFadeIn 0.4s ease;
}}
@keyframes rcFadeIn {{
    from {{ opacity: 0; transform: translateY(-12px); }}
    to {{ opacity: 1; transform: translateY(0); }}
}}
.result-card .rc-inner {{
    background: rgba(255,255,255,0.5);
    border: 1px solid rgba(220,200,150,0.3);
    border-radius: 14px;
    padding: 10px 14px;
    backdrop-filter: blur(20px);
    box-shadow: 0 8px 32px rgba(200,180,120,0.1), inset 0 1px 0 rgba(255,255,255,0.6);
}}
.result-card .rc-header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 6px;
}}
.result-card .rc-status {{
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 0.82rem;
    color: rgba(80,70,55,0.7);
}}
.result-card .rc-status .rc-spinner {{
    width: 14px; height: 14px;
    border: 2px solid rgba(180,160,120,0.3);
    border-top-color: #c8a45a;
    border-radius: 50%;
    animation: rcSpin 0.8s linear infinite;
    display: none;
}}
.result-card .rc-status .rc-spinner.active {{ display: inline-block; }}
@keyframes rcSpin {{
    to {{ transform: rotate(360deg); }}
}}
.result-card .rc-close {{
    background: none; border: none;
    color: rgba(80,70,55,0.4);
    font-size: 1.2rem; cursor: pointer;
    padding: 4px 8px; border-radius: 6px;
    transition: all 0.2s;
}}
.result-card .rc-close:hover {{ color: #4a3f30; background: rgba(180,160,120,0.15); }}
.result-card .rc-prompt {{
    font-size: 0.78rem;
    color: rgba(80,70,55,0.4);
    margin-bottom: 14px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}}
.result-card .rc-grid {{
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 8px;
}}
.result-card .rc-slot {{
    position: relative;
    height: 320px;
    background: rgba(180,160,120,0.1);
    border-radius: 10px;
    overflow: hidden;
    display: flex;
    align-items: center;
    justify-content: center;
}}
.result-card .rc-slot img {{
    width: 100%; height: 100%;
    object-fit: contain;
    border-radius: 12px;
    display: none;
}}
.result-card .rc-slot img.loaded {{ display: block; }}
.result-card .rc-slot .rc-placeholder {{
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 10px;
    color: rgba(120,100,70,0.35);
}}
.result-card .rc-slot .rc-placeholder .rc-ring {{
    width: 36px; height: 36px;
    border: 2.5px solid rgba(180,160,120,0.2);
    border-top-color: #c8a45a;
    border-radius: 50%;
    animation: rcSpin 1s linear infinite;
}}
.result-card .rc-slot .rc-placeholder .rc-num {{
    font-size: 0.85rem;
    font-weight: 600;
    color: rgba(120,100,70,0.25);
}}
.result-card .rc-slot.done .rc-placeholder {{ display: none; }}
.result-card .rc-slot.done img {{ display: block; }}
.result-card .rc-slot .rc-overlay {{
    position: absolute; inset: 0;
    background: rgba(0,0,0,0.45);
    border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    gap: 10px;
    opacity: 0;
    transition: opacity 0.2s;
    z-index: 2;
    cursor: default;
}}
.result-card .rc-slot.done:hover .rc-overlay {{ opacity: 1; }}
.rc-overlay-btn {{
    width: 38px; height: 38px;
    border-radius: 50%;
    background: rgba(255,255,255,0.15);
    border: 1.5px solid rgba(255,255,255,0.35);
    color: #fff;
    display: flex; align-items: center; justify-content: center;
    cursor: pointer;
    backdrop-filter: blur(6px);
    transition: background 0.18s, transform 0.15s;
    padding: 0;
}}
.rc-overlay-btn svg {{ width: 16px; height: 16px; stroke: currentColor; fill: none; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }}
.rc-overlay-btn:hover {{ background: rgba(200,164,90,0.85); border-color: transparent; transform: scale(1.1); }}
.rc-overlay-btn.copied {{ background: rgba(80,180,100,0.85); border-color: transparent; }}
.rc-save-tip {{
    text-align: center;
    font-size: 0.7rem;
    color: rgba(80,70,55,0.3);
    padding-top: 8px;
    letter-spacing: 0.3px;
}}

/* ── 底部输入卡片 ── */
.bottom-wrap {{
    max-width: 900px;
    width: 100%;
    flex-shrink: 0;
    margin: 0 auto;
    padding: 0 28px 20px;
}}
.input-card {{
    background: rgba(255,255,255,0.5);
    border: 1px solid rgba(220,200,150,0.3);
    border-radius: 16px;
    overflow: hidden;
    backdrop-filter: blur(20px);
    box-shadow: 0 8px 32px rgba(200,180,120,0.1), inset 0 1px 0 rgba(255,255,255,0.6), 0 0 60px rgba(255,210,130,0.05);
}}

/* 标签头 */
.tab-bar {{
    display: flex;
    align-items: center;
    padding: 11px 20px;
    gap: 22px;
    border-bottom: 1px solid rgba(160,140,100,0.12);
}}
.tab-bar .tab {{
    font-size: 0.82rem;
    color: rgba(80,70,55,0.4);
    display: flex;
    align-items: center;
    gap: 5px;
    padding-bottom: 6px;
    border-bottom: 2px solid transparent;
    cursor: pointer;
}}
.tab-bar .tab.active {{
    color: #4a3f30;
    border-bottom-color: #c8a45a;
}}
.tab-bar .spacer {{ flex: 1; }}
.tab-bar .history {{
    font-size: 0.78rem;
    color: rgba(80,70,55,0.3);
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 4px;
}}
.tab-bar .history:hover {{ color: rgba(80,70,55,0.6); }}

/* 输入主行 */
.input-body {{
    display: flex;
    align-items: flex-start;
    gap: 12px;
    padding: 14px 20px;
    position: relative;
}}

/* 上传框组 */
.upload-boxes {{
    display: flex;
    flex-direction: row;
    flex-wrap: wrap;
    gap: 6px;
    flex-shrink: 0;
    align-content: flex-start;
}}
/* 上传框 */
.upload-box {{
    width: 108px; height: 108px; min-width: 108px;
    border: 1.5px dashed rgba(180,160,120,0.35);
    border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    cursor: pointer; position: relative; overflow: hidden;
    transition: border-color 0.2s;
    background: rgba(255,255,255,0.3);
}}
.upload-box:hover {{ border-color: rgba(180,160,120,0.6); }}
.upload-box .upload-input {{
    position: absolute; width: 100%; height: 100%; opacity: 0; cursor: pointer;
    border-radius: 10px; overflow: hidden;
}}
.upload-box svg {{ width: 30px; height: 30px; color: rgba(120,100,70,0.4); }}
.upload-box img {{
    width: 100%; height: 100%; object-fit: cover; border-radius: 8px; pointer-events: none;
}}
/* 删除按钮 */
.upload-del-btn {{
    position: absolute; top: 5px; right: 5px;
    width: 20px; height: 20px;
    background: rgba(30,25,20,0.75);
    border: none; border-radius: 50%;
    color: #fff; font-size: 13px; line-height: 1;
    display: none; align-items: center; justify-content: center;
    cursor: pointer; z-index: 20; padding: 0;
    transition: background 0.2s;
}}
.upload-del-btn:hover {{ background: rgba(200,60,50,0.85); }}
.upload-del-btn.visible {{ display: flex; }}
/* 预览悬浮层 */
.upload-zoom-overlay {{
    position: absolute; inset: 0;
    background: rgba(0,0,0,0); display: none;
    align-items: center; justify-content: center;
    border-radius: 8px; transition: background 0.2s;
    pointer-events: none; z-index: 10;
}}
.upload-zoom-overlay.visible {{ display: flex; }}
.upload-box:hover .upload-zoom-overlay.visible {{
    background: rgba(0,0,0,0.28);
    pointer-events: auto;
    cursor: zoom-in;
}}
.upload-zoom-overlay svg {{ opacity: 0; transition: opacity 0.2s; }}
.upload-box:hover .upload-zoom-overlay.visible svg {{ opacity: 1; }}
.upload-box .upload-icon {{ pointer-events: none; }}

/* 粘贴提示 */
.paste-hint {{
    font-size: 0.72rem;
    color: rgba(120,100,70,0.45);
    letter-spacing: 0.5px;
    margin-top: 2px;
}}

/* 提示词 */
.prompt-input {{
    flex: 1;
    background: transparent;
    border: none;
    color: #3a2f20;
    font-size: 0.92rem;
    font-weight: 500;
    resize: none;
    outline: none;
    line-height: 1.5;
    font-family: inherit;
    min-height: 80px;
    max-height: 180px;
    overflow-y: auto;
    padding-right: 110px;
    padding-bottom: 10px;
}}
.prompt-input::placeholder {{ color: rgba(80,70,55,0.3); }}

/* 生成按钮 */
.action-btns {{
    position: absolute;
    bottom: 8px;
    right: 32px;
    display: flex;
    align-items: center;
    gap: 6px;
    z-index: 10;
}}
.opt-btn {{
    width: 38px; height: 38px; min-width: 38px;
    background: rgba(200,164,90,0.12);
    color: #a08840;
    border: 1px solid rgba(200,164,90,0.3); border-radius: 50%;
    font-size: 0.95rem; cursor: pointer;
    display: flex; align-items: center; justify-content: center;
    transition: all 0.2s;
}}
.opt-btn:hover {{ background: rgba(200,164,90,0.25); border-color: rgba(200,164,90,0.5); }}
.opt-btn.loading {{
    pointer-events: none;
    animation: spin 1s linear infinite;
    background: rgba(200,164,90,0.25);
    border-color: rgba(200,164,90,0.6);
}}
@keyframes spin {{
    from {{ transform: rotate(0deg); }}
    to {{ transform: rotate(360deg); }}
}}
.gen-btn {{
    width: 38px; height: 38px; min-width: 38px;
    background: rgba(200,164,90,0.25);
    color: #a08840;
    border: none; border-radius: 50%;
    font-size: 1.05rem; cursor: pointer;
    display: flex; align-items: center; justify-content: center;
    transition: all 0.2s;
}}
.gen-btn:hover {{ background: #c8a45a; color: #fff; }}
.gen-btn.loading {{
    pointer-events: none;
    animation: pulse 1.2s infinite;
}}
.gen-btn svg {{ transform: rotate(-90deg); }}
@keyframes pulse {{
    0%, 100% {{ opacity: 1; }}
    50% {{ opacity: 0.4; }}
}}

/* 选项行 */
.opts-bar {{
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 0 20px 12px;
    border-top: 1px solid rgba(160,140,100,0.12);
    padding-top: 10px;
}}
.opts-bar select {{
    background: rgba(255,255,255,0.4);
    border: 1px solid rgba(180,160,120,0.25);
    border-radius: 8px;
    font-family: inherit; color: #3a2f20; font-size: 0.82rem; font-weight: 500;
    padding: 0 10px; height: 28px;
    outline: none; cursor: pointer; appearance: auto;
    flex-shrink: 0;
}}
.opts-bar select option {{ background: #faf6ee; color: #4a3f30; }}

/* 比例选择器 */
.ratio-picker {{ position: relative; }}
.ratio-trigger {{
    display: flex; align-items: center; gap: 6px;
    height: 28px; padding: 0 10px;
    background: rgba(255,255,255,0.4);
    border: 1px solid rgba(180,160,120,0.25);
    border-radius: 8px; color: #3a2f20; font-size: 0.82rem; font-weight: 500;
    cursor: pointer; font-family: inherit; transition: background 0.2s;
    flex-shrink: 0;
}}
.ratio-trigger:hover {{ background: rgba(255,255,255,0.65); }}
.ratio-trigger svg {{ opacity: 0.5; transition: transform 0.2s; }}
.ratio-picker.open .ratio-trigger svg {{ transform: rotate(180deg); }}
.ratio-panel {{
    display: none; position: absolute;
    bottom: calc(100% + 8px); left: 0;
    background: rgba(252,248,240,0.97);
    border: 1px solid rgba(180,160,120,0.25);
    border-radius: 14px; padding: 12px;
    box-shadow: 0 8px 32px rgba(0,0,0,0.12);
    backdrop-filter: blur(20px); z-index: 200; width: 236px;
}}
.ratio-picker.open .ratio-panel {{ display: block; }}
.ratio-grid {{
    display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px;
}}
.ratio-opt {{
    display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    gap: 6px; padding: 8px 4px; border-radius: 8px; cursor: pointer;
    border: 1px solid transparent; transition: background 0.15s, border-color 0.15s;
}}
.ratio-opt:hover {{ background: rgba(200,164,90,0.1); }}
.ratio-opt.selected {{ background: rgba(200,164,90,0.15); border-color: rgba(200,164,90,0.5); }}
.ratio-thumb {{ border: 1.5px solid rgba(100,80,50,0.35); border-radius: 2px; flex-shrink: 0; }}
.ratio-opt.selected .ratio-thumb {{ border-color: #c8a45a; background: rgba(200,164,90,0.15); }}
.ratio-thumb-auto {{
    width: 30px; height: 30px;
    display: flex; align-items: center; justify-content: center;
    font-size: 0.62rem; font-weight: 700;
    color: rgba(80,70,55,0.6); letter-spacing: -0.5px;
}}
.ratio-opt.selected .ratio-thumb-auto {{ color: #a07830; }}
.ratio-opt span {{ font-size: 0.68rem; color: rgba(80,70,55,0.65); white-space: nowrap; }}
.ratio-opt.selected span {{ color: #a07830; font-weight: 700; }}

/* 模型切换 */
.model-picker {{ position: relative; }}
.model-toggle {{
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 0 10px;
    height: 28px;
    background: rgba(255,255,255,0.4);
    border: 1px solid rgba(180,160,120,0.25);
    border-radius: 8px;
    cursor: pointer;
    font-size: 0.82rem;
    font-weight: 500;
    font-family: inherit;
    color: #3a2f20;
    white-space: nowrap;
    flex-shrink: 0;
    transition: background 0.2s;
}}
.model-toggle:hover {{ background: rgba(255,255,255,0.65); }}
.model-toggle svg {{ opacity: 0.5; transition: transform 0.2s; }}
.model-picker.open .model-toggle svg {{ transform: rotate(180deg); }}
.model-panel {{
    display: none; position: absolute;
    bottom: calc(100% + 8px); left: 0;
    background: rgba(252,248,240,0.97);
    border: 1px solid rgba(180,160,120,0.25);
    border-radius: 12px; padding: 6px;
    box-shadow: 0 8px 32px rgba(0,0,0,0.12);
    backdrop-filter: blur(20px); z-index: 200;
    min-width: 110px;
}}
.model-picker.open .model-panel {{ display: block; }}
.model-opt {{
    display: flex; align-items: center;
    padding: 7px 12px; border-radius: 8px; cursor: pointer;
    font-size: 0.82rem; color: #3a2f20; font-weight: 500;
    font-family: inherit; border: 1px solid transparent;
    transition: background 0.15s, border-color 0.15s;
    white-space: nowrap;
}}
.model-opt:hover {{ background: rgba(200,164,90,0.1); }}
.model-opt.selected {{ background: rgba(200,164,90,0.15); border-color: rgba(200,164,90,0.5); color: #a07830; font-weight: 700; }}

.opts-bar .info {{
    font-size: 0.76rem;
    color: rgba(80,70,55,0.35);
    display: flex;
    align-items: center;
    gap: 6px;
    margin-left: 4px;
}}
.opts-bar .info .dot {{
    width: 6px; height: 6px; border-radius: 50%;
    background: #c8a45a; display: inline-block;
}}

/* 状态 */
.status {{
    text-align: center;
    font-size: 0.8rem;
    color: rgba(80,70,55,0.35);
    padding: 8px 0;
    min-height: 20px;
}}

/* ── 历史面板 ── */
.hist-overlay {{
    display: none;
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0,0,0,0.4);
    z-index: 100;
    backdrop-filter: blur(4px);
}}
.hist-overlay.show {{ display: block; }}
.hist-panel {{
    position: fixed;
    top: 0; right: 0;
    width: 380px; max-width: 90vw;
    height: 100vh;
    background: rgba(40,36,30,0.95);
    backdrop-filter: blur(20px);
    z-index: 101;
    transform: translateX(100%);
    transition: transform 0.3s ease;
    display: flex;
    flex-direction: column;
    box-shadow: -4px 0 24px rgba(0,0,0,0.3);
}}
.hist-panel.show {{ transform: translateX(0); }}
.hist-panel .hp-header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 18px 20px;
    border-bottom: 1px solid rgba(255,255,255,0.08);
}}
.hist-panel .hp-title {{
    font-size: 0.95rem;
    font-weight: 600;
    color: rgba(255,255,255,0.85);
}}
.hist-panel .hp-actions {{
    display: flex;
    gap: 8px;
    align-items: center;
}}
.hist-panel .hp-clear {{
    background: none; border: 1px solid rgba(255,255,255,0.12);
    color: rgba(255,255,255,0.4);
    font-size: 0.72rem;
    padding: 4px 10px;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.2s;
}}
.hist-panel .hp-clear:hover {{ color: #e88; border-color: rgba(255,100,100,0.3); }}
.hist-panel .hp-close {{
    background: none; border: none;
    color: rgba(255,255,255,0.4);
    font-size: 1.2rem; cursor: pointer;
    padding: 4px 8px; border-radius: 6px;
    transition: all 0.2s;
}}
.hist-panel .hp-close:hover {{ color: #fff; background: rgba(255,255,255,0.1); }}
.hist-panel .hp-list {{
    flex: 1;
    overflow-y: auto;
    padding: 12px 16px;
}}
.hist-panel .hp-empty {{
    text-align: center;
    color: rgba(255,255,255,0.2);
    font-size: 0.82rem;
    padding: 60px 0;
}}
.hist-panel .hp-item {{
    display: flex;
    gap: 12px;
    padding: 12px;
    border-radius: 10px;
    cursor: pointer;
    transition: background 0.2s;
    margin-bottom: 8px;
    position: relative;
}}
.hist-panel .hp-item:hover {{ background: rgba(255,255,255,0.06); }}
.hist-panel .hp-thumbs {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 3px;
    width: 56px; min-width: 56px; height: 56px;
    border-radius: 8px;
    overflow: hidden;
}}
.hist-panel .hp-thumbs img {{
    width: 100%; height: 100%;
    object-fit: cover;
}}
.hist-panel .hp-info {{
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: 4px;
}}
.hist-panel .hp-prompt {{
    font-size: 0.8rem;
    color: rgba(255,255,255,0.7);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}}
.hist-panel .hp-meta {{
    font-size: 0.7rem;
    color: rgba(255,255,255,0.25);
}}
.hist-panel .hp-del {{
    position: absolute;
    top: 8px; right: 8px;
    background: none; border: none;
    color: rgba(255,255,255,0.15);
    font-size: 0.9rem; cursor: pointer;
    padding: 2px 6px; border-radius: 4px;
    transition: all 0.2s;
    display: none;
}}
.hist-panel .hp-item:hover .hp-del {{ display: block; }}
.hist-panel .hp-del:hover {{ color: #e88; background: rgba(255,100,100,0.1); }}

/* ── 图片预览 ── */
.preview-overlay {{
    display: none;
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0,0,0,0.85);
    z-index: 200;
    align-items: center;
    justify-content: center;
    cursor: zoom-out;
}}
.preview-overlay.show {{ display: flex; }}
.preview-overlay .pv-close {{
    position: absolute;
    top: 20px; right: 24px;
    background: rgba(255,255,255,0.1);
    border: none;
    color: rgba(255,255,255,0.7);
    font-size: 1.6rem;
    width: 40px; height: 40px;
    border-radius: 50%;
    cursor: pointer;
    transition: all 0.2s;
    display: flex;
    align-items: center;
    justify-content: center;
}}
.preview-overlay .pv-close:hover {{ background: rgba(255,255,255,0.2); color: #fff; }}
.preview-overlay .pv-img {{
    max-width: 90vw;
    max-height: 90vh;
    border-radius: 8px;
    object-fit: contain;
    box-shadow: 0 8px 40px rgba(0,0,0,0.5);
    cursor: default;
}}
</style>
</head>
<body>

<div class="light-beams">
    <div class="beam beam-1"></div>
    <div class="beam beam-2"></div>
    <div class="beam beam-3"></div>
    <div class="beam beam-4"></div>
</div>
<div class="sparkles" id="sparkles"></div>
<div class="petals" id="petals"></div>
<div class="glow glow-1"></div>
<div class="glow glow-2"></div>
<div class="glow glow-3"></div>
<div class="vine vine-tl"></div>
<div class="vine vine-tr"></div>

<div class="page">

<!-- 导航 -->
<div class="brand">
    <span class="brand-letters">ZMKJ</span>
    <span class="brand-sub">造梦空间</span>
</div>

<!-- 可滚动主区域 -->
<div class="scroll-area">

<!-- 英雄区 -->
<div class="hero" id="heroArea">
    <div class="hero-deco-line"></div>
    <div class="hero-label">AI · 图像创作</div>
    <h1 class="hero-title">造梦空间</h1>
    <p class="hero-sub">上传参考图，描述你的想象，让 AI 为你造梦</p>
    <div class="hero-deco-line"></div>
</div>

<!-- 结果容器 — 动态追加卡片 -->
<div class="results-container" id="resultsContainer"></div>

<!-- 后置占位，与 hero(collapsed) 共同实现卡片垂直居中 -->
<div class="results-spacer"></div>

</div>

<!-- 底部输入卡片 -->
<div class="bottom-wrap">
    <div class="input-card">
        <div class="tab-bar">
            <div class="tab active">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16" style="flex-shrink:0"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="m21 15-5-5L5 21"/></svg>
                图片
            </div>
            <div class="spacer"></div>
            <div class="history">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
                生成历史
            </div>
        </div>

        <div class="input-body">
            <div class="upload-boxes" id="uploadBoxes"></div>
            <textarea class="prompt-input" id="promptInput" placeholder="使用中文输入您的修改请求（Ctrl+Enter 提交）" rows="2"></textarea>
            <div class="action-btns">
                <button class="opt-btn" id="optBtn" title="优化提示词">✦</button>
                <button class="gen-btn" id="genBtn" title="生成图像">
                    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M5 12h14M13 6l6 6-6 6"/></svg>
                </button>
            </div>
        </div>

        <div class="opts-bar">
            <div class="ratio-picker" id="ratioPicker">
                <button class="ratio-trigger" id="ratioTrigger">
                    <span id="ratioTriggerLabel">AUTO</span>
                    <svg viewBox="0 0 10 6" width="10" height="6" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M1 1l4 4 4-4"/></svg>
                </button>
                <div class="ratio-panel" id="ratioPanel">
                    <div class="ratio-grid">{ratios_grid}</div>
                </div>
            </div>
            <select id="sizeSel">{sizes_opts}</select>
            <div class="model-picker" id="modelPicker">
                <button class="model-toggle" id="modelToggle">
                    <span id="modelLabel">SD 4.5</span>
                    <svg viewBox="0 0 10 6" width="10" height="6" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M1 1l4 4 4-4"/></svg>
                </button>
                <div class="model-panel" id="modelPanel">
                    <div class="model-opt selected" data-model="{ARK_MODEL_ID}" data-label="SD 4.5">SD 4.5</div>
                    <div class="model-opt" data-model="{ARK_MODEL_ID_V5}" data-label="SD 5.0">SD 5.0</div>
                </div>
            </div>
            <div class="info"><span class="dot"></span> 每次生成 2 张图片</div>
        </div>
    </div>

    <div class="status" id="status"></div>
</div>

<!-- 历史面板 -->
<div class="hist-overlay" id="histOverlay"></div>
<div class="hist-panel" id="histPanel">
    <div class="hp-header">
        <span class="hp-title">生成历史</span>
        <div class="hp-actions">
            <button class="hp-clear" id="histClear">清空</button>
            <button class="hp-close" id="histClose">&times;</button>
        </div>
    </div>
    <div class="hp-list" id="histList">
        <div class="hp-empty">暂无历史记录</div>
    </div>
</div>

<!-- 图片预览 -->
<div class="preview-overlay" id="previewOverlay">
    <button class="pv-close" id="pvClose">&times;</button>
    <img class="pv-img" id="pvImg" src="" alt="">
</div>

</div>

<script>
const promptInput = document.getElementById('promptInput');
const genBtn = document.getElementById('genBtn');
const sizeSel = document.getElementById('sizeSel');
const statusEl = document.getElementById('status');
const heroArea = document.getElementById('heroArea');
const resultsContainer = document.getElementById('resultsContainer');

// ── 模型切换 ──
let currentModel = '{ARK_MODEL_ID}';
const modelPicker = document.getElementById('modelPicker');
const modelToggle = document.getElementById('modelToggle');
const modelLabel = document.getElementById('modelLabel');
const modelOpts = document.querySelectorAll('.model-opt');
modelToggle.addEventListener('click', e => {{ e.stopPropagation(); modelPicker.classList.toggle('open'); }});
document.addEventListener('click', () => modelPicker.classList.remove('open'));
modelOpts.forEach(opt => {{
    opt.addEventListener('click', e => {{
        e.stopPropagation();
        modelOpts.forEach(o => o.classList.remove('selected'));
        opt.classList.add('selected');
        currentModel = opt.dataset.model;
        modelLabel.textContent = opt.dataset.label;
        modelPicker.classList.remove('open');
    }});
}});
let currentRatio = 'AUTO';
const ratioPicker = document.getElementById('ratioPicker');
const ratioTrigger = document.getElementById('ratioTrigger');
const ratioTriggerLabel = document.getElementById('ratioTriggerLabel');
const ratioPanel = document.getElementById('ratioPanel');
const ratioOpts = document.querySelectorAll('.ratio-opt');
ratioOpts[0].classList.add('selected');
ratioTrigger.addEventListener('click', e => {{ e.stopPropagation(); ratioPicker.classList.toggle('open'); }});
document.addEventListener('click', () => ratioPicker.classList.remove('open'));
ratioOpts.forEach(opt => {{
    opt.addEventListener('click', e => {{
        e.stopPropagation();
        ratioOpts.forEach(o => o.classList.remove('selected'));
        opt.classList.add('selected');
        currentRatio = opt.dataset.v;
        ratioTriggerLabel.textContent = currentRatio;
        ratioPicker.classList.remove('open');
    }});
}});

const histOverlay = document.getElementById('histOverlay');
const histPanel = document.getElementById('histPanel');
const histList = document.getElementById('histList');
const histClear = document.getElementById('histClear');
const histClose = document.getElementById('histClose');
const histBtn = document.querySelector('.tab-bar .history');

const previewOverlay = document.getElementById('previewOverlay');
const pvImg = document.getElementById('pvImg');
const pvClose = document.getElementById('pvClose');

// ── 动态上传框（初始1个，上传后追加，最多9个）──
const uploadBoxesEl = document.getElementById('uploadBoxes');
const uploadState = [];
const MAX_UPLOAD = 9;
const _UPLOAD_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="m21 15-5-5L5 21"/></svg>';

const _ZOOM_SVG = '<svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="white" stroke-width="2"><circle cx="11" cy="11" r="7"/><path d="m21 21-4.35-4.35"/><path d="M11 8v6M8 11h6"/></svg>';

function createUploadBox(idx) {{
    uploadState.push({{ file: null, dataUrl: null }});
    const box = document.createElement('div');
    box.className = 'upload-box';
    box.id = 'uploadBox' + idx;
    box.innerHTML =
        '<input type="file" accept="image/*" class="upload-input">' +
        '<span class="upload-icon">' + _UPLOAD_SVG + '</span>' +
        '<button class="upload-del-btn" title="删除图片">×</button>' +
        '<div class="upload-zoom-overlay">' + _ZOOM_SVG + '</div>';
    box.querySelector('.upload-del-btn').addEventListener('click', e => {{
        e.stopPropagation();
        deleteSlot(idx);
    }});
    box.querySelector('.upload-zoom-overlay').addEventListener('click', e => {{
        e.stopPropagation();
        if (uploadState[idx] && uploadState[idx].dataUrl) openPreview(uploadState[idx].dataUrl);
    }});
    box.querySelector('.upload-input').addEventListener('change', e => {{
        const f = e.target.files[0];
        if (f) loadFileIntoSlot(f, idx);
    }});
    uploadBoxesEl.appendChild(box);
    return box;
}}

function loadFileIntoSlot(file, idx) {{
    const box = document.getElementById('uploadBox' + idx);
    if (!box) return;
    uploadState[idx].file = file;
    const reader = new FileReader();
    reader.onload = ev => {{
        uploadState[idx].dataUrl = ev.target.result;
        box.querySelector('.upload-icon').style.display = 'none';
        let img = box.querySelector('img');
        if (!img) {{ img = document.createElement('img'); box.insertBefore(img, box.querySelector('.upload-del-btn')); }}
        img.src = ev.target.result;
        box.querySelector('.upload-del-btn').classList.add('visible');
        box.querySelector('.upload-zoom-overlay').classList.add('visible');
        if (idx === uploadState.length - 1 && uploadState.length < MAX_UPLOAD) {{
            createUploadBox(uploadState.length);
        }}
    }};
    reader.readAsDataURL(file);
}}

function deleteSlot(idx) {{
    uploadState[idx] = {{ file: null, dataUrl: null }};
    rebuildUploadBoxes();
}}

function rebuildUploadBoxes() {{
    const filled = uploadState.filter(s => s.file !== null);
    uploadBoxesEl.innerHTML = '';
    uploadState.length = 0;
    filled.forEach((saved, newIdx) => {{
        createUploadBox(newIdx);
        uploadState[newIdx] = saved;
        const box = document.getElementById('uploadBox' + newIdx);
        box.querySelector('.upload-icon').style.display = 'none';
        const img = document.createElement('img');
        img.src = saved.dataUrl;
        box.insertBefore(img, box.querySelector('.upload-del-btn'));
        box.querySelector('.upload-del-btn').classList.add('visible');
        box.querySelector('.upload-zoom-overlay').classList.add('visible');
    }});
    if (uploadState.length < MAX_UPLOAD) createUploadBox(uploadState.length);
}}

// 初始化第一个上传框
createUploadBox(0);

// ── 粘贴图片（Ctrl+V）──
document.addEventListener('paste', e => {{
    const items = e.clipboardData && e.clipboardData.items;
    if (!items) return;
    for (const item of items) {{
        if (item.type.startsWith('image/')) {{
            const file = item.getAsFile();
            if (!file) continue;
            let targetIdx = uploadState.findIndex(s => !s.file);
            if (targetIdx === -1) targetIdx = 0;
            loadFileIntoSlot(file, targetIdx);
            break;
        }}
    }}
}});

const HIST_KEY = 'dreamspace_history';
const HIST_MAX = 20;

promptInput.addEventListener('keydown', e => {{
    if (e.ctrlKey && e.key === 'Enter') doGenerate();
}});
promptInput.addEventListener('input', () => {{
    promptInput.style.height = 'auto';
    promptInput.style.height = Math.min(promptInput.scrollHeight, 180) + 'px';
}});

genBtn.addEventListener('click', doGenerate);

const optBtn = document.getElementById('optBtn');
optBtn.addEventListener('click', async () => {{
    const text = promptInput.value.trim();
    if (!text) {{ statusEl.textContent = '请先输入描述再优化'; return; }}
    optBtn.classList.add('loading');
    statusEl.textContent = '正在优化提示词…';
    try {{
        const fd = new FormData();
        fd.append('text', text);
        const resp = await fetch('/optimize', {{ method: 'POST', body: fd }});
        const data = await resp.json();
        if (data.error) {{
            statusEl.textContent = data.error;
        }} else {{
            promptInput.value = data.prompt;
            promptInput.style.height = 'auto';
            promptInput.style.height = Math.min(promptInput.scrollHeight, 180) + 'px';
            statusEl.textContent = '✦ 提示词已优化，可直接生成';
        }}
    }} catch (e) {{
        statusEl.textContent = '优化失败: ' + e.message;
    }} finally {{
        optBtn.classList.remove('loading');
    }}
}});

/* ── 动态创建一张结果卡片 ── */
function createCard(promptText) {{
    const card = document.createElement('div');
    card.className = 'result-card';
    card.innerHTML =
        '<div class="rc-inner">' +
            '<div class="rc-header">' +
                '<div class="rc-status">' +
                    '<div class="rc-spinner active"></div>' +
                    '<span class="rc-status-text">生成中 00:00</span>' +
                '</div>' +
                '<button class="rc-close" title="关闭">&times;</button>' +
            '</div>' +
            '<div class="rc-prompt">' + escHtml(promptText) + '</div>' +
            '<div class="rc-grid">' +
                [1,2].map(n =>
                    '<div class="rc-slot">' +
                        '<div class="rc-placeholder"><div class="rc-ring"></div><div class="rc-num">' + n + '</div></div>' +
                        '<img src="" alt="">' +
                        '<div class="rc-overlay">' +
                            '<button class="rc-overlay-btn rc-btn-copy" title="复制图片"><svg viewBox="0 0 24 24"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg></button>' +
                            '<button class="rc-overlay-btn rc-btn-ref" title="以图生图"><svg viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="m21 15-5-5L5 21"/></svg></button>' +
                            '<button class="rc-overlay-btn rc-btn-dl" title="下载"><svg viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg></button>' +
                        '</div>' +
                    '</div>'
                ).join('') +
            '</div>' +
            '<div class="rc-save-tip">请及时下载重要图片</div>' +
        '</div>';

    const closeBtn = card.querySelector('.rc-close');
    closeBtn.addEventListener('click', () => {{
        card.remove();
        if (resultsContainer.children.length === 0) heroArea.classList.remove('collapsed');
    }});

    const cardSlots = card.querySelectorAll('.rc-slot');
    cardSlots.forEach(slot => {{
        // 点击图片空白区域 → 预览
        slot.addEventListener('click', e => {{
            if (e.target.closest('.rc-overlay-btn')) return;
            const img = slot.querySelector('img');
            if (img && img.src && slot.classList.contains('done')) openPreview(img.src);
        }});

        // 复制
        slot.querySelector('.rc-btn-copy').addEventListener('click', async e => {{
            e.stopPropagation();
            const img = slot.querySelector('img');
            if (!img || !img.src) return;
            try {{
                const blob = await (await fetch(img.src)).blob();
                await navigator.clipboard.write([new ClipboardItem({{ 'image/png': blob }})]);
                const btn = e.currentTarget;
                btn.classList.add('copied');
                setTimeout(() => btn.classList.remove('copied'), 1200);
            }} catch(_) {{}}
        }});

        // 以图生图
        slot.querySelector('.rc-btn-ref').addEventListener('click', async e => {{
            e.stopPropagation();
            const img = slot.querySelector('img');
            if (!img || !img.src) return;
            const blob = await (await fetch(img.src)).blob();
            const file = new File([blob], 'reference.png', {{ type: 'image/png' }});
            // 放入第一个空位，没空位就放到第0个
            const idx = uploadState.findIndex(s => !s.file) !== -1
                ? uploadState.findIndex(s => !s.file) : 0;
            loadFileIntoSlot(file, idx);
        }});

        // 下载
        slot.querySelector('.rc-btn-dl').addEventListener('click', e => {{
            e.stopPropagation();
            const img = slot.querySelector('img');
            if (!img || !img.src) return;
            const a = document.createElement('a');
            a.href = img.src;
            a.download = 'dreamspace_' + Date.now() + '.png';
            a.click();
        }});
    }});

    // 启动计时器
    let sec = 0;
    const statusText = card.querySelector('.rc-status-text');
    const timer = setInterval(() => {{
        sec++;
        const mm = String(Math.floor(sec / 60)).padStart(2, '0');
        const ss = String(sec % 60).padStart(2, '0');
        statusText.textContent = '生成中 ' + mm + ':' + ss;
    }}, 1000);

    card._timer = timer;
    card._statusText = statusText;
    card._spinner = card.querySelector('.rc-spinner');
    card._slots = cardSlots;

    return card;
}}

function finishCard(card, images) {{
    clearInterval(card._timer);
    card._spinner.classList.remove('active');
    const count = images.filter(Boolean).length;
    card._statusText.textContent = '生成完成 · ' + count + ' 张';
    images.forEach((src, i) => {{
        if (i < 2 && src) {{
            const slot = card._slots[i];
            const img = slot.querySelector('img');
            img.src = src;
            img.classList.add('loaded');
            slot.classList.add('done');
        }}
    }});
}}

function failCard(card, msg) {{
    clearInterval(card._timer);
    card._spinner.classList.remove('active');
    card._statusText.textContent = msg;
}}

/* ── 历史记录 ── */
function getHistory() {{
    try {{ return JSON.parse(localStorage.getItem(HIST_KEY)) || []; }}
    catch {{ return []; }}
}}

function saveHistory(list) {{
    try {{ localStorage.setItem(HIST_KEY, JSON.stringify(list)); }}
    catch(e) {{
        if (list.length > 1) {{
            list.pop();
            saveHistory(list);
        }}
    }}
}}

// 压缩图片为缩略图再存入历史（避免 localStorage 溢出）
function compressForHistory(dataUrl) {{
    return new Promise(resolve => {{
        const img = new Image();
        img.onload = () => {{
            const MAX = 400;
            let w = img.naturalWidth, h = img.naturalHeight;
            if (Math.max(w, h) > MAX) {{
                const s = MAX / Math.max(w, h);
                w = Math.round(w * s); h = Math.round(h * s);
            }}
            const cv = document.createElement('canvas');
            cv.width = w; cv.height = h;
            cv.getContext('2d').drawImage(img, 0, 0, w, h);
            resolve(cv.toDataURL('image/jpeg', 0.72));
        }};
        img.onerror = () => resolve(dataUrl);
        img.src = dataUrl;
    }});
}}

async function addToHistory(prompt, images) {{
    const thumbs = await Promise.all(images.map(src => src ? compressForHistory(src) : Promise.resolve(null)));
    const list = getHistory();
    const now = new Date();
    const time = now.getFullYear() + '-' +
        String(now.getMonth()+1).padStart(2,'0') + '-' +
        String(now.getDate()).padStart(2,'0') + ' ' +
        String(now.getHours()).padStart(2,'0') + ':' +
        String(now.getMinutes()).padStart(2,'0');
    list.unshift({{ id: Date.now(), prompt, images: thumbs, time }});
    if (list.length > HIST_MAX) list.length = HIST_MAX;
    saveHistory(list);
}}

function deleteFromHistory(id) {{
    const list = getHistory().filter(h => h.id !== id);
    saveHistory(list);
    renderHistory();
}}

function clearHistory() {{
    localStorage.removeItem(HIST_KEY);
    renderHistory();
}}

function renderHistory() {{
    const list = getHistory();
    if (list.length === 0) {{
        histList.innerHTML = '<div class="hp-empty">暂无历史记录</div>';
        return;
    }}
    histList.innerHTML = '';
    list.forEach(h => {{
        const item = document.createElement('div');
        item.className = 'hp-item';
        const thumbs = h.images.slice(0, 4);
        item.innerHTML =
            '<div class="hp-thumbs">' +
                thumbs.map(src => '<img src="' + src + '" alt="">').join('') +
            '</div>' +
            '<div class="hp-info">' +
                '<div class="hp-prompt">' + escHtml(h.prompt) + '</div>' +
                '<div class="hp-meta">' + h.time + ' · ' + h.images.length + ' 张</div>' +
            '</div>' +
            '<button class="hp-del" title="删除">&times;</button>';
        item.querySelector('.hp-del').addEventListener('click', e => {{
            e.stopPropagation();
            deleteFromHistory(h.id);
        }});
        item.addEventListener('click', () => {{
            showHistoryItem(h);
        }});
        histList.appendChild(item);
    }});
}}

function escHtml(s) {{
    return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}}

function showHistoryItem(h) {{
    closeHistPanel();
    heroArea.classList.add('collapsed');
    const card = createCard(h.prompt);
    clearInterval(card._timer);
    card._spinner.classList.remove('active');
    card._statusText.textContent = '历史记录（预览图已压缩）· ' + h.images.length + ' 张';
    resultsContainer.prepend(card);
    h.images.forEach((src, i) => {{
        if (i < 2 && src) {{
            const slot = card._slots[i];
            const img = slot.querySelector('img');
            img.src = src;
            img.classList.add('loaded');
            slot.classList.add('done');
            // 历史图片已压缩，禁用下载按钮
            const dlBtn = slot.querySelector('.rc-btn-dl');
            dlBtn.disabled = true;
            dlBtn.title = '历史图片已压缩，请在生成后立即下载原图';
            dlBtn.style.opacity = '0.3';
            dlBtn.style.cursor = 'not-allowed';
        }}
    }});
}}

function openHistPanel() {{
    renderHistory();
    histOverlay.classList.add('show');
    histPanel.classList.add('show');
}}

function closeHistPanel() {{
    histPanel.classList.remove('show');
    histOverlay.classList.remove('show');
}}

histBtn.addEventListener('click', openHistPanel);
histClose.addEventListener('click', closeHistPanel);
histOverlay.addEventListener('click', closeHistPanel);
histClear.addEventListener('click', () => {{
    if (confirm('确定要清空所有历史记录吗？')) clearHistory();
}});

/* ── 图片预览 ── */
function openPreview(src) {{
    pvImg.src = src;
    previewOverlay.classList.add('show');
}}

function closePreview() {{
    previewOverlay.classList.remove('show');
    pvImg.src = '';
}}

pvClose.addEventListener('click', e => {{
    e.stopPropagation();
    closePreview();
}});
previewOverlay.addEventListener('click', e => {{
    if (e.target === previewOverlay) closePreview();
}});
document.addEventListener('keydown', e => {{
    if (e.key === 'Escape') {{
        if (previewOverlay.classList.contains('show')) closePreview();
        else if (histPanel.classList.contains('show')) closeHistPanel();
    }}
}});

/* ── 生成 ── */
async function doGenerate() {{
    const prompt = promptInput.value.trim();
    if (!prompt) {{ statusEl.textContent = '请输入描述'; return; }}

    statusEl.textContent = '';
    heroArea.classList.add('collapsed');

    const card = createCard(prompt);
    resultsContainer.prepend(card);
    window.scrollTo({{ top: 0, behavior: 'smooth' }});

    const fd = new FormData();
    fd.append('prompt', prompt);
    fd.append('ratio', currentRatio);
    fd.append('size_label', sizeSel.value);
    fd.append('model_id', currentModel);
    uploadState.forEach((state, i) => {{
        if (state.file) fd.append('image_' + i, state.file);
    }});

    try {{
        const resp = await fetch('/generate', {{ method: 'POST', body: fd }});
        const data = await resp.json();

        if (data.error) {{
            failCard(card, data.error);
            statusEl.textContent = data.error;
        }} else {{
            const images = data.images || [];
            finishCard(card, images);
            statusEl.textContent = data.status || '生成成功';
            addToHistory(prompt, images);
        }}
    }} catch (err) {{
        failCard(card, '请求失败');
        statusEl.textContent = '请求失败: ' + err.message;
    }}
}}

// 生成金色光粒子
(function() {{
    const container = document.getElementById('sparkles');
    const count = 60;
    for (let i = 0; i < count; i++) {{
        const s = document.createElement('div');
        s.className = 'sparkle';
        s.style.left = Math.random() * 100 + '%';
        const size = 2 + Math.random() * 5;
        s.style.width = s.style.height = size + 'px';
        s.style.animationDuration = (5 + Math.random() * 12) + 's';
        s.style.animationDelay = (Math.random() * 15) + 's';
        s.style.opacity = 0.3 + Math.random() * 0.6;
        container.appendChild(s);
    }}
}})();

// 生成飘落花瓣
(function() {{
    const container = document.getElementById('petals');
    const types = ['', 'white', 'gold'];
    const count = 20;
    for (let i = 0; i < count; i++) {{
        const p = document.createElement('div');
        p.className = 'petal ' + types[Math.floor(Math.random() * types.length)];
        p.style.left = Math.random() * 100 + '%';
        const size = 8 + Math.random() * 14;
        p.style.width = size + 'px';
        p.style.height = (size * 1.3) + 'px';
        p.style.animationDuration = (8 + Math.random() * 14) + 's';
        p.style.animationDelay = (Math.random() * 18) + 's';
        p.style.opacity = 0.3 + Math.random() * 0.5;
        container.appendChild(p);
    }}
}})();
</script>
</body>
</html>"""


@app.route("/optimize", methods=["POST"])
def optimize():
    text = request.form.get("text", "").strip()
    if not text:
        return jsonify({"error": "请输入描述"})
    result, msg = optimize_prompt(text)
    if result is None:
        return jsonify({"error": msg})
    return jsonify({"prompt": result, "status": msg})


@app.route("/generate", methods=["POST"])
def generate():
    prompt = request.form.get("prompt", "").strip()
    ratio = request.form.get("ratio", "AUTO")
    size_label = request.form.get("size_label", "2K")
    model_id = request.form.get("model_id", ARK_MODEL_ID)

    if not prompt:
        return jsonify({"error": "请输入描述提示词"})

    ref_imgs = []
    for i in range(9):
        f = request.files.get(f'image_{i}')
        if f and f.filename:
            ref_imgs.append(Image.open(f.stream).convert("RGB"))

    # AUTO：从第一张参考图推算比例，无图则默认 1:1
    if ratio == "AUTO":
        if ref_imgs:
            iw, ih = ref_imgs[0].size
            base = _QUALITY_BASE.get(size_label, 2048)
            if iw >= ih:
                sw, sh = base, int(base * ih / iw)
            else:
                sh, sw = base, int(base * iw / ih)
            if sw * sh < _MIN_PIXELS:
                scale = (_MIN_PIXELS / (sw * sh)) ** 0.5
                sw = gcd_ceil(sw * scale)
                sh = gcd_ceil(sh * scale)
            else:
                sw = gcd_ceil(sw)
                sh = gcd_ceil(sh)
            g = gcd(sw, sh)
            size_val = f"{sw}x{sh}"
            actual_ratio = f"{sw // g}:{sh // g}"
        else:
            size_val = compute_size("1:1", size_label)
            actual_ratio = "1:1"
    else:
        size_val = compute_size(ratio, size_label)
        actual_ratio = ratio

    def _gen(_):
        return generate_id_photo(
            prompt_en=prompt, reference_images=ref_imgs,
            size=size_val, aspect_ratio=actual_ratio, extra_negative="",
            model_id=model_id,
        )

    with ThreadPoolExecutor(max_workers=2) as ex:
        futures = [ex.submit(_gen, i) for i in range(2)]
        results = [f.result() for f in futures]

    imgs = [img for img, _ in results if img is not None]
    errs = [s for img, s in results if img is None]

    images = [pil_to_data_uri(img) for img in imgs]

    if len(imgs) == 0:
        return jsonify({"error": errs[0] if errs else "生成失败"})

    status = "生成成功"
    if len(imgs) < 2:
        status = f"生成完成 ({len(imgs)}/2)"

    return jsonify({"status": status, "images": images})


if __name__ == "__main__":
    port = int(os.getenv("PORT", 7860))
    app.run(host="0.0.0.0", port=port, debug=False)
