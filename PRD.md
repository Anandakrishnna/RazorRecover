# RazorRecover — Product Requirements Document

**Track:** Razorpay AI Buildathon 2026 — Track 3: AI Revenue Recovery
**One-line pitch:** RazorRecover is an autonomous revenue recovery agent that detects revenue at risk, diagnoses why it's failing, chooses the safest intervention, executes a bounded recovery workflow, and verifies whether the money was actually recovered.

---

## 1. Problem Statement

Merchant revenue leaks through multiple channels that are rarely handled together:

- Payment failures (card decline, network timeout, insufficient funds)
- Checkout abandonment
- Failed subscription renewals
- Overdue B2B receivables

Merchants typically don't know which of this money is still recoverable, why it was lost, or what the correct next action is. RazorRecover automates detection → diagnosis → intervention → verification for all four categories in one agent loop.

---

## 2. Goals

- Detect revenue-at-risk events in near real time
- Diagnose root cause with a confidence score
- Estimate recovery probability and expected recovery value
- Select an intervention via a **deterministic, auditable policy engine** (LLM recommends, policy engine decides)
- Execute a bounded action (simulated payment API)
- Verify whether revenue was actually recovered
- Log a full audit trail for every decision and action
- Evaluate the system on a held-out synthetic dataset with honest metrics

## 3. Non-Goals

- No real money movement — all payment actions are simulated against mocked/test-mode APIs
- No unbounded autonomous spending or unlimited retries — every action is capped by policy
- Not building a general-purpose chatbot — the LLM only classifies and recommends, never executes directly

---

## 4. Core Agent Loop

```
Revenue Event
     → Revenue Monitor (flag at-risk)
     → Root Cause Classifier (LLM + rules → cause, confidence)
     → Recovery Probability Model (→ probability)
     → Expected Recovery Value = amount × probability
     → AI Recommender (LLM proposes intervention + reasoning)
     → Policy Engine (deterministic: approve / modify / reject)
     → Tool Executor (simulated action)
     → Verifier (did the payment actually succeed?)
     → Audit Logger (full record)
     → Stop / Retry (bounded) / Escalate
```

**Execution Modes (MVP):**
- **Autonomous Mode (`POST /events/ingest`):** Event ingestion automatically triggers the entire pipeline asynchronously, evaluating policy rules, executing approved simulated tools, verifying results, and writing audit logs.

Design principle: **the LLM decides what to recommend; the policy engine decides what is allowed to happen.** Every money-affecting action must be explainable, bounded, and gated, with a visible audit trail and graceful handling of at least one failure case.

---

## 5. Dataset (MVP Scope)

Synthetic dataset of revenue-loss events, generated before any model work begins.

**Fields per event:**
`transaction_id, customer_id, amount, payment_method, failure_type, timestamp, retry_history, customer_purchase_history, subscription_status, checkout_behavior, invoice_age_days, previous_recovery_outcome`

**Size (MVP):** 1,000 events
**Distribution (approx):** 40% temporary payment failure (400), 20% card/method issue (200), 20% checkout abandonment (200), 10% subscription failure (100), 10% overdue invoice (100)

**Split:** 800 dev (build/tune against this) / 200 held-out (final evaluation only — never tune against this set)

---

## 6. System Architecture

```
                    FRONTEND (React/Next.js Single-Page)
                                     │
                                     ▼
                           API LAYER (FastAPI)
                                     │
        ┌────────────────────────────┼────────────────────────────┐
        ▼                            ▼                            ▼
 Revenue Engine                Agent Engine                 Policy Engine
        │                            │                            │
        │                     ┌──────┴──────┐                     │
        │                     ▼             ▼                     │
        │                 Recommender   Classifier                │
        │                     │             │                     │
        └─────────────────────┼─────────────┼─────────────────────┘
                              ▼
                        Action Planner
                              │
                              ▼
                        Tool Executor
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
    Payment API           Messaging API         Escalation API
     (simulated)           (simulated)           (simulated)
                              │
                              ▼
                     SQLite (razorrecover.db)
                              │
                              ▼
                         Audit Logs
```

---

## 7. Database Schema (SQLite / SQLAlchemy)

```sql
-- Merchants Table
CREATE TABLE merchants (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Customers Table
CREATE TABLE customers (
    id VARCHAR(64) PRIMARY KEY,
    merchant_id VARCHAR(64) REFERENCES merchants(id),
    name VARCHAR(255) NOT NULL,
    subscription_status VARCHAR(32) NOT NULL, -- 'ACTIVE', 'PAUSED', 'CANCELLED', 'PAST_DUE'
    previous_recovery_outcome VARCHAR(32), -- 'RECOVERED', 'FAILED', 'NONE'
    history_json JSON -- includes purchase count, total spent, order history
);

-- Transactions Table
CREATE TABLE transactions (
    id VARCHAR(64) PRIMARY KEY,
    merchant_id VARCHAR(64) REFERENCES merchants(id),
    customer_id VARCHAR(64) REFERENCES customers(id),
    amount NUMERIC(12, 2) NOT NULL,
    method VARCHAR(32) NOT NULL, -- 'card', 'upi', 'netbanking', 'invoice'
    status VARCHAR(32) NOT NULL, -- 'SUCCESS', 'FAILED', 'PENDING'
    failure_type VARCHAR(64) NOT NULL, -- 'temporary', 'card_expired', 'insufficient_funds', 'checkout_abandoned', 'subscription_failed', 'overdue_invoice'
    retry_count INT DEFAULT 0,
    checkout_behavior VARCHAR(64), -- 'abandoned_at_payment', 'abandoned_at_cart'
    invoice_age_days INT DEFAULT 0,
    retry_history_json JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Recovery Cases Table
CREATE TABLE recovery_cases (
    id VARCHAR(64) PRIMARY KEY,
    transaction_id VARCHAR(64) REFERENCES transactions(id),
    revenue_at_risk NUMERIC(12, 2) NOT NULL,
    root_cause VARCHAR(64) NOT NULL,
    confidence NUMERIC(4, 3) NOT NULL,
    recovery_probability NUMERIC(4, 3) NOT NULL,
    expected_recovery_value NUMERIC(12, 2) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'OPEN', -- 'OPEN', 'IN_PROGRESS', 'RECOVERED', 'FAILED', 'ESCALATED', 'STOPPED'
    opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    closed_at TIMESTAMP
);

-- Agent Decisions Table
CREATE TABLE agent_decisions (
    id VARCHAR(64) PRIMARY KEY,
    case_id VARCHAR(64) REFERENCES recovery_cases(id),
    recommendation VARCHAR(64) NOT NULL,
    policy_check_result VARCHAR(32) NOT NULL, -- 'APPROVED', 'DOWNGRADED', 'REJECTED'
    action_taken VARCHAR(64) NOT NULL,
    result VARCHAR(32) NOT NULL, -- 'SUCCESS', 'FAILED', 'PENDING'
    reasoning_text TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Audit Log Table
CREATE TABLE audit_log (
    id VARCHAR(64) PRIMARY KEY,
    case_id VARCHAR(64) REFERENCES recovery_cases(id),
    event_type VARCHAR(64) NOT NULL, -- 'EVENT_INGESTED', 'CLASSIFIED', 'POLICY_CHECK', 'ACTION_EXECUTED', 'VERIFIED', 'ESCALATED'
    detail_json JSON NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 8. Policy Engine Rules (deterministic — no LLM involvement)

### 8.1 Rule Evaluation Strategy: Priority Ranking (First Match Wins)
When evaluating an event, policy rules are executed sequentially in top-to-bottom order of priority. **The first rule whose condition evaluates to `TRUE` is selected as the winning rule**, and all subsequent rules are short-circuited (skipped). Safety guardrails and hard stopping limits are positioned at the highest priority to prevent unsafe operations regardless of LLM recommendations.

### 8.2 Rule Definitions & Priority Ranking Matrix

```
# PRIORITY 1: Safety Guardrails & Hard Stopping Rules
1. IF failure IN (temporary, card_expired, insufficient_funds, network_timeout, bank_downtime) AND retry_count >= 2
     → STOP (Payment retry limit cap)

2. IF failure = temporary AND amount >= ₹50,000
     → human escalation (High-value transaction safety cap)

# PRIORITY 2: Severe Overdue & Subscription Escalations
3. IF invoice_age_days > 30
     → human escalation

4. IF failure = subscription_failed AND retry_count >= 3
     → pause_subscription_and_escalate

# PRIORITY 3: Targeted Interventions
5. IF failure = card_expired
     → request payment-method update

6. IF failure IN (insufficient_funds, network_timeout, bank_downtime) AND retry_count < 2
     → scheduled_retry_24h

7. IF failure = temporary AND amount < ₹50,000 AND retry_count < 2
     → retry (with 24h cooldown)

8. IF failure = checkout_abandoned AND high_purchase_intent
     → send recovery message

9. IF failure = checkout_abandoned AND NOT high_purchase_intent
     → log_and_suppress (no outreach)

10. IF failure = subscription_failed AND retry_count < 3
     → notify_customer_and_retry

11. IF failure = overdue_invoice AND invoice_age_days > 7 AND invoice_age_days <= 30
     → reminder

12. IF failure = overdue_invoice AND invoice_age_days <= 7
     → gentle_reminder

# PRIORITY 4: Default Fallback Rule
13. IF no prior rule matches
     → log_and_suppress
```

### 8.3 Parameter Definitions
- **`high_purchase_intent`:** Defined deterministically as `(customers.history_json->>'total_orders')::int >= 2 OR (customers.history_json->>'total_spent')::numeric >= 5000 OR recovery_probability >= 0.60`.

### 8.4 LLM Rejection & Downgrade Behavior
The LLM recommender proposes an action and reasoning. The Policy Engine checks the proposal against the winning rule from the Priority Ranking Matrix:
- If the proposed action matches or is safer than the policy rule, it is marked `APPROVED`.
- If the proposed action violates policy (e.g., proposing `retry` when `retry_count >= 2`), the Policy Engine **overrides** the LLM proposal with the policy rule's action (`STOP`) and marks it `DOWNGRADED` or `REJECTED`.
- No LLM re-prompting loop is executed; the deterministic policy action is executed immediately.

### 8.5 Cooldown & Rate Limiting Constraints
- **Payment Retry Cooldown:** Minimum 24 hours between automated payment retries.
- **Messaging Rate Limit:** Maximum 1 recovery message per abandoned checkout session within 7 days.
- **Invoice Reminders:** Maximum 1 reminder per 7-day window.

---

## 9. API Endpoints (MVP Core Suite)

```http
POST /events/ingest        # Ingest a revenue-loss event & trigger autonomous agent loop
                           # Payload: { transaction_id, customer_id, amount, method, failure_type, timestamp, ... }
                           # Response: { case_id, status: "OPEN", expected_recovery_value }

GET  /cases                # List open recovery cases, sorted by expected_recovery_value DESC
                           # Query Params: ?status=OPEN&merchant_id=xyz&limit=50&offset=0
                           # Response: { total: 42, cases: [...] }

GET  /cases/{id}           # Full case detail including decisions, policy evaluation, and audit trail
                           # Response: { case: {...}, decisions: [...], audit_log: [...] }

GET  /metrics/eval         # Run full evaluation suite against the 200 held-out evaluation set
                           # Response: { heldout_events: 200, recovery_rate: 68.5, unnecessary_interventions_pct: 1.2, policy_violations: 0, escalated_cases: 14 }
```

---

## 10. Evaluation Plan & Verification Metrics

Run the full pipeline against the 200-event held-out set (never used for tuning) and report, without fabrication:

1. **Revenue at risk (₹):** Total sum of `amount` across all held-out events.
2. **Potentially recoverable (₹):** Sum of `amount` for held-out events where synthetic ground-truth tag `is_recoverable == true`.
3. **Successfully recovered (₹):** Sum of `amount` where simulated `Verifier` confirms `status == RECOVERED`.
4. **Recovery rate (%):** `(Successfully recovered / Revenue at risk) × 100`.
5. **Unnecessary interventions (%):** `(Interventions sent on self-healing or non-recoverable events / Total interventions executed) × 100`.
6. **Policy violations:** Count of actions executed that violated Section 8 rules (must be exactly `0`).
7. **Unresolved / Escalated cases:** Total count of cases marked `ESCALATED` or `OPEN` at evaluation end.

### 10.1 Simulator Verifier Logic
During evaluation and test execution, simulated Payment/Messaging/Escalation tool APIs return deterministic outcomes using synthetic ground-truth transition probabilities:
- Card expiration update requests succeed with **70%** probability upon outreach.
- Temporary payment retry succeeds with **80%** on 1st retry, **40%** on 2nd retry.
- Abandoned checkout recovery messages convert with **35%** probability for high purchase intent customers.

---

## 11. Folder Structure

```
razorrecover/
  PRD.md
  TASKS.md
  BUILD_LOG.md
  data/
    generate_dataset.py
    events_dev.csv
    events_holdout.csv
  backend/
    models.py
    engine/
      revenue_monitor.py
      classifier.py
      recovery_model.py
      recommender.py
      policy_engine.py
      executor.py
      verifier.py
      audit.py
    api/
      main.py
      routes/
    db/
      session.py
  frontend/
    dashboard/
  eval/
    run_eval.py
    report.json
  README.md
```

---

## 12. Build Phases (18-Hour MVP Sprint)

1. **Dataset generator** (1,000 synthetic events: 800 dev / 200 holdout split) — *1.5h*
2. **SQLite DB schema + SQLAlchemy session** — *1.0h*
3. **Revenue monitor** (flag at-risk transactions) — *1.0h*
4. **Root cause classifier** (cause + confidence score) — *1.5h*
5. **Recovery probability model** (simple scikit-learn Logistic Regression / heuristic) — *1.0h*
6. **Policy engine** (Priority Ranking Matrix 1–13 — **Must be 100% complete**) — *2.5h*
7. **LLM recommender** (proposes action + reasoning only, gated by policy engine) — *1.5h*
8. **Tool executor** (simulated payment/messaging/escalation actions) — *1.0h*
9. **Verifier** (confirms whether revenue was actually recovered) — *0.5h*
10. **Audit logger** (records decisions, policy checks, and results to SQLite) — *0.5h*
11. **FastAPI routes** (4 core endpoints: ingest, list cases, case detail, eval) — *1.5h*
12. **React single-page dashboard** (KPI header, case table, "Why?" audit modal) — *3.0h*
13. **Evaluation run against held-out 200 + report & pitch video** — *1.5h*

---

## 13. Submission Requirements (Razorpay Buildathon)

- Public GitHub repository
- 5-minute pitch video (unlisted)
- Architecture documentation (this PRD serves as the base)
- Explanation of what broke during development and how it was resolved — maintained continuously in `BUILD_LOG.md`

---

## 14. Judging Criteria Alignment (from Razorpay's official page)

- **Problem Taste** — real, well-scoped merchant revenue problem (Section 1)
- **Build Quality** — clean repo structure (Section 11), reliable execution
- **AI Judgment** — LLM used only where judgment is needed (classification, recommendation); deterministic code used everywhere else (policy engine, verification)
- **Failure Recovery** — `BUILD_LOG.md` shows what broke and how it was fixed

---

## 15. Phase 2 & Stretch Goals (Post-MVP)

If ahead of schedule after completing the MVP, the following features from the full specification can be implemented:

1. **Scale Dataset to 10,000 Events:** Expand generator to 10,000 synthetic events (8,000 dev / 2,000 holdout).
2. **PostgreSQL Database Server:** Migrate from SQLite to PostgreSQL with Alembic migration scripts.
3. **Manual Operator Execution Endpoint (`POST /cases/{id}/execute`):** Allow manual triggering of case steps.
4. **Human Escalation Resolution Endpoint (`POST /cases/{id}/resolve`):** Provide API & UI workflow for human operators to resolve escalated cases.
5. **Dashboard Summary Endpoint (`GET /metrics/summary`):** Add standalone summary metrics API.
6. **Multi-Page React Dashboard UI:** Add dedicated routing, dark mode toggle, and custom filtering drawers.
7. **Sandbox Messaging Integration:** Connect real Twilio or WhatsApp sandbox APIs for live outreach simulation.