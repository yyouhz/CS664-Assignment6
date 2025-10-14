from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Optional, Dict

# Perception result structure (intent/emotion/entities)
@dataclass
class PerceptionResult:
    emotion: str                  # angry/confused/polite/neutral
    intent: str                   # refund_request/defect_report/billing_issue/cancellation_threat/missing_part/praise/...
    entities: Dict[str, str]      # order_id/phone/amount/ticket_id/serial/part_name
    churn_risk: bool
    urgency: str                  # low/medium/high

# Entity regexes (order/phone/amount/ticket/serial/part/agent)
ORDER_PATTERNS = [
    r"(?:\border|\bord|#)\s*[:\-#]?\s*(ORD[A-Z0-9]{5,})",
    r"(?:\border|\bord|#)\s*[:\-#]?\s*(ORD-[A-Z0-9\-]{5,})",
    r"(?:\border|\bord|#)\s*[:\-#]?\s*([A-Z]{2,3}-\d{4,})",
]
ORDER_RE_LIST = [re.compile(p, re.I) for p in ORDER_PATTERNS]
PHONE_RE  = re.compile(r"(\+?\d[\d\-\s]{7,}\d)")
AMOUNT_RE = re.compile(r"\$?\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.\d{1,2})|\d+(?:\.\d{1,2})?)")
TICKET_RE = re.compile(r"(TCK-\d{4}-\d{2}-\d{2}-[A-Z0-9]+|T\d{3,}|RET-\d{4}-\d{2}-\d{2}-[A-Z0-9]+)")
SERIAL_RE = re.compile(r"\b([A-Z]{2,}-[A-Z0-9]{2,}-[A-Z0-9]{2,})\b")
MISSING_PART_RE = re.compile(r"(hex key|allen key|screw|adapter|cable|charger|manual|tool)", re.I)
AGENT_MENTION_RE = re.compile(r"\b([A-Z][a-z]+)\b\s+(?:from|in|at)\s+support\b")

def analyze_emotion(text: str) -> str:
    """
    Rule-first emotion classifier with optional VADER refinement.
    Design intent:
    1. Keep decisions deterministic and cheap (no API calls).
    2. Use VADER only as a backstop to correct obvious misses in neutral/polite/confused.
    3. Never let the refinement downgrade an already “angry” classification.
    Tunables (documented here for clarity, defined inline below):
    anger_keywords / polite_keywords / confusion_keywords (extendable per domain)
    punctuation signals: “?” → uncertainty; “!” → arousal/anger
    VADER thresholds: compound ≤ −0.5 -> negative; ≥ +0.5 -> positive
    """

    # --- Block 1: Keyword/Punctuation Baseline (O(n) scan) ---
    # Intended outcome:
    #   Produce a fast, deterministic initial label from surface cues:
    #   “confused” if uncertainty markers are present AND at least one '?'
    #   “angry” if strong anger words OR at least one '!' (arousal proxy)
    #   “polite” if courtesy/thanks markers appear
    #   else “neutral”
    # Notes:
    #   Branch order makes “angry” outrank “polite” if both appear (safety bias).
    #   This block is language/lexicon dependent (English focus).
    content = text.lower()
    anger_keywords = ["angry", "furious", "unacceptable", "terrible", "hate",
                      "ridiculous", "done", "fed up", "awful"]
    polite_keywords = ["please", "thank you", "thanks", "kindly"]
    confusion_keywords = ["don't understand", "confused", "explain", "what is",
                          "why is", "how", "?"]  # '?' included as a token cue

    if any(k in content for k in confusion_keywords) and content.count("?") >= 1:
        emotion = "confused"   # uncertainty explicit + question punctuation
    elif any(k in content for k in anger_keywords) or content.count("!") >= 1:
        emotion = "angry"      # lexical anger or high arousal
    elif any(k in content for k in polite_keywords):
        emotion = "polite"     # courtesy markers dominate in absence of anger/uncertainty
    else:
        emotion = "neutral"    # default safe bucket

    # --- Block 2: VADER Refinement (fail-safe, optional) ---
    # Intended outcome:
    #   Correct obvious sentiment misses when baseline is neutral/polite/confused:
    #   If compound ≤ −0.5 -> upgrade to “angry”
    #   If compound ≥ +0.5 AND baseline == “neutral” -> upgrade to “polite”
    # Guarantees:
    #   Never downgrade an “angry” baseline (preserve safety).
    #   Always fail gracefully: if VADER or its lexicon isn’t available, skip refinement.
    try:
        import nltk
        from nltk.sentiment.vader import SentimentIntensityAnalyzer
        try:
            nltk.data.find('sentiment/vader_lexicon.zip')
        except LookupError:
            nltk.download('vader_lexicon', quiet=True)

        sid = SentimentIntensityAnalyzer()
        c = sid.polarity_scores(text)['compound']  # c ∈ [-1.0, +1.0]

        if emotion in {"neutral", "polite", "confused"}:
            if c <= -0.5:
                emotion = "angry"   # strong negative signal -> safety-upgrade
            elif c >= 0.5 and emotion == "neutral":
                emotion = "polite"  # strong positive neutral -> politeness upgrade
    except Exception:
        pass  # Refinement is optional; baseline remains deterministic.

    # Examples (for test clarity):
    #   - "This is unacceptable!" -> angry (exclamation + anger word)
    #   - "I don't understand why I'm charged?" -> confused (uncertainty + '?')
    #   - "Thanks for the quick help." -> polite (courtesy)
    #   - "ok" -> neutral; may upgrade to polite if VADER compound ≥ 0.5
    return emotion

def detect_missing_part_name(text: str) -> Optional[str]:
    # Extract missing part keyword if present
    m = MISSING_PART_RE.search(text)
    return m.group(1) if m else None

def detect_agent_name(text: str) -> Optional[str]:
    """Capture 'Name from support' pattern."""
    m = AGENT_MENTION_RE.search(text)
    return m.group(1) if m else None

def perceive(text: str) -> PerceptionResult:
    """
    Outcome: Classify intent (refund_request/defect_report/billing_issue/…)
    and extract entities (order_id/phone/amount/ticket_id/serial) to enable
    downstream actions. No actions are executed here.
    """
    # intent rules … (refund/defect/billing/cancel/callback/praise/followup)
    # entity regexes … (ORDER_RE_LIST / PHONE_RE / AMOUNT_RE / TICKET_RE / SERIAL_RE)
    content = text.lower()
    emotion = analyze_emotion(text)

    # Intent selection (actionable → follow-up → praise → generic)
    if any(k in content for k in ["refund", "return", "money back", "chargeback"]):
        intent = "refund_request"
    elif any(k in content for k in ["defect", "broken", "damaged", "cracked", "not working", "doesn't work", "dies"]):
        intent = "defect_report"
    elif any(k in content for k in ["bill", "charged", "invoice", "fee", "renewal", "charge "]):
        intent = "billing_issue"
    elif any(k in content for k in ["cancel", "canceling", "switch", "leave", "take my business elsewhere"]):
        intent = "cancellation_threat"
    elif re.search(r"\b(missing|no|not included|did(?:n't| not) come with)\b", content) and \
         MISSING_PART_RE.search(content):
        intent = "missing_part"
    elif any(k in content for k in ["call me", "call back", "callback", "phone"]):
        intent = "callback_request"
    elif TICKET_RE.search(text):
        intent = "followup_existing"
    elif any(k in content for k in ["great service", "perfect service", "kudos", "appreciate", "thank you", "thanks"]):
        intent = "praise"
    else:
        intent = "generic_complaint"

    # Entity extraction
    entities: Dict[str, str] = {}
    for rx in ORDER_RE_LIST:
        m = rx.search(text)
        if m:
            entities["order_id"] = m.group(1).rstrip(".,;:!?)]}").upper()
            break

    # Phone guard (avoid matching ISO dates)
    m = PHONE_RE.search(text)
    if m:
        raw = m.group(1)
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
            digits = re.sub(r"\D", "", raw)
            if 10 <= len(digits) <= 15:
                entities["phone"] = raw

    m = AMOUNT_RE.search(text)
    if m:
        entities["amount"] = m.group(1).replace(",", "")
    m = TICKET_RE.search(text)
    if m:
        entities["ticket_id"] = m.group(1)
    m = SERIAL_RE.search(text)
    if m:
        entities["serial"] = m.group(1)

    if intent == "missing_part":
        part = detect_missing_part_name(text)
        if part:
            entities["part_name"] = part

    churn_risk = intent == "cancellation_threat"
    urgency = "high" if churn_risk or emotion == "angry" else ("medium" if intent in {"billing_issue","refund_request","defect_report"} else "low")

    return PerceptionResult(emotion=emotion, intent=intent, entities=entities,
                            churn_risk=churn_risk, urgency=urgency)


