Basic CLI based ebay tracker. Uses ebay OAuth api.
Manage searches via manager.py  
Set worker.py as service or cronjob or whatever you like.


ebay-sniper-cli/
│
├── data/
│   └── tracker.db           # SQLite database file
│
├── core/
│   ├── db.py                # Database connection and queries
│   ├── ebay_api.py          # Handles OAuth and eBay Browse API requests
│   └── notifier.py          # Twilio and SMTP logic
│
├── manager.py               # The CLI tool (Frontend)
├── worker.py                # The polling loop (Backend)
├── config.json              # API keys, email addresses, phone numbers

