"""Salus — an autonomous Revenue Recovery agent for Razorpay merchants.

Salus detects revenue at risk (failed payments, abandoned checkouts, failed
subscription renewals, overdue invoices), diagnoses the root cause, chooses a
*bounded* recovery intervention, executes it (Razorpay test-mode payment links
or simulation), and stops when it should — with a full audit trail.

Design principle: the LLM proposes, the deterministic policy engine disposes.
Every money action is explainable, bounded, and gated.
"""

__version__ = "0.1.0"
