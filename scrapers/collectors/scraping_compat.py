"""Legacy import compatibility for the retired scraping compatibility patch."""


def activate() -> None:
    """Keep the historical module importable without patching runtime classes."""
    return None


__all__ = ["activate"]
