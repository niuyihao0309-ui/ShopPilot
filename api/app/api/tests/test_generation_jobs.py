from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import (
    Base,
    CreativePlan,
    CreativePlanType,
    GenerationJob,
    GenerationJobEvent,
    GenerationJobKind,
    GenerationJobStatus,
    Product,
)
from app.services import generation_jobs
from app.services.generation_jobs import (
    cancel_generation_job_record,
    enqueue_generation_job,
    mark_stale_running_generation_jobs,
    retry_generation_job_record,
)


def test_enqueue_generation_job_sets_queue_fields() -> None:
    """验证“enqueue生成任务任务sets队列fields”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    with _session() as db:
        product = Product(name="oil control cushion")
        plan = CreativePlan(
            product=product,
            type=CreativePlanType.MAIN_IMAGE,
            title="main image",
            content={},
        )
        db.add_all([product, plan])
        db.flush()

        job = enqueue_generation_job(
            db,
            product_id=product.id,
            creative_plan_id=plan.id,
            kind=GenerationJobKind.MAIN_IMAGE_ASSET,
        )
        db.commit()
        db.refresh(job)

        assert job.status == GenerationJobStatus.PENDING
        assert job.attempts == 0
        assert job.max_attempts == 3
        assert job.next_run_at is not None
        event = db.query(GenerationJobEvent).one()
        assert event.event_type == "queued"
        assert event.status == GenerationJobStatus.PENDING
        assert event.payload["kind"] == "main_image_asset"


def test_retry_generation_job_record_clears_lock_and_error() -> None:
    """验证“重试生成任务任务记录clears锁定and错误”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    with _session() as db:
        product = Product(name="oil control cushion")
        plan = CreativePlan(
            product=product,
            type=CreativePlanType.VIDEO_SCRIPT,
            title="video",
            content={},
        )
        db.add_all([product, plan])
        db.flush()
        job = enqueue_generation_job(
            db,
            product_id=product.id,
            creative_plan_id=plan.id,
            kind=GenerationJobKind.VIDEO_ASSET,
        )
        job.status = GenerationJobStatus.FAILED
        job.error = "temporary"
        job.locked_by = "worker-1"

        retry_generation_job_record(job)

        assert job.status == GenerationJobStatus.PENDING
        assert job.error is None
        assert job.locked_by is None
        assert job.next_run_at is not None
        db.flush()
        event = db.query(GenerationJobEvent).filter_by(job_id=job.id, event_type="retry_requested").one()
        assert event.event_type == "retry_requested"


def test_cancel_generation_job_record_marks_pending_job_cancelled() -> None:
    """验证“取消生成任务任务记录markspending任务cancelled”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    with _session() as db:
        product, plan = _seed_product_and_plan(db)
        job = enqueue_generation_job(
            db,
            product_id=product.id,
            creative_plan_id=plan.id,
            kind=GenerationJobKind.MAIN_IMAGE_ASSET,
        )

        cancelled = cancel_generation_job_record(job, reason="manual stop")
        db.flush()

        assert cancelled is True
        assert job.status == GenerationJobStatus.CANCELLED
        assert job.next_run_at is None
        event = db.query(GenerationJobEvent).filter_by(job_id=job.id, event_type="cancelled").one()
        assert event.message == "manual stop"


def test_mark_stale_running_generation_jobs_requeues_before_max_attempts() -> None:
    """验证“标记超时running生成任务jobsrequeuesbeforemaxattempts”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    with _session() as db:
        product, plan = _seed_product_and_plan(db)
        job = enqueue_generation_job(
            db,
            product_id=product.id,
            creative_plan_id=plan.id,
            kind=GenerationJobKind.MAIN_IMAGE_ASSET,
        )
        job.status = GenerationJobStatus.RUNNING
        job.attempts = 1
        job.started_at = datetime.now(UTC) - timedelta(minutes=45)
        job.locked_by = "worker-timeout"
        db.flush()

        count = mark_stale_running_generation_jobs(db, timeout_minutes=30, now=datetime.now(UTC))

        assert count == 1
        assert job.status == GenerationJobStatus.PENDING
        assert job.locked_by is None
        assert job.next_run_at is not None
        assert db.query(GenerationJobEvent).filter_by(job_id=job.id, event_type="timeout_checked").count() == 1


def test_mark_stale_running_generation_jobs_fails_after_max_attempts() -> None:
    """验证“标记超时running生成任务jobsfailsaftermaxattempts”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    with _session() as db:
        product, plan = _seed_product_and_plan(db)
        job = enqueue_generation_job(
            db,
            product_id=product.id,
            creative_plan_id=plan.id,
            kind=GenerationJobKind.MAIN_IMAGE_ASSET,
        )
        job.status = GenerationJobStatus.RUNNING
        job.attempts = job.max_attempts
        job.started_at = datetime.now(UTC) - timedelta(minutes=45)
        db.flush()

        count = mark_stale_running_generation_jobs(db, timeout_minutes=30, now=datetime.now(UTC))

        assert count == 1
        assert job.status == GenerationJobStatus.FAILED
        assert job.next_run_at is None
        assert "超时处理" in (job.error or "")


def test_dispatch_generation_job_uses_inline_background_task(monkeypatch) -> None:
    """验证“调度生成任务任务usesinlinebackground任务”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    class Settings:
        task_queue_backend = "inline"

    class BackgroundTasks:
        def __init__(self) -> None:
            """初始化 BackgroundTasks 的依赖与运行状态，避免执行阶段临时拼装共享资源。"""
            self.calls = []

        def add_task(self, func, *args) -> None:
            """构造或执行测试所需的add任务，让测试数据、依赖替身与断言保持集中。"""
            self.calls.append((func, args))

    background_tasks = BackgroundTasks()
    monkeypatch.setattr(generation_jobs, "get_settings", lambda: Settings())

    generation_jobs.dispatch_generation_job(12, background_tasks)

    assert len(background_tasks.calls) == 1
    assert background_tasks.calls[0][1] == (12,)


def test_dispatch_generation_job_uses_celery_when_configured(monkeypatch) -> None:
    """验证“调度生成任务任务usescelerywhenconfigured”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    class Settings:
        task_queue_backend = "celery"

    class FakeCeleryTask:
        calls: list[int] = []

        @classmethod
        def delay(cls, job_id: int) -> None:
            """构造或执行测试所需的delay，让测试数据、依赖替身与断言保持集中。"""
            cls.calls.append(job_id)

    monkeypatch.setattr(generation_jobs, "get_settings", lambda: Settings())
    monkeypatch.setattr("app.worker.tasks.run_generation_job_task", FakeCeleryTask)

    generation_jobs.dispatch_generation_job(42)

    assert FakeCeleryTask.calls == [42]


def test_enqueue_writes_next_run_at_in_the_past() -> None:
    """入队时间必须回拨，避免 MySQL 秒级四舍五入把到期时间推到未来导致任务永挂。"""
    # 这是“点生成后约一半概率卡在 pending”的根因，回归测试守住这条不变量。
    with _session() as db:
        product, plan = _seed_product_and_plan(db)
        before = datetime.now(UTC)
        job = enqueue_generation_job(
            db,
            product_id=product.id,
            creative_plan_id=plan.id,
            kind=GenerationJobKind.MAIN_IMAGE_ASSET,
        )

        assert job.next_run_at is not None
        assert job.next_run_at <= before
        assert job.next_run_at < datetime.now(UTC)


def test_retry_record_writes_next_run_at_in_the_past() -> None:
    """手动重试与首次入队同理，到期时间必须落在当前时间之前。"""
    with _session() as db:
        product, plan = _seed_product_and_plan(db)
        job = enqueue_generation_job(
            db,
            product_id=product.id,
            creative_plan_id=plan.id,
            kind=GenerationJobKind.VIDEO_ASSET,
        )
        job.status = GenerationJobStatus.FAILED

        retry_generation_job_record(job)

        assert job.next_run_at < datetime.now(UTC)


def test_is_due_tolerates_small_clock_skew() -> None:
    """到期判断要容忍几秒偏差，但不能把真正的退避等待也算成到期。"""
    now = datetime.now(UTC)

    assert generation_jobs._is_due(None, now) is True
    assert generation_jobs._is_due(now, now) is True
    assert generation_jobs._is_due(now + timedelta(seconds=1), now) is True
    assert generation_jobs._is_due(now + timedelta(minutes=2), now) is False


def test_dispatch_generation_job_schedules_celery_countdown(monkeypatch) -> None:
    """celery 模式下的退避重试应延迟投递，而不是立刻执行。"""
    class Settings:
        task_queue_backend = "celery"

    class FakeCeleryTask:
        calls: list[tuple[tuple, float | None]] = []

        @classmethod
        def apply_async(cls, args=None, countdown=None) -> None:
            """记录延迟投递，验证 countdown 被正确透传。"""
            cls.calls.append((tuple(args or ()), countdown))

        @classmethod
        def delay(cls, job_id: int) -> None:
            """记录立即投递。"""
            cls.calls.append(((job_id,), None))

    monkeypatch.setattr(generation_jobs, "get_settings", lambda: Settings())
    monkeypatch.setattr("app.worker.tasks.run_generation_job_task", FakeCeleryTask)

    generation_jobs.dispatch_generation_job(7, countdown=120)

    assert FakeCeleryTask.calls == [((7,), 120)]


def test_dispatch_generation_job_inline_deferred_uses_timer(monkeypatch) -> None:
    """inline 模式没有轮询器，延迟派发必须落到 daemon 定时器上，否则任务没人捡。"""
    class Settings:
        task_queue_backend = "inline"

    timers: list[tuple[float, object, tuple]] = []

    class FakeTimer:
        def __init__(self, interval, function, args=()) -> None:
            """记录定时器参数，不真正启动线程。"""
            timers.append((interval, function, tuple(args)))
            self.daemon = False

        def start(self) -> None:
            """空实现：测试只关心定时器是否被正确安排。"""

    monkeypatch.setattr(generation_jobs, "get_settings", lambda: Settings())
    monkeypatch.setattr(generation_jobs.threading, "Timer", FakeTimer)

    generation_jobs.dispatch_generation_job(9, countdown=5)

    assert len(timers) == 1
    assert timers[0][0] == 5
    assert timers[0][1] is generation_jobs.run_generation_job
    assert timers[0][2] == (9,)


def test_run_generation_job_schedules_retry_after_failure(monkeypatch) -> None:
    """执行失败进入退避重试时，必须自己安排下一次唤醒，不能只写个未来时间就撒手。"""
    factory = _shared_session_factory()
    with factory() as db:
        product, plan = _seed_product_and_plan(db)
        job = enqueue_generation_job(
            db,
            product_id=product.id,
            creative_plan_id=plan.id,
            kind=GenerationJobKind.MAIN_IMAGE_ASSET,
        )
        db.commit()
        job_id = job.id

    def _boom(*args, **kwargs):
        raise RuntimeError("provider down")

    dispatched: list[tuple[int, dict]] = []

    monkeypatch.setattr(generation_jobs, "SessionLocal", factory)
    monkeypatch.setattr(generation_jobs, "_generate_asset", _boom)
    monkeypatch.setattr(
        generation_jobs,
        "dispatch_generation_job",
        lambda job_id, **kwargs: dispatched.append((job_id, kwargs)),
    )

    generation_jobs.run_generation_job(job_id)

    assert dispatched and dispatched[0][0] == job_id
    assert dispatched[0][1]["countdown"] > 0

    with factory() as db:
        stored = db.get(GenerationJob, job_id)
        assert stored.status == GenerationJobStatus.PENDING
        assert stored.attempts == 1
        assert stored.next_run_at is not None


def test_run_generation_job_does_not_retry_after_max_attempts(monkeypatch) -> None:
    """尝试次数用尽后应置为 FAILED，不再安排重试。"""
    factory = _shared_session_factory()
    with factory() as db:
        product, plan = _seed_product_and_plan(db)
        job = enqueue_generation_job(
            db,
            product_id=product.id,
            creative_plan_id=plan.id,
            kind=GenerationJobKind.MAIN_IMAGE_ASSET,
            max_attempts=1,
        )
        db.commit()
        job_id = job.id

    def _boom(*args, **kwargs):
        raise RuntimeError("provider down")

    dispatched: list[tuple[int, dict]] = []

    monkeypatch.setattr(generation_jobs, "SessionLocal", factory)
    monkeypatch.setattr(generation_jobs, "_generate_asset", _boom)
    monkeypatch.setattr(
        generation_jobs,
        "dispatch_generation_job",
        lambda job_id, **kwargs: dispatched.append((job_id, kwargs)),
    )

    generation_jobs.run_generation_job(job_id)

    assert dispatched == []
    with factory() as db:
        assert db.get(GenerationJob, job_id).status == GenerationJobStatus.FAILED


def _session() -> Session:
    """构造或执行测试所需的会话，让测试数据、依赖替身与断言保持集中。"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def _shared_session_factory():
    """构造跨 Session 共享同一内存库的工厂，供需要多次开启会话的链路测试使用。"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def _seed_product_and_plan(db: Session) -> tuple[Product, CreativePlan]:
    """创建素材生成任务测试所需的商品与主图方案，并保留同一会话关系。"""
    # 使用 ORM 关系绑定方案和商品，确保队列测试覆盖真实外键与 flush 行为。
    product = Product(name="oil control cushion")
    plan = CreativePlan(
        product=product,
        type=CreativePlanType.MAIN_IMAGE,
        title="main image",
        content={},
    )
    db.add_all([product, plan])
    db.flush()
    return product, plan
