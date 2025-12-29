import time
from decimal import Decimal

from config import (
    TRADE_SIZES_BASE,
    TRADE_SIZES_QUOTE,
    POOL_BASE_DECIMALS,
    POOL_QUOTE_DECIMALS,
    POOL_BASE_SYMBOL,
    POOL_QUOTE_SYMBOL,
    NATIVE_SYMBOL,
    GAS_QUOTE_SYMBOL,
)
from models.types import (
    ArbitrageOpportunity,
    DEXQuote,
    Direction,
    OrderbookLevel,
)
from quoter.quoter_v2 import QuoterV2Client
from orderbook.execution_sim import CEXExecutionSimulator
from arbitrage.gas_calc import GasCostCalculator


class ArbitrageEvaluator:
    def __init__(
        self,
        quoter: QuoterV2Client,
        execution_sim: CEXExecutionSimulator,
        gas_calc: GasCostCalculator,
        trade_sizes_base: list = TRADE_SIZES_BASE,
        trade_sizes_quote: list = TRADE_SIZES_QUOTE,
    ):
        self.quoter = quoter
        self.exec_sim = execution_sim
        self.gas_calc = gas_calc
        self.trade_sizes_base = trade_sizes_base
        self.trade_sizes_quote = trade_sizes_quote

    def evaluate_block(
        self,
        block_number: int,
        bids: list,
        asks: list,
        gas_price_wei: int,
        base_price_quote: Decimal = None,
        native_price_quote: Decimal = None,
    ):
        opportunities = []
        timestamp = time.time()

        # Convert ETH gas cost into quote token units
        gas_price_quote = None
        # 1:1 ratio if quote token is ETH/WETH
        if POOL_QUOTE_SYMBOL in {NATIVE_SYMBOL, "WETH"}:
            gas_price_quote = Decimal("1")
        # Base price already expresses ETH in quote units
        elif POOL_BASE_SYMBOL in {NATIVE_SYMBOL, "WETH"}:
            gas_price_quote = base_price_quote
        # Use the gas stream price when quote matches GAS_QUOTE_SYMBOL
        elif POOL_QUOTE_SYMBOL == GAS_QUOTE_SYMBOL:
            gas_price_quote = native_price_quote

        # Skip block if we cannot price gas in quote units
        if gas_price_quote is None:
            return opportunities

        # Precompute gas cost once per block
        gas_cost_native = self.gas_calc.calculate_gas_cost_eth(gas_price_wei)
        gas_cost_quote = self.gas_calc.calculate_gas_cost_quote(
            gas_price_wei, gas_price_quote
        )

        # DEX buy with quote -> CEX sell with base -> quote
        for trade_size_quote in self.trade_sizes_quote:
            opp_a = self.evaluate_dex_buy_cex_sell(
                block_number=block_number,
                timestamp=timestamp,
                trade_size_quote=trade_size_quote,
                bids=bids,
                gas_price_wei=gas_price_wei,
                gas_cost_native=gas_cost_native,
                gas_cost_quote=gas_cost_quote,
            )
            if opp_a:
                opportunities.append(opp_a)

        # DEX sell with base -> CEX buy with quote -> base
        for trade_size_base in self.trade_sizes_base:
            opp_b = self.evaluate_dex_sell_cex_buy(
                block_number=block_number,
                timestamp=timestamp,
                trade_size_base=trade_size_base,
                asks=asks,
                gas_price_wei=gas_price_wei,
                gas_cost_native=gas_cost_native,
                gas_cost_quote=gas_cost_quote,
            )
            if opp_b:
                opportunities.append(opp_b)

        return opportunities

    def evaluate_dex_buy_cex_sell(
        self,
        block_number: int,
        timestamp: float,
        trade_size_quote: Decimal,
        bids: list,
        gas_price_wei: int,
        gas_cost_native: Decimal,
        gas_cost_quote: Decimal,
    ):
        try:
            # DEX leg - sell quote, get base
            quote_result, base_out = self.quoter.quote_quote_to_base(
                trade_size_quote,
                block_number=block_number,
            )
            if base_out <= 0:
                return None

            # CEX leg - sell base into bids
            cex_quote = self.exec_sim.simulate_sell(
                base_out,
                bids,
                token_in=POOL_BASE_SYMBOL,
                token_out=POOL_QUOTE_SYMBOL,
            )

            # Insufficient liquidity
            if cex_quote is None:
                bid_base_liq = sum(
                    level.quantity
                    for level in bids
                    if level.price > 0 and level.quantity > 0
                )
                print(
                    f"[evaluator] DEX buy skip for {trade_size_quote} {POOL_QUOTE_SYMBOL}: "
                    f"insufficient CEX bids (base_qty={base_out:.6f} "
                    f"bid_base_liq={bid_base_liq:.6f})"
                )
                return None

            # Track raw amounts for tx building
            dex_quote = DEXQuote(
                token_in=POOL_QUOTE_SYMBOL,
                token_out=POOL_BASE_SYMBOL,
                amount_in=trade_size_quote,
                amount_out=base_out,
                amount_in_raw=int(trade_size_quote * (10 ** POOL_QUOTE_DECIMALS)),
                amount_out_raw=quote_result.amount_out,
                gas_estimate=quote_result.gas_estimate,
            )

            dex_price = trade_size_quote / base_out if base_out > 0 else Decimal("0")
            cex_price = cex_quote.average_price

            # Profit in quote units
            gross_profit_token = cex_quote.amount_out - trade_size_quote
            net_profit_token = gross_profit_token

            return ArbitrageOpportunity(
                timestamp=timestamp,
                block_number=block_number,
                direction=Direction.DEX_BUY_CEX_SELL,
                trade_size_base=base_out,
                dex_quote=dex_quote,
                cex_quote=cex_quote,
                gas_price_wei=gas_price_wei,
                gas_cost_native=gas_cost_native,
                gas_cost_quote=gas_cost_quote,
                profit_token=POOL_QUOTE_SYMBOL,
                gross_profit_token=gross_profit_token,
                net_profit_token=net_profit_token,
                dex_price=dex_price,
                cex_price=cex_price,
            )

        except Exception:
            return None

    def evaluate_dex_sell_cex_buy(
        self,
        block_number: int,
        timestamp: float,
        trade_size_base: Decimal,
        asks: list,
        gas_price_wei: int,
        gas_cost_native: Decimal,
        gas_cost_quote: Decimal,
    ):
        try:
            # DEX leg - sell base, get quote
            quote_result, quote_out = self.quoter.quote_base_to_quote(
                trade_size_base,
                block_number=block_number,
            )

            if quote_out <= 0:
                return None

            # CEX leg - sell quote into asks
            cex_quote = self.exec_sim.simulate_buy(
                quote_out,
                asks,
                token_in=POOL_QUOTE_SYMBOL,
                token_out=POOL_BASE_SYMBOL,
            )
            
            # Insufficient liqudity
            if cex_quote is None:
                ask_base_liq = sum(level.quantity for level in asks)
                best_ask = asks[0].price if asks else Decimal("0")
                base_qty = quote_out / best_ask if best_ask else Decimal("0")
                print(
                    f"[evaluator] DEX sell skip for {trade_size_base} {POOL_BASE_SYMBOL}: "
                    f"insufficient CEX asks (base_qty={base_qty:.6f} "
                    f"ask_base_liq={ask_base_liq:.6f})"
                )
                return None

            # Net base after CEX fill
            net_base = cex_quote.amount_out

            # Track raw amounts for tx building
            dex_quote = DEXQuote(
                token_in=POOL_BASE_SYMBOL,
                token_out=POOL_QUOTE_SYMBOL,
                amount_in=trade_size_base,
                amount_out=quote_out,
                amount_in_raw=int(trade_size_base * (10 ** POOL_BASE_DECIMALS)),
                amount_out_raw=quote_result.amount_out,
                gas_estimate=quote_result.gas_estimate,
            )

            dex_price = quote_out / trade_size_base
            cex_price = cex_quote.average_price

            # Profit in base units
            gross_profit_token = net_base - trade_size_base
            net_profit_token = gross_profit_token

            return ArbitrageOpportunity(
                timestamp=timestamp,
                block_number=block_number,
                direction=Direction.DEX_SELL_CEX_BUY,
                trade_size_base=trade_size_base,
                dex_quote=dex_quote,
                cex_quote=cex_quote,
                gas_price_wei=gas_price_wei,
                gas_cost_native=gas_cost_native,
                gas_cost_quote=gas_cost_quote,
                profit_token=POOL_BASE_SYMBOL,
                gross_profit_token=gross_profit_token,
                net_profit_token=net_profit_token,
                dex_price=dex_price,
                cex_price=cex_price,
            )

        except Exception:
            return None
