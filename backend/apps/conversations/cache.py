from django.core.cache import cache

INBOX_CACHE_TTL = 45  # seconds

def get_inbox_cache_key(user_id: str, filter_type: str = "all") -> str:
    """Generate a consistent cache key for a user's inbox."""
    return f"inbox:{user_id}:{filter_type}"

def get_cached_inbox(user_id: str, filter_type: str = "all"):
    """Get inbox data from cache. Returns None on cache miss."""
    return cache.get(get_inbox_cache_key(user_id, filter_type))

def set_inbox_cache(user_id: str, filter_type: str, data):
    """Store inbox data in cache with TTL."""
    cache.set(get_inbox_cache_key(user_id, filter_type), data, INBOX_CACHE_TTL)

def invalidate_inbox_cache(user_id: str) -> None:
    """
    Invalidate ALL inbox cache variants for a user.
    Called after: new message, read message, star/unstar, new conversation.
    """
    cache.delete_many([
        get_inbox_cache_key(user_id, "all"),
        get_inbox_cache_key(user_id, "unread"),
        get_inbox_cache_key(user_id, "starred"),
    ])
