import json
from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from app.models import PerformanceRecord, Product
from app.services.llm import (
    LLMNotConfiguredError,
    LLMResponseError,
    create_json_chat_completion,
)




def enrich_performance_metrics(payload: dict) -> dict:
    # 只在用户未填报指标时补算，保留平台报表已有 CTR、CVR、ROI 的原始口径。
    """补充经营数据metrics；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    impressions = payload.get("impressions")
    clicks = payload.get("clicks")
    conversions = payload.get("conversions")
    spend = payload.get("spend")
    revenue = payload.get("revenue")

    if payload.get("ctr") is None:
        payload["ctr"] = _ratio(clicks, impressions)
    if payload.get("conversion_rate") is None:
        payload["conversion_rate"] = _ratio(conversions, clicks)
    if payload.get("roi") is None:
        payload["roi"] = _ratio(revenue, spend)

    return payload














def _ratio(numerator: Decimal | int | None, denominator: Decimal | int | None) -> Decimal | None:
    """比率，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    if numerator is None or denominator is None:
        return None

    numerator_decimal = Decimal(str(numerator))
    denominator_decimal = Decimal(str(denominator))
    if denominator_decimal == 0:
        return None

    return (numerator_decimal / denominator_decimal).quantize(Decimal("0.0001"))


class ReviewReportOutput(BaseModel):
    """LLM 复盘报告的输出结构，约束 summary / insights / next_actions 的格式。"""
    period_start: date = Field(description="复盘周期开始日期")
    period_end: date = Field(description="复盘周期结束日期")
    summary: str = Field(min_length=1, description="本期经营整体结论，1-3 句话")
    insights: list[str] = Field(default_factory=list, description="关键洞察，2-5 条")
    next_actions: list[str] = Field(default_factory=list, description="可执行下一步动作，2-5 条")


def generate_review(product: Product) -> dict[str, Any]:
    """生成商品经营复盘；优先调用 LLM 生成结构化报告，不可用时用规则兜底。"""
    try:
        return generate_llm_review(product)
    except (LLMNotConfiguredError, LLMResponseError, ValidationError) as exc:
        fallback = generate_rule_based_review(product)
        fallback["raw_output"]["fallback_reason"] = str(exc)
        return fallback


def generate_llm_review(product: Product) -> dict[str, Any]:
    """通过 LLM 生成复盘；集中执行业务校验并返回可验证的结构化结果。"""
    parsed, raw_response = create_json_chat_completion(
        _build_review_messages(product),
        max_tokens=1800,
        temperature=0.25,
    )
    review = ReviewReportOutput.model_validate(parsed)
    return review.model_dump()


def generate_rule_based_review(product: Product) -> dict[str, Any]:
    """规则版复盘；仅基于已有 performance_records 汇总，不依赖 LLM。"""
    records = product.performance_records
    if not records:
        raise ValueError(
            "商品暂无经营数据，无法生成复盘报告，请先录入 performance_records"
        )

    period_start = min(r.period_start for r in records)
    period_end = max(r.period_end for r in records)

    insights: list[str] = []
    next_actions: list[str] = []

    # 汇总各指标均值，驱动规则分支
    avg_ctr = _avg_decimal(records, "ctr")
    avg_cvr = _avg_decimal(records, "conversion_rate")
    avg_roi = _avg_decimal(records, "roi")
    total_spend = sum(r.spend or Decimal("0") for r in records)
    total_revenue = sum(r.revenue or Decimal("0") for r in records)

    if avg_ctr is not None and avg_ctr < Decimal("0.01"):
        insights.append(f"点击率均值 {avg_ctr:.4f} 偏低（<1%），主图/短视频前 3 秒吸引力不足")
        next_actions.append("更换主图测试，优先对比高点击素材与当前素材的 CTR 差异")
    elif avg_ctr is not None:
        insights.append(f"点击率均值 {avg_ctr:.4f}，处于正常区间")

    if avg_cvr is not None and avg_cvr < Decimal("0.02"):
        insights.append(f"转化率均值 {avg_cvr:.4f} 偏低（<2%），落地页或价格竞争力需优化")
        next_actions.append("检查商品详情页加载速度与价格对比，考虑限时优惠提升转化")
    elif avg_cvr is not None:
        insights.append(f"转化率均值 {avg_cvr:.4f}，处于正常区间")

    if avg_roi is not None:
        if avg_roi < Decimal("1"):
            insights.append(f"ROI 均值 {avg_roi:.2f} 低于盈亏平衡线，投放效率需调整")
            next_actions.append("缩减低效广告计划，将预算向高 ROI 素材和人群定向倾斜")
        elif avg_roi >= Decimal("3"):
            insights.append(f"ROI 均值 {avg_roi:.2f} 表现优秀，可考虑扩大投放规模")
            next_actions.append("对当前高 ROI 计划逐步加预算测试放量边界")
        else:
            insights.append(f"ROI 均值 {avg_roi:.2f}，处于可控区间")

    if total_spend > Decimal("0") and total_revenue > Decimal("0"):
        gross_profit = total_revenue - total_spend
        insights.append(f"本期总投放花费 ¥{total_spend:.2f}，总营收 ¥{total_revenue:.2f}，毛利润 ¥{gross_profit:.2f}")

    summary = (
        f"{product.name} 在 {period_start} 至 {period_end} 期间的经营复盘：{'；'.join(insights)}。"
    )

    return {
        "period_start": period_start,
        "period_end": period_end,
        "summary": summary,
        "insights": insights,
        "next_actions": next_actions,
    }


def _avg_decimal(records: list[PerformanceRecord], field: str) -> Decimal | None:
    """从记录列表中计算指定 Decimal 字段的平均值，全部为空时返回 None。"""
    values = [getattr(r, field) for r in records if getattr(r, field) is not None]
    if not values:
        return None
    return (sum(values, Decimal("0")) / Decimal(len(values))).quantize(Decimal("0.0001"))


def _build_review_messages(product: Product) -> list[dict[str, str]]:
    """构建复盘 LLM 消息，统一主流程中的格式、默认值和异常边界。"""
    records_summary = []
    for r in sorted(product.performance_records, key=lambda x: x.period_start):
        records_summary.append(
            f"  - {r.period_start} ~ {r.period_end}: "
            f"曝光 {r.impressions}, 点击 {r.clicks}, CTR {r.ctr}, "
            f"转化 {r.conversions}, CVR {r.conversion_rate}, "
            f"花费 ¥{r.spend}, 营收 ¥{r.revenue}, ROI {r.roi}"
        )
    records_text = "\n".join(records_summary) if records_summary else "（无经营数据记录）"

    return [
        {
            "role": "system",
            "content": (
                "你是一个资深电商运营复盘助手，擅长从经营数据中提炼洞察和可执行建议。"
                "你必须只输出合法 json，不要输出 markdown，不要输出解释性前后缀。"
            ),
        },
        {
            "role": "user",
            "content": (
                "请基于以下商品信息和经营数据，生成经营复盘报告。输出 json 必须严格符合示例结构：\n"
                "{\n"
                '  "period_start": "2026-09-01",\n'
                '  "period_end": "2026-09-30",\n'
                '  "summary": "本期整体经营结论，1-3 句话",\n'
                '  "insights": ["关键洞察1", "关键洞察2"],\n'
                '  "next_actions": ["下一步动作1", "下一步动作2"]\n'
                "}\n\n"
                "要求：\n"
                "- 所有内容使用简体中文。\n"
                "- period_start/period_end 从经营数据中推断合理周期。\n"
                "- insights 聚焦数据反映的真实问题或机会。\n"
                "- next_actions 必须可执行，适合运营人员直接落地。\n"
                "- 如果经营数据不足，请在 summary 中明确指出缺少的数据。\n"
                "- 每个数组建议输出 2 到 5 条。\n\n"
                f"商品信息：名称={product.name}，平台={product.platform}，类目={product.category}，"
                f"售价=¥{product.price}，成本=¥{product.cost}"
                f"{'，卖点=' + ', '.join(product.selling_points) if product.selling_points else ''}\n\n"
                f"经营数据记录：\n{records_text}"
            ),
        },
    ]










