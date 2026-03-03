# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

造梦空间 (Dream Space) is an AI portrait/image generation web app built on Flask. It wraps ByteDance's SeedDream 4.5 API (doubao-seedream-4-5-251128) via an OpenAI-compatible interface to generate 2 images per request.

## Running the App

```bash
# Start the Flask server (port 7860)
python app.py

# Install dependencies (core)
pip install -r requirements.txt

# Install optional local photo processing dependencies
pip install rembg onnxruntime opencv-python
```

The app requires `ARK_API_KEY` to be set as an environment variable (or it falls back to the default in `config.py`).

## Diagnostic Scripts

```bash
# Test plain text-to-image API call
python test_ref.py

# Test image-to-image with a reference photo
python test_ref.py <image_path>

# Probe which extra_body parameter names the API accepts for reference images
python probe_character_ref.py <image_path>
```

## Architecture

**Request flow for image generation:**
1. `app.py` `POST /generate` receives form data (prompt, ratio, size_label, optional image)
2. `config.compute_size()` converts ratio + quality label to a pixel dimension string (e.g. `"2048x1536"`)
3. `api_client.generate_id_photo()` is called **twice in parallel** via `ThreadPoolExecutor`
4. If a reference image is provided → `_img2img()` (streaming, `extra_body["image"]` = base64 data URI)
5. If no reference image → `_text2img()` (non-streaming, returns a URL)
6. Results are base64-encoded PNGs returned as `data:image/png;base64,...` to the frontend

**Local photo processing pipeline** (`photo_processor.py`) — currently not wired into the main generation flow, exists as a standalone utility:
- `remove_background()` → rembg u2net_human_seg model → RGBA
- `apply_background()` → composites onto flat color (white/blue/red/gray)
- `crop_to_id_photo()` → OpenCV Haar cascade face detection → face-centered crop + resize

**Prompt database** (`prompt_db.py`):
- SQLite at `data/prompts.db` (path in `config.DB_PATH`)
- 8 built-in presets (is_preset=1, undeletable) seeded on `init_db()`
- CRUD: `upsert_prompt()`, `delete_prompt()`, `get_all_prompts()`, `get_prompt_by_name()`
- Note: `init_db()` is defined but not called from `app.py` — must be called explicitly if prompt management is needed

**Frontend** (all inlined in `app.py:index()`):
- Single-page app with no build step; HTML/CSS/JS is a Python f-string
- Generation history stored in `localStorage` under key `dreamspace_history`
- Two result slots per card, filled concurrently

## Key Configuration (`config.py`)

| Variable | Default | Purpose |
|---|---|---|
| `ARK_API_KEY` | env or hardcoded | ByteDance Ark API key |
| `ARK_MODEL_ID` | `doubao-seedream-4-5-251128` | SeedDream model endpoint |
| `MAX_REF_IMAGE_PX` | `1024` | Reference image max side before base64 encoding |
| `REQUEST_TIMEOUT` | `120` | OpenAI client timeout (seconds) |
| `GLOBAL_NEGATIVE_PROMPT` | string | Appended to every generation request |

## API Notes

- img2img uses `stream=True` and reads `event.b64_json` from `image_generation.partial_succeeded` events
- text2img uses `response_format="url"` and fetches the URL with requests
- Image sizes must meet a minimum pixel count (~3.7M px); `compute_size()` enforces this and rounds to multiples of 8
- `reference_strength` parameter in `generate_id_photo()` signature is not currently forwarded to `extra_body` — only `"image"` key is sent
