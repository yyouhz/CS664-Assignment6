# Customer Service Bot - CS664 Assignment 6: Natural Language

An intelligent customer service bot that processes customer complaints and inquiries using natural language processing, sentiment analysis, and automated response generation.

## Overview

This system demonstrates a complete customer service automation pipeline that:

- Analyzes customer messages for emotion, intent, and entities
- Applies business policies to determine appropriate actions
- Generates contextually appropriate responses
- Optionally polishes responses using Google's Gemini AI

## Architecture

The bot follows a modular architecture with clear separation of concerns:

### Core Components

- **`perception.py`** - Natural language understanding and entity extraction
- **`actions.py`** - Business logic and action execution
- **`policy.py`** - Configurable business rules and policies
- **`handle.py`** - Main orchestration and workflow management
- **`compose.py`** - Response generation and optional AI polishing
- **`main.py`** - Demo runner with sample customer interactions

## Features

### Emotion Analysis

- Rule-based emotion classification (angry, confused, polite, neutral)
- Optional VADER sentiment analysis refinement
- Deterministic and fast emotion detection

### Intent Recognition

Supports multiple customer intents:

- `refund_request` - Customer wants money back
- `defect_report` - Product quality issues
- `billing_issue` - Payment or charge problems
- `cancellation_threat` - Customer threatening to leave
- `missing_part` - Incomplete shipments
- `callback_request` - Request for phone contact
- `followup_existing` - Follow-up on previous tickets
- `praise` - Positive feedback
- `generic_complaint` - General issues

### Entity Extraction

Automatically extracts:

- Order IDs (multiple formats supported)
- Phone numbers
- Monetary amounts
- Ticket IDs
- Product serial numbers
- Missing part names
- Agent names

### Business Actions

The system can automatically:

- Create support tickets
- Process refunds (with eligibility checks)
- Schedule replacements
- Ship missing parts
- Issue loyalty credits
- Schedule callbacks
- Escalate urgent cases
- Apply retention offers

## Usage

### Basic Usage

```python
from customer_service_bot import handle_complaint

# Process a customer complaint
response = handle_complaint(
    "Your 'AeroBlend' blender (order ORD-7842-CA) arrived cracked. I want a refund!",
    use_gemini_polish=True
)
print(response)
```

### Running the Demo

```bash
cd Assignment6
python -m customer_service_bot.main
```

This will process 6 sample customer interactions demonstrating different scenarios.

## Configuration

Business policies are centralized in `policy.py`:

```python
POLICY = {
    "refund_window_days": 30,
    "goodwill_credit_default": 10.0,
    "loyalty_credit_amount": 5.0,
    "callback_window": "today 4–6pm",
    "replacement_delivery_days": 2,
    "refund_eta_days": 3,
}
```

## Optional AI Enhancement

The system supports optional response polishing using Google's Gemini AI:

1. Set your `GEMINI_API_KEY` environment variable
2. Enable polishing by setting `use_gemini_polish=True`

The AI polishing:

- Improves tone and clarity
- Maintains all factual information unchanged
- Preserves bullet points and specific details
- Adapts style based on customer emotion

## Sample Interactions

The demo includes 6 realistic customer scenarios:

1. **Angry Complaint** - Damaged product with refund demand
2. **Confused Inquiry** - Billing confusion with duplicate charges
3. **Missing Part** - Polite request for missing accessory
4. **Cancellation Threat** - Service quality issues
5. **Product Defect** - Hardware malfunction report
6. **Positive Feedback** - Praise for good service

## Technical Details

### Dependencies

- Python 3.7+
- `nltk` (optional, for VADER sentiment analysis)
- `google-generativeai` (optional, for response polishing)

### Design Principles

- **Deterministic**: Core logic is rule-based and predictable
- **Modular**: Clear separation between perception, action, and composition
- **Extensible**: Easy to add new intents, entities, or business rules
- **Configurable**: Business policies centralized and adjustable
- **Graceful Degradation**: Optional AI features fail gracefully

## File Structure

```
customer_service_bot/
├── __init__.py          # Package initialization
├── main.py              # Demo runner
├── handle.py            # Main orchestration
├── perception.py        # NLP and entity extraction
├── actions.py           # Business logic and actions
├── policy.py            # Business rules configuration
└── compose.py           # Response generation and AI polishing
```
