import json
import operator
from math import isfinite


PRODUCT_PRICES = {"ノート": 250, "ペン": 120, "消しゴム": 80}
OPERATIONS = {
    "add": operator.add,
    "subtract": operator.sub,
    "multiply": operator.mul,
    "divide": operator.truediv,
}


def get_product_price(product):
    if not isinstance(product, str) or product not in PRODUCT_PRICES:
        raise ValueError("登録されていない商品です。")
    return {"product": product, "price_yen": PRODUCT_PRICES[product]}


def calculate(operation, a, b):
    if not isinstance(operation, str) or operation not in OPERATIONS:
        raise ValueError("対応していない演算です。")
    if any(type(value) not in (int, float) or not isfinite(value) for value in (a, b)):
        raise ValueError("a と b には有限の数値を指定してください。")
    result = OPERATIONS[operation](a, b)
    if not isfinite(result):
        raise ValueError("計算結果が数値の範囲を超えました。")
    return {"result": result}


TOOLS = [
    {
        "type": "function",
        "name": "get_product_price",
        "description": "商品の価格を円で取得する。登録商品はノート、ペン、消しゴム。",
        "parameters": {
            "type": "object",
            "properties": {"product": {"type": "string"}},
            "required": ["product"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "calculate",
        "description": "四則演算。subtract は a-b、divide は a/b。",
        "parameters": {
            "type": "object",
            "properties": {
                "operation": {"type": "string", "enum": list(OPERATIONS)},
                "a": {"type": "number"},
                "b": {"type": "number"},
            },
            "required": ["operation", "a", "b"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]

TOOL_FUNCTIONS = {
    "get_product_price": get_product_price,
    "calculate": calculate,
}


def execute_tool(name, arguments_json):
    if not isinstance(name, str) or name not in TOOL_FUNCTIONS:
        return {"error": "未登録のツールです。"}
    try:
        arguments = json.loads(arguments_json)
        if not isinstance(arguments, dict):
            raise ValueError("ツールの引数は JSON オブジェクトにしてください。")
        return TOOL_FUNCTIONS[name](**arguments)
    except (ValueError, TypeError, ArithmeticError) as exc:
        return {"error": str(exc)}
