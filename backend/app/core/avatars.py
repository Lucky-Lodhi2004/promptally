"""Shared avatar defaults for account creation and API responses."""

DEFAULT_AVATAR_URL = "/avatars/default-avatar.svg"


def avatar_url(value: str | None) -> str:
    return (value or "").strip() or DEFAULT_AVATAR_URL
