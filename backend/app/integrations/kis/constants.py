# KIS Open Trading API endpoints
REAL_BASE_URL = "https://openapi.koreainvestment.com:9443"
PAPER_BASE_URL = "https://openapivts.koreainvestment.com:29443"

REAL_WS_URL = "ws://ops.koreainvestment.com:21000"
PAPER_WS_URL = "ws://ops.koreainvestment.com:31000"

# Token
TOKEN_PATH = "/oauth2/tokenP"
TOKEN_REVOKE_PATH = "/oauth2/revokeP"

# Domestic stock
STOCK_PRICE_PATH = "/uapi/domestic-stock/v1/quotations/inquire-price"
STOCK_DAILY_PRICE_PATH = "/uapi/domestic-stock/v1/quotations/inquire-daily-price"
STOCK_MINUTE_PRICE_PATH = "/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice"
STOCK_ORDERBOOK_PATH = "/uapi/domestic-stock/v1/quotations/inquire-asking-price-exp-ccn"

# Orders
ORDER_PATH = "/uapi/domestic-stock/v1/trading/order-cash"
ORDER_CANCEL_PATH = "/uapi/domestic-stock/v1/trading/order-rvsecncl"
ORDER_STATUS_PATH = "/uapi/domestic-stock/v1/trading/inquire-daily-ccld"

# Balance
BALANCE_PATH = "/uapi/domestic-stock/v1/trading/inquire-balance"

# Transaction IDs
TR_ID_BUY = "TTTC0802U"       # Real buy
TR_ID_SELL = "TTTC0801U"      # Real sell
TR_ID_BUY_PAPER = "VTTC0802U"  # Paper buy
TR_ID_SELL_PAPER = "VTTC0801U"  # Paper sell
TR_ID_BALANCE = "TTTC8434R"
TR_ID_BALANCE_PAPER = "VTTC8434R"
TR_ID_PRICE = "FHKST01010100"
TR_ID_INDEX_PRICE = "FHPUP02100000"
INDEX_PRICE_PATH = "/uapi/domestic-stock/v1/quotations/inquire-index-price"
TR_ID_DAILY_PRICE = "FHKST01010400"
TR_ID_MINUTE_PRICE = "FHKST03010200"

# Condition search (psearch)
CONDITION_LIST_PATH = "/uapi/domestic-stock/v1/quotations/psearch-title"
CONDITION_RESULT_PATH = "/uapi/domestic-stock/v1/quotations/psearch-result"
TR_ID_CONDITION_LIST = "HHKST03900300"
TR_ID_CONDITION_RESULT = "HHKST03900400"

# Investor trends (투자자별 매매동향)
INVESTOR_TREND_PATH = "/uapi/domestic-stock/v1/quotations/inquire-investor"
TR_ID_INVESTOR_TREND = "FHKST01010900"

# Volume ranking (거래량 순위)
VOLUME_RANKING_PATH = "/uapi/domestic-stock/v1/quotations/volume-rank"
TR_ID_VOLUME_RANKING = "FHPST01710000"

# Price change ranking (등락률 순위)
PRICE_RANKING_PATH = "/uapi/domestic-stock/v1/ranking/fluctuation"
TR_ID_PRICE_RANKING = "FHPST01700000"

# WebSocket data types
WS_REALTIME_EXEC = "H0STCNT0"    # Real-time execution (체결)
WS_REALTIME_ORDERBOOK = "H0STASP0"  # Real-time orderbook (호가)
WS_REALTIME_NOTIFY = "H0STCNI0"    # Real-time notification
