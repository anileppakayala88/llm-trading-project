"""
Claude API Client — LLM Reasoning Layer
LLM Trading Project

Handles all calls to the Anthropic API for trade plan generation.
Reads system prompts from modules/*/prompts/system_prompt.md
Reads project context from CLAUDE.md
"""

import os
import json
from pathlib import Path
from typing import Optional
import anthropic

# ── Config ────────────────────────────────────────────────────────────────────

ROOT = Path(__file__).parent.parent.parent
CLAUDE_MD = ROOT / "CLAUDE.md"
PROMPTS = {
    "orb_mmxm":    ROOT / "modules/module1_orb_mmxm/prompts/system_prompt.md",
    "pm_sweep_smt":ROOT / "modules/module2_pm_sweep/prompts/system_prompt.md",
    "scam_range":  ROOT / "modules/module3_scam_range/prompts/system_prompt.md",
}

MODEL_DEV  = os.getenv("CLAUDE_MODEL_DEV",  "claude-haiku-4-5-20251001")
MODEL_LIVE = os.getenv("CLAUDE_MODEL_LIVE", "claude-sonnet-4-6")
PIPELINE_MODE = os.getenv("PIPELINE_MODE", "advisory")

# ── Client ────────────────────────────────────────────────────────────────────

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def get_model() -> str:
    """Use Haiku in dev/advisory, Sonnet in live automation."""
    if PIPELINE_MODE in ("conditional_auto", "semi_auto"):
        return MODEL_LIVE
    return MODEL_DEV


def load_system_prompt(module: str) -> str:
    """Load module-specific system prompt + CLAUDE.md context."""
    claude_md = CLAUDE_MD.read_text() if CLAUDE_MD.exists() else ""
    module_prompt_path = PROMPTS.get(module)

    if module_prompt_path and module_prompt_path.exists():
        module_prompt = module_prompt_path.read_text()
    else:
        module_prompt = f"You are an expert trading assistant analyzing {module} signals."

    return f"{claude_md}\n\n---\n\n## Module-Specific Instructions\n\n{module_prompt}"


# ── Main Call ─────────────────────────────────────────────────────────────────

def generate_trade_plan(
    module: str,
    live_context: dict,
    analog_days: Optional[list] = None,
    kill_switch: Optional[dict] = None,
) -> dict:
    """
    Call Claude API to generate a trade plan for the given module and context.

    Args:
        module: "orb_mmxm" | "pm_sweep_smt" | "scam_range"
        live_context: Current session data (from feature builder)
        analog_days: Top 10 similar historical days (from similarity engine)
        kill_switch: Kill switch evaluation result

    Returns:
        dict with keys: plan (raw JSON), narrative (str), confidence (str), model_used (str)
    """

    system_prompt = load_system_prompt(module)

    user_message = build_user_message(
        module=module,
        live_context=live_context,
        analog_days=analog_days or [],
        kill_switch=kill_switch or {},
    )

    model = get_model()

    try:
        response = client.messages.create(
            model=model,
            max_tokens=1000,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_message}
            ]
        )

        raw_text = response.content[0].text

        # Attempt to parse JSON from response
        try:
            plan = json.loads(raw_text)
        except json.JSONDecodeError:
            # If not valid JSON, return as narrative only
            plan = {
                "narrative": raw_text,
                "confidence": "low",
                "parse_error": True
            }

        return {
            "plan": plan,
            "narrative": plan.get("narrative", raw_text),
            "confidence": plan.get("confidence", "low"),
            "model_used": model,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }

    except Exception as e:
        return {
            "plan": None,
            "narrative": f"Claude API error: {str(e)}",
            "confidence": "no_signal",
            "model_used": model,
            "error": str(e),
        }


def build_user_message(
    module: str,
    live_context: dict,
    analog_days: list,
    kill_switch: dict,
) -> str:
    """Build the structured user message sent to Claude."""

    kill_switch_blocked = kill_switch.get("blocked", False)
    kill_switch_reasons = kill_switch.get("reasons", [])

    return f"""
## Today's Live Session Context

Module: {module}
Date: {live_context.get('session_date', 'unknown')}
Instrument: {live_context.get('instrument', 'MNQ1!')}

### Kill Switch Status
Blocked: {kill_switch_blocked}
Reasons: {', '.join(kill_switch_reasons) if kill_switch_reasons else 'None — all clear'}

### Live Data
{json.dumps(live_context, indent=2)}

### Top Analog Days (Historical Similarity)
{json.dumps(analog_days[:10], indent=2) if analog_days else 'No analog days available yet.'}

---

Based on the above context, generate a trade plan for this session.
Respond ONLY with a valid JSON object matching the output schema defined in CLAUDE.md.
Include a 'narrative' field with a plain English summary of the plan.
If kill switch is blocked, set confidence to 'no_signal' and explain why in narrative.
"""


# ── Usage Example ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Test call with sample context
    sample_context = {
        "session_date": "2026-05-10",
        "instrument": "MNQ1!",
        "premarket": {
            "high": 19234.50,
            "low": 19198.25,
            "range": 36.25,
        },
        "pm1_range": {"high": 19230.00, "low": 19198.25},
        "pm2_range": {"high": 19234.50, "low": 19210.00},
        "sweep_detected": True,
        "sweep_side": "bear_sweep",
        "sweep_level": "pm2_low",
        "smt_es": True,
        "smt_ym": True,
        "volume_ratio": 1.25,
        "current_price": 19218.00,
        "time_et": "09:37",
    }

    result = generate_trade_plan(
        module="pm_sweep_smt",
        live_context=sample_context,
        analog_days=[],
        kill_switch={"blocked": False, "reasons": []},
    )

    print(json.dumps(result, indent=2))
