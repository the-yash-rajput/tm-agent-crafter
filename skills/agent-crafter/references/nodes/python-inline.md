# `functional` / `python_inline`

Sandboxed Python. Reach for it for anything deterministic — parsing, arithmetic, reshaping state,
building a reply string. It costs nothing and never hallucinates, so prefer it over an LLM node
whenever the logic is expressible in code.

```json
{"node_type": "functional", "function_type": "python_inline",
 "python_inline": {
   "code": "def run(state):\n    n = state.get('number', 0)\n    state['is_even'] = n % 2 == 0\n    return state",
   "max_memory_mb": 256}}
```

`function_type` must be `python_inline`, and remember `functional` configs also carry
`agent_call` and `rag` sub-dicts — leave them at their defaults or omit them.

## The contract

Define `def run(state)`. Return the whole mutated `state` (house style, and what every production
agent here does) or just a dict of updates — both merge. Anything you write must be declared in
`state_schema` or it will not survive to the next node.

## Never write `import` inside `run()`

RestrictedPython blocks it and the node fails at runtime with `__import__ not found`. You do not
need it: these are already injected as globals, so use them directly.

| Available | Use as |
|---|---|
| `re` | `re.search(r'-?\d+', text)` |
| `json` | `json.loads(...)` / `json.dumps(...)` |
| `math` | `math.sqrt(...)` |
| `datetime`, `date`, `timedelta` | `datetime.now()` |
| `Counter` | `Counter(items)` |

`os`, `sys`, `subprocess`, `socket` and the filesystem are unavailable by design. The node runs
in an isolated child process with a timeout and the `max_memory_mb` cap.

## Guarding against missing state

Use `state.get('k', default)` rather than `state['k']`. A `KeyError` fails the whole run, whereas
a default lets a branch handle the empty case. This matters most on the first node, which sees
only what the caller supplied plus `state_schema` defaults.

## Worked example

```python
def run(state):
    m = re.search(r'-?\d+', state.get('message') or '')
    state['number'] = int(m.group()) if m else 0
    state['is_even'] = state['number'] % 2 == 0
    return state
```

Verified working: routed correctly through a paired-complementary conditional split and returned
`7 is odd`.
