"""
Authentication Routes
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, UserAPIKey, LLMProvider, SubscriptionTier
from app.schemas.auth import (
    UserCreate, UserLogin, UserResponse, TokenResponse, TokenRefresh
)
from app.utils import (
    get_db, hash_password, verify_password,
    create_access_token, create_refresh_token, verify_refresh_token,
    encrypt_api_key, decrypt_api_key, mask_api_key
)
from pydantic import BaseModel
from typing import List, Optional
from app.api.middleware.auth import get_current_user
from app.config import get_settings

router = APIRouter()
settings = get_settings()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    """Register a new user"""
    import logging
    logging.info(f"Registration attempt for email: {user_data.email}")

    try:
        # Check if email already exists
        result = await db.execute(
            select(User).where(User.email == user_data.email)
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

        # Create user with default subscription tier
        user = User(
            email=user_data.email,
            password_hash=hash_password(user_data.password),
            full_name=user_data.full_name,
            subscription_tier=SubscriptionTier.FREE,
            monthly_token_limit=100000,
            tokens_used_this_month=0,
            is_active=True,
            is_verified=False,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

        return user
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Registration error: {e}")
        import traceback
        logging.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}",
        )


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: UserLogin,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate and get tokens"""
    import logging
    logging.info(f"Login attempt for email: {credentials.email}")

    try:
        # Find user
        result = await db.execute(
            select(User).where(User.email == credentials.email)
        )
        user = result.scalar_one_or_none()

        if not user or not verify_password(credentials.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is disabled",
            )

        # Update last login
        user.last_login_at = datetime.utcnow()
        await db.commit()

        # Generate tokens
        access_token = create_access_token(user.id)
        refresh_token = create_refresh_token(user.id)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Login error: {e}")
        import traceback
        logging.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {str(e)}",
        )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    token_data: TokenRefresh,
    db: AsyncSession = Depends(get_db),
):
    """Refresh access token"""
    user_id = verify_refresh_token(token_data.refresh_token)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    # Verify user still exists and is active
    result = await db.execute(
        select(User).where(User.id == user_id, User.is_active == True)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    # Generate new tokens
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get("/me", response_model=UserResponse)
async def get_me(
    user: User = Depends(get_current_user),
):
    """Get current user info"""
    return user


@router.put("/me", response_model=UserResponse)
async def update_me(
    full_name: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update current user info"""
    user.full_name = full_name
    await db.commit()
    await db.refresh(user)
    return user


# ============================================================================
# API KEY MANAGEMENT
# ============================================================================

class APIKeyCreate(BaseModel):
    provider: str  # openai, anthropic, google, perplexity
    api_key: str


class APIKeyResponse(BaseModel):
    provider: str
    masked_key: str
    is_active: bool

    class Config:
        from_attributes = True


class APIKeysListResponse(BaseModel):
    items: List[APIKeyResponse]


@router.get("/api-keys", response_model=APIKeysListResponse)
async def list_api_keys(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List user's saved API keys (masked)"""
    result = await db.execute(
        select(UserAPIKey).where(UserAPIKey.user_id == user.id)
    )
    keys = result.scalars().all()

    items = []
    for key in keys:
        try:
            decrypted = decrypt_api_key(key.encrypted_key)
            masked = mask_api_key(decrypted)
        except Exception:
            masked = "***"
        items.append(APIKeyResponse(
            provider=key.provider.value,
            masked_key=masked,
            is_active=key.is_active
        ))

    return APIKeysListResponse(items=items)


@router.post("/api-keys", response_model=APIKeyResponse, status_code=status.HTTP_201_CREATED)
async def save_api_key(
    key_data: APIKeyCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Save or update an API key for a provider"""
    # Validate provider
    try:
        provider = LLMProvider(key_data.provider.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid provider. Must be one of: openai, anthropic, google, perplexity"
        )

    # Check if key already exists for this provider
    result = await db.execute(
        select(UserAPIKey).where(
            UserAPIKey.user_id == user.id,
            UserAPIKey.provider == provider
        )
    )
    existing_key = result.scalar_one_or_none()

    # Encrypt the API key
    encrypted = encrypt_api_key(key_data.api_key)

    if existing_key:
        # Update existing key
        existing_key.encrypted_key = encrypted
        existing_key.is_active = True
        await db.commit()
        await db.refresh(existing_key)
        key = existing_key
    else:
        # Create new key
        key = UserAPIKey(
            user_id=user.id,
            provider=provider,
            encrypted_key=encrypted,
            is_active=True
        )
        db.add(key)
        await db.commit()
        await db.refresh(key)

    return APIKeyResponse(
        provider=key.provider.value,
        masked_key=mask_api_key(key_data.api_key),
        is_active=key.is_active
    )


@router.delete("/api-keys/{provider}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_key(
    provider: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete an API key for a provider"""
    try:
        provider_enum = LLMProvider(provider.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid provider"
        )

    result = await db.execute(
        select(UserAPIKey).where(
            UserAPIKey.user_id == user.id,
            UserAPIKey.provider == provider_enum
        )
    )
    key = result.scalar_one_or_none()

    if not key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )

    await db.delete(key)
    await db.commit()
