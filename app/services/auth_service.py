import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tables import User


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


async def create_user(
    db: AsyncSession, user_id: str, email: str, display_name: str, password: str, role: str = "user"
) -> User:
    if len(password) < 8:
        raise ValueError("비밀번호는 최소 8자 이상이어야 합니다.")

    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise ValueError("이미 등록된 이메일입니다.")

    existing_id = await db.execute(select(User).where(User.user_id == user_id))
    if existing_id.scalar_one_or_none():
        raise ValueError("이미 사용 중인 사용자 ID입니다.")

    user = User(
        user_id=user_id,
        email=email,
        display_name=display_name,
        hashed_password=hash_password(password),
        role=role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate_user(
    db: AsyncSession, login_id: str, password: str
) -> User | None:
    """이메일 또는 사용자 ID로 로그인."""
    result = await db.execute(
        select(User).where(
            (User.email == login_id) | (User.user_id == login_id)
        )
    )
    user = result.scalar_one_or_none()
    if user is None:
        return None
    if not user.is_active:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user
