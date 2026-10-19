import time
import uuid
import json
from typing import Any

import httpx

from app.core.config import API_DIR, Settings
from app.models import CreativePlan, CreativePlanType
from app.services.model_settings import get_runtime_settings
from app.services.volcengine import VolcengineCredentialsError, parse_access_key_pair, signed_json_headers


class ImageGenerationNotConfiguredError(RuntimeError):
    pass


class ImageGenerationError(RuntimeError):
    pass


UPLOADS_DIR = API_DIR / "uploads"
GENERATED_IMAGES_DIR = UPLOADS_DIR / "generated"


def is_image_generation_configured(settings: Settings | None = None) -> bool:
    """判断图片生成任务configured；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    settings = settings or get_runtime_settings()
    return bool(
        settings.image_provider
        and settings.image_base_url
        and settings.image_api_key
        and settings.image_model
    )


def generate_main_image_asset(
    creative_plan: CreativePlan,
    *,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """生成主流程图片素材；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    settings = settings or get_runtime_settings()
    if not is_image_generation_configured(settings):
        raise ImageGenerationNotConfiguredError("Image generation provider is not configured.")
    if settings.image_provider not in {"dashscope", "jimeng", "siliconflow"}:
        raise ImageGenerationNotConfiguredError(
            f"Unsupported image provider: {settings.image_provider}"
        )
    if creative_plan.type != CreativePlanType.MAIN_IMAGE:
        raise ImageGenerationError("Only main image plans can generate image assets.")

    # 生成前清洗 prompt，减少不可见字符和特殊货币符号导致供应商接口解析失败的概率。
    prompt = _sanitize_image_prompt(_main_image_prompt(creative_plan))
    if settings.image_provider == "siliconflow":
        # 硅基流动走 OpenAI 兼容的同步出图接口（POST /v1/images/generations），
        # 一次请求直接返回图片 URL，没有 task_id 和轮询环节。
        result = _create_siliconflow_image(prompt, settings)
        task_id = result.get("request_id", "")
        image_url = _extract_siliconflow_image_url(result)
    elif settings.image_provider == "jimeng":
        task_id = _create_jimeng_image_task(prompt, settings)
        result = _poll_jimeng_image_task(task_id, settings)
        image_url = _extract_jimeng_image_url(result)
    elif settings.image_model == "wan2.6-t2i":
        task_id = _create_dashscope_wan26_text_to_image_task(prompt, settings)
        result = _poll_dashscope_task(task_id, settings)
        image_url = _extract_dashscope_wan26_task_image_url(result)
    elif settings.image_model == "wan2.6-image" or settings.image_model.startswith("qwen-image"):
        # qwen-image 系列与 wan2.6-image 共用同步多模态生成接口：
        # 部分中转网关不支持 X-DashScope-Async 异步调用（会返回 AccessDenied），只能走同步请求直接拿结果。
        result = _create_dashscope_wan26_image(prompt, settings)
        task_id = result.get("request_id", "")
        image_url = _extract_dashscope_wan26_image_url(result)
    else:
        task_id = _create_dashscope_text_to_image_task(prompt, settings)
        result = _poll_dashscope_task(task_id, settings)
        image_url = _extract_dashscope_image_url(result)
    public_path = _download_generated_image(image_url, creative_plan.id)

    return {
        "provider": settings.image_provider,
        "model": settings.image_model,
        "size": settings.image_size,
        "prompt": prompt,
        "task_id": task_id,
        "source_url": image_url,
        "url": public_path,
        "created_at": int(time.time()),
    }


def _create_siliconflow_image(prompt: str, settings: Settings) -> dict[str, Any]:
    """调用硅基流动文生图；同步返回结果，无异步任务与轮询。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    url = _join_base_url(settings.image_base_url or "", "images/generations")
    payload: dict[str, Any] = {
        "model": settings.image_model,
        "prompt": prompt,
        # 硅基流动的尺寸写法是「宽x高」（字母 x），与项目内的「宽*高」不同，这里统一转换。
        "image_size": _siliconflow_image_size(settings.image_size),
        "batch_size": 1,
    }
    headers = {
        "Authorization": f"Bearer {settings.image_api_key}",
        "Content-Type": "application/json",
    }
    # 复用 dashscope 的 POST 封装，主要取其「失败重试 3 次」的容错能力。
    try:
        response = _post_dashscope_json(url, headers=headers, payload=payload, timeout=180)
    except httpx.HTTPStatusError as exc:
        raise ImageGenerationError(_provider_error_detail(exc.response)) from exc
    except httpx.HTTPError as exc:
        raise ImageGenerationError(
            _http_error_detail("SiliconFlow image generation failed", exc)
        ) from exc

    return response.json()


def _extract_siliconflow_image_url(result: dict[str, Any]) -> str:
    """提取siliconflow图片URL，统一主流程中的格式、默认值和异常边界。"""
    # 硅基流动按 OpenAI 兼容格式返回 {"images": [{"url": "..."}]}，老版本可能用 "data"。
    for container in (result.get("images"), result.get("data")):
        if not isinstance(container, list):
            continue
        for item in container:
            if isinstance(item, dict):
                url = item.get("url")
                if isinstance(url, str) and url:
                    return url
    raise ImageGenerationError("SiliconFlow response did not contain an image url.")


def _siliconflow_image_size(size: str) -> str:
    """把项目内的 1024*1024 转成硅基流动要求的 1024x1024。"""
    width, height = _parse_image_size(size)
    return f"{width}x{height}"


def _create_jimeng_image_task(prompt: str, settings: Settings) -> str:
    """创建jimeng图片任务，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    width, height = _parse_image_size(settings.image_size)
    payload: dict[str, Any] = {
        "req_key": settings.image_model,
        "prompt": prompt,
        "use_pre_llm": True,
        "seed": -1,
        "width": width,
        "height": height,
    }
    data = _post_jimeng_json(
        settings=settings,
        action="CVSync2AsyncSubmitTask",
        payload=payload,
        timeout=120,
    )
    task_id = _extract_jimeng_task_id(data)
    if not task_id:
        raise ImageGenerationError("Jimeng image response did not contain task_id.")
    return task_id


def _poll_jimeng_image_task(task_id: str, settings: Settings) -> dict[str, Any]:
    """轮询jimeng图片任务，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    max_attempts = max(settings.image_poll_max_attempts, 1)
    interval = max(settings.image_poll_interval_seconds, 1)
    payload = {
        "req_key": settings.image_model,
        "task_id": task_id,
        "req_json": json.dumps({"return_url": True}, ensure_ascii=False),
    }

    for _attempt in range(max_attempts):
        data = _post_jimeng_json(
            settings=settings,
            action="CVSync2AsyncGetResult",
            payload=payload,
            timeout=30,
        )
        status_value = _jimeng_status(data)
        if status_value in {"done", "succeeded", "success", ""} and _extract_jimeng_image_url(data):
            return data
        if status_value in {"failed", "expired", "not_found"}:
            raise ImageGenerationError(f"Jimeng image task ended with status: {status_value}")
        time.sleep(interval)

    raise ImageGenerationError("Jimeng image task timed out.")


def _post_jimeng_json(
    *,
    settings: Settings,
    action: str,
    payload: dict[str, Any],
    timeout: int,
) -> dict[str, Any]:
    """发送jimengJSON，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    try:
        access_key, secret_key = parse_access_key_pair(settings.image_api_key)
    except VolcengineCredentialsError as exc:
        raise ImageGenerationNotConfiguredError(str(exc)) from exc

    base_url = settings.image_base_url or "https://visual.volcengineapi.com"
    query = {"Action": action, "Version": "2022-08-31"}
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    headers = signed_json_headers(
        access_key=access_key,
        secret_key=secret_key,
        method="POST",
        url=base_url,
        query=query,
        body=body,
    )
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(base_url, params=query, content=body, headers=headers)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as exc:
        raise ImageGenerationError(_provider_error_detail(exc.response)) from exc
    except httpx.HTTPError as exc:
        raise ImageGenerationError(_http_error_detail("Jimeng image request failed", exc)) from exc

    code = data.get("code")
    if code != 10000:
        raise ImageGenerationError(str(data)[:500])
    return data


def _extract_jimeng_task_id(data: dict[str, Any]) -> str:
    """提取jimeng任务id，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    for container in (data.get("data"), data.get("Result"), data.get("output"), data):
        if isinstance(container, dict) and isinstance(container.get("task_id"), str):
            return container["task_id"]
    return ""


def _jimeng_status(data: dict[str, Any]) -> str:
    """jimeng状态，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    container = data.get("data")
    if isinstance(container, dict) and isinstance(container.get("status"), str):
        return container["status"].lower()
    if isinstance(data.get("status"), str):
        return data["status"].lower()
    return ""


def _extract_jimeng_image_url(data: dict[str, Any]) -> str:
    """提取jimeng图片URL，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    containers = [data.get("data"), data.get("Result"), data.get("output"), data]
    for container in containers:
        if not isinstance(container, dict):
            continue
        for key in ("image_url", "url"):
            value = container.get(key)
            if isinstance(value, str) and value:
                return value
        for key in ("image_urls", "urls", "result_urls"):
            value = container.get(key)
            if isinstance(value, list) and value and isinstance(value[0], str):
                return value[0]
        binary_data = container.get("binary_data_base64")
        if isinstance(binary_data, list) and binary_data:
            raise ImageGenerationError("Jimeng returned base64 image data; set return_url=true.")
    return ""


def _parse_image_size(size: str) -> tuple[int, int]:
    """解析图片size，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    normalized = size.replace("*", "x").lower()
    parts = normalized.split("x", 1)
    if len(parts) != 2:
        return 1328, 1328
    try:
        width = int(parts[0])
        height = int(parts[1])
    except ValueError:
        return 1328, 1328
    return max(width, 1), max(height, 1)


def _main_image_prompt(creative_plan: CreativePlan) -> str:
    """主流程图片prompt，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    content = creative_plan.content or {}
    image_prompt = content.get("image_prompt")
    if isinstance(image_prompt, str) and image_prompt.strip():
        return image_prompt.strip()

    prompt_parts = [
        f"电商商品主图，方案标题：{creative_plan.title}",
        f"主文案：{content.get('headline', '')}",
        f"副文案：{content.get('sub_headline', '')}",
        f"画面布局：{content.get('layout', '')}",
        f"视觉重点：{content.get('visual_focus', '')}",
        "干净背景，商品主体清晰，商业摄影质感，适合电商首图。",
    ]
    return "\n".join(part for part in prompt_parts if part.strip())


def _sanitize_image_prompt(prompt: str) -> str:
    """清洗图片prompt，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    replacements = {
        "\u00a5": "yuan",
        "\uffe5": "yuan",
        "\u201c": '"',
        "\u201d": '"',
        "\u2018": "'",
        "\u2019": "'",
        "\u2028": "\n",
        "\u2029": "\n",
    }
    for old, new in replacements.items():
        prompt = prompt.replace(old, new)

    return "".join(
        char for char in prompt if char in {"\n", "\t"} or ord(char) >= 32
    ).strip()


def _create_dashscope_text_to_image_task(prompt: str, settings: Settings) -> str:
    """创建dashscope文本to图片任务，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    url = _join_base_url(settings.image_base_url or "", "services/aigc/text2image/image-synthesis")
    payload = {
        "model": settings.image_model,
        "input": {
            "prompt": prompt,
        },
        "parameters": {
            "size": settings.image_size,
            "n": 1,
            "prompt_extend": True,
            "watermark": False,
        },
    }
    try:
        response = _post_dashscope_json(
            url,
            headers=_dashscope_headers(settings, async_request=True),
            payload=payload,
            timeout=120,
        )
    except httpx.HTTPStatusError as exc:
        raise ImageGenerationError(_dashscope_error_detail(exc.response)) from exc
    except httpx.HTTPError as exc:
        raise ImageGenerationError(_http_error_detail("DashScope image task creation failed", exc)) from exc

    data = response.json()
    task_id = data.get("output", {}).get("task_id")
    if not isinstance(task_id, str) or not task_id:
        raise ImageGenerationError("DashScope response did not contain task_id.")
    return task_id


def _create_dashscope_wan26_image(prompt: str, settings: Settings) -> dict[str, Any]:
    """创建dashscopewan26图片，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    url = _join_base_url(
        settings.image_base_url or "",
        "services/aigc/multimodal-generation/generation",
    )
    payload = {
        "model": settings.image_model,
        "input": {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "text": prompt,
                        },
                    ],
                },
            ],
        },
        "parameters": {
            "size": settings.image_size,
            "n": 1,
            "prompt_extend": True,
            "watermark": False,
        },
    }
    try:
        response = _post_dashscope_json(
            url,
            headers=_dashscope_headers(settings),
            payload=payload,
            timeout=180,
        )
    except httpx.HTTPStatusError as exc:
        raise ImageGenerationError(_dashscope_error_detail(exc.response)) from exc
    except httpx.HTTPError as exc:
        raise ImageGenerationError(_http_error_detail("DashScope wan2.6 image generation failed", exc)) from exc

    return response.json()


def _create_dashscope_wan26_text_to_image_task(prompt: str, settings: Settings) -> str:
    """创建dashscopewan26文本to图片任务，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    url = _join_base_url(
        settings.image_base_url or "",
        "services/aigc/image-generation/generation",
    )
    payload = {
        "model": settings.image_model,
        "input": {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "text": prompt,
                        },
                    ],
                },
            ],
        },
        "parameters": {
            "prompt_extend": True,
            "watermark": False,
            "n": 1,
            "negative_prompt": "",
            "size": settings.image_size,
        },
    }
    try:
        response = _post_dashscope_json(
            url,
            headers=_dashscope_headers(settings, async_request=True),
            payload=payload,
            timeout=120,
        )
    except httpx.HTTPStatusError as exc:
        raise ImageGenerationError(_dashscope_error_detail(exc.response)) from exc
    except httpx.HTTPError as exc:
        raise ImageGenerationError(
            _http_error_detail("DashScope wan2.6 text-to-image task creation failed", exc)
        ) from exc

    data = response.json()
    task_id = data.get("output", {}).get("task_id")
    if not isinstance(task_id, str) or not task_id:
        raise ImageGenerationError("DashScope wan2.6 response did not contain task_id.")
    return task_id


def _poll_dashscope_task(task_id: str, settings: Settings) -> dict[str, Any]:
    """轮询dashscope任务，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    url = _join_base_url(settings.image_base_url or "", f"tasks/{task_id}")
    max_attempts = max(settings.image_poll_max_attempts, 1)
    interval = max(settings.image_poll_interval_seconds, 1)

    try:
        for _attempt in range(max_attempts):
            data = _get_dashscope_json(
                url,
                headers=_dashscope_headers(settings, include_content_type=False),
                timeout=30,
            )
            status = data.get("output", {}).get("task_status")
            if status == "SUCCEEDED":
                return data
            if status in {"FAILED", "CANCELED", "UNKNOWN"}:
                raise ImageGenerationError(f"DashScope image task ended with status: {status}")
            time.sleep(interval)
    except httpx.HTTPStatusError as exc:
        raise ImageGenerationError(_dashscope_error_detail(exc.response)) from exc
    except httpx.HTTPError as exc:
        raise ImageGenerationError(_http_error_detail("DashScope image task polling failed", exc)) from exc

    raise ImageGenerationError("DashScope image task timed out.")


def _get_dashscope_json(
    url: str,
    *,
    headers: dict[str, str],
    timeout: int,
) -> dict[str, Any]:
    """获取dashscopeJSON，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    last_error: httpx.HTTPError | None = None
    for attempt in range(3):
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.get(url, headers=headers)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError:
            raise
        except httpx.HTTPError as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(2 + attempt * 2)

    assert last_error is not None
    raise last_error


def _extract_dashscope_image_url(result: dict[str, Any]) -> str:
    """提取dashscope图片URL，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    output = result.get("output", {})
    results = output.get("results", [])
    if not isinstance(results, list) or not results:
        raise ImageGenerationError("DashScope image task did not return results.")

    image_url = results[0].get("url")
    if not isinstance(image_url, str) or not image_url:
        raise ImageGenerationError("DashScope image result did not contain url.")
    return image_url


def _extract_dashscope_wan26_image_url(result: dict[str, Any]) -> str:
    """提取dashscopewan26图片URL，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    choices = result.get("output", {}).get("choices", [])
    if not isinstance(choices, list) or not choices:
        raise ImageGenerationError("DashScope wan2.6 response did not return choices.")

    content = choices[0].get("message", {}).get("content", [])
    if not isinstance(content, list):
        raise ImageGenerationError("DashScope wan2.6 response did not return content.")

    for item in content:
        if isinstance(item, dict) and isinstance(item.get("image"), str):
            return item["image"]

    raise ImageGenerationError("DashScope wan2.6 response did not contain image url.")


def _extract_dashscope_wan26_task_image_url(result: dict[str, Any]) -> str:
    """提取dashscopewan26任务图片URL，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    output = result.get("output", {})
    choices = output.get("choices", [])
    if isinstance(choices, list):
        for choice in choices:
            if not isinstance(choice, dict):
                continue
            content = choice.get("message", {}).get("content", [])
            if not isinstance(content, list):
                continue
            for item in content:
                if isinstance(item, dict) and isinstance(item.get("image"), str):
                    return item["image"]

    results = output.get("results", [])
    if isinstance(results, list):
        for item in results:
            if isinstance(item, dict) and isinstance(item.get("url"), str):
                return item["url"]

    raise ImageGenerationError("DashScope wan2.6 task result did not contain image url.")


def _join_base_url(base_url: str, path: str) -> str:
    """拼接baseURL，统一主流程中的格式、默认值和异常边界。"""
    return f"{base_url.strip().rstrip('/')}/{path.strip('/')}"


def _dashscope_headers(
    settings: Settings,
    *,
    async_request: bool = False,
    include_content_type: bool = True,
) -> dict[str, str]:
    """dashscopeheaders，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    headers = {
        "Authorization": f"Bearer {settings.image_api_key}",
    }
    if include_content_type:
        headers["Content-Type"] = "application/json"
    if async_request:
        headers["X-DashScope-Async"] = "enable"
    if settings.image_workspace_id:
        headers["X-DashScope-WorkSpace"] = settings.image_workspace_id
    return headers


def _post_dashscope_json(
    url: str,
    *,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout: int,
) -> httpx.Response:
    """发送dashscopeJSON，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    last_error: httpx.HTTPError | None = None
    for attempt in range(3):
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                return response
        except httpx.HTTPStatusError:
            raise
        except httpx.HTTPError as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(3 + attempt * 2)

    assert last_error is not None
    raise last_error


def _dashscope_error_detail(response: httpx.Response) -> str:
    """dashscope错误详情，统一主流程中的格式、默认值和异常边界。"""
    try:
        data = response.json()
    except ValueError:
        return response.text[:500]
    return str(data)[:500]


def _download_generated_image(image_url: str, creative_plan_id: int) -> str:
    """下载生成图片，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    GENERATED_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"main-image-plan-{creative_plan_id}-{uuid.uuid4().hex}.png"
    output_path = GENERATED_IMAGES_DIR / filename

    # 将供应商临时 URL 下载到本地 uploads，避免外部链接过期后素材审核记录失效。
    try:
        with httpx.Client(timeout=120, follow_redirects=True) as client:
            response = client.get(image_url)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise ImageGenerationError(_http_error_detail("Generated image download failed", exc)) from exc

    output_path.write_bytes(response.content)
    return f"/uploads/generated/{filename}"


def _provider_error_detail(response: httpx.Response) -> str:
    """供应商错误详情，统一主流程中的格式、默认值和异常边界。"""
    try:
        data = response.json()
    except ValueError:
        return response.text[:500]
    return str(data)[:500]


def _http_error_detail(message: str, exc: httpx.HTTPError) -> str:
    """HTTP错误详情，统一主流程中的格式、默认值和异常边界。"""
    return f"{message}: {type(exc).__name__}: {exc}"