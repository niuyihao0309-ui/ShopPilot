from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.routes.auth import require_edit_permission
from app.db.session import get_db
from app.models import User
from app.schemas import ModelSettingsRead, ModelSettingsUpdate
from app.schemas import ModelSettingsTestRequest, ModelSettingsTestResult
from app.services.image_generation import (
    ImageGenerationError,
    ImageGenerationNotConfiguredError,
    _create_dashscope_text_to_image_task,
    _create_dashscope_wan26_image,
    _create_dashscope_wan26_text_to_image_task,
    _create_jimeng_image_task,
    is_image_generation_configured,
)
from app.services.llm import LLMNotConfiguredError, LLMResponseError, create_json_chat_completion
from app.services.model_settings import get_runtime_settings, read_model_settings, update_model_settings
from app.services.video_generation import (
    VideoGenerationError,
    VideoGenerationNotConfiguredError,
    create_dashscope_video_task,
    create_jimeng_video_task,
    is_video_generation_configured,
)

router = APIRouter(prefix='/model-settings', tags=['model-settings'])
SessionDep = Annotated[Session, Depends(get_db)]
EditorDep = Annotated[User, Depends(require_edit_permission)]


@router.get('', response_model=ModelSettingsRead)
def get_model_settings(db: SessionDep, _current_user: EditorDep) -> dict:
    return read_model_settings(db)


@router.patch('', response_model=ModelSettingsRead)
def patch_model_settings(payload: ModelSettingsUpdate, db: SessionDep, _current_user: EditorDep) -> dict:
    return update_model_settings(payload.model_dump(exclude_unset=True), db)


@router.post('/test', response_model=ModelSettingsTestResult)
def test_model_settings(payload: ModelSettingsTestRequest, _current_user: EditorDep) -> dict:
    # 连通性测试只验证供应商可达，不生成业务素材记录，也不把测试响应写入数据库。
    if payload.target == 'text':
        return _test_text_model()
    if payload.target == 'image':
        return _test_image_model()
    return _test_video_model()


def _test_text_model() -> dict:
    settings = get_runtime_settings()
    try:
        result, _raw = create_json_chat_completion(
            [
                {'role': 'system', 'content': '你是一个接口连通性测试助手，只返回 JSON。'},
                {'role': 'user', 'content': '返回 {"ok": true, "message": "ready"}'},
            ],
            max_tokens=80,
            temperature=0,
            settings=settings,
        )
    except LLMNotConfiguredError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LLMResponseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if result.get('ok') is not True:
        raise HTTPException(status_code=502, detail='Text model test response must contain ok=true.')
    return {'target': 'text', 'ok': True, 'message': 'Text model is reachable and returned ok=true.'}


def _test_image_model() -> dict:
    """测试图片模型连通性；只创建供应商任务，不下载、不入素材库。"""
    settings = get_runtime_settings()
    if not is_image_generation_configured(settings):
        raise HTTPException(status_code=400, detail='Image generation provider is not configured.')

    prompt = '电商商品主图连通性测试，白底，商品清晰，专业摄影质感'
    try:
        # 图片测试只创建供应商任务，不下载、不入素材库，避免测试污染运营资产。
        if settings.image_provider == 'jimeng':
            task_id = _create_jimeng_image_task(prompt, settings)
        elif settings.image_model == 'wan2.6-t2i':
            task_id = _create_dashscope_wan26_text_to_image_task(prompt, settings)
        elif settings.image_model == 'wan2.6-image' or settings.image_model.startswith('qwen-image'):
            # qwen-image 系列与 wan2.6-image 一样走同步多模态生成接口，部分网关不支持异步调用。
            result = _create_dashscope_wan26_image(prompt, settings)
            task_id = str(result.get('request_id') or '')
        else:
            task_id = _create_dashscope_text_to_image_task(prompt, settings)
    except ImageGenerationNotConfiguredError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ImageGenerationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {'target': 'image', 'ok': True, 'message': f'Image model is reachable. task_id={task_id}'}


def _test_video_model() -> dict:
    """测试视频模型连通性；同样停留在任务创建层。"""
    settings = get_runtime_settings()
    if not is_video_generation_configured(settings):
        raise HTTPException(status_code=400, detail='Video generation provider is not configured.')

    prompt = '电商短视频连通性测试，白底商品展示，专业广告质感，镜头稳定'
    try:
        # 视频测试同样停留在任务创建层，真实素材生成仍必须从创意方案进入任务队列。
        if settings.video_provider == 'jimeng':
            task_id = create_jimeng_video_task(prompt, settings)
        else:
            task_id = create_dashscope_video_task(prompt, settings)
    except VideoGenerationNotConfiguredError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except VideoGenerationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {'target': 'video', 'ok': True, 'message': f'Video model is reachable. task_id={task_id}'}