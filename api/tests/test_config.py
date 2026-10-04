import pytest

from app.core.config import Settings


def test_production_rejects_default_auth_secret() -> None:
    """验证“productionrejects默认认证密钥”场景，确保重构后仍满足预期业务与安全边界。"""
    with pytest.raises(ValueError, match="Production requires AUTH_SECRET_KEY"):
        Settings(
            DATABASE_URL="sqlite://",
            APP_ENV="production",
            AUTH_SECRET_KEY="dev-auth-secret-change-me",
        )


def test_production_rejects_short_auth_secret() -> None:
    """验证“productionrejects短链认证密钥”场景，确保重构后仍满足预期业务与安全边界。"""
    with pytest.raises(ValueError, match="Production requires AUTH_SECRET_KEY"):
        Settings(
            DATABASE_URL="sqlite://",
            APP_ENV="prod",
            AUTH_SECRET_KEY="short-secret",
        )


def test_production_accepts_long_auth_secret() -> None:
    """验证“productionacceptslong认证密钥”场景，确保重构后仍满足预期业务与安全边界。"""
    settings = Settings(
        DATABASE_URL="sqlite://",
        APP_ENV="production",
        AUTH_SECRET_KEY="prod-secret-with-at-least-thirty-two-chars",
        AGENT_CHECKPOINT_PASSWORD="checkpoint-secret-with-enough-entropy",
    )

    assert settings.app_env == "production"


def test_checkpoint_url_password_is_validated_in_production() -> None:
    """验证“checkpointURLpassword判断validatedinproduction”场景，确保重构后仍满足预期业务与安全边界。"""
    with pytest.raises(ValueError, match="checkpoint database password"):
        Settings(
            DATABASE_URL="sqlite://",
            APP_ENV="production",
            AUTH_SECRET_KEY="prod-secret-with-at-least-thirty-two-chars",
            AGENT_CHECKPOINT_DATABASE_URL="postgresql://agent:agent@localhost/agent_checkpoints",
        )


def test_checkpoint_url_encodes_reserved_password_characters() -> None:
    """验证“checkpointURLencodesreservedpasswordcharacters”场景，确保重构后仍满足预期业务与安全边界。"""
    settings = Settings(
        DATABASE_URL="sqlite://",
        AGENT_CHECKPOINT_PASSWORD="secret@with:/reserved?characters",
    )

    assert "secret%40with%3A%2Freserved%3Fcharacters" in settings.agent_checkpoint_connection_url
