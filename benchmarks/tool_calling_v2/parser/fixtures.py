"""Versioned diagnostic parser inputs. The original v1 fixture file is immutable."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
V1 = ROOT / "benchmarks/tool_calling/fixtures/minicpm5_parser_fixtures.json"
VERSION = "ij06-native-1.0.0"
LEXICAL_VERSION = "ij06-native-1.1.0"


def tool(name, properties, required):
    return {"type": "function", "function": {
        "name": name, "description": "Synthetic parser qualification marker.",
        "parameters": {"type": "object", "properties": properties,
                       "required": required, "additionalProperties": False},
    }}


def param(name, body):
    return f'<param name="{name}">{body}</param>'


def call(name, *parameters):
    return f'<function name="{name}">' + "".join(parameters) + "</function>"


def cdata(value):
    return "<![CDATA[" + value + "]]>"


def build(include_lexical=False):
    original = json.loads(V1.read_text(encoding="utf-8"))
    tools = original["tools"] + [
        tool("echo_text", {"text": {"type": "string", "maxLength": 256}}, ["text"]),
        tool("typed_probe", {
            "count": {"type": "integer"}, "amount": {"type": "number"},
            "enabled": {"type": "boolean"}, "nothing": {"type": "null"},
        }, ["count", "amount", "enabled", "nothing"]),
    ]
    cases = []

    def add(case_id, native_output, calls=None, *, reasoning=None, content=None, reject=None, layer=None):
        entry = {"id": case_id, "native_output": native_output, "expect": "exact", "calls": calls or []}
        if reasoning is not None:
            entry["reasoning"] = reasoning
        if content is not None:
            entry["content"] = content
        if reject:
            entry.update(expect="reject", rejection=reject, layer=layer)
        cases.append(entry)

    def expected(name, **kwargs):
        return {"name": name, "arguments": kwargs}

    def echo(value):
        return call("echo_text", param("text", value))

    for index, value in enumerate((
        "", "plain text", "你好，评测", "包装📦", "e\u0301 / é", "１２３", 'quote " and \\',
        "  leading", "trailing  ", "\t both \t", "עברית", "日本語", "مرحبا",
    )):
        add(f"text-{index:02}", echo(value), [expected("echo_text", text=value)])

    for index, value in enumerate((
        "a\nb", "  \n 保留首尾  \n", " < > & ", "&amp; &lt; &#x4E00;", "</param>",
        "</function>", '<function name="echo_text">', "<think>literal</think>",
        "✨\n&<>", "one\r\ntwo", "  ampersand & ", "x" * 256,
    )):
        add(f"cdata-{index:02}", echo(cdata(value)), [expected("echo_text", text=value)])

    # The official MiniCPM5 template uses CDATA for newline-bearing values.
    # The v1 whitespace fixture still exists and is still scored as written.
    raw = next(c for c in original["fixtures"] if c["id"] == "fx-valid-whitespace-between-tags")
    add("v1-whitespace-observation", raw["native_output"], [
        expected("get_purchase_order", order_id="\n    PO-2026-0333\n  "),
        expected("get_purchase_order", order_id="PO-2026-0334"),
    ])
    add("v1-whitespace-template-conformant", raw["native_output"].replace(
        "\n    PO-2026-0333\n  ", cdata("\n    PO-2026-0333\n  ")), cases[-1]["calls"])

    for index, (count, amount, enabled) in enumerate((
        (0, 0, False), (1, 0.001, True), (-1, -2.75, False), (7, 100000, True),
        (2147483647, 0.5, True), (-2147483648, 0.125, False), (17, 1.25, True),
        (10, -81.04, True), (2, 3.14159, False), (12, 9999.99, True),
        (13, -0.25, False), (4, 1e-5, True),
    )):
        args = {"count": count, "amount": amount, "enabled": enabled, "nothing": None}
        pairs = list(args.items())
        args_xml = [param(key, json.dumps(value)) for key, value in (pairs[index % 4:] + pairs[:index % 4])]
        add(f"typed-{index:02}", call("typed_probe", *args_xml), [expected("typed_probe", **args)])

    for index, fields in enumerate((
        {"unit": "个"}, {"unit": "箱", "price": 1.30}, {"price": 0}, {},
        {"name": "包装📦", "unit": "包"}, {"name": "含引号 \""}, {"name": ""},
        {"name": "前\n后"}, {"name": "  preserve  ", "price": 25.71}, {"price": 100},
    )):
        sku = f"SKU-{index:04}"
        add(f"nested-{index:02}", call("update_product_record", param("sku", sku),
            param("fields", json.dumps(fields, ensure_ascii=True))),
            [expected("update_product_record", sku=sku, fields=fields)])

    for index, values in enumerate((
        ("北京", "上海"), ("A", ""), ("a & b", "</param>"), ("🛍️", "📦"),
        (" 1 ", " 2 "), ("1\n3", "4"), ('"quoted"', "\\escaped"),
        ("你好", "你好"), ("e\u0301", "é"), ("1", "2", "3"), ("一", "二", "三"),
        ("", "", ""),
    )):
        add(f"multiple-{index:02}", ("\n" if index % 2 else "").join(echo(cdata(value)) for value in values),
            [expected("echo_text", text=value) for value in values])

    for index, reasoning in enumerate(("推理", "isolated", "🧠", "工具不会执行。", "a\nb", 'quotes "')):
        add(f"reasoning-{index:02}", f"<think>\n{reasoning}\n</think>\n\n" + echo("visible call"),
            [expected("echo_text", text="visible call")], reasoning=reasoning)

    valid = echo("control")
    for suffix_length in (1, 6, 11, 12, 16, 21, 27, 34, 39):
        add(f"truncation-{suffix_length:02}", valid[:-suffix_length], reject="incomplete tags", layer="native")
    for index, payload in enumerate(("x", "  ", "测试", "</param>", "line 1\nline 2", " < & >", "📦")):
        add(f"unclosed-cdata-{index:02}", echo("<![CDATA[" + payload),
            reject="unclosed CDATA", layer="native")
    for index, payload in enumerate(("control", "different", "一致", "📦", "", " ")):
        add(f"duplicate-param-{index:02}", call("echo_text", param("text", "control"), param("text", payload)),
            reject="duplicate parameter", layer="native")
    for index, fields in enumerate((
        '{"unit":"箱","unit":"包"}', '{"unit":"箱","unit":"箱"}',
        '{"price":5,"price":6}', '{"name":"x","name":"y"}',
        '{"name":"x","na\\u006de":"y"}',
    )):
        add(f"duplicate-json-{index:02}", call("update_product_record", param("sku", "SKU-0001"), param("fields", fields)),
            reject="duplicate JSON key", layer="arguments")
    for index, fields in enumerate((
        '{"unit":"托盘"}', '{"price":false}', '{"price":null}', '{"name":1}',
        '{"name":"ok","unexpected":true}', '{"name":"\\ud800"}', '{"name":"\\udc00"}',
        '{"price":1e999}', '{"price":NaN}', '{"price":Infinity}', '{"unit":',
        '{"unit":"箱",}', '[]', 'null', 'true', '"x"', '{} trailing',
    )):
        add(f"invalid-nested-{index:02}", call("update_product_record", param("sku", "SKU-0001"), param("fields", fields)),
            reject="invalid nested JSON or schema", layer="arguments")
    for length in (257, 512, 1024, 2048):
        add(f"over-length-{length:04}", echo(cdata("x" * length)), reject="length cap", layer="arguments")
    for name in ("undeclared", "echo", "ECHO_TEXT", "echo_text_2"):
        add(f"unknown-{name}", call(name, param("text", "control")), reject="undeclared tool", layer="native")

    for index, key in enumerate(("unexpected", "Text", " text", "text ", "文本")):
        add(f"unknown-param-{index:02}", call("echo_text", param(key, "control")),
            reject="undeclared parameter", layer="native")
    add("required-missing", call("echo_text"), reject="missing required property", layer="arguments")
    add("function-unclosed", valid.removesuffix("</function>"), reject="missing function close", layer="native")
    add("parameter-unclosed", valid.replace("</param>", ""), reject="missing parameter close", layer="native")
    add("without-tools", "No tool needed.", content="No tool needed.")
    add("entity-in-cdata", echo(cdata("a&amp;b")), [expected("echo_text", text="a&amp;b")])
    add("entity-as-unwrapped-text-observation", echo("a&amp;b"), [expected("echo_text", text="a&amp;b")])

    if include_lexical:
        for index, char in enumerate(("\x00", "\x01", "\x08", "\t", "\n", "\x0b", "\x0c", "\r")):
            raw_fields = '{"name":"prefix' + char + 'suffix"}'
            valid_fields = json.dumps({"name": "prefix" + char + "suffix"})
            add(f"unescaped-control-{index}", call("update_product_record",
                param("sku", "SKU-0001"), param("fields", raw_fields)),
                reject="unescaped control in nested JSON string", layer="native")
            add(f"escaped-control-{index}", call("update_product_record",
                param("sku", "SKU-0001"), param("fields", valid_fields)),
                [expected("update_product_record", sku="SKU-0001", fields={"name": "prefix" + char + "suffix"})])

    assert len(cases) >= 120 and len({case["id"] for case in cases}) == len(cases)
    return {"version": LEXICAL_VERSION if include_lexical else VERSION, "tools": tools, "fixtures": cases}


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=True, indent=2))
