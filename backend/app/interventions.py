"""Turn a diagnosis into an ordered list of concrete, *candidate* interventions.

Candidates are NOT yet allowed — every one is later run through the policy engine.
The planner also drafts the outbound copy (Hinglish/English) and picks a sensible
send/retry time; the policy engine may still defer or block it.
"""
from __future__ import annotations

from datetime import timedelta

from .models import (Channel, Diagnosis, EventRecord, Intervention,
                     InterventionType as IT, RevenueEvent, RootCause, new_id, now_ist)

# Messaging cost per channel, in paise (what the merchant pays to reach out).
_CHANNEL_COST = {Channel.WHATSAPP: 35, Channel.SMS: 20, Channel.EMAIL: 5, Channel.NONE: 0}

_RETRY_DELAY_H = {
    RootCause.INSUFFICIENT_FUNDS: 48,   # give the customer's balance time to recover
    RootCause.ISSUER_DOWN: 2,           # issuer outages are short
    RootCause.NETWORK_TIMEOUT: 1,       # transient — retry almost immediately
    RootCause.DO_NOT_HONOR: 24,
    RootCause.LIMIT_EXCEEDED: 24,
}

_HINGLISH = {
    RootCause.INSUFFICIENT_FUNDS: "Hi {name}, aapka ₹{amt} ka payment complete nahi hua — lagta hai balance ka issue tha. Jab convenient ho, yahan se pay kar dijiye: {link}",
    RootCause.CARD_EXPIRED: "Hi {name}, aapka saved card expire ho gaya hai, isliye ₹{amt} ka payment ruk gaya. Naya card add karke yahan complete karein: {link}",
    RootCause.AUTHENTICATION_FAILED: "Hi {name}, ₹{amt} ka payment authentication me fail hua. Koi baat nahi — is secure link se dobara try karein: {link}",
    RootCause.DO_NOT_HONOR: "Hi {name}, aapke bank ne ₹{amt} ka payment decline kar diya. Doosre method (UPI ya dusra card) se yahan try karein: {link}",
    RootCause.LIMIT_EXCEEDED: "Hi {name}, ₹{amt} aapke card ki limit se zyada tha. Aap EMI me convert kar sakte hain ya UPI se pay karein: {link}",
    RootCause.ABANDONED_HESITATION: "Hi {name}, aapka ₹{amt} ka order abhi complete nahi hua. Bas ek step baaki hai — yahan se finish karein: {link}",
    RootCause.ABANDONED_PRICE: "Hi {name}, aapka ₹{amt} ka cart ready hai. No-cost EMI available hai — yahan dekhein aur checkout karein: {link}",
    RootCause.INVOICE_FORGOTTEN: "Namaste {name}, aapka invoice ₹{amt} ka due hai. Ek tap me yahan pay karein: {link}. Zaroorat ho to hum help karenge.",
    RootCause.MANDATE_REVOKED: "Hi {name}, aapki subscription ka auto-pay mandate cancel ho gaya hai. Continue rakhne ke liye yahan re-authorise karein: {link}",
}
_ENGLISH = {
    RootCause.INSUFFICIENT_FUNDS: "Hi {name}, your ₹{amt} payment didn't go through — looks like a balance issue. Whenever convenient, pay here: {link}",
    RootCause.CARD_EXPIRED: "Hi {name}, your saved card has expired, so the ₹{amt} payment stopped. Add a new card and finish here: {link}",
    RootCause.AUTHENTICATION_FAILED: "Hi {name}, the ₹{amt} payment failed authentication. No worries — retry securely here: {link}",
    RootCause.DO_NOT_HONOR: "Hi {name}, your bank declined the ₹{amt} payment. Try another method (UPI or another card) here: {link}",
    RootCause.LIMIT_EXCEEDED: "Hi {name}, ₹{amt} was over your card limit. Convert to EMI or pay via UPI here: {link}",
    RootCause.ABANDONED_HESITATION: "Hi {name}, your ₹{amt} order isn't complete yet. Just one step left — finish here: {link}",
    RootCause.ABANDONED_PRICE: "Hi {name}, your ₹{amt} cart is ready. No-cost EMI is available — check out here: {link}",
    RootCause.INVOICE_FORGOTTEN: "Hi {name}, your invoice for ₹{amt} is due. Pay in one tap here: {link}. Reach out if you need help.",
    RootCause.MANDATE_REVOKED: "Hi {name}, your subscription auto-pay mandate was cancelled. Re-authorise here to continue: {link}",
}


# Firmer, step-specific copy for the receivables ladder.
_SPECIAL = {
    (IT.PROMISE_TO_PAY, "hinglish"): "Namaste {name}, ₹{amt} ka invoice pending hai. Aap kab tak clear kar paayenge? Abhi pay karein ya date confirm karein: {link}",
    (IT.PROMISE_TO_PAY, "english"): "Hi {name}, your ₹{amt} invoice is pending. When can you clear it? Pay now or confirm a date: {link}",
    (IT.FINAL_NOTICE, "hinglish"): "Namaste {name}, yeh ₹{amt} ke invoice ka final reminder hai. Kripya aaj {link} se payment complete karein, taaki ise aur aage na badhaana pade.",
    (IT.FINAL_NOTICE, "english"): "Hi {name}, this is a final reminder for your ₹{amt} invoice. Please complete payment today via {link} so we don't have to escalate.",
}


def draft_message(ev: RevenueEvent, dg: Diagnosis, itype: IT | None = None) -> str:
    lang = ev.customer.language_pref if ev.customer.language_pref == "hinglish" else "english"
    special = _SPECIAL.get((itype, lang)) if itype else None
    if special:
        template = special
    else:
        table = _HINGLISH if lang == "hinglish" else _ENGLISH
        template = table.get(dg.root_cause, "Hi {name}, please complete your ₹{amt} payment here: {link}")
    return template.format(name=ev.customer.name.split()[0],
                           amt=f"{ev.amount_paise // 100:,}", link="{link}")


def _channel_for(ev: RevenueEvent) -> Channel:
    # WhatsApp for consumers (best open rate); email for B2B invoices.
    if ev.type.value == "invoice_overdue":
        return Channel.EMAIL
    return Channel.WHATSAPP


_CONTACT_TYPES = {IT.REMINDER_MESSAGE, IT.NEW_PAYMENT_LINK, IT.RETRY_ALT_METHOD,
                  IT.EMI_OFFER, IT.PROMISE_TO_PAY, IT.FINAL_NOTICE}
_FIRMNESS = ["gentle", "firm", "firm", "final", "final"]


def plan(rec: EventRecord) -> list[Intervention]:
    ev, dg = rec.event, rec.diagnosis
    assert dg is not None
    out: list[Intervention] = []
    channel = _channel_for(ev)
    contact_step = 0  # increments per outreach step to space the sequence over time

    for itype in dg.suggested:
        iv = Intervention(id=new_id("act"), event_id=ev.id, type=itype)

        if itype in (IT.SMART_RETRY, IT.MANDATE_RETRY):
            delay = _RETRY_DELAY_H.get(dg.root_cause, 12 if itype == IT.SMART_RETRY else 24)
            iv.scheduled_for = now_ist() + timedelta(hours=delay)

        elif itype in _CONTACT_TYPES:
            iv.channel = channel
            iv.cost_paise = _CHANNEL_COST[channel]
            iv.message = draft_message(ev, dg, itype)
            iv.step = contact_step
            iv.firmness = _FIRMNESS[min(contact_step, len(_FIRMNESS) - 1)]
            # Space the ladder: step 0 now, then +72h, +48h, +48h ...
            iv.scheduled_for = now_ist() + timedelta(hours=(0 if contact_step == 0 else 24 + contact_step * 24))
            contact_step += 1

        elif itype == IT.ESCALATE_HUMAN:
            iv.scheduled_for = now_ist()

        out.append(iv)
    return out
