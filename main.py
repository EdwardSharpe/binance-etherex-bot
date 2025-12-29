import asyncio
import json
import os
import signal
import time
from datetime import datetime
from decimal import Decimal
from functools import lru_cache
from eth_abi import encode as abi_encode
from eth_utils import keccak

try:
    import orjson

    def dumps(obj):
        return orjson.dumps(obj).decode()
except ImportError:

    def dumps(obj):
        return json.dumps(obj, default=str)

from config import (
    LOG_PATH,
    LOG_ALL_EVALUATIONS,
    BEST_TRADE_LOG_PATH,
    DEPTH_WEIGHTED_LEVELS,
    LINEA_RPC,
    BINANCE_WS_PAIR,
    BINANCE_WS_GAS,
    POOL_ADDRESS,
    POOL_TICK_SPACING,
    POOL_BASE_SYMBOL,
    POOL_QUOTE_SYMBOL,
    POOL_BASE_ADDRESS,
    POOL_QUOTE_ADDRESS,
    NATIVE_SYMBOL,
    GAS_QUOTE_SYMBOL,
    UNIVERSAL_ROUTER_ADDRESS,
    UNIVERSAL_ROUTER_RECIPIENT,
    UR_DEADLINE_SECONDS,
    UR_COMMAND_V3_SWAP_EXACT_IN,
    UR_PAYER_IS_USER,
)
from md.linea_rpc import LineaRpcClient
from md.binance_ws import BinanceOrderbookStream
from quoter.quoter_v2 import QuoterV2Client
from orderbook.execution_sim import CEXExecutionSimulator
from arbitrage.gas_calc import GasCostCalculator
from arbitrage.evaluator import ArbitrageEvaluator
from models.types import ArbitrageOpportunity, Direction
from web3 import Web3


TOKEN_ADDRESS_BY_SYMBOL = {
    POOL_BASE_SYMBOL: POOL_BASE_ADDRESS,
    POOL_QUOTE_SYMBOL: POOL_QUOTE_ADDRESS,
}


def format_opportunity(
    opp: ArbitrageOpportunity,
    base_price_quote: Decimal,
    quote_price_usd: Decimal,
) :
    cex_token_in = opp.cex_quote.token_in
    cex_token_out = opp.cex_quote.token_out
    cex_amount_in = opp.cex_quote.amount_in
    cex_amount_out = opp.cex_quote.amount_out
    avg_price = opp.cex_quote.average_price

    profit_token_amount = opp.gross_profit_token
    profit_usd = compute_profit_token_usd(opp, base_price_quote, quote_price_usd)
    gas_cost_usd = compute_gas_cost_usd(opp, quote_price_usd)
    net_profit_usd = profit_usd - gas_cost_usd
    if opp.dex_quote.token_in == POOL_QUOTE_SYMBOL:
        notional_quote = opp.dex_quote.amount_in
    elif opp.dex_quote.token_in == POOL_BASE_SYMBOL:
        notional_quote = opp.dex_quote.amount_in * base_price_quote
    else:
        notional_quote = Decimal("0")
    notional_usd = notional_quote * quote_price_usd
    profit_bps = None
    capital_usd = notional_usd + gas_cost_usd
    if capital_usd > 0:
        profit_bps = (net_profit_usd / capital_usd) * Decimal("10000")

    is_profitable = net_profit_usd > 0
    opp.is_profitable = is_profitable

    return {
        "timestamp": datetime.fromtimestamp(opp.timestamp).isoformat(),
        "block": opp.block_number,
        "net_profit_usd": float(net_profit_usd),
        "direction": opp.direction.value,
        "dex": {
            "token_in": opp.dex_quote.token_in,
            "token_out": opp.dex_quote.token_out,
            "amount_in": float(opp.dex_quote.amount_in),
            "amount_out": float(opp.dex_quote.amount_out),
            "price": float(opp.dex_price),
            "gas_estimate": opp.dex_quote.gas_estimate,
        },
        "cex": {
            "token_in": cex_token_in,
            "token_out": cex_token_out,
            "amount_in": float(cex_amount_in),
            "amount_out": float(cex_amount_out),
            "avg_price": float(avg_price),
        },
        "gas_price_gwei": opp.gas_price_wei / 1e9,
        "gas_cost_usd": float(gas_cost_usd),
        "profit_token": opp.profit_token,
        "profit_token_amount": float(profit_token_amount),
        "profit_bps": float(profit_bps) if profit_bps is not None else None,
        "is_profitable": is_profitable,
    }

# Load & cache byte call data for set token_in + tick_spacing + token_out
@lru_cache(maxsize=2)
def encode_v3_path(token_in: str, token_out: str, tick_spacing: int) :
    token_in_bytes = bytes.fromhex(Web3.to_checksum_address(token_in)[2:])
    token_out_bytes = bytes.fromhex(Web3.to_checksum_address(token_out)[2:])
    tick_bytes = int(tick_spacing).to_bytes(3, "big")
    return token_in_bytes + tick_bytes + token_out_bytes


def build_universal_router_exact_in_tx(
    opp: ArbitrageOpportunity,
    deadline: int,
) :
    token_in_symbol = opp.dex_quote.token_in
    token_out_symbol = opp.dex_quote.token_out
    token_in = TOKEN_ADDRESS_BY_SYMBOL.get(token_in_symbol)
    token_out = TOKEN_ADDRESS_BY_SYMBOL.get(token_out_symbol)
    router_address = Web3.to_checksum_address(UNIVERSAL_ROUTER_ADDRESS)
    recipient = Web3.to_checksum_address(UNIVERSAL_ROUTER_RECIPIENT)

    commands = bytes([int(UR_COMMAND_V3_SWAP_EXACT_IN)])
    path = encode_v3_path(token_in, token_out, POOL_TICK_SPACING)
    amount_in_raw = int(opp.dex_quote.amount_in_raw)
    amount_out_min_raw = int(opp.dex_quote.amount_out_raw)

    input_bytes = abi_encode(
        ["address", "uint256", "uint256", "bytes", "bool"],
        [
            recipient,
            amount_in_raw,
            amount_out_min_raw,
            path,
            bool(UR_PAYER_IS_USER),
        ],
    )

    call_data = abi_encode(
        ["bytes", "bytes[]", "uint256"],
        [commands, [input_bytes], int(deadline)],
    )
    selector = keccak(text="execute(bytes,bytes[],uint256)")[:4]
    data = "0x" + (selector + call_data).hex()

    return {
        "to": router_address,
        "data": data,
        "value": 0,
        "deadline": int(deadline),
        "commands": Web3.to_hex(commands),
        "inputs": [Web3.to_hex(input_bytes)],
        "path": Web3.to_hex(path),
        "token_in": Web3.to_checksum_address(token_in),
        "token_out": Web3.to_checksum_address(token_out),
        "amount_in_raw": amount_in_raw,
        "amount_out_min_raw": amount_out_min_raw,
        "recipient": recipient,
        "payer_is_user": bool(UR_PAYER_IS_USER),
        "tick_spacing": int(POOL_TICK_SPACING),
    }


# Cost of 1 pool quote token as 1 dollar
def compute_quote_price_usd(
    base_price_quote: Decimal,
    native_price_quote: Decimal,
) :
    # quote token already USDC - pegged
    if POOL_QUOTE_SYMBOL == GAS_QUOTE_SYMBOL:
        return Decimal("1")
    # quote token is native gas so native_price_quote is weth/usdc - pegged
    if POOL_QUOTE_SYMBOL in {NATIVE_SYMBOL, "WETH"}:
        return native_price_quote
    
    # Consider WETH/WBTC - need to approx convert WBTC to USD for pnl
    # native_price_quote (gas stream weth/usdc) represents USDC per ETH
    # base_price_quote (pair stream weth/wbtc) - so need approx USDC per WBTC
    # (weth/usdc) / (weth/wbtc) = wbtc/usdc - can now convert to $
    # This is all infinitely easier if I had pricing for everything separately
    if POOL_BASE_SYMBOL in {NATIVE_SYMBOL, "WETH"}:
        if base_price_quote <= 0:
            return None
        return native_price_quote / base_price_quote
    # no conversion path from quote to USD
    return None


def compute_profit_token_usd(
    opp: ArbitrageOpportunity,
    base_price_quote: Decimal,
    quote_price_usd: Decimal,
) :
    if opp.profit_token == POOL_QUOTE_SYMBOL:
        return opp.gross_profit_token * quote_price_usd
    if opp.profit_token == POOL_BASE_SYMBOL:
        return opp.gross_profit_token * base_price_quote * quote_price_usd
    return Decimal("0")


def compute_gas_cost_usd(
    opp: ArbitrageOpportunity,
    quote_price_usd: Decimal,
) :
    return opp.gas_cost_quote * quote_price_usd


def compute_net_profit_usd(
    opp: ArbitrageOpportunity,
    base_price_quote: Decimal,
    quote_price_usd: Decimal,
) :
    return compute_profit_token_usd(opp, base_price_quote, quote_price_usd) - compute_gas_cost_usd(
        opp, quote_price_usd
    )


def format_best_trade(
    opp: ArbitrageOpportunity,
    base_price_quote: Decimal,
    quote_price_usd: Decimal,
    tx_payload: dict,
) :
    data = format_opportunity(opp, base_price_quote, quote_price_usd)
    data["tx"] = {
        "to": tx_payload.get("to"),
        "data": tx_payload.get("data"),
    }
    return data


def log_best_trade(
    opp: ArbitrageOpportunity,
    base_price_quote: Decimal,
    quote_price_usd: Decimal,
    tx_payload: dict,
) :
    data = format_best_trade(opp, base_price_quote, quote_price_usd, tx_payload)
    line = dumps(data)
    with open(BEST_TRADE_LOG_PATH, "a") as f:
        f.write(line + "\n")


def log_opportunity(
    opp: ArbitrageOpportunity,
    base_price_quote: Decimal,
    quote_price_usd: Decimal,
) :
    data = format_opportunity(opp, base_price_quote, quote_price_usd)
    line = dumps(data)
    with open(LOG_PATH, "a") as f:
        f.write(line + "\n")


def print_opportunity_summary(
    opp: ArbitrageOpportunity,
    base_price_quote: Decimal,
    quote_price_usd: Decimal,
) :
    if opp.direction == Direction.DEX_BUY_CEX_SELL:
        direction_str = "DEX(buy)->CEX(sell)"
    elif opp.direction == Direction.DEX_SELL_CEX_BUY:
        direction_str = "DEX(sell)->CEX(buy)"
    else:
        direction_str = opp.direction.value
    size_token = opp.dex_quote.token_in
    size_precision = ".2f" if size_token == POOL_QUOTE_SYMBOL else ".4f"
    size_value = format(opp.dex_quote.amount_in, size_precision)
    cex_price = opp.cex_quote.average_price
    net_profit_usd = compute_net_profit_usd(opp, base_price_quote, quote_price_usd)
    if opp.dex_quote.token_in == POOL_QUOTE_SYMBOL:
        notional_quote = opp.dex_quote.amount_in
    elif opp.dex_quote.token_in == POOL_BASE_SYMBOL:
        notional_quote = opp.dex_quote.amount_in * base_price_quote
    else:
        notional_quote = Decimal("0")
    notional_usd = notional_quote * quote_price_usd
    gas_cost_usd = compute_gas_cost_usd(opp, quote_price_usd)
    profit_bps = None
    capital_usd = notional_usd + gas_cost_usd
    if capital_usd > 0:
        profit_bps = (net_profit_usd / capital_usd) * Decimal("10000")
    bps_str = f"{profit_bps:.2f}" if profit_bps is not None else "n/a"
    profit_indicator = "+" if net_profit_usd > 0 else ""

    print(
        f"[arb] block={opp.block_number} "
        f"dir={direction_str} "
        f"size={size_value}{size_token} "
        f"dex_px={opp.dex_price:.6f} "
        f"cex_px={cex_price:.6f} "
        f"gas=${gas_cost_usd:.6f} "
        f"pnl={profit_indicator}${net_profit_usd:.6f} "
        f"bps={bps_str}"
    )


def load_pool_abi() :
    abi_path = os.path.join(os.path.dirname(__file__), "abis", "v3_abi.json")
    with open(abi_path, "r", encoding="utf-8") as abi_file:
        return json.load(abi_file)


def check_pool_tick_spacing() :
    web3 = Web3(Web3.HTTPProvider(LINEA_RPC))
    contract = web3.eth.contract(
        address=Web3.to_checksum_address(POOL_ADDRESS),
        abi=load_pool_abi(),
    )
    tick_spacing = contract.functions.tickSpacing().call()

    print(
        f"[main] Pool tickSpacing={tick_spacing} "
        f"(config POOL_TICK_SPACING={POOL_TICK_SPACING})"
    )
    if tick_spacing != POOL_TICK_SPACING:
        print("[main] WARNING: Pool tickSpacing does not match config")
        return False

    print("[main] Pool tickSpacing confirmed")
    return True


async def main() :
    print("=" * 60)
    print("Binance-Etherex CEX-DEX Arbitrage Bot")
    print("=" * 60)

    # Setup signal handlers for graceful shutdown
    shutdown_event = asyncio.Event()

    def signal_handler(sig, frame):
        print("\n[main] Kill switch received...")
        shutdown_event.set()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    linea = LineaRpcClient()
    binance_pair = BinanceOrderbookStream(BINANCE_WS_PAIR, label="pair")
    binance_gas = BinanceOrderbookStream(BINANCE_WS_GAS, label="gas")
    quoter = QuoterV2Client()
    exec_sim = CEXExecutionSimulator()
    gas_calc = GasCostCalculator()
    evaluator = ArbitrageEvaluator(quoter, exec_sim, gas_calc)

    await asyncio.gather(
        linea.connect(),
        binance_pair.connect(),
        binance_gas.connect(),
    )

    # Verify quoter connection
    if not quoter.is_connected:
        print("[main] ERROR: Cannot connect to Linea RPC for QuoterV2")
        return

    if not check_pool_tick_spacing():
        print("[main] ERROR: Pool tickSpacing mismatch; aborting")
        return

    # Subscribe to new blocks
    block_queue = await linea.subscribe_new_heads()
    print("[main] Subscribed to new block headers")

    # Wait for first orderbook update
    print("[main] Waiting for Binance orderbook...")
    while (
        not binance_pair.is_connected()
        or binance_pair.last_update_time() == 0
        or not binance_gas.is_connected()
        or binance_gas.last_update_time() == 0
    ):
        await asyncio.sleep(0.1)
        if shutdown_event.is_set():
            return

    print("[main] Ready. Starting arbitrage evaluation loop...")
    print("-" * 60)

    blocks_processed = 0
    opportunities_found = 0
    last_eval = 0.0

    try:
        while not shutdown_event.is_set():
            # Wait for new block with timeout
            try:
                block = await asyncio.wait_for(
                    block_queue.get(),
                    timeout=1.0,
                )
            except asyncio.TimeoutError:
                continue

            block_number = int(block["number"], 16)
            block_timestamp = int(block["timestamp"], 16)
            received_at = block.get("received_at")
            blocks_processed += 1


            bids, asks = binance_pair.get_orderbook()
            if not bids or not asks:
                continue

            try:
                gas_price_wei = await linea.eth_gas_price()
            except Exception:
                continue

            base_price_quote = binance_pair.depth_weighted_mid(DEPTH_WEIGHTED_LEVELS)
            if base_price_quote is None:
                continue

            native_price_quote = binance_gas.depth_weighted_mid(DEPTH_WEIGHTED_LEVELS)
            if native_price_quote is None:
                continue
            quote_price_usd = compute_quote_price_usd(base_price_quote, native_price_quote)
            if quote_price_usd is None:
                continue

            # Evaluate opportunities
            eval_start = time.perf_counter()
            opportunities = evaluator.evaluate_block(
                block_number=block_number,
                bids=bids,
                asks=asks,
                gas_price_wei=gas_price_wei,
                base_price_quote=base_price_quote,
                native_price_quote=native_price_quote,
            )
            last_eval = (time.perf_counter() - eval_start) * 1000

            # Log and print opportunities
            for opp in opportunities:
                net_profit_usd = compute_net_profit_usd(
                    opp, base_price_quote, quote_price_usd
                )
                opp.is_profitable = net_profit_usd > 0
                if opp.is_profitable:
                    opportunities_found += 1
                    print_opportunity_summary(opp, base_price_quote, quote_price_usd)
                    log_opportunity(opp, base_price_quote, quote_price_usd)
                elif LOG_ALL_EVALUATIONS:
                    log_opportunity(opp, base_price_quote, quote_price_usd)

            # Build and log best trade per block (profitable only)
            best_opp = None
            best_profit_usd = None
            for opp in opportunities:
                profit_usd = compute_net_profit_usd(
                    opp, base_price_quote, quote_price_usd
                )
                if profit_usd <= 0:
                    continue
                opp.is_profitable = True
                if best_profit_usd is None or profit_usd > best_profit_usd:
                    best_profit_usd = profit_usd
                    best_opp = opp

            if best_opp is not None:
                base_ts = block_timestamp
                deadline = int(base_ts + UR_DEADLINE_SECONDS)
                tx_payload = build_universal_router_exact_in_tx(best_opp, deadline)
                if tx_payload:
                    log_best_trade(best_opp, base_price_quote, quote_price_usd, tx_payload)

            now = time.time()
            block_age_ms = (now - block_timestamp) * 1000

            block_age_str = f"{block_age_ms:.0f}ms"
            recv_delay_ms = None
            if received_at is not None:
                recv_delay_ms = (received_at - block_timestamp) * 1000
            recv_delay_str = f"{recv_delay_ms:.0f}ms"
            print(
                f"[block] num={block_number} "
                f"age={block_age_str} "
                f"recv={recv_delay_str} "
                f"pair_mid={base_price_quote:.6f} "
                f"gas={gas_price_wei/1e9:.4f}gwei "
                f"eval={last_eval:.0f}ms"
            )

    except Exception as e:
        print(f"[main] Error in main loop: {e}")
        raise
    finally:
        print("[main] Shutting down...")
        await linea.close()
        await binance_pair.close()
        await binance_gas.close()
        print(f"[main] Processed {blocks_processed} blocks, found {opportunities_found} profitable opportunities")
        print("[main] Goodbye!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
