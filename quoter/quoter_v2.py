import json
import os
from decimal import Decimal
from web3 import Web3

from config import (
    LINEA_RPC,
    QUOTER_V2_ADDRESS,
    POOL_BASE_ADDRESS,
    POOL_QUOTE_ADDRESS,
    POOL_BASE_DECIMALS,
    POOL_QUOTE_DECIMALS,
    POOL_TICK_SPACING,
)
from models.types import QuoteResult


def load_quoter_abi() :
    abi_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "abis",
        "quoterv2_abi.json",
    )
    with open(abi_path, "r", encoding="utf-8") as abi_file:
        return json.load(abi_file)


class QuoterV2Client:
    def __init__(
        self,
        rpc_url: str = LINEA_RPC,
        quoter_address: str = QUOTER_V2_ADDRESS,
        base_address: str = POOL_BASE_ADDRESS,
        quote_address: str = POOL_QUOTE_ADDRESS,
        base_decimals: int = POOL_BASE_DECIMALS,
        quote_decimals: int = POOL_QUOTE_DECIMALS,
        tick_spacing: int = POOL_TICK_SPACING,
    ) :
        self.web3 = Web3(Web3.HTTPProvider(rpc_url))
        self.quoter_address = Web3.to_checksum_address(quoter_address)
        self.base_address = Web3.to_checksum_address(base_address)
        self.quote_address = Web3.to_checksum_address(quote_address)
        self.base_decimals = int(base_decimals)
        self.quote_decimals = int(quote_decimals)
        self.tick_spacing = tick_spacing

        abi = load_quoter_abi()
        self.contract = self.web3.eth.contract(
            address=self.quoter_address,
            abi=abi,
        )

    @property
    def is_connected(self) :
        try:
            return self.web3.is_connected()
        except Exception:
            return False

    def quote_exact_input_single(
        self,
        token_in: str,
        token_out: str,
        amount_in: int,
        tick_spacing: int,
        sqrt_price_limit_x96: int = 0,
        block_number = None,
    ) :
        token_in = Web3.to_checksum_address(token_in)
        token_out = Web3.to_checksum_address(token_out)

        params = (
            token_in,
            token_out,
            amount_in,
            tick_spacing,
            sqrt_price_limit_x96,
        )

        if block_number is not None:
            result = self.contract.functions.quoteExactInputSingle(params).call(
                block_identifier=block_number
            )
        else:
            result = self.contract.functions.quoteExactInputSingle(params).call()

        amount_out, sqrt_price_x96_after, ticks_crossed, gas_estimate = result

        return QuoteResult(
            amount_out=amount_out,
            sqrt_price_x96_after=sqrt_price_x96_after,
            ticks_crossed=ticks_crossed,
            gas_estimate=gas_estimate,
        )

    def quote_quote_to_base(
        self,
        quote_amount: Decimal,
        block_number = None,
    ):
        quote_raw = int(quote_amount * (10 ** self.quote_decimals))

        result = self.quote_exact_input_single(
            token_in=self.quote_address,
            token_out=self.base_address,
            amount_in=quote_raw,
            tick_spacing=self.tick_spacing,
            block_number=block_number,
        )

        base_amount = Decimal(result.amount_out) / (10 ** self.base_decimals)

        return result, base_amount

    def quote_base_to_quote(
        self,
        base_amount: Decimal,
        block_number = None,
    ) :
        base_raw = int(base_amount * (10 ** self.base_decimals))

        result = self.quote_exact_input_single(
            token_in=self.base_address,
            token_out=self.quote_address,
            amount_in=base_raw,
            tick_spacing=self.tick_spacing,
            block_number=block_number,
        )

        quote_amount = Decimal(result.amount_out) / (10 ** self.quote_decimals)

        return result, quote_amount
