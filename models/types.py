from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


class Direction(Enum):
    DEX_SELL_CEX_BUY = "dex_sell_cex_buy"
    DEX_BUY_CEX_SELL = "dex_buy_cex_sell"


@dataclass
class QuoteResult:
    amount_out: int
    sqrt_price_x96_after: int
    ticks_crossed: int
    gas_estimate: int


@dataclass
class OrderbookLevel:
    price: Decimal
    quantity: Decimal


@dataclass
class CEXQuote:
    token_in: str
    token_out: str
    amount_in: Decimal
    amount_out: Decimal
    average_price: Decimal


@dataclass
class DEXQuote:
    token_in: str
    token_out: str
    amount_in: Decimal
    amount_out: Decimal
    amount_in_raw: int
    amount_out_raw: int
    gas_estimate: int


@dataclass
class ArbitrageOpportunity:
    timestamp: float
    block_number: int
    direction: Direction
    trade_size_base: Decimal
    dex_quote: DEXQuote
    cex_quote: CEXQuote
    gas_price_wei: int
    gas_cost_native: Decimal
    gas_cost_quote: Decimal
    profit_token: str
    gross_profit_token: Decimal
    net_profit_token: Decimal
    dex_price: Decimal
    cex_price: Decimal
    is_profitable: bool = False
