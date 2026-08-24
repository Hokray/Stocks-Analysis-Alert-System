"""
Configuration for the AI-infrastructure stock screener.

Every threshold lives here so you can tune the screener without touching logic.
"""

# ---------------------------------------------------------------------------
# Universe
# ---------------------------------------------------------------------------
TICKER_FILE = "data/tickers.csv"
FUNDAMENTALS_CACHE_FILE = "cache/fundamentals.json"

# Set to a number to only process the first N tickers (for testing).
# Set to None to run the full universe.
TEST_LIMIT = None

# Only screen these exchanges. Empty list = no exchange filter.
EXCHANGE_FILTER = []          # e.g. ["NASDAQ"] to go NASDAQ-only

# ---------------------------------------------------------------------------
# Screening thresholds  ---  this is the part you tune
# ---------------------------------------------------------------------------

# 1. Dollar-volume surge
RECENT_WINDOW_DAYS = 10       # "recent" period, in trading days
BASELINE_WINDOW_DAYS = 63     # "normal" period (~3 months of trading days)
VOLUME_SURGE_THRESHOLD = 1.50 # recent avg $ volume must be >= 150% of baseline

# 2. Price momentum
PRICE_CHANGE_THRESHOLD = 0.07 # +7% over RECENT_WINDOW_DAYS

# 3. Quality gate
REQUIRE_POSITIVE_TTM_CFO = True

# 4. Size gate
MIN_MARKET_CAP = 0            # 0 = no floor. Set to 2_000_000_000 for $2B.

# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------
HISTORY_PERIOD = "1y"         # how much price history to pull per ticker
REQUEST_DELAY_SECONDS = 1.0   # pause between tickers to stay under rate limits
FUNDAMENTALS_CACHE_FILE = "cache/fundamentals.json"
FUNDAMENTALS_CACHE_DAYS = 7   # cash flow changes quarterly; no need to refetch daily

# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------
ALERTS_HISTORY_FILE = "alerts_history.json"
ALERT_COOLDOWN_DAYS = 7    # don't re-alert the same ticker within this window
SEND_EMAIL = True         # flip to True once you've added credentials


#Stock Streak Alert System
STREAK_WINDOW_DAYS = 14        # look back this far when counting qualifying days
PERSISTENT_STREAK_MIN = 4      # this many hits = "persistent" (green tag)