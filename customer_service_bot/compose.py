from __future__ import annotations
import os
from typing import Dict, List
from .perception import PerceptionResult
import os
os.environ["GRPC_VERBOSITY"] = "ERROR"
os.environ["GRPC_LOG_SEVERITY_THRESHOLD"] = "ERROR"

# Optional Gemini-based tone polish (facts/bullets must remain unchanged)
def polish_with_gemini(text: str, style_hint: str = "") -> str:
    """Polish tone/clarity ONLY. Do NOT change facts or bullets."""
    try:
        api_key = os.getenv("GEMINI_API_KEY", "")
        if not api_key:
            print("[Gemini] Skipped: GEMINI_API_KEY not set")
            return text
        import google.generativeai as genai
        genai.configure(api_key=api_key)

        available = []
        for m in genai.list_models():
            methods = set(getattr(m, "supported_generation_methods", []) or [])
            if "generateContent" in methods:
                available.append(m.name)
        if not available:
            print("[Gemini] No models support generateContent for this account.")
            return text

        preferred = [
            "models/gemini-2.0-flash",
            "models/gemini-2.0-flash-lite",
            "models/gemini-1.5-flash",
            "models/gemini-1.5-flash-8b",
            "models/gemini-1.5-pro",
        ]
        model_name = next((p for p in preferred if p in available), available[0])
        print(f"[Gemini] Using model: {model_name}")

        model = genai.GenerativeModel(model_name)
        prompt = (
            "Improve clarity and empathy WITHOUT changing facts. "
            "KEEP every bullet line that starts with '-' exactly as-is (do not merge into prose). "
            "Do NOT invent dates/times not present in bullets; do NOT alter numerals (IDs, amounts, ETAs). "
            "Start with one concise paragraph that clearly states completed actions and next steps with timeframes. "
            "Then show the original bullet list unchanged.\n\n"
            f"STYLE HINT: {style_hint}\n\n"
            + text
        )
        resp = model.generate_content(prompt)
        out = getattr(resp, "text", "") or (
            resp.candidates[0].content.parts[0].text if getattr(resp, "candidates", None) else ""
        )
        out = (out or "").strip()
        return "[Polished by Gemini] " + out if out else text
    except Exception as e:
        print("[Gemini] Error:", repr(e))
        return text

# Compose deterministic reply paragraph + bullet facts
def compose_sections(p: PerceptionResult, actions: Dict[str, str], facts: List[str]) -> str:
    # Completed actions summary
    done_lines = []
    if actions.get("ticket_id"):
        done_lines.append(f"Created support case {actions['ticket_id']} and documented your issue.")
    if actions.get("refund_id"):
        done_lines.append(f"Initiated a refund (ID {actions['refund_id']}).")
    if actions.get("replacement_id"):
        done_lines.append(f"Queued a replacement shipment (ID {actions['replacement_id']}).")
    if actions.get("shipment_id"):
        done_lines.append(f"Dispatched the missing part (shipment {actions['shipment_id']}).")
    if actions.get("callback"):
        done_lines.append(actions["callback"])
    if actions.get("escalation_id"):
        done_lines.append(f"Escalated your case internally (ID {actions['escalation_id']}).")
    if actions.get("credit_id"):
        done_lines.append(f"Applied a credit (ID {actions['credit_id']}).")
    if not done_lines:
        done_lines.append("Documented your report and confirmed next steps.")

    # Friendly ordering for missing-part scenarios
    if p.intent == "missing_part":
        if actions.get("credit_id"):
            for i, line in enumerate(done_lines):
                if line.startswith("Applied a credit"):
                    done_lines[i] = f"We also applied a small courtesy credit (ID {actions['credit_id']})."
                    break

        def _rank_missing_part(s: str) -> int:
            if s.startswith("Dispatched the missing part"):
                return 0
            if s.startswith("Created support case"):
                return 1
            if s.startswith("We also applied") or s.startswith("Applied a credit"):
                return 2
            return 3

        done_lines.sort(key=_rank_missing_part)

    # Next-steps timelines
    next_lines = []
    if actions.get("refund_eta"):
        next_lines.append(f"Refund posts by {actions['refund_eta']}.")
    if actions.get("delivery_eta"):
        next_lines.append(f"Replacement delivery ETA {actions['delivery_eta']}.")
    if actions.get("shipment_eta"):
        next_lines.append(f"Missing part delivery ETA {actions['shipment_eta']}.")
    if p.intent == "billing_issue":
        next_lines.append("Billing audit update within 1–2 business days.")
    if p.intent == "followup_existing":
        next_lines.append("We will summarize prior actions and outcomes today.")
    if p.intent == "cancellation_threat":
        next_lines.append("Retention specialist will reach out today.")

    # Intro based on intent/emotion
    if p.intent == "praise":
        agent_note = f" — I'll make sure {actions['agent_name']} sees this." if actions.get("agent_name") else " — we really appreciate it."
        intro = "Thanks so much for the shout-out" + agent_note
    elif p.intent == "missing_part":
        intro = "Thanks for flagging this — we've shipped the missing part."
    elif p.intent == "defect_report":
        intro = "I know how frustrating hardware issues can be — here's what we've done."
    else:
        intro_map = {
            "angry":   "I'm truly sorry for the trouble you've experienced.",
            "confused":"I'm happy to clarify this for you.",
            "polite":  "Thanks for reaching out — happy to help.",
            "neutral": "Thanks for reaching out — let's get this resolved.",
        }
        intro = intro_map.get(p.emotion, "Thanks for reaching out — let's get this resolved.")

    para = f"{intro} What we did: " + " ".join(done_lines) + " Next steps & timelines: " + (" ".join(next_lines) or "We'll keep you posted.")
    bullets = "\n- " + "\n- ".join(facts) if facts else ""
    closing = "\nIf there's anything else you'd like us to address, please let me know."
    return para + bullets + closing
