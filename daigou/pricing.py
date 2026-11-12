"""Shipping fee rules (Japan -> Taiwan air line).

Weight is rounded up to the next whole kilogram. Up to the last row of
`table` the price is read straight from the table; above it each bracket in
`per_kg` gives a per-kilogram price for the whole weight. The price never
drops below the heaviest table row.

All numbers are defaults an admin can change in 後台 > 系統設定.
"""
import json
import math

DEFAULT_RULES = {
    "currency": "TWD",
    "line": "空運專線（包稅）",
    "lead_time": "航班日 + 2 日",
    "table": [[1, 290], [2, 570], [3, 830], [4, 1070], [5, 1290],
              [6, 1500], [7, 1700], [8, 1900], [9, 2100], [10, 2300]],
    "per_kg": [[20, 210], [30, 195], [50, 190], [9999, 180]],
    "max_kg": 35,
}


def load_rules(raw):
    if not raw:
        return DEFAULT_RULES
    try:
        rules = json.loads(raw)
        rules["table"] and rules["per_kg"]  # noqa: B018 - shape check
        return rules
    except (ValueError, KeyError, TypeError):
        return DEFAULT_RULES


def chargeable_kg(weight):
    weight = float(weight)
    if weight <= 0:
        raise ValueError("weight must be positive")
    return max(1, math.ceil(round(weight, 3)))


def shipping_fee(weight, rules=None):
    rules = rules or DEFAULT_RULES
    kg = chargeable_kg(weight)
    table = sorted(rules["table"])
    for limit, price in table:
        if kg <= limit:
            return int(price)
    floor = table[-1][1]
    for limit, per_kg in sorted(rules["per_kg"]):
        if kg <= limit:
            return int(max(floor, kg * per_kg))
    return int(max(floor, kg * sorted(rules["per_kg"])[-1][1]))
