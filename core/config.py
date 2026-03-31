import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional


Mode = Literal["sandbox", "production"]


def _repo_root() -> str:
    return os.path.dirname(os.path.dirname(__file__))


def default_config_path() -> str:
    return os.path.join(_repo_root(), "config.json")


@dataclass(frozen=True)
class EbayConfig:
    mode: Mode
    client_id: str
    client_secret: str
    marketplace_id: str = "EBAY_US"
    currency: str = "USD"

    @property
    def oauth_endpoint(self) -> str:
        if self.mode == "sandbox":
            return "https://api.sandbox.ebay.com/identity/v1/oauth2/token"
        return "https://api.ebay.com/identity/v1/oauth2/token"

    @property
    def browse_search_endpoint(self) -> str:
        if self.mode == "sandbox":
            return "https://api.sandbox.ebay.com/buy/browse/v1/item_summary/search"
        return "https://api.ebay.com/buy/browse/v1/item_summary/search"


@dataclass(frozen=True)
class AppConfig:
    poll_interval_minutes: int
    ebay: EbayConfig
    notifications: Dict[str, Any]


def _get(d: Dict[str, Any], path: str, default: Any = None) -> Any:
    cur: Any = d
    for key in path.split("."):
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


def load_config(path: Optional[str] = None) -> AppConfig:
    cfg_path = path or default_config_path()
    with open(cfg_path) as f:
        raw = json.load(f)

    poll_interval_minutes = int(raw.get("poll_interval_minutes", 10))

    # Backwards compatible:
    # - legacy: raw["ebay"]["client_id"], raw["ebay"]["client_secret"]
    # - new: raw["ebay"]["mode"] + raw["ebay"]["sandbox|production"]["client_id|client_secret"]
    ebay_mode: Mode = _get(raw, "ebay.mode", "production")
    if ebay_mode not in ("sandbox", "production"):
        ebay_mode = "production"

    legacy_client_id = _get(raw, "ebay.client_id")
    legacy_client_secret = _get(raw, "ebay.client_secret")
    mode_client_id = _get(raw, f"ebay.{ebay_mode}.client_id")
    mode_client_secret = _get(raw, f"ebay.{ebay_mode}.client_secret")

    client_id = mode_client_id or legacy_client_id or ""
    client_secret = mode_client_secret or legacy_client_secret or ""

    marketplace_id = _get(raw, "ebay.marketplace_id", "EBAY_US")
    currency = _get(raw, "ebay.currency", "USD")

    ebay = EbayConfig(
        mode=ebay_mode,
        client_id=client_id,
        client_secret=client_secret,
        marketplace_id=marketplace_id,
        currency=currency,
    )

    notifications = raw.get("notifications", {})

    return AppConfig(
        poll_interval_minutes=poll_interval_minutes,
        ebay=ebay,
        notifications=notifications,
    )

