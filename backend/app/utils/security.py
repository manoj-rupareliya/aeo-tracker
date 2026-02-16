"""
Security utilities - Authentication, Encryption, Hashing
"""

import base64
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Tuple
from uuid import UUID

import bcrypt
from cryptography.fernet import Fernet
from jose import JWTError, jwt

from app.config import get_settings

settings = get_settings()

# Encryption for API keys
_fernet: Optional[Fernet] = None


def get_fernet() -> Fernet:
    """Get Fernet instance for encryption"""
    global _fernet
    if _fernet is None:
        key = settings.ENCRYPTION_KEY.encode()
        # Ensure key is valid Fernet key (32 url-safe base64 encoded bytes)
        if len(key) != 44:
            # If not valid, derive a key from the provided secret
            derived_key = hashlib.sha256(key).digest()
            key = base64.urlsafe_b64encode(derived_key)
        _fernet = Fernet(key)
    return _fernet


# Password utilities
def hash_password(password: str) -> str:
    """Hash a password for storage"""
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    try:
        password_bytes = plain_password.encode('utf-8')
        hashed_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except Exception:
        return False


# JWT utilities
def create_access_token(
    user_id: UUID,
    expires_delta: Optional[timedelta] = None
) -> str:
    """Create a JWT access token"""
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

    expire = datetime.utcnow() + expires_delta
    to_encode = {
        "sub": str(user_id),
        "type": "access",
        "exp": expire,
        "iat": datetime.utcnow(),
    }
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(user_id: UUID) -> str:
    """Create a JWT refresh token"""
    expires_delta = timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    expire = datetime.utcnow() + expires_delta

    to_encode = {
        "sub": str(user_id),
        "type": "refresh",
        "exp": expire,
        "iat": datetime.utcnow(),
        "jti": secrets.token_hex(16),  # Unique token ID
    }
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT token"""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except JWTError:
        return None


def verify_access_token(token: str) -> Optional[UUID]:
    """Verify an access token and return the user ID"""
    payload = decode_token(token)
    if payload is None:
        return None
    if payload.get("type") != "access":
        return None
    try:
        return UUID(payload.get("sub"))
    except (TypeError, ValueError):
        return None


def verify_refresh_token(token: str) -> Optional[UUID]:
    """Verify a refresh token and return the user ID"""
    payload = decode_token(token)
    if payload is None:
        return None
    if payload.get("type") != "refresh":
        return None
    try:
        return UUID(payload.get("sub"))
    except (TypeError, ValueError):
        return None


# API Key encryption
def encrypt_api_key(api_key: str) -> str:
    """Encrypt an API key for storage"""
    fernet = get_fernet()
    return fernet.encrypt(api_key.encode()).decode()


def decrypt_api_key(encrypted_key: str) -> str:
    """Decrypt an API key from storage"""
    fernet = get_fernet()
    return fernet.decrypt(encrypted_key.encode()).decode()


def mask_api_key(api_key: str) -> str:
    """Mask an API key for display (e.g., sk-...abc123)"""
    if len(api_key) <= 8:
        return "***"
    return f"{api_key[:3]}...{api_key[-6:]}"


# Hashing utilities
def generate_prompt_hash(prompt_text: str, template_version: str) -> str:
    """Generate a deterministic hash for prompt caching"""
    content = f"{prompt_text}|{template_version}"
    return hashlib.sha256(content.encode()).hexdigest()


def generate_cache_key(prompt_hash: str, model: str, temperature: float) -> str:
    """Generate cache key for LLM responses"""
    # Round temperature to avoid floating point issues
    temp_str = f"{temperature:.2f}"
    content = f"{prompt_hash}|{model}|{temp_str}"
    return hashlib.sha256(content.encode()).hexdigest()


def generate_response_hash(response_text: str) -> str:
    """Generate hash of LLM response for change detection"""
    return hashlib.sha256(response_text.encode()).hexdigest()


# Token generation
def generate_verification_token() -> str:
    """Generate a secure token for email verification"""
    return secrets.token_urlsafe(32)


def generate_reset_token() -> str:
    """Generate a secure token for password reset"""
    return secrets.token_urlsafe(32)
