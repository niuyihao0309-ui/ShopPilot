"""验证生成任务入队时间的正确性，用于回归“点生成后卡在 pending”的 bug。

用法（在 api 目录下）：

    .venv/Scripts/python.exe -m scripts.verify_generation_due_time

脚本分两段：
1. 穷举全部 100 万个微秒取值，验算旧写法/新写法各自被判成“未到期而跳过”的比例。
   这一步不需要数据库，是纯逻辑推演，可离线跑。
2. 若能连上业务库，再往真实 MySQL 写一次探针值，确认落库后的秒级取整方向。
"""
from datetime import UTC, datetime, timedelta

from app.services.generation_jobs import (
    DISPATCH_CLOCK_SKEW,
    DUE_TOLERANCE,
    _dispatch_now,
    _is_due,
)

BASE = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)


def mysql_datetime_round(value: datetime) -> datetime:
    """模拟 MySQL DATETIME(0) 落库：微秒 >= 500ms 进位到下一秒，否则直接舍去。"""
    if value.microsecond >= 500_000:
        return value.replace(microsecond=0) + timedelta(seconds=1)
    return value.replace(microsecond=0)


def was_skipped_old(now: datetime) -> bool:
    """旧写法：写入 now，落库后严格比较 due_at > now。返回 True 表示被跳过并永久卡住。"""
    return mysql_datetime_round(now) > now


def was_skipped_new(now: datetime) -> bool:
    """新写法：写入 now - 1s，再走带容差的到期判断。返回 True 表示被跳过。"""
    return not _is_due(mysql_datetime_round(now - DISPATCH_CLOCK_SKEW), now)


def verify_by_exhaustion() -> None:
    """穷举所有微秒取值，对比修复前后被跳过的比例。"""
    total = 1_000_000
    old_skipped = 0
    new_skipped = 0
    first_old = None

    for micro in range(total):
        now = BASE.replace(microsecond=micro)
        if was_skipped_old(now):
            old_skipped += 1
            if first_old is None:
                first_old = micro
        if was_skipped_new(now):
            new_skipped += 1

    print(f"穷举 {total:,} 个微秒取值（每个代表一个入队瞬间）")
    print()
    print("旧写法  next_run_at = datetime.now(UTC)")
    print(f"  被跳过 {old_skipped:,} 次  →  卡死率 {old_skipped / total:.2%}")
    print(f"  最早从 microsecond = {first_old:,} 开始卡（>= 500ms 必挂）")
    print()
    print(f"新写法  next_run_at = datetime.now(UTC) - {DISPATCH_CLOCK_SKEW}")
    print(f"  被跳过 {new_skipped:,} 次  →  卡死率 {new_skipped / total:.2%}")
    print()
    print(f"到期判断容差 DUE_TOLERANCE = {DUE_TOLERANCE}")
    print("结论:", "修复后任何入队瞬间都能被正常执行" if new_skipped == 0 else "仍有未覆盖场景")


def verify_against_mysql() -> None:
    """若能连上业务库，确认真实 MySQL 确实按四舍五入进位，并检查新写法落库值。"""
    try:
        from sqlalchemy import create_engine, text

        from app.core.config import get_settings
    except Exception as exc:  # pragma: no cover - 仅用于人工排查
        print(f"跳过真实库校验：{type(exc).__name__}")
        return

    try:
        engine = create_engine(get_settings().database_url, connect_args={"connect_timeout": 3})
        with engine.connect() as conn:
            conn.execute(text("CREATE TEMPORARY TABLE due_time_probe (id INT PRIMARY KEY, ts DATETIME)"))
            conn.execute(
                text("INSERT INTO due_time_probe VALUES (1, :ts)"),
                {"ts": datetime(2026, 1, 1, 0, 0, 0, 600000)},
            )
            stored = conn.execute(text("SELECT ts FROM due_time_probe WHERE id = 1")).scalar()
            print()
            print("真实 MySQL 校验")
            print(f"  写入 00:00:00.600000  →  落库 {stored}")
            print(f"  确认四舍五入进位: {stored == datetime(2026, 1, 1, 0, 0, 1)}")

            now = datetime.now(UTC).replace(tzinfo=None)
            conn.execute(text("INSERT INTO due_time_probe VALUES (2, :ts)"), {"ts": now})
            old_stored = conn.execute(text("SELECT ts FROM due_time_probe WHERE id = 2")).scalar()
            new_value = _dispatch_now().replace(tzinfo=None)
            conn.execute(text("INSERT INTO due_time_probe VALUES (3, :ts)"), {"ts": new_value})
            new_stored = conn.execute(text("SELECT ts FROM due_time_probe WHERE id = 3")).scalar()
            print(f"  旧写法写入 {now}  →  落库 {old_stored}  →  是否变成未来: {old_stored > now}")
            print(f"  新写法写入 {new_value}  →  落库 {new_stored}  →  是否变成未来: {new_stored > new_value}")
    except Exception as exc:
        print()
        print(f"跳过真实库校验：{type(exc).__name__}: {exc}")


if __name__ == "__main__":
    verify_by_exhaustion()
    verify_against_mysql()
