"""Reaching a person: a real phone call (Twilio) and a text (Telegram).

Each channel turns on when its environment variables are set; otherwise the
alert is printed, so the demo runs anywhere.

    TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM, ALERT_PHONE
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
"""

from __future__ import annotations

import os
from xml.sax.saxutils import escape

import httpx


async def call(message: str) -> str:
    sid, tok = os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN")
    frm, to = os.getenv("TWILIO_FROM"), os.getenv("ALERT_PHONE")
    if not all((sid, tok, frm, to)):
        print(f"[alert] (no Twilio configured) would call {to or 'family'}: {message}")
        return "printed"
    twiml = f'<Response><Say voice="Polly.Joanna">{escape(message)}</Say><Pause length="1"/><Say>{escape(message)}</Say></Response>'
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Calls.json",
                         auth=(sid, tok), data={"From": frm, "To": to, "Twiml": twiml})
    r.raise_for_status()
    return r.json().get("sid", "called")


async def text(message: str) -> str:
    tok, chat = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not (tok and chat):
        print(f"[alert] (no Telegram configured) {message}")
        return "printed"
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(f"https://api.telegram.org/bot{tok}/sendMessage", data={"chat_id": chat, "text": message})
    r.raise_for_status()
    return "sent"
