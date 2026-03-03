"""
api_client.py — SeedDream 4.5 / 5.0 API 封装
"""
import base64
import io
import requests
from PIL import Image
from openai import OpenAI, APIStatusError, APIConnectionError, APITimeoutError

from config import (
    ARK_API_KEY,
    ARK_BASE_URL,
    ARK_MODEL_ID,
    ARK_MODEL_ID_V5,
    ARK_CHAT_MODEL,
    GLOBAL_NEGATIVE_PROMPT,
    MAX_REF_IMAGE_PX,
    REQUEST_TIMEOUT,
)


def _client() -> OpenAI:
    return OpenAI(
        api_key=ARK_API_KEY,
        base_url=ARK_BASE_URL,
        timeout=REQUEST_TIMEOUT,
    )


# ── 图像工具 ────────────────────────────────────────────────────────────────────

def image_to_base64(pil_image: Image.Image) -> str:
    """等比缩放至 MAX_REF_IMAGE_PX 后 JPEG 编码，返回 data URI 字符串。"""
    img = pil_image.convert("RGB")
    w, h = img.size
    if max(w, h) > MAX_REF_IMAGE_PX:
        scale = MAX_REF_IMAGE_PX / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    return f"data:image/jpeg;base64,{b64}"


def _b64_to_pil(b64_str: str) -> Image.Image:
    return Image.open(io.BytesIO(base64.b64decode(b64_str)))


def _url_to_pil(url: str) -> Image.Image:
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    return Image.open(io.BytesIO(resp.content))


# ── 提示词优化 ──────────────────────────────────────────────────────────────────

_OPTIMIZE_SYSTEM = (
    "你是一个专业的AI图像生成提示词工程师。"
    "用户会给你一段中文描述，请将其扩展为更详细、更专业的中文图像生成提示词。"
    "要求：细化光线、构图、镜头、风格、氛围、画质等细节，使提示词更丰富专业。"
    "保持中文输出，只输出优化后的提示词，不要任何解释或说明。"
)

def optimize_prompt(text: str) -> tuple[str | None, str]:
    """调用豆包对话模型优化提示词。"""
    if ARK_API_KEY in ("", "your-key-here"):
        return None, "错误：未配置 ARK_API_KEY"
    if not ARK_CHAT_MODEL:
        return None, "错误：未配置 ARK_CHAT_MODEL，请在火山引擎控制台创建豆包对话模型推理接入点，并设置环境变量 ARK_CHAT_MODEL"
    try:
        client = _client()
        resp = client.chat.completions.create(
            model=ARK_CHAT_MODEL,
            messages=[
                {"role": "system", "content": _OPTIMIZE_SYSTEM},
                {"role": "user", "content": text},
            ],
            max_tokens=512,
        )
        result = resp.choices[0].message.content.strip()
        return result, "提示词优化完成"
    except Exception as e:
        return None, f"优化失败：{e}"




def generate_id_photo(
    prompt_en: str,
    reference_images: list,
    size: str = "2k",
    aspect_ratio: str = "1:1",
    reference_strength: float = 0.82,
    extra_negative: str = "",
    model_id: str = None,
) -> tuple[Image.Image | None, str]:
    """
    调用 SeedDream API 生成图像。
    model_id: 传 None 则使用 ARK_MODEL_ID（4.5），传 ARK_MODEL_ID_V5 则使用 5.0。
    """
    if ARK_API_KEY in ("", "your-key-here"):
        return None, "错误：未配置 ARK_API_KEY，请设置环境变量或在 config.py 中填入 API Key"

    if model_id is None:
        model_id = ARK_MODEL_ID

    negative = GLOBAL_NEGATIVE_PROMPT
    if extra_negative and extra_negative.strip():
        negative = f"{negative}, {extra_negative.strip()}"

    try:
        client = _client()

        if model_id == ARK_MODEL_ID_V5:
            return _v5_generate(client, prompt_en, reference_images, size, aspect_ratio, negative)
        elif reference_images:
            return _img2img(client, prompt_en, reference_images, size, aspect_ratio, negative)
        else:
            return _text2img(client, prompt_en, size, aspect_ratio, negative)

    except APITimeoutError:
        return None, f"请求超时（>{REQUEST_TIMEOUT}s），请检查网络后重试"
    except APIConnectionError as e:
        return None, f"网络连接失败：{e}"
    except APIStatusError as e:
        return None, _format_status_error(e)
    except Exception as e:
        return None, f"请求异常：{e}"


# ── SeedDream 4.5 ───────────────────────────────────────────────────────────────

def _img2img(
    client: OpenAI,
    prompt: str,
    ref_images: list,
    size: str,
    aspect_ratio: str,
    negative: str,
) -> tuple[Image.Image | None, str]:
    """图生图：stream=True，单图传字符串，多图传列表。"""
    b64_list = [image_to_base64(img) for img in ref_images]
    image_param = b64_list[0] if len(b64_list) == 1 else b64_list

    stream = client.images.generate(
        model=ARK_MODEL_ID,
        prompt=prompt,
        size=size,
        response_format="b64_json",
        stream=True,
        extra_body={
            "image": image_param,
            "watermark": False,
            "negative_prompt": negative,
            "sequential_image_generation": "disabled",
            "aspect_ratio": aspect_ratio,
        },
    )

    last_b64 = None
    for event in stream:
        if event is None:
            continue
        if event.type == "image_generation.partial_succeeded":
            if event.b64_json:
                last_b64 = event.b64_json
        elif event.type == "image_generation.completed":
            pass

    if last_b64 is None:
        return None, "img2img 未返回图像数据，请重试"

    return _b64_to_pil(last_b64), "生成成功！（图生图）"


def _text2img(
    client: OpenAI,
    prompt: str,
    size: str,
    aspect_ratio: str,
    negative: str,
) -> tuple[Image.Image | None, str]:
    """纯文生图：stream=False，response_format=url。"""
    response = client.images.generate(
        model=ARK_MODEL_ID,
        prompt=prompt,
        size=size,
        n=1,
        response_format="url",
        extra_body={
            "watermark": False,
            "negative_prompt": negative,
            "sequential_image_generation": "disabled",
            "aspect_ratio": aspect_ratio,
        },
    )
    img_url = response.data[0].url
    return _url_to_pil(img_url), "生成成功！（文生图）"


# ── SeedDream 5.0 ───────────────────────────────────────────────────────────────

def _v5_generate(
    client: OpenAI,
    prompt: str,
    ref_images: list,
    size: str,
    aspect_ratio: str,
    negative: str,
) -> tuple[Image.Image | None, str]:
    """SeedDream 5.0：stream=False，response_format=url，有无参考图均适用。"""
    extra = {
        "watermark": False,
        "negative_prompt": negative,
        "sequential_image_generation": "disabled",
        "aspect_ratio": aspect_ratio,
    }
    if ref_images:
        b64_list = [image_to_base64(img) for img in ref_images]
        extra["image"] = b64_list[0] if len(b64_list) == 1 else b64_list

    response = client.images.generate(
        model=ARK_MODEL_ID_V5,
        prompt=prompt,
        size=size,
        response_format="url",
        extra_body=extra,
    )
    img_url = response.data[0].url
    label = "图生图" if ref_images else "文生图"
    return _url_to_pil(img_url), f"生成成功！（SeedDream 5.0 · {label}）"


# ── 错误格式化 ──────────────────────────────────────────────────────────────────

def _format_status_error(e: APIStatusError) -> str:
    code = e.status_code
    try:
        body = e.response.json()
        msg = body.get("error", {}).get("message", str(e))
    except Exception:
        msg = str(e)

    if code == 401:
        return "认证失败（401）：API Key 无效或已过期"
    if code == 422:
        return f"参数错误（422）：{msg}"
    if code == 429:
        return "请求过于频繁（429）：请稍等片刻后重试"
    if code == 404:
        return f"模型不存在（404）：{ARK_MODEL_ID_V5 if 'v5' in str(e) else ARK_MODEL_ID}，请确认 endpoint ID"
    return f"API 错误 {code}：{msg}"
