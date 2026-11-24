# Reject unsupported explicit tool choices in chat completions

## Observed behavior

With a pinned b12359 server that exposes a `lookup_account` tool, submit
the following Chat Completions request. The affected path treats the
object-valued selector as the default `auto` and can select the available
tool even though the client explicitly named a different function.

```json
{
  "model": "minicpm5-2b",
  "messages": [{"role": "user", "content": "Use lookup_account for Orchid Works."}],
  "tools": [{
    "type": "function",
    "function": {
      "name": "lookup_account",
      "parameters": {
        "type": "object",
        "properties": {"company": {"type": "string"}},
        "required": ["company"],
        "additionalProperties": false
      }
    }
  }],
  "tool_choice": {"type": "function", "function": {"name": "not_exposed"}},
  "temperature": 0,
  "stream": false
}
```

## Proposed change

Validate the type before reading `tool_choice` through the string default
in `oaicompat_chat_params_parse`. Return HTTP 400 for unsupported explicit
types, including an object on the pinned string-only implementation.
Preserve the behavior of omitted and null choices and of the supported
`auto`, `none` and `required` strings. Recheck the current upstream
selector contract before applying this pinned patch.

## Regression evidence

Repeat the request with `stream` set to true. Test omitted, null, each
supported string, unsupported string, number and unsupported named
object in both response modes. The pinned CPU control exercised all
16 pairs. The original rejected the invalid string in both modes, and
the patch also rejected the numeric and object forms in both modes.
All ten valid requests preserved their observed semantics.
 [Patch](llama-b12359-explicit-tool-choice.patch)
 · [Control runner](../../benchmarks/root_cause/probe_tool_choice.py)
 · [Paired evidence](../../evidence/IJ07/root_causes/explicit_tool_choice_cpu.json)
