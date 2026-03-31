#!/usr/bin/env python3
import time
import json
import os
import datetime
from core.db import init_db, get_active_searches, item_seen, mark_item_seen, record_alerts
from core.config import load_config
from core.ebay_api import search_ebay
from core.notifier import send_alerts

CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')

def log(msg):
    print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)

def run_loop():
    init_db()
    config = load_config(CONFIG_PATH)
    poll_seconds = config.poll_interval_minutes * 60

    log("eBay Sniper Worker Started...")

    while True:
        searches = get_active_searches()
        if not searches:
            log("No active searches found. Sleeping...")
        
        for search in searches:
            search_id = search['id']
            keyword = search['keyword']
            log(f"Running search: {keyword}")

            items = search_ebay(
                keyword=keyword,
                min_price=search['min_price'],
                max_price=search['max_price'],
                category_id=search['category_id'],
                buying_option=search['buying_option']
            )

            new_items = []
            for item in items:
                item_id = item['itemId']
                if not item_seen(search_id, item_id):
                    mark_item_seen(item_id, search_id)
                    new_items.append(item)

            if new_items:
                log(f"Found {len(new_items)} new items for '{keyword}'! Sending alerts...")
                record_alerts(search_id, new_items)
                send_alerts(new_items, keyword, config=config)
                
            time.sleep(1) # Tiny sleep to avoid slamming the API instantly if you have many searches

        log(f"Cycle complete. Sleeping for {poll_seconds / 60} minutes.")
        time.sleep(poll_seconds)

if __name__ == "__main__":
    try:
        run_loop()
    except KeyboardInterrupt:
        log("Worker terminated by user.")