Basic CLI based ebay tracker. Uses ebay OAuth api.
Manage searches via manager.py  
Set worker.py as service or cronjob or whatever you like.

Text UI available via `tui.py` (uses Textual).


```
ebaybot/
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
├── tui.py                   # Textual TUI (Status/Add Search)
├── config.json              # API keys, email addresses, phone numbers
```

## Run

Create a venv and install deps:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Start the TUI:

```bash
.venv/bin/python tui.py
```

- Status tab: `j/k` to move, `Enter` to view alerts, `r` to refresh.
- Add Search tab: type a keyword, `Enter` to preview, `Ctrl+S` to save.
