import py.config_loader as config_loader

"""
calculate_up_to_date_pricing.py
--------------------------------
Calculates up-to-date cloud pricing using formulas, workload, and
live price fetchers for AWS and Azure (from cloud_price_fetcher.py).

Expected companion file:
  cloud_price_fetcher.py — implements:
    fetch_aws_price(service_name: str, region: str) -> dict
    fetch_azure_price(service_name: str, region: str) -> dict
"""

import json
import ast
import operator as op
from math import ceil, floor
from pathlib import Path

# Import your fetcher functions
from cloud_price_fetcher import fetch_aws_price, fetch_azure_price

# ---------------------------------------------------------------------
# Safe expression evaluator (for formulas)
# ---------------------------------------------------------------------
OPS = {
    ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul, ast.Div: op.truediv,
    ast.Pow: op.pow, ast.Mod: op.mod, ast.FloorDiv: op.floordiv,
    ast.UAdd: op.pos, ast.USub: op.neg,
}
FUNCS = {"ceil": ceil, "floor": floor, "min": min, "max": max, "abs": abs, "round": round}

def safe_eval(expr, names):
    """Safely evaluate arithmetic expressions used in formulas.json."""
    node = ast.parse(expr, mode="eval")

    def _eval(n):
        if isinstance(n, ast.Expression): return _eval(n.body)
        if isinstance(n, ast.Constant): return n.value
        if isinstance(n, ast.Num): return n.n
        if isinstance(n, ast.BinOp): return OPS[type(n.op)](_eval(n.left), _eval(n.right))
        if isinstance(n, ast.UnaryOp): return OPS[type(n.op)](_eval(n.operand))
        if isinstance(n, ast.Name):
            if n.id in names: return names[n.id]
            raise NameError(f"Unknown variable: {n.id}")
        if isinstance(n, ast.Call):
            fn = n.func.id if isinstance(n.func, ast.Name) else None
            if fn in FUNCS:
                args = [_eval(a) for a in n.args]
                return FUNCS[fn](*args)
            raise ValueError(f"Function '{fn}' not allowed")
        raise ValueError(f"Unsupported node {type(n)}")
    return _eval(node)

# ---------------------------------------------------------------------
# Value resolver
# ---------------------------------------------------------------------
def resolve_value(param_key, workload, service_prices):
    """Find a parameter value from workload inputs or fetched prices."""
    if param_key in workload:
        return workload[param_key]
    if param_key in service_prices:
        return service_prices[param_key]
    return 0


def get_service_name(provider: str, neutral_name: str) -> str:
    mapping = config_loader.load_json_file("service_mapping.json")
    return mapping.get(neutral_name, {}).get(provider, neutral_name)

# ---------------------------------------------------------------------
# Main computation
# ---------------------------------------------------------------------
def main():
    print("🔄 Loading configuration files...")
    formulas = config_loader.load_json_file("formulas.json")["formulas"]
    providers = config_loader.load_json_file("service_calc_params.json")
    workload = config_loader.load_json_file("base_workload.json")["inputs"]

    credentials = config_loader.load_credentials_file()
    aws_region = credentials.get("aws", {}).get("region", "eu-central-1")
    azure_region = credentials.get("azure", {}).get("region", "westeurope")
    gcp_region = credentials.get("gcp", {}).get("region", "europe-west3")

    output = {}

    for provider_name, services in providers.items():
        print(f"\n⚙️  Processing provider: {provider_name.upper()}")
        provider_total = 0.0
        output[provider_name] = {}

        for provider_name, services in providers.items():
            provider_total = 0.0
            output[provider_name] = {}

            for neutral_service_name, service_def in services.items():
                # Get provider-specific service name
                provider_service_name = get_service_name(provider_name, neutral_service_name)
                print(f"  • Fetching {provider_name.upper()} → {provider_service_name}")

                # Fetch pricing dynamically using provider-specific name
                if provider_name == "aws":
                    service_prices = fetch_aws_price(provider_service_name, aws_region)
                elif provider_name == "azure":
                    service_prices = fetch_azure_price(provider_service_name, azure_region)
                else:
                    service_prices = {}

            entry = dict(service_prices)
            calc_cost = 0.0
            formula_refs = []
            if "formula_ref" in service_def:
                formula_refs = [service_def["formula_ref"]]
            elif "formula_refs" in service_def:
                formula_refs = service_def["formula_refs"]

            for fref in formula_refs:
                formula = formulas.get(fref)
                if not formula:
                    continue
                expr = formula.get("expression", "")
                param_defs = formula.get("parameters", {})
                param_map = service_def.get("parameters", {})

                # Build names for formula evaluation
                names = {}
                for pname in param_defs.keys():
                    mapped = param_map.get(pname, pname)
                    val = resolve_value(mapped, workload, service_prices)
                    entry[mapped] = val
                    names[pname] = val

                if expr.strip():
                    cost_part = safe_eval(expr, names)
                    calc_cost += float(cost_part)

            entry["calculated_cost"] = round(calc_cost, 8)
            provider_total += calc_cost
            output[provider_name][service_name] = entry

        output[provider_name]["total_cost"] = round(provider_total, 8)

    # Add workload to the output for traceability
    output["example_workload"] = workload

    # Write final JSON
    Path("output_with_costs.json").write_text(json.dumps(output, indent=2))
    print("\n✅ Wrote output_with_costs.json successfully!")

# ---------------------------------------------------------------------
if __name__ == "__main__":
    main()
