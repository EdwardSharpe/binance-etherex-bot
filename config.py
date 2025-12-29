from decimal import Decimal
import os

# Main Params To Change
# Pick from: weth_usdc, weth_usdt, weth_wbtc, linea_usdc, linea_usdc_low_tvl
# By default will use weth_usdc
ACTIVE_POOL = os.getenv("ACTIVE_POOL", "weth_usdc")

# Binance Fee in bps
BINANCE_TAKER_FEE_BPS = Decimal("1")
# Note: To Reach a "profitable" arb for testing easily, can turn negative
# Value of "-100" would mean binance gives you an extra 1% for free than expected amount

# All profit calcs take the worst case of all gas limit being used
DEFAULT_GAS_LIMIT = 150000

# Number of levels to calculate approx theo
DEPTH_WEIGHTED_LEVELS = 5

# For building call data - wallet you're trading from
UNIVERSAL_ROUTER_RECIPIENT = "0x0000000000000000000000000000000000000000"

# Choose logging all simulations, or just profitable ones
LOG_ALL_EVALUATIONS = True




# Network endpoints
# Ideally run your own
# For best public ones check: https://chainlist.org/?chain=59144&search=linea
# No Block Builders on Linea for submissions unfortunately

# Infura - Originally used but the calls were much slower, and runs out of daily credits after 2-3 hours
# Key 1
#LINEA_WSS = "wss://linea-mainnet.infura.io/ws/v3/bfc68481e6754b498c6068c5dc78eef7"
#LINEA_RPC = "https://linea-mainnet.infura.io/v3/bfc68481e6754b498c6068c5dc78eef7"
# Key 2
#LINEA_WSS = "wss://linea-mainnet.infura.io/ws/v3/456cb8ac39824dea845ad1ad110d16d2"
#LINEA_RPC = "https://linea-mainnet.infura.io/v3/456cb8ac39824dea845ad1ad110d16d2"

#LINEA_RPC= "https://rpc.linea.build"
#LINEA_RPC = "https://1rpc.io/linea"
LINEA_RPC = "https://linea-rpc.publicnode.com"
LINEA_WSS = "wss://linea-rpc.publicnode.com"

BINANCE_WS_GAS = "wss://stream.binance.com:9443/ws/ethusdc@depth10@100ms"

# Contract addresses
QUOTER_V2_ADDRESS = "0xE660C95E17884b6C81B01445EFC24556f8ABa037"

# Pool configuration
POOLS = {
    "weth_usdc": {
        "pool_address": "0x90e8a5b881d211f418d77ba8978788b62544914b",
        "base_symbol": "WETH",
        "quote_symbol": "USDC",
        "base_address": "0xe5D7C2a44fFDDf6b295A15c148167daaAf5Cf34f",
        "quote_address": "0x176211869cA2b568f2A7D4EE941E073a821EE1ff",
        "base_decimals": 18,
        "quote_decimals": 6,
        "tick_spacing": 50,
        "binance_ws_pair": "wss://stream.binance.com:9443/ws/ethusdc@depth10@100ms",
        "trade_sizes_base": [
            Decimal("0.15"),
            Decimal("0.4"),
            Decimal("1"),
            Decimal("4")
        ],
        "trade_sizes_quote": [
            Decimal("400"),
            Decimal("1000"),
            Decimal("3000"),
            Decimal("10000"),
        ],
    },
    "weth_usdt": {
        "pool_address": "0xd5E04ba35908D7bF5BD2eAd7e3e14d21df07DC01",
        "base_symbol": "WETH",
        "quote_symbol": "USDT",
        "base_address": "0xe5D7C2a44fFDDf6b295A15c148167daaAf5Cf34f",
        "quote_address": "0xA219439258ca9da29E9Cc4cE5596924745e12B93",
        "base_decimals": 18,
        "quote_decimals": 6,
        "tick_spacing": 50,
        "binance_ws_pair": "wss://stream.binance.com:9443/ws/ethusdt@depth10@100ms",
        "trade_sizes_base": [
            Decimal("0.15"),
            Decimal("0.4"),
            Decimal("1"),
            Decimal("4")
        ],
        "trade_sizes_quote": [
            Decimal("400"),
            Decimal("1000"),
            Decimal("3000"),
            Decimal("10000"),
        ],
    },
    "weth_wbtc": {
        "pool_address": "0xC0Cd56E070e25913D631876218609F2191dA1c2A",
        "base_symbol": "WETH",
        "quote_symbol": "WBTC",
        "base_address": "0xe5D7C2a44fFDDf6b295A15c148167daaAf5Cf34f",
        "quote_address": "0x3aAB2285ddcDdaD8edf438C1bAB47e1a9D05a9b4",
        "base_decimals": 18,
        "quote_decimals": 8,
        "tick_spacing": 10,
        "binance_ws_pair": "wss://stream.binance.com:9443/ws/ethbtc@depth10@100ms",
        "trade_sizes_base": [
            Decimal("0.15"),
            Decimal("0.4"),
            Decimal("1"),
            Decimal("4")
        ],
        "trade_sizes_quote": [
            Decimal("0.005"),
            Decimal("0.015"),
            Decimal("0.03"),
            Decimal("0.13"),
        ],
    },
    "linea_usdc": {
        "pool_address": "0x70f536B375296b60078a6e1Bb0790919a13EFE77",
        "base_symbol": "LINEA",
        "quote_symbol": "USDC",
        "base_address": "0x1789e0043623282D5DCc7F213d703C6D8BAfBB04",
        "quote_address": "0x176211869cA2b568f2A7D4EE941E073a821EE1ff",
        "base_decimals": 18,
        "quote_decimals": 6,
        "tick_spacing": 1,
        "binance_ws_pair": "wss://stream.binance.com:9443/ws/lineausdc@depth10@100ms",
        "trade_sizes_base": [
            Decimal("15000"),
            Decimal("50000"),
            Decimal("70000"),
            Decimal("110000"),
        ],
        "trade_sizes_quote": [
            Decimal("100"),
            Decimal("350"),
            Decimal("500"),
            Decimal("800"),
        ],
    }
    ,
    "linea_usdc_low_tvl": {
        "pool_address": "0x85895583a73ca811Cc9CD5346AdC8CF036c361A6",
        "base_symbol": "LINEA",
        "quote_symbol": "USDC",
        "base_address": "0x1789e0043623282D5DCc7F213d703C6D8BAfBB04",
        "quote_address": "0x176211869cA2b568f2A7D4EE941E073a821EE1ff",
        "base_decimals": 18,
        "quote_decimals": 6,
        "tick_spacing": 10,
        "binance_ws_pair": "wss://stream.binance.com:9443/ws/lineausdc@depth10@100ms",
        "trade_sizes_base": [
            Decimal("1000"),
            Decimal("3000"),
            Decimal("5000"),
            Decimal("8000"),
        ],
        "trade_sizes_quote": [
            Decimal("10"),
            Decimal("25"),
            Decimal("50"),
            Decimal("100"),
        ],
    }
}

# Deadline for tx inclusion (passed into calldata)
UR_DEADLINE_SECONDS = 4

POOL_ADDRESS = POOLS[ACTIVE_POOL]["pool_address"]
POOL_BASE_SYMBOL = POOLS[ACTIVE_POOL]["base_symbol"]
POOL_QUOTE_SYMBOL = POOLS[ACTIVE_POOL]["quote_symbol"]
POOL_BASE_ADDRESS = POOLS[ACTIVE_POOL]["base_address"]
POOL_QUOTE_ADDRESS = POOLS[ACTIVE_POOL]["quote_address"]
POOL_BASE_DECIMALS = POOLS[ACTIVE_POOL]["base_decimals"]
POOL_QUOTE_DECIMALS = POOLS[ACTIVE_POOL]["quote_decimals"]
POOL_TICK_SPACING = POOLS[ACTIVE_POOL]["tick_spacing"]

BINANCE_WS_PAIR = POOLS[ACTIVE_POOL]["binance_ws_pair"]

# Gas pricing
NATIVE_SYMBOL = "ETH"
NATIVE_DECIMALS = 18
GAS_QUOTE_SYMBOL = "USDC"

# Trade sizes to evaluate (directional inputs)
TRADE_SIZES_BASE = POOLS[ACTIVE_POOL]["trade_sizes_base"]  # DEX sell -> CEX buy
TRADE_SIZES_QUOTE = POOLS[ACTIVE_POOL]["trade_sizes_quote"]  # DEX buy -> CEX sell


# Universal router configuration
UNIVERSAL_ROUTER_ADDRESS = "0x85974429677c2a701af470B82F3118e74307826e"
# Sourced from universal router commands.sol for calldata
UR_COMMAND_V3_SWAP_EXACT_IN = 0x00
UR_PAYER_IS_USER = True

# Logging config
LOG_PATH = os.getenv("LOG_PATH", f"arb_opportunities_{ACTIVE_POOL}.log")
LOG_ALL_EVALUATIONS = True  # Log all evaluations including unprofitable ones
BEST_TRADE_LOG_PATH = os.getenv(
    "BEST_TRADE_LOG_PATH", f"arb_best_trade_{ACTIVE_POOL}.log"
)

# WebSocket config
WS_PING_INTERVAL = 20
WS_PING_TIMEOUT = 20
WS_RECONNECT_DELAY = 2  # seconds
