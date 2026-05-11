"""Seed the data/api_keys.yaml store with 5 demo keys.

Run once after `make install`:
    uv run python scripts/seed_demo_keys.py

Idempotent: re-running overwrites the demo keys with fresh state.
"""

from pathlib import Path

from ikusa.auth import ApiKey, save_keys

_DEMO_KEYS = [
    ApiKey(key="ikusa_sk_demo", user_id="demo", tier="free", credits=10),
    ApiKey(key="ikusa_sk_free_demo", user_id="user_free", tier="free", credits=0),
    ApiKey(key="ikusa_sk_team_demo", user_id="user_team", tier="team", credits=0),
    ApiKey(key="ikusa_sk_biz_demo", user_id="user_biz", tier="business", credits=0),
    ApiKey(key="ikusa_sk_ent_demo", user_id="user_ent", tier="enterprise", credits=0),
]


def main() -> None:
    out = Path("data/api_keys.yaml")
    save_keys({k.key: k for k in _DEMO_KEYS}, out)
    print(f"Seeded {len(_DEMO_KEYS)} keys to {out}")
    for k in _DEMO_KEYS:
        print(f"  {k.key:30s} tier={k.tier:10s} credits={k.credits}")


if __name__ == "__main__":
    main()
