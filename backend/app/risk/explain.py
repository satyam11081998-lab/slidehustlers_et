"""
KAVACH — Alert Narration (optional LLM, deterministic fallback)
==============================================================

Turns an alert's evidence bundle into a short control-room narrative. This is
the *only* place an LLM touches the system, and it is strictly a garnish:

* If ``KAVACH_DETERMINISTIC=1`` (default for the hosted demo) **or** no
  ``OPENAI_API_KEY`` is set **or** the SDK/network is unavailable, we return a
  crisp template built purely from the evidence. The demo never waits on, or
  fails because of, a network call.
* If a key is present and deterministic mode is off, we ask the model to
  phrase the same evidence more naturally. The facts still come from the
  engine — the model only rewords them, so it cannot invent a hazard.
"""

from __future__ import annotations

import os

_RULE_PLAIN = {
    "R1": "gas is building up around a crew working inside a confined space",
    "R2": "hot work is happening next to a zone where gas is rising",
    "R3": "the confined-space entry went ahead without isolating the gas main",
    "R4": "the shift handover did not pass on an unacknowledged pressure drift",
    "R5": "entry was cleared on a single-point gas test that missed the rear of the chamber",
    "R6": "a valve was throttled, pushing back-pressure toward the occupied space",
    "R7": "several gas channels are rising together, corroborating the trend",
    "R8": "an elevated reading was explained by an active calibration and set aside",
}


def deterministic_narrative(alert: dict) -> str:
    """A faithful, fact-only narrative assembled from the evidence bundle."""
    zone = alert.get("zone_name") or alert.get("zone")
    band = alert.get("band_name", "alert").upper()
    clock = alert.get("clock", "")
    reasons = [_RULE_PLAIN.get(c["id"], c["label"]) for c in alert.get("rules", [])]
    reason_txt = "; ".join(reasons) if reasons else "multiple compounding factors"

    sig = alert.get("signals", {})
    rising = sig.get("rising_gas", {})
    press = sig.get("gas_main_pressure", {})
    bits = []
    for s, d in list(rising.items())[:3]:
        bits.append(f"{s} at {d['value']}")
    for s, d in list(press.items())[:2]:
        tag = " (sub-threshold drift)" if d.get("drifting") else ""
        bits.append(f"{s} at {d['value']} kPa{tag}")
    ev = ("Key readings: " + ", ".join(bits) + ". ") if bits else ""

    permits = ", ".join(p["id"] for p in alert.get("permits", [])[:3])
    perm_txt = f"Active permits: {permits}. " if permits else ""

    return (
        f"{band} compound risk in {zone} at {clock}. "
        f"KAVACH fused {len(reasons)} signals no single alarm would connect: "
        f"{reason_txt}. {ev}{perm_txt}"
        f"Recommended: hold work, verify gas-main isolation, re-test the rear "
        f"of the chamber, and confirm the crew is clear before proceeding."
    )


def narrate(alert: dict) -> dict:
    """Return {text, source}. source is 'template' or 'llm'."""
    text = deterministic_narrative(alert)
    if os.getenv("KAVACH_DETERMINISTIC", "1") == "1":
        return {"text": text, "source": "template"}
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        return {"text": text, "source": "template"}
    try:  # pragma: no cover - exercised only with a live key
        from openai import OpenAI

        client = OpenAI(api_key=key)
        rules = "; ".join(f"{c['id']}: {c['detail']}" for c in alert.get("rules", []))
        prompt = (
            "You are a control-room safety assistant. In 3-4 sentences, explain "
            "this compound industrial-safety alert to a shift supervisor. Use ONLY "
            "the evidence provided; do not invent facts. Evidence: "
            f"zone={alert.get('zone_name')}, time={alert.get('clock')}, "
            f"band={alert.get('band_name')}, score={alert.get('score')}, "
            f"rules=[{rules}]."
        )
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=220,
        )
        llm = (resp.choices[0].message.content or "").strip()
        return {"text": llm or text, "source": "llm" if llm else "template"}
    except Exception:
        # Any failure (no SDK, no network, rate limit) → deterministic text.
        return {"text": text, "source": "template"}
