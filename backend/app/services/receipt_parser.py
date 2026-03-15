"""
Receipt parser — extracts structured data from email HTML.

Two-tier approach:
1. Merchant templates for common retailers (fast, reliable)
2. Local LLM via Ollama for unknown merchants (flexible, private)
"""

import re
import json
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime, timedelta

import httpx

from app.config import settings


@dataclass
class ParsedItem:
    name: str
    quantity: int = 1
    price: float = 0.0


@dataclass
class ParsedReceipt:
    merchant: str
    date: Optional[str] = None
    order_number: Optional[str] = None
    items: list[ParsedItem] = field(default_factory=list)
    subtotal: Optional[float] = None
    tax: Optional[float] = None
    total: Optional[float] = None
    return_window_days: int = 30
    return_deadline: Optional[str] = None
    confidence: float = 0.0  # 0-1

    def compute_return_deadline(self):
        if self.date and self.return_window_days:
            try:
                purchase_date = datetime.fromisoformat(self.date)
                deadline = purchase_date + timedelta(days=self.return_window_days)
                self.return_deadline = deadline.strftime("%Y-%m-%d")
            except ValueError:
                pass


# Known return windows per merchant
RETURN_POLICIES: dict[str, int] = {
    "amazon": 30,
    "best buy": 15,
    "target": 90,
    "walmart": 90,
    "costco": 90,  # most items
    "apple": 14,
    "home depot": 90,
    "lowes": 90,
    "nordstrom": 0,  # unlimited for most items
    "rei": 365,
}


def parse_with_templates(subject: str, body_html: str, sender: str) -> Optional[ParsedReceipt]:
    """Try merchant-specific templates first."""
    sender_lower = sender.lower()
    subject_lower = subject.lower()

    if "amazon" in sender_lower or "amazon" in subject_lower:
        return _parse_amazon(subject, body_html)
    if "bestbuy" in sender_lower or "best buy" in subject_lower:
        return _parse_generic(subject, body_html, "Best Buy", 15)
    if "target" in sender_lower:
        return _parse_generic(subject, body_html, "Target", 90)
    if "walmart" in sender_lower:
        return _parse_generic(subject, body_html, "Walmart", 90)
    if "apple" in sender_lower:
        return _parse_generic(subject, body_html, "Apple", 14)

    return None


def _parse_amazon(subject: str, body_html: str) -> ParsedReceipt:
    """Parse Amazon order confirmation."""
    receipt = ParsedReceipt(merchant="Amazon", return_window_days=30, confidence=0.7)

    # Extract order number
    order_match = re.search(r"(?:order|#)\s*([\d-]{10,})", subject + body_html, re.IGNORECASE)
    if order_match:
        receipt.order_number = order_match.group(1)

    # Extract total
    total_match = re.search(r"(?:order total|grand total|total)[:\s]*\$?([\d,]+\.?\d*)", body_html, re.IGNORECASE)
    if total_match:
        receipt.total = float(total_match.group(1).replace(",", ""))

    # Extract items (simplified — looks for price patterns near text)
    item_pattern = re.compile(r'(?:>|^)\s*([^<>]{5,80}?)\s*(?:</[^>]+>)?\s*\$(\d+\.?\d*)', re.MULTILINE)
    for match in item_pattern.finditer(body_html):
        name = re.sub(r'<[^>]+>', '', match.group(1)).strip()
        price = float(match.group(2))
        if name and price > 0 and len(name) < 100:
            receipt.items.append(ParsedItem(name=name, price=price))

    receipt.compute_return_deadline()
    return receipt


def _parse_generic(subject: str, body_html: str, merchant: str, return_days: int) -> ParsedReceipt:
    """Generic receipt parser using regex patterns."""
    receipt = ParsedReceipt(
        merchant=merchant,
        return_window_days=return_days,
        confidence=0.5,
    )

    # Extract total
    total_match = re.search(r"(?:total|amount|charged)[:\s]*\$?([\d,]+\.?\d*)", body_html, re.IGNORECASE)
    if total_match:
        receipt.total = float(total_match.group(1).replace(",", ""))

    # Extract order number
    order_match = re.search(r"(?:order|confirmation|reference)\s*#?\s*:?\s*([\w-]{6,})", body_html, re.IGNORECASE)
    if order_match:
        receipt.order_number = order_match.group(1)

    receipt.compute_return_deadline()
    return receipt


async def parse_with_ollama(
    subject: str,
    body_text: str,
    model: str = "llama3.1:8b",
) -> Optional[ParsedReceipt]:
    """
    Parse receipt using local LLM via Ollama.
    Falls back gracefully if Ollama is not running.
    """
    ollama_url = f"http://{settings.ollama_host}:11434/api/generate"

    prompt = f"""Extract structured receipt data from this email. Return ONLY valid JSON, no other text.

Subject: {subject}

Email body:
{body_text[:3000]}

Return JSON with this exact schema:
{{
  "merchant": "store name",
  "date": "YYYY-MM-DD or null",
  "order_number": "order number or null",
  "items": [{{"name": "item name", "quantity": 1, "price": 0.00}}],
  "subtotal": 0.00,
  "tax": 0.00,
  "total": 0.00
}}

JSON:"""

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                ollama_url,
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.1},
                },
            )
            resp.raise_for_status()
            result = resp.json()
            response_text = result.get("response", "")

        # Extract JSON from response
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if not json_match:
            return None

        data = json.loads(json_match.group())

        receipt = ParsedReceipt(
            merchant=data.get("merchant", "Unknown"),
            date=data.get("date"),
            order_number=data.get("order_number"),
            total=data.get("total"),
            subtotal=data.get("subtotal"),
            tax=data.get("tax"),
            confidence=0.6,
        )

        for item in data.get("items", []):
            receipt.items.append(ParsedItem(
                name=item.get("name", ""),
                quantity=item.get("quantity", 1),
                price=item.get("price", 0),
            ))

        # Apply known return policy
        merchant_key = receipt.merchant.lower()
        for key, days in RETURN_POLICIES.items():
            if key in merchant_key:
                receipt.return_window_days = days
                break

        receipt.compute_return_deadline()
        return receipt

    except (httpx.ConnectError, httpx.TimeoutException):
        # Ollama not running — that's OK
        return None
    except (json.JSONDecodeError, KeyError):
        return None


async def parse_email(subject: str, body_html: str, body_text: str, sender: str) -> Optional[ParsedReceipt]:
    """
    Parse a receipt email using the two-tier approach:
    1. Try merchant templates first (fast, reliable)
    2. Fall back to Ollama LLM (flexible)
    """
    # Tier 1: Templates
    result = parse_with_templates(subject, body_html, sender)
    if result and result.total:
        return result

    # Tier 2: Ollama LLM
    text = body_text or body_html
    if text:
        result = await parse_with_ollama(subject, text)
        if result and result.total:
            return result

    return None
