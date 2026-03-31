import requests
import base64
import os
import time
from typing import Optional

from core.config import AppConfig, load_config

# Global token cache
_ACCESS_TOKEN = None
_ACCESS_TOKEN_EXPIRES_AT = 0.0

_SESSION = requests.Session()

def _now() -> float:
    return time.time()

def get_token(cfg: AppConfig) -> str:
    global _ACCESS_TOKEN, _ACCESS_TOKEN_EXPIRES_AT
    if _ACCESS_TOKEN and _now() < (_ACCESS_TOKEN_EXPIRES_AT - 30):
        return _ACCESS_TOKEN

    client_id = cfg.ebay.client_id
    client_secret = cfg.ebay.client_secret
    
    auth_str = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode('utf-8')
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Authorization': f'Basic {auth_str}'
    }
    data = {
        'grant_type': 'client_credentials',
        'scope': 'https://api.ebay.com/oauth/api_scope'
    }

    resp = _SESSION.post(cfg.ebay.oauth_endpoint, headers=headers, data=data, timeout=20)
    resp.raise_for_status()
    payload = resp.json()
    _ACCESS_TOKEN = payload['access_token']
    expires_in = float(payload.get("expires_in", 7200))
    _ACCESS_TOKEN_EXPIRES_AT = _now() + expires_in
    return _ACCESS_TOKEN

def _request_with_retries(method: str, url: str, *, headers: dict, params: dict, timeout: int, max_attempts: int = 4):
    last_exc: Optional[Exception] = None
    for attempt in range(1, max_attempts + 1):
        try:
            resp = _SESSION.request(method, url, headers=headers, params=params, timeout=timeout)
            if resp.status_code in (429, 500, 502, 503, 504):
                delay = min(8.0, 0.5 * (2 ** (attempt - 1)))
                time.sleep(delay)
                continue
            return resp
        except Exception as e:
            last_exc = e
            delay = min(8.0, 0.5 * (2 ** (attempt - 1)))
            time.sleep(delay)
    raise last_exc if last_exc else RuntimeError("Request failed")


def search_ebay(keyword, min_price=None, max_price=None, category_id=None, buying_option=None, config: Optional[AppConfig] = None):
    cfg = config or load_config()
    try:
        token = get_token(cfg)
        headers = {
            'Authorization': f'Bearer {token}',
            'X-EBAY-C-MARKETPLACE-ID': cfg.ebay.marketplace_id,
        }
    except Exception as e:
        print(f"API Error: {e}")
        return []
    
    params = {'q': keyword, 'limit': 20} # Limit to top 20 recent items
    filters = []
    
    if min_price or max_price:
        p_min = min_price if min_price else ''
        p_max = max_price if max_price else ''
        filters.append(f"price:[{p_min}..{p_max}],priceCurrency:{cfg.ebay.currency}")
    
    if buying_option: # Options: FIXED_PRICE or AUCTION
        filters.append(f"buyingOptions:{{{buying_option.upper()}}}")

    if filters:
        params['filter'] = ','.join(filters)

    if category_id:
        params['category_ids'] = category_id

    try:
        resp = _request_with_retries("GET", cfg.ebay.browse_search_endpoint, headers=headers, params=params, timeout=20)
        
        # If token expired, clear it and retry once
        if resp.status_code == 401:
            global _ACCESS_TOKEN, _ACCESS_TOKEN_EXPIRES_AT
            _ACCESS_TOKEN = None
            _ACCESS_TOKEN_EXPIRES_AT = 0.0
            return search_ebay(keyword, min_price, max_price, category_id, buying_option, config=cfg)
            
        resp.raise_for_status()
        return resp.json().get('itemSummaries', [])
    except Exception as e:
        print(f"API Error: {e}")
        return []