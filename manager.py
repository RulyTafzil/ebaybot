#!/usr/bin/env python3
import argparse
from core.db import init_db, add_search, get_active_searches, delete_search, get_total_seen_count
from tabulate import tabulate
from core.config import load_config, default_config_path

def setup():
    init_db()

def main():
    setup()
    parser = argparse.ArgumentParser(description="eBay Sniper CLI Manager")
    subparsers = parser.add_subparsers(dest="command")

    # ADD Command
    add_parser = subparsers.add_parser("add", help="Add a new search")
    add_parser.add_argument("--keyword", required=True, help="Search keyword")
    add_parser.add_argument("--min-price", type=float, help="Minimum price")
    add_parser.add_argument("--max-price", type=float, help="Maximum price")
    add_parser.add_argument("--category", help="eBay Category ID")
    add_parser.add_argument("--type", choices=["AUCTION", "FIXED_PRICE"], help="Buying option")

    # LIST Command
    subparsers.add_parser("list", help="List active searches")

    # DELETE Command
    del_parser = subparsers.add_parser("delete", help="Delete a search")
    del_parser.add_argument("id", type=int, help="ID of the search to delete")

    # STATUS / API MONITOR Command
    subparsers.add_parser("status", help="Show system status and API call limits")

    args = parser.parse_args()

    if args.command == "add":
        add_search(args.keyword, args.min_price, args.max_price, args.category, args.type)
        print(f"Added search for '{args.keyword}'.")

    elif args.command == "list":
        searches = get_active_searches()
        if not searches:
            print("No active searches.")
            return
        
        table = [[s['id'], s['keyword'], s['min_price'], s['max_price'], s['category_id'], s['buying_option']] for s in searches]
        print(tabulate(table, headers=["ID", "Keyword", "Min $", "Max $", "Category", "Type"], tablefmt="grid"))

    elif args.command == "delete":
        delete_search(args.id)
        print(f"Deleted search ID {args.id}.")

    elif args.command == "status":
        config = load_config(default_config_path())
        active_searches = len(get_active_searches())
        poll_interval = config.poll_interval_minutes
        
        # Calculate API Usage
        # Number of searches * times polled per hour * 24 hours
        calls_per_day = active_searches * (60 / poll_interval) * 24
        
        # Add ~12 calls a day for OAuth token refreshes
        total_estimated = int(calls_per_day + 12) 
        daily_limit = 5000 # Standard eBay application tier
        
        print("\n=== SYSTEM STATUS & API MONITOR ===")
        print(f"Active Searches: {active_searches}")
        print(f"Polling Interval: Every {poll_interval} minutes")
        print(f"Total Unique Items Processed (Lifetime): {get_total_seen_count()}")
        print(f"Mode: {config.ebay.mode}")
        print("\n=== DAILY API USAGE CALCULATION ===")
        print(f"Estimated API Calls / Day:  {total_estimated}")
        print(f"eBay Default Daily Limit:   {daily_limit}")
        
        usage_percent = (total_estimated / daily_limit) * 100
        print(f"API Quota Utilized:         {usage_percent:.1f}%\n")
        
        if usage_percent > 80:
            print("WARNING: You are approaching the eBay API limits.")
            print("Consider deleting some searches or increasing 'poll_interval_minutes' in config.json.")

if __name__ == "__main__":
    main()