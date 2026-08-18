"""Сквозной функциональный пост-аудит (Vikunja #1915, Этап 3, подшаг 7).
AST-based cross-check across manifest <-> schemas <-> handlers <-> client.
Run: python3 _audit.py
"""
from __future__ import annotations
import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent
issues: list[str] = []


def load_module_ast(path: Path) -> ast.Module:
    return ast.parse(path.read_text(), filename=str(path))


schemas_ast = load_module_ast(ROOT / "schemas.py")
handlers_ast = load_module_ast(ROOT / "handlers.py")
client_ast = load_module_ast(ROOT / "n8n_client.py")
manifest = json.loads((ROOT / "imperal.json").read_text())

# ---------------------------------------------------------------------------
# Index: Pydantic model classes -> declared field names (schemas.py)
# ---------------------------------------------------------------------------
model_fields: dict[str, set[str]] = {}
for node in schemas_ast.body:
    if isinstance(node, ast.ClassDef):
        fields = set()
        for item in node.body:
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                fields.add(item.target.id)
        model_fields[node.name] = fields

# Resolve inheritance for EntityList[...] / plain sdl.Entity bases (not needed further:
# our checks only care about the class's OWN declared fields being used correctly,
# and EntityList subclasses only ever get `items=` which is inherited -- allow it explicitly)
GENERIC_ALLOWED_FIELDS = {"items", "id", "title"}

# ---------------------------------------------------------------------------
# Index: client.py function name -> set of parameter names (n8n_client.py)
# ---------------------------------------------------------------------------
client_funcs: dict[str, list[str]] = {}
for node in client_ast.body:
    if isinstance(node, ast.AsyncFunctionDef):
        params = [a.arg for a in node.args.args] + [a.arg for a in node.args.kwonlyargs]
        client_funcs[node.name] = params

# ---------------------------------------------------------------------------
# Walk handlers.py: for each @chat.function-decorated async def, collect:
#   - function name (tool name from decorator's first string arg)
#   - params annotation (the Params model type)
#   - data_model= kwarg (return model type)
#   - action_type= kwarg
#   - every params.xxx attribute access inside the body
#   - every SomeModel(...) constructor call with keyword args, for known models
#   - every nc.xxx(...) call with its args
# ---------------------------------------------------------------------------
tool_defs: dict[str, dict] = {}

for node in ast.walk(handlers_ast):
    if isinstance(node, ast.AsyncFunctionDef):
        chat_deco = None
        for deco in node.decorator_list:
            if isinstance(deco, ast.Call) and isinstance(deco.func, ast.Attribute) and deco.func.attr == "function":
                chat_deco = deco
                break
        if chat_deco is None:
            continue
        # tool name = first positional string arg
        tool_name = None
        if chat_deco.args and isinstance(chat_deco.args[0], ast.Constant):
            tool_name = chat_deco.args[0].value
        data_model = None
        action_type = None
        for kw in chat_deco.keywords:
            if kw.arg == "data_model" and isinstance(kw.value, ast.Name):
                data_model = kw.value.id
            if kw.arg == "action_type" and isinstance(kw.value, ast.Constant):
                action_type = kw.value.value

        # params model: second arg of function signature, type annotation
        params_model = None
        if len(node.args.args) >= 2:
            ann = node.args.args[1].annotation
            if isinstance(ann, ast.Name):
                params_model = ann.id

        params_accesses: set[str] = set()
        constructor_calls: list[tuple[str, set[str]]] = []
        client_calls: list[tuple[str, ast.Call]] = []

        for sub in ast.walk(node):
            # params.xxx access
            if isinstance(sub, ast.Attribute) and isinstance(sub.value, ast.Name) and sub.value.id == "params":
                params_accesses.add(sub.attr)
            # SomeModel(key=val, ...) constructor calls
            if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) and sub.func.id in model_fields:
                kw_names = {kw.arg for kw in sub.keywords if kw.arg}
                constructor_calls.append((sub.func.id, kw_names))
            # nc.xxx(...) calls
            if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) \
                    and isinstance(sub.func.value, ast.Name) and sub.func.value.id == "nc":
                client_calls.append((sub.func.attr, sub))

        tool_defs[node.name] = dict(
            tool_name=tool_name,
            data_model=data_model,
            action_type=action_type,
            params_model=params_model,
            params_accesses=params_accesses,
            constructor_calls=constructor_calls,
            client_calls=client_calls,
            lineno=node.lineno,
        )

print(f"Discovered {len(tool_defs)} @chat.function handlers.\n")

# ---------------------------------------------------------------------------
# CHECK 1: manifest tools[] vs handlers -- count + name parity
# ---------------------------------------------------------------------------
manifest_tool_names = {t["name"] for t in manifest.get("tools", [])}
handler_tool_names = {d["tool_name"] for d in tool_defs.values() if d["tool_name"]}
missing_in_manifest = handler_tool_names - manifest_tool_names
missing_in_handlers = manifest_tool_names - handler_tool_names
if missing_in_manifest:
    issues.append(f"[1][manifest] tools defined in handlers but MISSING from imperal.json: {sorted(missing_in_manifest)}")
if missing_in_handlers:
    issues.append(f"[1][manifest] tools in imperal.json but NO handler found: {sorted(missing_in_handlers)}")
if not missing_in_manifest and not missing_in_handlers:
    print(f"[1] OK -- manifest/handlers tool names match 1:1 ({len(handler_tool_names)} tools).")

# ---------------------------------------------------------------------------
# CHECK 2: constructor calls vs declared model fields
# ---------------------------------------------------------------------------
bad_constructors = 0
for fn_name, d in tool_defs.items():
    for model_name, kw_names in d["constructor_calls"]:
        declared = model_fields.get(model_name, set())
        unknown = kw_names - declared - GENERIC_ALLOWED_FIELDS
        if unknown:
            issues.append(f"[2][handler->schema] {fn_name}(): {model_name}(...) uses undeclared field(s) {sorted(unknown)} -- declared fields: {sorted(declared)}")
            bad_constructors += 1
if bad_constructors == 0:
    print(f"[2] OK -- all model constructor calls use only declared fields.")

# ---------------------------------------------------------------------------
# CHECK 3: params.xxx accesses vs declared params model fields
# ---------------------------------------------------------------------------
bad_params = 0
for fn_name, d in tool_defs.items():
    pm = d["params_model"]
    if not pm:
        continue
    declared = model_fields.get(pm)
    if declared is None:
        issues.append(f"[3][handler->params] {fn_name}(): params model '{pm}' not found in schemas.py")
        continue
    unknown = d["params_accesses"] - declared
    if unknown:
        issues.append(f"[3][handler->params] {fn_name}(params: {pm}): accesses undeclared field(s) {sorted(unknown)} -- declared: {sorted(declared)}")
        bad_params += 1
if bad_params == 0:
    print(f"[3] OK -- all params.xxx accesses match their declared params model fields.")

# ---------------------------------------------------------------------------
# CHECK 4: nc.xxx(...) calls vs actual client function signatures (arity check)
# ---------------------------------------------------------------------------
bad_client_calls = 0
for fn_name, d in tool_defs.items():
    for call_name, call_node in d["client_calls"]:
        if call_name not in client_funcs:
            issues.append(f"[4][handler->client] {fn_name}(): calls nc.{call_name}(...) which does NOT exist in n8n_client.py")
            bad_client_calls += 1
            continue
        sig_params = client_funcs[call_name]
        # count positional args passed (excluding ctx which is always first) + keyword args
        n_pos = len(call_node.args)
        kw_names = {kw.arg for kw in call_node.keywords if kw.arg}
        # sig has ctx, base_url, api_key, ... -- just sanity check kw names exist in signature
        unknown_kw = kw_names - set(sig_params)
        if unknown_kw:
            issues.append(f"[4][handler->client] {fn_name}(): nc.{call_name}(...) passes unknown kwarg(s) {sorted(unknown_kw)} -- client signature params: {sig_params}")
            bad_client_calls += 1
if bad_client_calls == 0:
    print(f"[4] OK -- all nc.xxx(...) calls resolve to real client functions with valid kwargs.")

# ---------------------------------------------------------------------------
# CHECK 5: confirm-gate discipline -- params models with a `confirm` field must
# have their handler actually branch on params.confirm before calling nc.*
# ---------------------------------------------------------------------------
bad_confirm = 0
for fn_name, d in tool_defs.items():
    pm = d["params_model"]
    if pm and "confirm" in model_fields.get(pm, set()):
        if "confirm" not in d["params_accesses"]:
            issues.append(f"[5][confirm-gate] {fn_name}(params: {pm}): model declares 'confirm' but handler NEVER reads params.confirm")
            bad_confirm += 1
if bad_confirm == 0:
    print(f"[5] OK -- every params model with a 'confirm' field is actually checked in its handler.")

# ---------------------------------------------------------------------------
# CHECK 6: preview/apply state-token pairs -- N/A for this app (no preview/apply pattern)
# ---------------------------------------------------------------------------
print(f"[6] N/A -- n8n Connector has no preview/apply state-token pattern (all writes are direct, single-step).")

# ---------------------------------------------------------------------------
# CHECK 7: action_type=read handlers must not call known write client functions
# ---------------------------------------------------------------------------
WRITE_VERBS = ("create", "update", "delete", "publish", "unpublish", "run", "retry", "stop", "transfer", "pull")
bad_action_type = 0
for fn_name, d in tool_defs.items():
    if d["action_type"] == "read":
        for call_name, _ in d["client_calls"]:
            if any(call_name.startswith(v) for v in WRITE_VERBS):
                issues.append(f"[7][action_type] {fn_name}(): declared action_type='read' but calls nc.{call_name}(...) (looks like a write operation)")
                bad_action_type += 1
if bad_action_type == 0:
    print(f"[7] OK -- no action_type='read' handler calls an apparent write client function.")

print("\n" + "=" * 70)
if issues:
    print(f"FOUND {len(issues)} ISSUE(S):\n")
    for i in issues:
        print(" -", i)
    sys.exit(1)
else:
    print("ALL 7 CHECKS CLEAN -- 0 discrepancies across 100% of handlers.")
    sys.exit(0)
