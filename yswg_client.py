"""
yswg_client.py — 造梦 AI 服务平台调用封装

调用流程（异步轮询）：
  1. invoke_service()  →  taskId
  2. poll_task()       →  任务状态/结果
  3. invoke_and_wait() →  一步完成（阻塞直到成功/失败/超时）

状态码：0=排队中，1=处理中，2=成功，3=失败，4=已取消
"""
import time
import uuid
import requests

from config import YSWG_BASE_URL, YSWG_APP_KEY, YSWG_APP_SECRET


def _headers() -> dict:
    return {
        "App-Key":    YSWG_APP_KEY,
        "App-Secret": YSWG_APP_SECRET,
        "Content-Type": "application/json",
    }


def _check_credentials():
    if not YSWG_APP_KEY or not YSWG_APP_SECRET:
        raise ValueError("未配置 YSWG_APP_KEY / YSWG_APP_SECRET，请在 .env 中设置")


def invoke_service(
    service_id: str | int,
    messages: list[dict],
    client_trace_id: str | None = None,
    timeout: int = 30,
) -> dict:
    """
    调用 AI 服务（异步），返回原始响应 data 字段，包含 taskId。

    参数
    ----
    service_id      : AI 服务 ID
    messages        : [{"role": "system"|"user", "content": "..."}]
    client_trace_id : 可选，调用方自定义链路追踪 ID
    timeout         : HTTP 请求超时（秒）

    返回
    ----
    {
        "taskId": 123456789,
        "requestId": "req_xxx",
        "serviceName": "...",
        "async": True,
        "clientTraceId": "..."   # 如有
    }
    """
    _check_credentials()

    body: dict = {
        "params": {"messages": messages},
    }
    if client_trace_id:
        body["clientTraceId"] = client_trace_id

    url = f"{YSWG_BASE_URL}/api/admin/api/v1/ai/service/invoke/{service_id}"
    resp = requests.post(url, json=body, headers=_headers(), timeout=timeout)
    resp.raise_for_status()

    payload = resp.json()
    if payload.get("code") != 200:
        raise RuntimeError(f"调用失败：{payload.get('message', payload)}")

    return payload["data"]


def poll_task(task_id: str | int, timeout: int = 30) -> dict:
    """
    查询单次任务状态，返回原始响应 data 字段。

    status 含义：
        0 排队中  1 处理中  2 成功  3 失败  4 已取消
    """
    _check_credentials()

    url = f"{YSWG_BASE_URL}/api/admin/api/v1/ai/service/tasks/{task_id}"
    resp = requests.get(url, headers=_headers(), timeout=timeout)
    resp.raise_for_status()

    payload = resp.json()
    if payload.get("code") != 200:
        raise RuntimeError(f"查询失败：{payload.get('message', payload)}")

    return payload["data"]


def invoke_and_wait(
    service_id: str | int,
    messages: list[dict],
    poll_interval: float = 3.0,
    max_wait: float = 300.0,
    client_trace_id: str | None = None,
) -> dict:
    """
    调用服务并阻塞轮询直到完成，返回最终 task data。

    成功时 data["status"] == 2，result 字段含生成内容。
    失败时抛出 RuntimeError，含 failReason。
    超时时抛出 TimeoutError。
    """
    if client_trace_id is None:
        client_trace_id = f"zmkj_{uuid.uuid4().hex[:12]}"

    invoke_data = invoke_service(service_id, messages, client_trace_id=client_trace_id)
    task_id = invoke_data["taskId"]

    deadline = time.monotonic() + max_wait
    while True:
        task = poll_task(task_id)
        status = task.get("status")

        if status == 2:      # 成功
            return task
        if status == 3:      # 失败
            raise RuntimeError(f"任务失败：{task.get('failReason', '未知原因')}")
        if status == 4:      # 已取消
            raise RuntimeError("任务已取消")

        if time.monotonic() >= deadline:
            raise TimeoutError(f"任务 {task_id} 超时（>{max_wait}s）")

        time.sleep(poll_interval)
