"""Watcher: pull all sources. ATS feeds now; LinkedIn-email ingest via gmail_confirm.ingest_linkedin."""
from __future__ import annotations
try:
    from . import feeds
except ImportError:
    import feeds


def poll():
    """Returns (roles, health) from every configured ATS feed."""
    return feeds.fetch_all()


if __name__ == "__main__":
    roles, health = poll()
    print(f"{len(roles)} roles from {len(health)} feeds")
