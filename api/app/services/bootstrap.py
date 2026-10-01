from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User, UserRole, UserStatus
from app.services.users import hash_password


def ensure_bootstrap_user(
    db: Session,
    *,
    email: str,
    display_name: str,
    password: str,
    role: UserRole = UserRole.OWNER,
) -> tuple[User, bool]:
    normalized_email = email.strip().lower()
    existing = db.scalars(select(User).where(User.email == normalized_email)).first()
    if existing is not None:
        return existing, False
    user = User(
        email=normalized_email,
        display_name=display_name.strip() or normalized_email,
        role=role,
        status=UserStatus.ACTIVE,
        password_hash=hash_password(password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user, True