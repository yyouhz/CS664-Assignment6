from __future__ import annotations
from typing import Dict, List
from datetime import datetime, timedelta
from .policy import POLICY
from .perception import perceive, detect_agent_name
from .actions import *
from .compose import compose_sections, polish_with_gemini

# Orchestration entrypoint
def handle_complaint(user_text: str, use_gemini_polish: bool = True) -> str:
    p = perceive(user_text)

    steps: List[str] = []   # debug prints for screenshots
    facts: List[str] = []
    actions: Dict[str, str] = {}

    # Order lookup (adds order facts if found)
    order = None
    if oid := p.entities.get("order_id"):
        order = lookup_order(oid)
        steps.append(f"Looked up order: {oid} -> {'FOUND' if order else 'NOT_FOUND'}")
        if order:
            facts.append(f"Order: {oid} | status: {order['status']} | amount: ${order['amount']:.2f}")

    # Ticket creation rules
    NEED_TICKET = {"defect_report", "billing_issue", "generic_complaint", "cancellation_threat", "missing_part"}
    if (p.intent in NEED_TICKET) or (p.intent == "refund_request" and not order):
        actions["ticket_id"] = create_ticket(kind=p.intent, payload={"text": user_text, "entities": p.entities})
        steps.append(f"Ticket created: {actions['ticket_id']}")
        facts.append(f"Ticket: {actions['ticket_id']}")
    elif p.intent == "followup_existing":
        tid = p.entities.get("ticket_id", "(not provided)")
        steps.append(f"Follow-up on existing ticket: {tid}")
        facts.append(f"Continuing prior ticket: {tid}")

    # Refund flow
    if p.intent == "refund_request" and order:
        elig, note = is_refund_eligible(order)
        facts.append(("Refund eligible. " if elig else "Refund ineligible. ") + note)
        if elig:
            rid, eta = issue_refund(p.entities["order_id"], order["amount"])
            actions["refund_id"], actions["refund_eta"] = rid, eta
            facts.append(f"Refund ID: {rid} | ETA: {eta}")
        else:
            ensure_loyalty_credit_once(actions, facts, POLICY["goodwill_credit_default"])
            facts[-1] = facts[-1].replace("Loyalty credit", "Goodwill credit")

    # Defect/quality flow
    if p.intent == "defect_report" and order:
        days_since = (datetime.now() - order["created_at"]).days
        if order["status"] == "carrier_damage_scan" or days_since <= POLICY["refund_window_days"]:
            rep_id, delivery_eta = create_replacement(p.entities["order_id"], sku_hint="auto-replacement")
            actions["replacement_id"], actions["delivery_eta"] = rep_id, delivery_eta
            facts.append(f"Replacement ID: {rep_id} | Delivery ETA: {delivery_eta}")
        else:
            facts.append("Outside 30 days; offering repair or prorated options.")
        if s := p.entities.get("serial"):
            facts.append(f"Serial: {s}")

    # Billing flow
    if p.intent == "billing_issue":
        facts.append("Billing audit opened to verify duplicate/incorrect charges.")
        content = user_text.lower()
        a_txt = p.entities.get("amount")
        if a_txt and any(k in content for k in ["twice", "duplicate", "charged again", "double"]):
            amt = float(a_txt)
            ensure_loyalty_credit_once(actions, facts, amt)
            facts[-1] = facts[-1].replace("Loyalty credit", "Immediate credit issued")
        elif a_txt:
            facts.append(f"Amount in question noted: ${a_txt}")

    # Missing part flow
    if p.intent == "missing_part":
        part = p.entities.get("part_name", "accessory")
        sh = ship_missing_part(part)
        actions["shipment_id"], actions["shipment_eta"] = sh["shipment_id"], sh["eta"]
        facts.append(f"Missing part shipment: {sh['shipment_id']} | {sh['content']} | ETA: {sh['eta']}")
        ensure_loyalty_credit_once(actions, facts, POLICY["loyalty_credit_amount"])

    # Praise flow
    if p.intent == "praise":
        agent_name = detect_agent_name(user_text)
        if agent_name:
            actions["agent_name"] = agent_name
            facts.append(f"Kudos recorded for {agent_name}.")
        ensure_loyalty_credit_once(actions, facts, POLICY["loyalty_credit_amount"])

    # Retention/escalation flow
    if p.intent == "cancellation_threat":
        esc_id = escalate("churn-risk")
        actions["escalation_id"] = esc_id
        facts.append(f"Escalation: {esc_id}")
        cred_id, amt = apply_retention_offer("acct-on-file", POLICY["goodwill_credit_default"])
        actions["credit_id"] = cred_id
        facts.append(f"Retention credit: ${amt:.2f} (ID {cred_id})")

    # Callback scheduling when requested or phone captured
    if p.intent == "callback_request" or p.entities.get("phone"):
        phone = p.entities.get("phone", "(not provided)")
        actions["callback"] = schedule_callback(phone=phone, when=POLICY["callback_window"])
        facts.append(actions["callback"])

    # Compose response and optional polish
    reply = compose_sections(p, actions, facts)
    print("\n".join(steps))  # debug steps for screenshots

    if not use_gemini_polish:
        return reply

    # Skip polish for praise/missing-part to keep consistent phrasing
    if p.intent in {"praise", "missing_part"}:
        return reply

    # Style hint for Gemini polish
    style = ""
    if p.emotion == "angry":
        style = "Customer is angry. Apologize once, then show decisive actions."
    elif p.emotion == "confused":
        style = "Customer is confused. Clarify simply and reassuringly."
    elif p.emotion == "polite":
        style = "Customer is polite. Friendly and concise tone."

    return polish_with_gemini(reply, style_hint=style)
