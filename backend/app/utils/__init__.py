"""
Utility modules for llmrefs.com
"""

from .database import (
    get_db,
    get_db_context,
    get_sync_db,
    init_db,
    close_db,
)
from .security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    verify_access_token,
    verify_refresh_token,
    encrypt_api_key,
    decrypt_api_key,
    mask_api_key,
    generate_prompt_hash,
    generate_cache_key,
    generate_response_hash,
)
from .cache import (
    cache,
    llm_cache,
    rate_limit,
    get_redis,
    close_redis,
)

__all__ = [
    # Database
    "get_db",
    "get_db_context",
    "get_sync_db",
    "init_db",
    "close_db",
    # Security
    "hash_password",
    "verify_password",
    "create_access_token",
    "create_refresh_token",
    "verify_access_token",
    "verify_refresh_token",
    "encrypt_api_key",
    "decrypt_api_key",
    "mask_api_key",
    "generate_prompt_hash",
    "generate_cache_key",
    "generate_response_hash",
    # Cache
    "cache",
    "llm_cache",
    "rate_limit",
    "get_redis",
    "close_redis",
]
