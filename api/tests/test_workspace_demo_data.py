from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.routes.auth import get_current_user
from app.db.session import get_db
from app.main import app
from app.models import (
    AdRecommendation,
    Base,
    CompetitorMonitor,
    GeneratedAsset,
    GenerationJob,
    GenerationJobEvent,
    InventoryItem,
    InventoryMovement,
    PerformanceRecord,
    Platform,
    PlatformAccount,
    Product,
    ProductDiagnosis,
    ProductSku,
    ReviewReport,
    Store,
    User,
    UserRole,
)


def test_create_demo_workspace_requires_edit_permission() -> None:
    """验证“创建demoWorkspacerequiresedit权限”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    engine = _engine()
    Base.metadata.create_all(engine)

    app.dependency_overrides[get_db] = _override_db(engine)
    app.dependency_overrides[get_current_user] = lambda: _user(UserRole.VIEWER)
    try:
        response = TestClient(app).post(
            "/api/v1/workspace/demo-data",
            headers={"Authorization": "Bearer test"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


def test_create_demo_workspace_creates_store_products_and_inventory_movements() -> None:
    """验证“创建demoWorkspacecreates店铺productsand库存movements”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    engine = _engine()
    Base.metadata.create_all(engine)

    app.dependency_overrides[get_db] = _override_db(engine)
    app.dependency_overrides[get_current_user] = lambda: _user(UserRole.OPERATOR)
    try:
        response = TestClient(app).post(
            "/api/v1/workspace/demo-data",
            headers={"Authorization": "Bearer test"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    payload = response.json()
    assert payload["store_id"] > 0
    assert len(payload["product_ids"]) == 2
    assert len(payload["sku_ids"]) == 3

    with Session(engine) as db:
        assert db.query(Store).count() == 1
        assert db.query(PlatformAccount).count() == 1
        assert db.query(ProductDiagnosis).count() == 1
        assert db.query(CompetitorMonitor).count() == 1
        assert db.query(GenerationJob).count() == 1
        assert db.query(GenerationJobEvent).count() == 2
        assert db.query(GeneratedAsset).count() == 1
        assert db.query(AdRecommendation).count() == 1
        assert db.query(ReviewReport).count() == 1
        assert db.query(InventoryMovement).count() >= 3

        recommendation = db.query(AdRecommendation).one()
        assert recommendation.confirmation_status == "confirmed"
        asset = db.query(GeneratedAsset).one()
        assert asset.status == "通过"
        assert asset.usage_contexts == ["冷启动", "人群测试"]


def test_download_performance_template() -> None:
    """验证“下载经营数据模板”场景，确保重构后仍满足预期业务与安全边界。"""
    response = TestClient(app).get("/api/v1/workspace/templates/performance-records.csv")

    assert response.status_code == 200
    assert "period_start,period_end" in response.text
    assert response.headers["content-type"].startswith("text/csv")


def test_download_workspace_import_templates() -> None:
    """验证“下载Workspace导入templates”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    client = TestClient(app)

    product_response = client.get("/api/v1/workspace/templates/products.csv")
    sku_response = client.get("/api/v1/workspace/templates/sku-inventory.csv")
    mapping_response = client.get("/api/v1/workspace/templates/field-mapping.csv")

    assert product_response.status_code == 200
    assert "store_name,platform,name" in product_response.text
    assert sku_response.status_code == 200
    assert "product_name,sku_code" in sku_response.text
    assert mapping_response.status_code == 200
    assert "source_field,target_field" in mapping_response.text


def test_product_import_preview_reports_row_errors() -> None:
    """验证“商品导入预览reports行errors”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    engine = _engine()
    Base.metadata.create_all(engine)

    app.dependency_overrides[get_db] = _override_db(engine)
    app.dependency_overrides[get_current_user] = lambda: _user(UserRole.OPERATOR)
    try:
        response = TestClient(app).post(
            "/api/v1/workspace/imports/products",
            json={"csv_text": _product_import_csv(), "commit": False},
            headers={"Authorization": "Bearer test"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["commit"] is False
    assert payload["total_rows"] == 2
    assert payload["valid_rows"] == 1
    assert payload["error_count"] == 1
    assert payload["rows"][1]["row_number"] == 3
    assert payload["rows"][1]["errors"]


def test_product_import_commit_partially_creates_valid_rows() -> None:
    """验证“商品导入commitpartiallycreatesvalid行”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    engine = _engine()
    Base.metadata.create_all(engine)

    app.dependency_overrides[get_db] = _override_db(engine)
    app.dependency_overrides[get_current_user] = lambda: _user(UserRole.OPERATOR)
    try:
        response = TestClient(app).post(
            "/api/v1/workspace/imports/products",
            json={"csv_text": _product_import_csv(), "commit": True},
            headers={"Authorization": "Bearer test"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["commit"] is True
    assert payload["created_count"] == 1
    assert payload["error_count"] == 1

    with Session(engine) as db:
        assert db.query(Product).count() == 1
        assert db.query(Store).count() == 1


def test_sku_inventory_import_preview_reports_missing_product() -> None:
    """验证“SKU库存导入预览reportsmissing商品”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    engine = _engine()
    Base.metadata.create_all(engine)
    _seed_product(engine)

    app.dependency_overrides[get_db] = _override_db(engine)
    app.dependency_overrides[get_current_user] = lambda: _user(UserRole.OPERATOR)
    try:
        response = TestClient(app).post(
            "/api/v1/workspace/imports/sku-inventory",
            json={"csv_text": _sku_inventory_import_csv(), "commit": False},
            headers={"Authorization": "Bearer test"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_rows"] == 2
    assert payload["valid_rows"] == 1
    assert payload["error_count"] == 1
    assert payload["rows"][1]["errors"]


def test_sku_inventory_import_commit_partially_creates_sku_and_inventory() -> None:
    """验证“SKU库存导入commitpartiallycreatesSKUand库存”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    engine = _engine()
    Base.metadata.create_all(engine)
    _seed_product(engine)

    app.dependency_overrides[get_db] = _override_db(engine)
    app.dependency_overrides[get_current_user] = lambda: _user(UserRole.OPERATOR)
    try:
        response = TestClient(app).post(
            "/api/v1/workspace/imports/sku-inventory",
            json={"csv_text": _sku_inventory_import_csv(), "commit": True},
            headers={"Authorization": "Bearer test"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["created_count"] == 1
    assert payload["error_count"] == 1

    with Session(engine) as db:
        assert db.query(ProductSku).count() == 1
        assert db.query(InventoryItem).count() == 1
        assert db.query(InventoryMovement).count() == 1


def test_performance_import_preview_reports_missing_product() -> None:
    """验证“经营数据导入预览reportsmissing商品”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    engine = _engine()
    Base.metadata.create_all(engine)
    _seed_product(engine)

    app.dependency_overrides[get_db] = _override_db(engine)
    app.dependency_overrides[get_current_user] = lambda: _user(UserRole.OPERATOR)
    try:
        response = TestClient(app).post(
            "/api/v1/workspace/imports/performance-records",
            json={"csv_text": _performance_import_csv(), "commit": False},
            headers={"Authorization": "Bearer test"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_rows"] == 2
    assert payload["valid_rows"] == 1
    assert payload["error_count"] == 1
    assert payload["rows"][1]["errors"]


def test_performance_import_commit_partially_creates_records() -> None:
    """验证“经营数据导入commitpartiallycreatesrecords”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    engine = _engine()
    Base.metadata.create_all(engine)
    _seed_product(engine)

    app.dependency_overrides[get_db] = _override_db(engine)
    app.dependency_overrides[get_current_user] = lambda: _user(UserRole.OPERATOR)
    try:
        response = TestClient(app).post(
            "/api/v1/workspace/imports/performance-records",
            json={"csv_text": _performance_import_csv(), "commit": True},
            headers={"Authorization": "Bearer test"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["created_count"] == 1
    assert payload["error_count"] == 1

    with Session(engine) as db:
        assert db.query(PerformanceRecord).count() == 1
        record = db.query(PerformanceRecord).first()
        assert str(record.ctr) == "0.0400"


def _override_db(engine):
    """构造或执行测试所需的覆盖db，让测试数据、依赖替身与断言保持集中。"""
    def override_db():
        """构造或执行测试所需的覆盖db，让测试数据、依赖替身与断言保持集中。"""
        with Session(engine) as db:
            yield db

    return override_db


def _user(role: UserRole) -> User:
    """构造或执行测试所需的用户，让测试数据、依赖替身与断言保持集中。"""
    return User(id=1, email=f"{role}@example.com", display_name=str(role), role=role)


def _engine():
    """构造或执行测试所需的engine，让测试数据、依赖替身与断言保持集中。"""
    return create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def _product_import_csv() -> str:
    """构造或执行测试所需的商品导入csv，让测试数据、依赖替身与断言保持集中。"""
    return (
        "store_name,platform,name,category,price,cost,target_audience,selling_points,external_product_id,platform_status\n"
        '抖音导入店,douyin,导入商品,食品,29.90,12.50,白领,"低糖;饱腹",item-1,online\n'
        "抖音导入店,unknown,,食品,abc,12.50,白领,低糖,item-2,online\n"
    )


def _seed_product(engine) -> None:
    """构造或执行测试所需的测试数据商品，让测试数据、依赖替身与断言保持集中。"""
    with Session(engine) as db:
        store = Store(name="抖音导入店", platform=Platform.DOUYIN)
        db.add(Product(store=store, name="导入商品", platform=Platform.DOUYIN))
        db.commit()


def _sku_inventory_import_csv() -> str:
    """构造或执行测试所需的SKU库存导入csv，让测试数据、依赖替身与断言保持集中。"""
    return (
        "product_name,sku_code,sku_name,price,cost,initial_quantity,warning_threshold,location,external_sku_id\n"
        "导入商品,SKU-1,标准装,29.90,12.50,100,20,A-01,sku-1\n"
        "不存在商品,SKU-2,标准装,29.90,12.50,10,5,A-02,sku-2\n"
    )


def _performance_import_csv() -> str:
    """构造或执行测试所需的经营数据导入csv，让测试数据、依赖替身与断言保持集中。"""
    return (
        "product_name,period_start,period_end,impressions,clicks,conversions,spend,revenue,notes\n"
        "导入商品,2026-05-01,2026-05-07,1000,40,5,120.00,600.00,首周数据\n"
        "不存在商品,2026-05-01,2026-05-07,1000,40,5,120.00,600.00,错误数据\n"
    )
