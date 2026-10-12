from datetime import UTC, datetime

from app.services.video_generation import (
    VideoGenerationError,
    _aspect_ratio_from_size,
    _duration_to_frames,
)
from app.services.volcengine import parse_access_key_pair, signed_json_headers


def test_parse_access_key_pair() -> None:
    """验证“解析访问keypair”场景，确保重构后仍满足预期业务与安全边界。"""
    assert parse_access_key_pair("ak:sk") == ("ak", "sk")


def test_signed_json_headers_are_deterministic() -> None:
    """验证“签名JSONheadersaredeterministic”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    headers = signed_json_headers(
        access_key="ak",
        secret_key="sk",
        method="POST",
        url="https://visual.volcengineapi.com",
        query={"Action": "CVSync2AsyncSubmitTask", "Version": "2022-08-31"},
        body=b'{"req_key":"jimeng_t2i_v31"}',
        request_time=datetime(2026, 6, 1, 1, 2, 3, tzinfo=UTC),
    )

    assert headers["X-Date"] == "20260601T010203Z"
    assert headers["Host"] == "visual.volcengineapi.com"
    assert "Credential=ak/20260601/cn-north-1/cv/request" in headers["Authorization"]
    assert "Signature=" in headers["Authorization"]


def test_jimeng_video_helpers() -> None:
    """验证“jimeng视频helpers”场景，确保重构后仍满足预期业务与安全边界。"""
    # 即梦3.0 720P 官方仅支持 5 秒(121帧) / 10 秒(241帧)。
    assert _duration_to_frames(5) == 121
    assert _duration_to_frames(10) == 241
    assert _aspect_ratio_from_size("1280*720") == "16:9"
    assert _aspect_ratio_from_size("720*1280") == "9:16"


def test_jimeng_video_rejects_unsupported_duration() -> None:
    """即梦3.0仅支持5/10秒，其他时长必须报错，而不是被静默换算。"""
    import pytest

    with pytest.raises(VideoGenerationError):
        _duration_to_frames(8)
