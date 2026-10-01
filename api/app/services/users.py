import base64
import hashlib
import hmac
import os

from app.models import User, UserRole

ROLE_PERMISSIONS = {
    UserRole.OWNER: {"can_read": True, "can_edit": True, "can_manage_users": True},
    UserRole.OPERATOR: {"can_read": True, "can_edit": True, "can_manage_users": False},
    UserRole.VIEWER: {"can_read": True, "can_edit": False, "can_manage_users": False},
}


def user_permissions(user: User) -> dict[str, bool]:
    return ROLE_PERMISSIONS[user.role]


def user_to_read(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role.value,
        "status": user.status.value,
        "permissions": user_permissions(user),
        "last_login_at": user.last_login_at,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
    }


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
    return f"pbkdf2_sha256${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, salt_value, digest_value = password_hash.split("$", 2)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    salt = base64.b64decode(salt_value)
    expected = base64.b64decode(digest_value)
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
    return hmac.compare_digest(actual, expected)