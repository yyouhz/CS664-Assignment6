from .handle import handle_complaint

# Demo runner (prints six canned examples)
if __name__ == "__main__":
    samples = [
        # 1 — Angry Complaint
        "Your 'AeroBlend' blender (order ORD-7842-CA, bought on Sep 30, 2025) arrived with a cracked jar and FedEx shows 'delayed—damaged in transit.' I've emailed twice and got nothing. This is ridiculous—either refund me or I'm filing a claim with my bank.",
        # 2 — Confused Inquiry + possible duplicate charge
        "I don't understand my bill. I was charged $19.99 twice on Oct 1 for the 'Pro Notes' subscription. I chatted last week—ticket TCK-2025-10-06-C8—but I still don't get what happened. Can someone explain in plain English?",
        # 3 — Missing part (polite)
        "Hello! My CityLite Laptop Stand arrived (order US-55291) but there's no hex key in the box. Everything else seems fine—could you send the tool or advise? Thank you!",
        # 4 — Cancellation Threat
        "I'm done. The StreamGo+ app keeps buffering. I pay for Premium and can't even watch soccer. If this isn't fixed today, I'm canceling and switching to a competitor.",
        # 5 — Product Defect / Quality Issue
        "My CleanTrail Cordless Vacuum (order CA-993144) runs 5 minutes and dies, even after a full charge overnight. I bought it 3 weeks ago. Serial CT-V11-9F2. What can we do? I can send a video.",
        # 6 — Positive Feedback / Praise
        "Just wanted to say thank you—Janelle from support fixed my shipping address mess yesterday and got my Aurora Desk Lamp delivered this morning. Perfect service!"
    ]

    for i, s in enumerate(samples, start=1):
        print(f"\n=== Example {i} ===")
        print("INPUT:", s)
        print("OUTPUT:\n", handle_complaint(s, use_gemini_polish=True))
        print("-" * 60)
