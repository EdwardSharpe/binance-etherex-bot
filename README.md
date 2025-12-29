# Binance-Etherex Arb Bot

Quick start

1) Install deps
```
pip install -r requirements.txt
```
2) Run

Defaults to "weth_usdc" pool
```
python ./main.py
```

Select a pool from weth_usdc, weth_usdt, weth_wbtc, linea_usdc, linea_usdc_low_tvl
```
ACTIVE_POOL="weth_usdc" python ./main.py
```

Check `config.py` for pool keys and endpoints. Logs write to `arb_opportunities_<pool>.log` and `arb_best_trade_<pool>.log`.

Full architecture write up - https://docs.google.com/document/d/1MZ3BpHnkJlzNYGHR3f35OPk1msbP9YQ3OAfbw-kMK98/edit?usp=sharing