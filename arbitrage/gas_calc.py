from decimal import Decimal

from config import DEFAULT_GAS_LIMIT, NATIVE_DECIMALS


class GasCostCalculator:
    def __init__(self, gas_limit: int = DEFAULT_GAS_LIMIT) :
        self.gas_limit = gas_limit

    def calculate_gas_cost_eth(self, gas_price_wei: int) :
        gas_cost_wei = gas_price_wei * self.gas_limit
        return Decimal(gas_cost_wei) / (10 ** NATIVE_DECIMALS)

    def calculate_gas_cost_quote(
        self,
        gas_price_wei: int,
        eth_price_quote: Decimal,
    ) :
        gas_cost_eth = self.calculate_gas_cost_eth(gas_price_wei)
        return gas_cost_eth * eth_price_quote
