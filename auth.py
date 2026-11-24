                                    # for calculating time differences, such as token expiration
from datetime import UTC, datetime, timedelta 
from fastapi.security import OAuth2PasswordBearer # for extracting Bearer token from incoming HTTP request
from pwdlib import PasswordHash # hash and verify password
import jwt
from config import settings

from typing import Annotated
from fastapi import Depends, status, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import models
from database import get_db

password_hash = PasswordHash.recommended()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/users/token")

DbSession = Annotated[AsyncSession, Depends(get_db)]


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(plain_password: str, hash_password: str) -> bool:
    return password_hash.verify(plain_password, hash_password)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create a JWT acces token"""

    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(
            minutes = settings.access_token_expire_minutes
        )

    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(
        to_encode,
        settings.secret_key.get_secret_value(),
        algorithm=settings.algorithm

    )

    return encoded_jwt

def verify_access_token(token: str) -> str | None:
    """Verify a JWT access token and return the subject (user id) if valid."""
    try:
        payload = jwt.decode(
            token,
            settings.secret_key.get_secret_value(),
            algorithms=[settings.algorithm],
            options={"require": ["exp", "sub"]},
        )
    except jwt.InvalidTokenError:
        return None
    else:
        return payload.get("sub")


async def get_current_user(
        token: Annotated[str, Depends(oauth2_scheme)],
        db: DbSession
) -> models.User:

    user_id = verify_access_token(token)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expire token",
            headers={"WWW-Authenticate": "Bearer"}
        )

    try:
        user_int_id = int(user_id)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expire token",
            headers={"WWW-Authenticate": "Bearer"}
        )

    result = await db.execute(
        select(models.User)
        .where(models.User.id == user_int_id)
    )

    user = result.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expire token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return user

CurrentUser = Annotated[models.User, Depends(get_current_user)]




# =======================

# Important distinction:
# - Encryption is reversible with the appropriate key.
# - Hashing is designed to be one-way.


# Flow

# User Registration (hash_password) -> 
# User Login (verify_password) (create_access_token) -> 
# Extract Token {oauth2_scheme}
# JWT verification (verify_accesss_token) for identify current user




# we have to consider idempodency aspect