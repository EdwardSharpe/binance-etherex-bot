
from decimal import Decimal

from config import BINANCE_TAKER_FEE_BPS
from models.types import OrderbookLevel, CEXQuote


class CEXExecutionSimulator:
    def __init__(self, taker_fee_bps: Decimal = BINANCE_TAKER_FEE_BPS):
        self.fee_rate = taker_fee_bps / Decimal("10000")

    # Walk through asks
    def simulate_buy(
        self,
        max_quote: Decimal,
        asks: list,
        token_in: str,
        token_out: str,
    ):
        if max_quote <= 0 or not asks:
            return None

        remaining_quote = max_quote
        total_quote_spent = Decimal("0")
        total_base_filled = Decimal("0")

        for level in asks:
            if level.price <= 0 or level.quantity <= 0:
                continue

            level_cost = level.price * level.quantity
            if level_cost <= remaining_quote:
                fill_base = level.quantity
                fill_quote = level_cost
            else:
                fill_base = remaining_quote / level.price
                fill_quote = remaining_quote

            total_base_filled += fill_base
            total_quote_spent += fill_quote
            remaining_quote -= fill_quote

            if remaining_quote <= 0:
                break

        # Insufficient liquidity
        if remaining_quote > 0:
            return None

        # Apply fee to base received
        fee_base = total_base_filled * self.fee_rate
        net_base = total_base_filled - fee_base

        amount_in = total_quote_spent
        amount_out = net_base
        avg_price = amount_in / amount_out if amount_out > 0 else Decimal("0")

        return CEXQuote(
            token_in=token_in,
            token_out=token_out,
            amount_in=amount_in,
            amount_out=amount_out,
            average_price=avg_price,
        )

    # Walk through bids
    def simulate_sell(
        self,
        target_base_qty: Decimal,
        bids: list,
        token_in: str,
        token_out: str,
    ):
        if target_base_qty <= 0 or not bids:
            return None

        remaining_base = target_base_qty
        total_quote_received = Decimal("0")
        total_base_sold = Decimal("0")

        for level in bids:
            if level.price <= 0 or level.quantity <= 0:
                continue

            fill_base = min(remaining_base, level.quantity)
            fill_quote = fill_base * level.price

            total_base_sold += fill_base
            total_quote_received += fill_quote
            remaining_base -= fill_base

            if remaining_base <= 0:
                break
        
        # Insufficient liquidity
        if remaining_base > 0:
            return None

        # Apply fee to quote received
        fee_quote = total_quote_received * self.fee_rate
        net_quote = total_quote_received - fee_quote

        amount_in = total_base_sold
        amount_out = net_quote
        avg_price = amount_out / amount_in if amount_in > 0 else Decimal("0")

        return CEXQuote(
            token_in=token_in,
            token_out=token_out,
            amount_in=amount_in,
            amount_out=amount_out,
            average_price=avg_price,
        )
