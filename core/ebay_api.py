import requests
import base64
import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.json')
with open(CONFIG_PATH) as f:
    config = json.load(f)

OAUTH_ENDPOINT = "https://api.ebay.com/identity/v1/oauth2/token"
SEARCH_ENDPOINT = "https://api.ebay.com/buy/browse/v1/item_summary/search"

# Global token cache
_ACCESS_TOKEN = None

def get_token():
    global _ACCESS_TOKEN
    if _ACCESS_TOKEN:
        return _ACCESS_TOKEN

    client_id = config['ebay']['client_id']
    client_secret = config['ebay']['client_secret']
    
    auth_str = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode('utf-8')
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Authorization': f'Basic {auth_str}'
    }
    data = {
        'grant_type': 'client_credentials',
        'scope': 'https://api.ebay.com/oauth/api_scope'
    }

    resp = requests.post(OAUTH_ENDPOINT, headers=headers, data=data)
    resp.raise_for_status()
    _ACCESS_TOKEN = resp.json()['access_token']
    return _ACCESS_TOKEN

def search_ebay(keyword, min_price=None, max_price=None, category_id=None, buying_option=None):
    token = get_token()
    headers = {'Authorization': f'Bearer {token}'}
    
    params = {'q': keyword, 'limit': 20} # Limit to top 20 recent items
    filters = []
    
    if min_price or max_price:
        p_min = min_price if min_price else ''
        p_max = max_price if max_price else ''
        filters.append(f"price:[{p_min}..{p_max}],priceCurrency:USD")
    
    if buying_option: # Options: FIXED_PRICE or AUCTION
        filters.append(f"buyingOptions:{{{buying_option.upper()}}}")

    if filters:
        params['filter'] = ','.join(filters)

    if category_id:
        params['category_ids'] = category_id

    try:
        resp = requests.get(SEARCH_ENDPOINT, headers=headers, params=params)
        
        # If token expired, clear it and retry once
        if resp.status_code == 401:
            global _ACCESS_TOKEN
            _ACCESS_TOKEN = None
            return search_ebay(keyword, min_price, max_price, category_id, buying_option)
            
        resp.raise_for_status()
        return resp.json().get('itemSummaries', [])
    except Exception as e:
        print(f"API Error: {e}")
        return []