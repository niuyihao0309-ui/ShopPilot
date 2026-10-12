"""电商运营助手 —— 端到端冒烟测试（真实服务 + 真实库）。

用法（先启动 API 服务，再执行本脚本）：
    python scripts/smoke_test.py
    SMOKE_BASE_URL=http://127.0.0.1:8000 python scripts/smoke_test.py

覆盖范围：
    健康/可观测 -> 鉴权与权限边界 -> 工作区 -> 门店 -> 商品/SKU/库存 ->
    竞品/创意方案/推广链接/短链/广告实验/效果记录/复盘 -> 诊断与建议(真实 LLM) ->
    两阶段导入 -> 模型设置 -> Agent 平台 -> 巡检/演示数据。

刻意不真实触发（只做契约校验或跳过）：
    - 图片素材生成（即梦）：只校验路由存在与归属校验，不真实发起生成任务；
    - 视频相关（视频脚本方案、视频素材生成、视频模型连通性）：全部跳过。

脚本只读取/创建带唯一后缀的测试数据，不改动任何已有业务数据。
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable

import httpx


API_DIR = Path(__file__).resolve().parents[1]
BASE_URL = os.getenv("SMOKE_BASE_URL", "http://127.0.0.1:8000")
OWNER_EMAIL = os.getenv("SMOKE_OWNER_EMAIL", "smoke-owner@example.com")
OWNER_PASSWORD = os.getenv("SMOKE_OWNER_PASSWORD", "Smoke-Owner-2026!")


def _now() -> float:
    return time.perf_counter()


class Smoke:
    """按分组执行接口调用，记录每步状态、耗时与结果片段。"""

    def __init__(self) -> None:
        self.client = httpx.Client(base_url=BASE_URL, timeout=60.0)
        self.results: list[dict[str, Any]] = []
        self.ctx: dict[str, Any] = {}
        self.tag = time.strftime("%m%d-%H%M%S")
        self.started = time.time()

    # ------------------------------------------------------------------ 记录
    def _record(
        self,
        group: str,
        name: str,
        method: str,
        path: str,
        status: int | None,
        expect: tuple[int, ...],
        level: str,
        note: str,
        ms: float,
        body: Any = None,
    ) -> None:
        self.results.append(
            {
                "group": group,
                "name": name,
                "method": method,
                "path": path,
                "status": status,
                "expect": list(expect),
                "level": level,
                "note": note,
                "ms": round(ms, 1),
                "body": body,
            }
        )
        icon = {"PASS": "PASS", "FAIL": "FAIL", "WARN": "WARN", "SKIP": "SKIP"}[level]
        status_text = "-" if status is None else str(status)
        print(f"  [{icon}] {method:6} {path:70} -> {status_text:>4}  ({ms:6.0f} ms)  {name}")

    # ------------------------------------------------------------------ 调用
    def call(
        self,
        group: str,
        name: str,
        method: str,
        path: str,
        *,
        expect: tuple[int, ...] = (200,),
        json_body: Any = None,
        expect_fn: Callable[[httpx.Response], bool] | None = None,
        note: str = "",
        allow_fail: bool = False,
        timeout: float | None = None,
        capture: str | None = None,
        capture_key: str | None = None,
    ) -> httpx.Response | None:
        t0 = _now()
        try:
            kwargs: dict[str, Any] = {}
            if json_body is not None:
                kwargs["json"] = json_body
            if timeout is not None:
                kwargs["timeout"] = timeout
            resp = self.client.request(method, path, **kwargs)
        except Exception as exc:  # noqa: BLE001
            ms = (_now() - t0) * 1000
            level = "WARN" if allow_fail else "FAIL"
            self._record(group, name, method, path, None, expect, level, f"请求异常: {exc}", ms)
            return None

        ms = (_now() - t0) * 1000
        ok = resp.status_code in expect
        detail = note
        if ok and expect_fn is not None:
            try:
                if not expect_fn(resp):
                    ok = False
                    detail = (note + " | 断言未通过").strip(" |")
            except Exception as exc:  # noqa: BLE001
                ok = False
                detail = (note + f" | 断言异常: {exc}").strip(" |")

        if ok:
            level = "PASS"
        else:
            level = "WARN" if allow_fail else "FAIL"

        body_snippet: Any = None
        try:
            body_snippet = resp.json()
            if isinstance(body_snippet, list):
                body_snippet = {"_list_len": len(body_snippet), "_first": body_snippet[:1]}
            elif isinstance(body_snippet, dict):
                body_snippet = {k: body_snippet[k] for k in list(body_snippet)[:12]}
        except Exception:  # noqa: BLE001
            body_snippet = resp.text[:300]

        if not ok and not detail:
            detail = f"期望 {expect}，实际 {resp.status_code}"

        self._record(group, name, method, path, resp.status_code, expect, level, detail, ms, body_snippet)

        if capture and capture_key and resp.status_code in expect:
            try:
                data = resp.json()
                self.ctx[capture_key] = data[capture] if isinstance(data, dict) else data
            except Exception:  # noqa: BLE001
                pass
        return resp

    def skip(self, group: str, name: str, method: str, path: str, note: str) -> None:
        self._record(group, name, method, path, None, (), "SKIP", note, 0.0)

    # ================================================================== 分组
    def group_health(self) -> None:
        g = "1. 健康与可观测"
        print(f"\n== {g} ==")
        self.call(g, "健康检查", "GET", "/health", expect=(200,), expect_fn=lambda r: r.json().get("status") == "ok")
        self.call(g, "Swagger UI", "GET", "/docs", expect=(200,))
        self.call(
            g,
            "OpenAPI 契约",
            "GET",
            "/openapi.json",
            expect=(200,),
            expect_fn=lambda r: r.json()["components"]["securitySchemes"]["HTTPBearer"]["scheme"] == "bearer",
        )

    def group_auth(self) -> None:
        g = "2. 鉴权与权限边界"
        print(f"\n== {g} ==")
        self.call(g, "未认证访问受保护接口", "GET", "/api/v1/products", expect=(401,))
        self.call(g, "错误密码登录", "POST", "/api/v1/auth/login", expect=(401,),
                  json_body={"email": OWNER_EMAIL, "password": "definitely-wrong"})
        resp = self.call(
            g, "owner 登录", "POST", "/api/v1/auth/login", expect=(200,),
            json_body={"email": OWNER_EMAIL, "password": OWNER_PASSWORD},
            capture="access_token", capture_key="token",
        )
        if resp is not None and resp.status_code == 200:
            token = resp.json()["access_token"]
            self.client.headers["Authorization"] = f"Bearer {token}"
        self.call(g, "读取当前用户", "GET", "/api/v1/auth/me", expect=(200,),
                  expect_fn=lambda r: r.json().get("email") == OWNER_EMAIL)

    def group_workspace(self) -> None:
        g = "3. 工作区"
        print(f"\n== {g} ==")

        def grab(r: httpx.Response) -> bool:
            data = r.json()
            if not data:
                return False
            self.ctx["workspace_id"] = data[0]["workspace"]["id"]
            return True

        self.call(g, "列出可见工作区", "GET", "/api/v1/workspaces", expect=(200,), expect_fn=grab)

    def group_stores(self) -> None:
        g = "4. 门店"
        print(f"\n== {g} ==")
        resp = self.call(
            g, "创建门店", "POST", "/api/v1/stores", expect=(201,),
            json_body={"name": f"冒烟门店-{self.tag}", "platform": "douyin", "owner_name": "冒烟测试"},
            capture="id", capture_key="store_id",
        )
        self.call(g, "门店列表", "GET", "/api/v1/stores", expect=(200,),
                  expect_fn=lambda r: any(s["id"] == self.ctx.get("store_id") for s in r.json()))
        sid = self.ctx.get("store_id")
        self.call(g, "门店详情", "GET", f"/api/v1/stores/{sid}", expect=(200,), expect_fn=lambda r: r.json()["id"] == sid)
        self.call(g, "更新门店", "PATCH", f"/api/v1/stores/{sid}", expect=(200,),
                  json_body={"note": f"冒烟更新 {self.tag}"},
                  expect_fn=lambda r: r.json().get("note") == f"冒烟更新 {self.tag}")
        self.call(g, "门店库存汇总", "GET", f"/api/v1/stores/{sid}/inventory-summary", expect=(200,))
        self.call(g, "门店库存流水", "GET", f"/api/v1/stores/{sid}/inventory-movements", expect=(200,))

    def group_platform_accounts(self) -> None:
        g = "4b. 平台账号与授权"
        print(f"\n== {g} ==")
        sid = self.ctx.get("store_id")
        self.call(g, "创建平台账号", "POST", f"/api/v1/stores/{sid}/platform-accounts", expect=(201,),
                  json_body={"platform": "douyin", "account_name": f"冒烟官方账号-{self.tag}"},
                  capture="id", capture_key="platform_account_id")
        aid = self.ctx.get("platform_account_id")
        if aid is None:
            return
        self.call(g, "发起平台授权", "POST",
                  f"/api/v1/stores/{sid}/platform-accounts/{aid}/authorization/start", expect=(200,),
                  json_body={"auth_type": "oauth2", "redirect_uri": "https://example.com/callback",
                             "scopes": ["products:read"], "note": "冒烟授权预留"},
                  capture="state", capture_key="auth_state")
        state = self.ctx.get("auth_state")
        self.call(g, "授权回调-state 不匹配被拒", "POST",
                  f"/api/v1/stores/{sid}/platform-accounts/{aid}/authorization/callback-placeholder",
                  expect=(400,), json_body={"state": "wrong-state", "status": "authorized"})
        if state:
            self.call(g, "授权回调-成功", "POST",
                      f"/api/v1/stores/{sid}/platform-accounts/{aid}/authorization/callback-placeholder",
                      expect=(200,), json_body={"state": state, "status": "authorized",
                                                "external_account_id": f"ext-{self.tag}"})

    def group_products_inventory(self) -> None:
        g = "5. 商品 / SKU / 库存"
        print(f"\n== {g} ==")
        sid = self.ctx.get("store_id")
        resp = self.call(
            g, "创建商品", "POST", "/api/v1/products", expect=(201,),
            json_body={
                "store_id": sid,
                "name": f"冒烟低糖燕麦饼干-{self.tag}",
                "platform": "douyin",
                "category": "休闲食品",
                "price": 29.9,
                "cost": 12.5,
                "target_audience": "办公室白领",
                "selling_points": ["独立包装", "便于携带", "低糖"],
            },
            capture="id", capture_key="product_id",
        )
        pid = self.ctx.get("product_id")
        self.call(g, "商品列表", "GET", "/api/v1/products", expect=(200,),
                  expect_fn=lambda r: any(p["id"] == pid for p in r.json()))
        self.call(g, "商品详情", "GET", f"/api/v1/products/{pid}", expect=(200,),
                  expect_fn=lambda r: {"skus", "competitors", "creative_plans"} <= set(r.json()))
        self.call(g, "更新商品", "PATCH", f"/api/v1/products/{pid}", expect=(200,),
                  json_body={"price": 27.9}, expect_fn=lambda r: float(r.json()["price"]) == 27.9)

        resp = self.call(
            g, "创建 SKU（带初始库存）", "POST", f"/api/v1/products/{pid}/skus", expect=(201,),
            json_body={"sku_code": f"OAT-{self.tag}", "name": "12 包装", "initial_quantity": 100, "warning_threshold": 20},
            capture="id", capture_key="sku_id",
        )
        sku_id = self.ctx.get("sku_id")
        self.call(g, "更新 SKU", "PATCH", f"/api/v1/products/{pid}/skus/{sku_id}", expect=(200,),
                  json_body={"warning_threshold": 25},
                  expect_fn=lambda r: r.json()["inventory_item"]["warning_threshold"] == 25)

        mv = f"/api/v1/products/{pid}/skus/{sku_id}/inventory-movements"
        self.call(g, "库存出库流水", "POST", mv, expect=(201,),
                  json_body={"movement_type": "outbound", "quantity_delta": -10, "reason": "冒烟出库"},
                  expect_fn=lambda r: r.json().get("after_quantity") == 90)
        self.call(g, "库存超量出库被拒(边界)", "POST", mv, expect=(400,),
                  json_body={"movement_type": "outbound", "quantity_delta": -100000})
        self.call(g, "商品详情回读库存", "GET", f"/api/v1/products/{pid}", expect=(200,),
                  expect_fn=lambda r: r.json()["skus"][0]["inventory_item"]["quantity"] == 90)
        self.call(g, "平台商品映射", "POST", f"/api/v1/products/{pid}/platform-mappings", expect=(201,),
                  json_body={"store_id": sid, "platform": "douyin", "external_product_id": f"EXT-{self.tag}"})

    def group_marketing(self) -> None:
        g = "6. 竞品 / 创意 / 推广 / 投放 / 复盘"
        print(f"\n== {g} ==")
        pid = self.ctx.get("product_id")
        base = f"/api/v1/products/{pid}"

        resp = self.call(g, "创建竞品", "POST", f"{base}/competitors", expect=(201,),
                         json_body={"name": f"同类早餐饼干-{self.tag}", "platform": "douyin", "price": 25.9,
                                    "url": "https://example.com/competitor-oat",
                                    "selling_points": ["大包装"], "review_keywords": ["偏甜"]},
                         capture="id", capture_key="competitor_id")
        cid = self.ctx.get("competitor_id")
        self.call(g, "竞品URL直接导入(网络)", "POST", f"{base}/competitors/import-url", expect=(201,),
                  json_body={"url": "https://example.com/imported-comp", "platform": "douyin"},
                  allow_fail=True)
        self.call(g, "竞品URL导入任务(异步)", "POST", f"{base}/competitors/import-url-tasks", expect=(201,),
                  json_body={"url": "https://example.com/task-comp", "platform": "douyin"},
                  capture="id", capture_key="parse_task_id", allow_fail=True)
        ptid = self.ctx.get("parse_task_id")
        if ptid is not None:
            self.call(g, "立即执行导入任务(网络)", "POST", f"{base}/link-parse-tasks/{ptid}/run",
                      expect=(200, 201), allow_fail=True)
        resp = self.call(g, "创建竞品监控", "POST", f"{base}/competitors/{cid}/monitor", expect=(201,),
                         json_body={"interval_days": 1, "note": "冒烟监控"},
                         capture="id", capture_key="monitor_id")
        monitor_id = self.ctx.get("monitor_id")
        if monitor_id is not None:
            self.call(g, "立即执行竞品监控(网络)", "POST", f"{base}/competitor-monitors/{monitor_id}/run",
                      expect=(201,), allow_fail=True)

        self.call(g, "创建创意方案(主图)", "POST", f"{base}/creative-plans", expect=(201,),
                  json_body={"type": "main_image", "title": f"冒烟主图方案-{self.tag}",
                             "content": {"headline": "早餐随身带", "description": "突出独立包装"}, "status": "draft"},
                  capture="id", capture_key="creative_plan_id")
        cpid = self.ctx.get("creative_plan_id")
        self.call(g, "更新创意方案", "PATCH", f"{base}/creative-plans/{cpid}", expect=(200,),
                  json_body={"status": "selected"},
                  expect_fn=lambda r: r.json().get("status") == "selected")
        asset_url = f"https://example.com/asset-{self.tag}.png"
        self.call(g, "写入方案素材清单", "PATCH", f"{base}/creative-plans/{cpid}", expect=(200,),
                  json_body={"content": {"headline": "早餐随身带", "description": "突出独立包装",
                                         "generated_images": [{"url": asset_url, "asset_version": 1}]}})
        self.call(g, "素材同步(由方案派生)", "POST", f"{base}/assets/sync", expect=(200,))
        self.call(g, "更新方案素材(真实)", "PATCH", f"{base}/creative-plans/{cpid}/assets", expect=(200,),
                  json_body={"url": asset_url, "asset_type": "image", "rating": 5})

        resp = self.call(g, "创建推广链接", "POST", f"{base}/promotion-links", expect=(201,),
                         json_body={"label": f"冒烟推广入口-{self.tag}", "url": "https://example.com/oat",
                                    "scenario": "冒烟演示"},
                         capture="short_code", capture_key="short_code")
        code = self.ctx.get("short_code")
        self.call(g, "自动生成推广链接", "POST", f"{base}/promotion-links/generate", expect=(201,))
        self.call(g, "短链跳转(307)", "GET", f"/api/v1/links/r/{code}", expect=(307,),
                  expect_fn=lambda r: "location" in {k.lower() for k in r.headers.keys()})

        resp = self.call(g, "创建广告实验", "POST", f"{base}/ad-experiments", expect=(201,),
                         json_body={"name": f"冒烟早餐人群实验-{self.tag}", "objective": "观察点击和转化",
                                    "daily_budget": 50},
                         capture="id", capture_key="experiment_id")
        eid = self.ctx.get("experiment_id")
        self.call(g, "更新广告实验(状态/预算)", "PATCH", f"{base}/ad-experiments/{eid}", expect=(200,),
                  json_body={"status": "active", "note": "冒烟启用"},
                  expect_fn=lambda r: r.json().get("status") == "active")
        self.call(g, "手工录入效果记录", "POST", f"{base}/performance-records", expect=(201,),
                  json_body={"ad_experiment_id": eid, "period_start": "2026-09-01", "period_end": "2026-09-07",
                             "impressions": 1000, "clicks": 100, "conversions": 10, "spend": 100, "revenue": 300},
                  expect_fn=lambda r: abs(float(r.json()["ctr"]) - 0.1) < 1e-6 and abs(float(r.json()["roi"]) - 3) < 1e-6)
        self.call(g, "批量录入效果记录", "POST", f"{base}/performance-records/bulk", expect=(201,),
                  json_body={"records": [
                      {"ad_experiment_id": eid, "period_start": "2026-09-08", "period_end": "2026-09-14",
                       "impressions": 2000, "clicks": 180, "conversions": 18, "spend": 200, "revenue": 500},
                  ]}, allow_fail=True)
        self.call(g, "广告实验仪表盘", "GET", f"{base}/ad-experiments/dashboard", expect=(200,),
                  allow_fail=True)
        self.call(g, "创建复盘报告", "POST", f"{base}/review-reports", expect=(201,),
                  json_body={"period_start": "2026-09-01", "period_end": "2026-09-07",
                             "summary": "冒烟复盘：继续观察", "insights": ["已有点击和转化"],
                             "next_actions": ["下周比较不同标题"]},
                  capture="id", capture_key="review_report_id")
        rrid = self.ctx.get("review_report_id")
        self.call(g, "更新复盘报告", "PATCH", f"{base}/review-reports/{rrid}", expect=(200,),
                  json_body={"summary": "冒烟复盘：已更新"})
        self.call(g, "商品详情回读营销集合", "GET", base, expect=(200,),
                  expect_fn=lambda r: all(
                      len(r.json()[k]) >= 1 for k in
                      ["competitors", "creative_plans", "promotion_links", "ad_experiments",
                       "performance_records", "review_reports"]
                  ))

    def group_llm(self) -> None:
        g = "7. LLM 生成（真实调用，失败自动回退规则）"
        print(f"\n== {g} ==")
        pid = self.ctx.get("product_id")
        base = f"/api/v1/products/{pid}"

        self.call(g, "商品诊断生成(LLM)", "POST", f"{base}/diagnoses/generate", expect=(201,),
                  timeout=120, capture="id", capture_key="diagnosis_id")
        did = self.ctx.get("diagnosis_id")
        if did is not None:
            self.call(g, "更新诊断", "PATCH", f"{base}/diagnoses/{did}", expect=(200,),
                      json_body={"recommendations": ["冒烟补充建议"]}, allow_fail=True)
        self.call(g, "主图方案生成(LLM)", "POST", f"{base}/creative-plans/main-images/generate", expect=(201,),
                  timeout=120)
        self.call(g, "投放建议生成(LLM)", "POST", f"{base}/ad-recommendations/generate", expect=(201,),
                  timeout=120, allow_fail=True, capture="id", capture_key="recommendation_id")
        rid = self.ctx.get("recommendation_id")
        if rid is not None:
            self.call(g, "投放建议人工确认", "PATCH",
                      f"{base}/ad-recommendations/{rid}/confirmation", expect=(200,),
                      json_body={"confirmation_status": "confirmed", "confirmation_note": "冒烟确认"})
        self.call(g, "投放实验方案生成", "POST", f"{base}/ad-experiments/generate", expect=(201,),
                  timeout=120, allow_fail=True)
        self.call(g, "复盘报告生成(LLM)", "POST", f"{base}/review-reports/generate", expect=(201,),
                  timeout=120, allow_fail=True)
        sid = self.ctx.get("store_id")
        self.call(g, "门店库存建议(LLM)", "POST", f"/api/v1/stores/{sid}/inventory-advice", expect=(200,),
                  timeout=120, allow_fail=True)

    def group_import(self) -> None:
        g = "8. 两阶段导入 / 模板"
        print(f"\n== {g} ==")
        for tmpl in ["products", "sku-inventory", "performance-records", "field-mapping"]:
            self.call(g, f"下载模板 {tmpl}.csv", "GET", f"/api/v1/workspace/templates/{tmpl}.csv", expect=(200,))

        before = self.client.get("/api/v1/products")
        before_n = len(before.json()) if before.status_code == 200 else -1
        csv_text = f"store_name,platform,name,price\n冒烟导入店-{self.tag},douyin,冒烟导入商品-{self.tag},19.90"
        self.call(g, "商品导入-预览(不落库)", "POST", "/api/v1/workspace/imports/products", expect=(200,),
                  json_body={"csv_text": csv_text, "commit": False},
                  expect_fn=lambda r: r.json().get("error_count") == 0)
        after_preview = self.client.get("/api/v1/products")
        if before_n >= 0 and after_preview.status_code == 200:
            self._record(g, "预览未落库校验", "GET", "/api/v1/products", 200, (200,),
                         "PASS" if len(after_preview.json()) == before_n else "FAIL",
                         f"预览前后商品数 {before_n} -> {len(after_preview.json())}", 0.0)
        self.call(g, "商品导入-提交", "POST", "/api/v1/workspace/imports/products", expect=(200,),
                  json_body={"csv_text": csv_text, "commit": True},
                  expect_fn=lambda r: r.json().get("created_count", 0) >= 1)
        imported_name = f"冒烟导入商品-{self.tag}"
        sku_csv = (
            "product_name,sku_code,sku_name,price,cost,initial_quantity,warning_threshold,location,external_sku_id\n"
            f"{imported_name},IMP-{self.tag},导入规格,19.90,8.00,5,2,C-01,ext-{self.tag}"
        )
        self.call(g, "SKU/库存导入-预览", "POST", "/api/v1/workspace/imports/sku-inventory", expect=(200,),
                  json_body={"csv_text": sku_csv, "commit": False},
                  expect_fn=lambda r: r.json().get("error_count") == 0)
        self.call(g, "SKU/库存导入-提交", "POST", "/api/v1/workspace/imports/sku-inventory", expect=(200,),
                  json_body={"csv_text": sku_csv, "commit": True},
                  expect_fn=lambda r: r.json().get("created_count", 0) >= 1)

        perf_csv = (
            "product_name,external_product_id,period_start,period_end,impressions,clicks,conversions,spend,revenue,notes\n"
            f"{imported_name},,2026-09-01,2026-09-07,1000,100,10,100.00,300.00,冒烟导入"
        )
        self.call(g, "经营数据导入-预览", "POST", "/api/v1/workspace/imports/performance-records", expect=(200,),
                  json_body={"csv_text": perf_csv, "commit": False},
                  expect_fn=lambda r: r.json().get("error_count") == 0)
        self.call(g, "经营数据导入-提交", "POST", "/api/v1/workspace/imports/performance-records", expect=(200,),
                  json_body={"csv_text": perf_csv, "commit": True},
                  expect_fn=lambda r: r.json().get("created_count", 0) >= 1)

    def group_model_settings(self) -> None:
        g = "9. 模型设置"
        print(f"\n== {g} ==")
        self.call(g, "读取模型设置(脱敏)", "GET", "/api/v1/model-settings", expect=(200,),
                  expect_fn=lambda r: {"text", "image", "video"} <= set(r.json()))
        self.call(g, "空 PATCH(无变更)", "PATCH", "/api/v1/model-settings", expect=(200,), json_body={})
        self.call(g, "文本模型连通性(真实 LLM)", "POST", "/api/v1/model-settings/test", expect=(200,),
                  json_body={"target": "text"}, timeout=90, allow_fail=True)
        self.skip(g, "图片模型连通性", "POST", "/api/v1/model-settings/test", "会真实创建供应商任务，按约定跳过")
        self.skip(g, "视频模型连通性", "POST", "/api/v1/model-settings/test", "视频相关，按约定跳过")

    def group_agent(self) -> None:
        g = "10. Agent 平台"
        print(f"\n== {g} ==")
        wid = self.ctx.get("workspace_id")
        base = f"/api/v1/workspaces/{wid}"
        self.call(g, "Agent 目录", "GET", f"{base}/agent/catalog", expect=(200,),
                  expect_fn=lambda r: "agents" in r.json() and "workflows" in r.json())

        resp = self.call(g, "创建会话", "POST", f"{base}/agent/conversations", expect=(201,),
                         json_body={"title": f"冒烟会话-{self.tag}", "context_scope": {}},
                         capture="id", capture_key="conversation_id")
        cvid = self.ctx.get("conversation_id")
        self.call(g, "会话列表", "GET", f"{base}/agent/conversations", expect=(200,))
        if cvid is not None:
            self.call(g, "追加会话消息", "POST", f"{base}/agent/conversations/{cvid}/messages", expect=(201,),
                      json_body={"content": "冒烟测试：帮我看下这个商品的投放方向"})

        self.call(g, "任务列表", "GET", f"{base}/agent/tasks", expect=(200,))
        resp = self.call(g, "创建 Agent 任务", "POST", f"{base}/agent/tasks", expect=(202,),
                         json_body={"intent": "冒烟测试：生成一版商品运营建议", "title": f"冒烟任务-{self.tag}",
                                    "context_scope": {"product_id": self.ctx.get("product_id")}},
                         capture="id", capture_key="task_id", timeout=180, allow_fail=True)
        tid = self.ctx.get("task_id")
        if tid is not None:
            self.call(g, "任务详情", "GET", f"{base}/agent/tasks/{tid}", expect=(200,))
            self.call(g, "任务运行记录", "GET", f"{base}/agent/tasks/{tid}/runs", expect=(200,))
            self.call(g, "取消任务", "POST", f"{base}/agent/tasks/{tid}/cancel", expect=(200, 409),
                      allow_fail=True)
        else:
            self.call(g, "任务详情(不存在)", "GET", f"{base}/agent/tasks/999999999", expect=(404,))

        self.call(g, "审批列表", "GET", f"{base}/agent/approvals", expect=(200,))
        self.call(g, "记忆列表", "GET", f"{base}/agent/memories", expect=(200,))
        resp = self.call(g, "创建记忆", "POST", f"{base}/agent/memories", expect=(201,),
                         json_body={"scope_type": "workspace", "memory_key": f"smoke_{self.tag}",
                                    "content": {"note": "冒烟写入的记忆"},
                                    "source_type": "user_confirmed"},
                         capture="id", capture_key="memory_id")
        mid = self.ctx.get("memory_id")
        if mid is not None:
            self.call(g, "撤销记忆", "POST", f"{base}/agent/memories/{mid}/revoke", expect=(200,),
                      allow_fail=True)
        self.call(g, "审批决策(不存在)", "POST", f"{base}/agent/approvals/999999999/decision", expect=(404,),
                  json_body={"decision": "approve"}, allow_fail=True)

    def group_agent_runs(self) -> None:
        g = "10b. Agent Runs（商品级）"
        print(f"\n== {g} ==")
        pid = self.ctx.get("product_id")
        self.call(g, "商品 Agent 执行列表", "GET", f"/api/v1/products/{pid}/agent-runs", expect=(200,))
        self.call(g, "创建 Agent 执行", "POST", f"/api/v1/products/{pid}/agent-runs", expect=(202,),
                  capture="id", capture_key="run_id", timeout=180, allow_fail=True)
        rid = self.ctx.get("run_id")
        if rid is not None:
            self.call(g, "Agent 执行详情", "GET", f"/api/v1/agent-runs/{rid}", expect=(200,))
            self.call(g, "Agent 执行人工审核", "POST", f"/api/v1/agent-runs/{rid}/review",
                      expect=(202, 409, 503), json_body={"decision": "approve", "note": "冒烟审核"},
                      allow_fail=True)
        else:
            self.call(g, "Agent 执行详情(不存在)", "GET", "/api/v1/agent-runs/999999999", expect=(404,))
        self.call(g, "Agent 执行审核(不存在-契约)", "POST", "/api/v1/agent-runs/999999999/review",
                  expect=(404,), json_body={"decision": "approve"}, allow_fail=True)

    def group_maintenance(self) -> None:
        g = "11. 巡检 / 演示数据"
        print(f"\n== {g} ==")
        self.call(g, "超时生成任务巡检", "POST", "/api/v1/workspace/generation-jobs/sweep-timeouts", expect=(200,),
                  allow_fail=True)
        self.call(g, "到期竞品监控巡检", "POST", "/api/v1/workspace/competitor-monitors/run-due", expect=(200,),
                  allow_fail=True)
        self.call(g, "创建演示数据", "POST", "/api/v1/workspace/demo-data", expect=(200, 201),
                  allow_fail=True)

    def group_users(self) -> None:
        g = "12. 用户管理"
        print(f"\n== {g} ==")
        email = f"smoke-viewer-{self.tag}@example.com"
        self.call(g, "用户列表", "GET", "/api/v1/users", expect=(200,))
        resp = self.call(g, "创建 viewer 用户", "POST", "/api/v1/users", expect=(201,),
                         json_body={"email": email, "display_name": "冒烟只读用户", "role": "viewer",
                                    "password": "Smoke-Viewer-2026!"},
                         capture="id", capture_key="viewer_id")
        vid = self.ctx.get("viewer_id")
        if vid is not None:
            self.call(g, "更新用户", "PATCH", f"/api/v1/users/{vid}", expect=(200,),
                      json_body={"display_name": "冒烟只读用户(已改名)"})
        # 用 viewer 登录验证只读权限边界
        r = self.client.post("/api/v1/auth/login", json={"email": email, "password": "Smoke-Viewer-2026!"})
        if r.status_code == 200:
            viewer_headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
            self._record(g, "viewer 登录", "POST", "/api/v1/auth/login", 200, (200,), "PASS", "", 0.0)
            rv = self.client.get("/api/v1/products", headers=viewer_headers)
            self._record(g, "viewer 可读商品", "GET", "/api/v1/products", rv.status_code, (200,),
                         "PASS" if rv.status_code == 200 else "FAIL", "", 0.0)
            rw = self.client.post("/api/v1/products", headers=viewer_headers,
                                  json={"name": "viewer不应能建", "platform": "douyin"})
            self._record(g, "viewer 写操作被拒(403)", "POST", "/api/v1/products", rw.status_code, (403,),
                         "PASS" if rw.status_code == 403 else "FAIL", "", 0.0)
        else:
            self._record(g, "viewer 登录", "POST", "/api/v1/auth/login", r.status_code, (200,), "FAIL",
                         r.text[:200], 0.0)

    def group_image_contract(self) -> None:
        g = "13. 图片生成（仅契约校验，不真实触发）"
        print(f"\n== {g} ==")
        pid = self.ctx.get("product_id")
        base = f"/api/v1/products/{pid}"
        self.call(g, "图片生成-路由存在且归属校验", "POST",
                  f"{base}/creative-plans/999999999/images/generate", expect=(404,),
                  expect_fn=lambda r: "not found" in json.dumps(r.json(), ensure_ascii=False).lower())
        self.call(g, "重试任务-不存在(契约)", "POST", f"{base}/generation-jobs/999999999/retry", expect=(404,),
                  expect_fn=lambda r: "not found" in json.dumps(r.json(), ensure_ascii=False).lower())
        self.call(g, "取消任务-不存在(契约)", "POST", f"{base}/generation-jobs/999999999/cancel", expect=(404,))
        self.call(g, "竞品URL导入任务-不存在(契约)", "POST", f"{base}/link-parse-tasks/999999999/run", expect=(404,))

    def group_video_skip(self) -> None:
        g = "14. 视频相关（按约定跳过）"
        print(f"\n== {g} ==")
        pid = self.ctx.get("product_id")
        base = f"/api/v1/products/{pid}"
        self.skip(g, "视频脚本方案生成", "POST", f"{base}/creative-plans/video-scripts/generate", "视频相关，跳过")
        self.skip(g, "视频素材生成", "POST", f"{base}/creative-plans/1/videos/generate", "视频相关，跳过")

    # ================================================================== 主流程
    def run(self) -> None:
        print(f"冒烟目标: {BASE_URL}")
        print(f"测试账号: {OWNER_EMAIL}")
        print(f"运行标识: {self.tag}")
        try:
            self.group_health()
            self.group_auth()
            self.group_workspace()
            self.group_stores()
            self.group_platform_accounts()
            self.group_products_inventory()
            self.group_marketing()
            self.group_llm()
            self.group_import()
            self.group_model_settings()
            self.group_agent()
            self.group_agent_runs()
            self.group_maintenance()
            self.group_users()
            self.group_image_contract()
            self.group_video_skip()
        finally:
            self.client.close()

    # ================================================================== 汇总
    def summary(self) -> dict[str, Any]:
        counts = {"PASS": 0, "FAIL": 0, "WARN": 0, "SKIP": 0}
        for r in self.results:
            counts[r["level"]] += 1
        groups: dict[str, dict[str, int]] = {}
        for r in self.results:
            gg = groups.setdefault(r["group"], {"PASS": 0, "FAIL": 0, "WARN": 0, "SKIP": 0})
            gg[r["level"]] += 1
        return {
            "base_url": BASE_URL,
            "tag": self.tag,
            "started_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.started)),
            "duration_seconds": round(time.time() - self.started, 1),
            "counts": counts,
            "groups": groups,
            "results": self.results,
        }


def write_reports(summary_data: dict[str, Any]) -> tuple[Path, Path]:
    tag = summary_data["tag"]
    json_path = API_DIR / f"smoke_report_{tag}.json"
    md_path = API_DIR / f"smoke_report_{tag}.md"
    json_path.write_text(json.dumps(summary_data, ensure_ascii=False, indent=2), encoding="utf-8")

    c = summary_data["counts"]
    lines: list[str] = []
    lines.append(f"# 端到端冒烟测试报告（{summary_data['started_at']}）\n")
    total = sum(c.values())
    lines.append(f"- 目标服务：`{summary_data['base_url']}`")
    lines.append(f"- 运行标识：`{tag}`")
    lines.append(f"- 总耗时：{summary_data['duration_seconds']} 秒")
    lines.append(f"- 用例总数：{total}")
    lines.append(f"- 结果：**PASS {c['PASS']}** / FAIL {c['FAIL']} / WARN {c['WARN']} / SKIP {c['SKIP']}\n")

    lines.append("## 分组概览\n")
    lines.append("| 分组 | PASS | FAIL | WARN | SKIP |")
    lines.append("| --- | --- | --- | --- | --- |")
    for name, g in summary_data["groups"].items():
        lines.append(f"| {name} | {g['PASS']} | {g['FAIL']} | {g['WARN']} | {g['SKIP']} |")
    lines.append("")

    lines.append("## 明细\n")
    current = None
    for r in summary_data["results"]:
        if r["group"] != current:
            current = r["group"]
            lines.append(f"\n### {current}\n")
            lines.append("| 级别 | 用例 | 请求 | 状态 | 期望 | 耗时(ms) | 备注 |")
            lines.append("| --- | --- | --- | --- | --- | --- | --- |")
        status = "-" if r["status"] is None else r["status"]
        expect = ",".join(str(x) for x in r["expect"]) or "-"
        note = (r["note"] or "").replace("|", "/")
        lines.append(f"| {r['level']} | {r['name']} | {r['method']} {r['path']} | {status} | {expect} | {r['ms']} | {note} |")

    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass
    smoke = Smoke()
    smoke.run()
    data = smoke.summary()
    json_path, md_path = write_reports(data)
    c = data["counts"]
    print("\n" + "=" * 72)
    print(f"总计 {sum(c.values())} 项：PASS={c['PASS']}  FAIL={c['FAIL']}  WARN={c['WARN']}  SKIP={c['SKIP']}")
    print(f"耗时 {data['duration_seconds']} 秒")
    print(f"JSON 报告: {json_path}")
    print(f"Markdown 报告: {md_path}")
    print("=" * 72)
    return 1 if c["FAIL"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
