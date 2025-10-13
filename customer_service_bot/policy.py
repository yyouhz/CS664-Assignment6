# Policy configuration (single source of truth)
POLICY = {
    "refund_window_days": 30,
    "goodwill_credit_default": 10.0,  # fallback when refund ineligible
    "loyalty_credit_amount": 5.0,     # small thank-you credit
    "callback_window": "today 4–6pm",
    "replacement_delivery_days": 2,
    "refund_eta_days": 3,
}
