"""
photo_processor.py — 本地证件照处理：抠图 + 换背景 + 裁剪
"""
import io
import numpy as np
from PIL import Image, ImageFilter

try:
    from rembg import remove, new_session
    _session = new_session("u2net_human_seg")
    REMBG_AVAILABLE = True
except Exception:
    REMBG_AVAILABLE = False

# 背景颜色映射
BG_COLORS = {
    "白底": (255, 255, 255),
    "蓝底": (67, 144, 196),   # #4390C4
    "红底": (204,   0,   0),  # #CC0000
    "灰底": (200, 200, 200),
}


def remove_background(pil_image: Image.Image) -> Image.Image:
    """
    使用 rembg 去除背景，返回 RGBA 图像。
    """
    if not REMBG_AVAILABLE:
        raise RuntimeError("rembg 未安装，请运行: pip install rembg onnxruntime")

    buf_in = io.BytesIO()
    pil_image.convert("RGB").save(buf_in, format="PNG")
    buf_in.seek(0)

    result_bytes = remove(buf_in.read(), session=_session)
    return Image.open(io.BytesIO(result_bytes)).convert("RGBA")


def apply_background(rgba_image: Image.Image, bg_color: tuple[int, int, int]) -> Image.Image:
    """将 RGBA 图像合成到纯色背景上，返回 RGB 图像。"""
    bg = Image.new("RGBA", rgba_image.size, (*bg_color, 255))
    bg.paste(rgba_image, mask=rgba_image.split()[3])
    return bg.convert("RGB")


def crop_to_id_photo(
    rgb_image: Image.Image,
    target_w: int,
    target_h: int,
    head_ratio: float = 0.75,
) -> Image.Image:
    """
    人脸居中裁剪到证件照尺寸。
    head_ratio: 头部高度占目标高度的比例（0.6~0.8）
    """
    try:
        import cv2
        face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        arr = np.array(rgb_image)
        gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.1, 5, minSize=(60, 60))

        if len(faces) > 0:
            # 取最大人脸
            x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
            face_cx = x + w // 2
            face_cy = y + h // 2

            # 根据 head_ratio 推算裁剪框高度
            crop_h = int(h / head_ratio)
            crop_w = int(crop_h * target_w / target_h)

            # 人脸垂直居中偏上（头顶留 15% 空间）
            top  = max(0, face_cy - int(h * 0.5) - int(crop_h * 0.15))
            left = max(0, face_cx - crop_w // 2)

            # 边界修正
            img_w, img_h = rgb_image.size
            if left + crop_w > img_w:
                left = img_w - crop_w
            if top + crop_h > img_h:
                top = img_h - crop_h
            left = max(0, left)
            top  = max(0, top)

            cropped = rgb_image.crop((left, top, left + crop_w, top + crop_h))
            return cropped.resize((target_w, target_h), Image.LANCZOS)

    except Exception:
        pass

    # 无法检测人脸时：居中裁剪
    img_w, img_h = rgb_image.size
    aspect = target_w / target_h
    if img_w / img_h > aspect:
        new_w = int(img_h * aspect)
        left = (img_w - new_w) // 2
        cropped = rgb_image.crop((left, 0, left + new_w, img_h))
    else:
        new_h = int(img_w / aspect)
        top = (img_h - new_h) // 4   # 偏上裁剪
        cropped = rgb_image.crop((0, top, img_w, top + new_h))

    return cropped.resize((target_w, target_h), Image.LANCZOS)


def process_id_photo(
    pil_image: Image.Image,
    bg_color_name: str,
    target_w: int,
    target_h: int,
) -> tuple[Image.Image | None, str]:
    """
    主流程：抠图 → 换背景 → 裁剪。
    返回 (result_image | None, status_str)
    """
    try:
        rgba = remove_background(pil_image)
    except Exception as e:
        return None, f"抠图失败：{e}"

    bg_color = BG_COLORS.get(bg_color_name, (255, 255, 255))
    rgb = apply_background(rgba, bg_color)

    result = crop_to_id_photo(rgb, target_w, target_h)
    return result, f"处理完成！背景：{bg_color_name}，尺寸：{target_w}×{target_h} px"
