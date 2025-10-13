from __future__ import annotations
import itertools
from typing import Optional, Dict, Tuple, List
from datetime import datetime, timedelta
from .policy import POLICY

# In-memory demo state and actions
ORDERS = {
    "ORD12345":    {"created_at": datetime.now() - timedelta(days=20), "status": "delivered",           "refundable_days": POLICY["refund_window_days"], "amount": 79.99},
    "ORD9ZX88":    {"created_at": datetime.now() - timedelta(days=45), "status": "delivered",           "refundable_days": POLICY["refund_window_days"], "amount": 129.00},
    "ORD-7842-CA": {"created_at": datetime.now() - timedelta(days=13), "status": "carrier_damage_scan", "refundable_days": POLICY["refund_window_days"], "amount": 149.00},
    "US-55291":    {"created_at": datetime.now() - timedelta(days=7),  "status": "delivered",           "refundable_days": POLICY["refund_window_days"], "amount": 29.00},
    "CA-993144":   {"created_at": datetime.now() - timedelta(days=21), "status": "delivered",           "refundable_days": POLICY["refund_window_days"], "amount": 199.00},
}

TICKET_COUNTER = itertools.count(1001)
ACTIONS_LOG: List[dict] = []
REFUNDS:   List[dict] = []
REPLACEMENTS: List[dict] = []
CREDITS:   List[dict] = []
CALLBACKS: List[dict] = []
ESCALATIONS: List[dict] = []
SHIPMENTS: List[dict] = []

def lookup_order(order_id: str) -> Optional[dict]:
    return ORDERS.get(order_id)

def is_refund_eligible(order: dict) -> Tuple[bool, str]:
    days_since = (datetime.now() - order["created_at"]).days
    if days_since <= order["refundable_days"]:
        return True, f"Within {order['refundable_days']}-day window (day {days_since})."
    return False, f"Past {order['refundable_days']}-day window (day {days_since})."

def _ticket_prefix_for_kind(kind: str) -> str:
    return "RET" if kind == "cancellation_threat" else "TCK"

def create_ticket(kind: str, payload: dict) -> str:
    prefix = _ticket_prefix_for_kind(kind)
    today = datetime.now().strftime("%Y-%m-%d")
    n = next(TICKET_COUNTER)
    ticket_id = f"{prefix}-{today}-{kind[:2].upper()}{n}"
    ACTIONS_LOG.append({"type": "ticket", "id": ticket_id, "kind": kind, "payload": payload})
    return ticket_id

def schedule_callback(phone: str, when: Optional[str] = None) -> str:
    window = when or POLICY["callback_window"]
    CALLBACKS.append({"phone": phone, "window": window})
    return f"Callback scheduled to {phone} {window}"

def escalate(account_or_reason: str) -> str:
    esc_id = f"ESC-{datetime.now().strftime('%Y%m%d')}-{len(ESCALATIONS)+1:04d}"
    ESCALATIONS.append({"id": esc_id, "reason": account_or_reason})
    return esc_id

def issue_refund(order_id: str, amount: float) -> Tuple[str, str]:
    refund_id = f"RF-{datetime.now().strftime('%Y%m%d')}-{len(REFUNDS)+1:04d}"
    eta = (datetime.now() + timedelta(days=POLICY["refund_eta_days"])).strftime("%b %d, %Y")
    REFUNDS.append({"refund_id": refund_id, "order_id": order_id, "amount": amount, "eta_date": eta})
    return refund_id, eta

def create_replacement(order_id: str, sku_hint: str = "replacement") -> Tuple[str, str]:
    repl_id = f"RP-{datetime.now().strftime('%Y%m%d')}-{len(REPLACEMENTS)+1:04d}"
    eta_delivery = (datetime.now() + timedelta(days=POLICY["replacement_delivery_days"])).strftime("%b %d, %Y")
    REPLACEMENTS.append({"replacement_id": repl_id, "order_id": order_id, "sku": sku_hint, "eta_delivery": eta_delivery})
    return repl_id, eta_delivery

def add_loyalty_credit(account_id: str, amount: float) -> Tuple[str, str]:
    cred_id = f"CR-{datetime.now().strftime('%Y%m%d')}-{len(CREDITS)+1:04d}"
    applied = datetime.now().strftime("%b %d, %Y")
    CREDITS.append({"credit_id": cred_id, "account": account_id, "amount": amount, "applied": applied})
    return cred_id, applied

def apply_retention_offer(account_id: str, amount: float = None) -> Tuple[str, float]:
    amt = amount if amount is not None else POLICY["goodwill_credit_default"]
    cred_id, _ = add_loyalty_credit(account_id, amt)
    return cred_id, amt

def ship_missing_part(part_name: str = "accessory") -> dict:
    """Ship the missing accessory and return shipment record."""
    sid = f"S{len(SHIPMENTS)+1:04d}"
    eta_days = 4
    eta = (datetime.now() + timedelta(days=eta_days)).strftime("%b %d, %Y")
    payload = {"shipment_id": sid, "content": part_name, "eta": eta}
    SHIPMENTS.append(payload)
    return payload

# One-time loyalty/goodwill credit helper
def ensure_loyalty_credit_once(actions: Dict[str, str], facts: List[str], amount: float) -> None:
    """
    Issue exactly one loyalty/goodwill credit for this request.
    - If actions['credit_id'] already exists, do nothing (avoid duplicates).
    - Otherwise issue and append one bullet line with 'Loyalty credit: $X (ID ...)'.
    Upstream callers may replace the label text (e.g. to 'Immediate credit issued' or 'Goodwill credit').
    """
    if actions.get("credit_id"):
        return
    cred_id, _ = add_loyalty_credit("acct-on-file", amount)
    actions["credit_id"] = cred_id
    facts.append(f"Loyalty credit: ${amount:.2f} (ID {cred_id})")
