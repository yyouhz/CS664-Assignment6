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
    """Rule-based emotion with optional VADER backstop."""
    content = text.lower()
    anger_keywords = ["angry", "furious", "unacceptable", "terrible", "hate",
                      "ridiculous", "done", "fed up", "awful"]
    polite_keywords = ["please", "thank you", "thanks", "kindly"]
    confusion_keywords = ["don't understand", "confused", "explain", "what is",
                          "why is", "how", "?"]

    if any(k in content for k in confusion_keywords) and content.count("?") >= 1:
        emotion = "confused"
    elif any(k in content for k in anger_keywords) or content.count("!") >= 1:
        emotion = "angry"
    elif any(k in content for k in polite_keywords):
        emotion = "polite"
    else:
        emotion = "neutral"

    # Optional VADER refinement (best-effort, safe fallback on errors)
    try:
        import nltk
        from nltk.sentiment.vader import SentimentIntensityAnalyzer
        try:
            nltk.data.find('sentiment/vader_lexicon.zip')
        except LookupError:
            nltk.download('vader_lexicon', quiet=True)
        sid = SentimentIntensityAnalyzer()
        c = sid.polarity_scores(text)['compound']
        if emotion in {"neutral", "polite", "confused"}:
            if c <= -0.5:
                emotion = "angry"
            elif c >= 0.5 and emotion == "neutral":
                emotion = "polite"
    except Exception:
        pass

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
    """Determine intent and extract entities (actionable intents prioritized)."""
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
