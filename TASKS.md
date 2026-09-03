# RazorRecover — MVP Implementation Checklist (`TASKS.md`)

This checklist breaks down the 13 build phases into an **MVP Sprint Plan** (18-Hour Budget across 3 Days, Sept 3–5) for the Razorpay AI Buildathon submission.

**Target MVP Scope:** 1,000 events, SQLite DB, 4 core API endpoints, single-page React dashboard.
**Total Estimated Effort:** ~18 Hours

---

## Phase 1: Synthetic Dataset Generator (Est. 1.5 Hours)
- [x] Create `data/generate_dataset.py` generator script
- [x] Implement synthetic schema logic for all 12 fields (`transaction_id`, `customer_id`, `amount`, `payment_method`, `failure_type`, `timestamp`, `retry_history`, `customer_purchase_history`, `subscription_status`, `checkout_behavior`, `invoice_age_days`, `previous_recovery_outcome`)
- [x] Configure 1,000 event distribution target:
  - [x] 40% Temporary payment failures (400 events)
  - [x] 20% Card / payment method issues (200 events)
  - [x] 20% Checkout abandonment (200 events)
  - [x] 10% Subscription failures (100 events)
  - [x] 10% Overdue B2B invoices (100 events)
- [x] Implement synthetic outcome simulation flags (`is_recoverable`, `ground_truth_cause`)
- [x] Split dataset into `data/events_dev.csv` (800 events) and `data/events_holdout.csv` (200 events)
- [x] Add basic dataset validation unit test

---

## Phase 2: SQLite Database & Schema (Est. 1.0 Hour)
- [x] Create SQLite database manager in `backend/db/session.py` using SQLAlchemy/SQLModel (zero-config, `razorrecover.db`)
- [x] Define tables in `backend/db/models.py`:
  - [x] `merchants` table
  - [x] `customers` table (`history_json`, `previous_recovery_outcome`)
  - [x] `transactions` table (`checkout_behavior`, `invoice_age_days`, `retry_history_json`)
  - [x] `recovery_cases` table (`status` enum & timestamps)
  - [x] `agent_decisions` table (`policy_check_result` & `reasoning_text`)
  - [x] `audit_log` table (`event_type` & `detail_json`)
- [x] Write DB auto-creation initialization function on app startup

---

## Phase 3: Revenue Monitor (Est. 1.0 Hour)
- [x] Create `backend/engine/revenue_monitor.py`
- [x] Implement `ingest_event()` function parsing incoming `RevenueEvent` models
- [x] Add at-risk detection logic (flag payment failures, abandoned checkouts, overdue invoices > 0 days, failed subscription renewals)
- [x] Persist case record to SQLite `recovery_cases` table with `OPEN` status

---

## Phase 4: Root Cause Classifier (Est. 1.5 Hours)
- [x] Create `backend/engine/classifier.py`
- [x] Implement hybrid classifier combining deterministic rule rules + LLM fallback
- [x] Map failure types to root cause taxonomy (`CARD_EXPIRED`, `NETWORK_TIMEOUT`, `INSUFFICIENT_FUNDS`, `INTENT_ABANDONED`, `SUBSCRIPTION_LAPSED`, `OVERDUE_INVOICE`)
- [x] Implement confidence score calculation (0.00 to 1.00)
- [x] Write basic unit test evaluating classification on sample dev events

---

## Phase 5: Recovery Probability Model (Est. 1.0 Hour)
- [x] Create `backend/engine/recovery_model.py`
- [x] Implement lightweight scikit-learn `LogisticRegression` pipeline (or deterministic weighted heuristic fallback)
- [x] Predict `recovery_probability` ($P \in [0.0, 1.0]$) using `amount`, `customer_history`, `invoice_age_days`, `previous_recovery_outcome`
- [x] Compute `expected_recovery_value` = $\text{amount} \times \text{recovery\_probability}$

---

## Phase 6: Policy Engine — Priority Ranking Matrix (Est. 2.5 Hours)
- [x] Create `backend/engine/policy_engine.py` (Pure Python — **Must be 100% complete**)
- [x] Implement sequential Priority Ranking Matrix (First Match Wins):
  - [x] **Priority 1 (Safety Guardrails):** Payment `failure IN (temporary, card_expired, insufficient_funds, network_timeout, bank_downtime) AND retry_count >= 2 → STOP`, `amount >= ₹50,000 → human escalation`
  - [x] **Priority 2 (Severe Escalations):** `invoice_age_days > 30 → human escalation`, `subscription_failed AND retry_count >= 3 → pause_and_escalate`
  - [x] **Priority 3 (Targeted Interventions):** Card expired update, 24h retry, intent-gated abandoned checkout outreach, reminders
  - [x] **Priority 4 (Default Fallback):** Default `log_and_suppress`
- [x] Implement `high_purchase_intent` evaluation rule
- [x] Implement policy check validation method (`APPROVED`, `DOWNGRADED`, `REJECTED`)
- [x] Write unit tests verifying all priority rules and stopping guardrails

---

## Phase 7: LLM Recommender (Est. 1.5 Hours)
- [x] Create `backend/engine/recommender.py`
- [x] Design structured JSON prompt for LLM recommendation generation (propose intervention + reasoning text)
- [x] Integrate Gemini / OpenAI API client
- [x] Connect Recommender output to Policy Engine gating (Policy Engine overrides invalid proposals without re-prompting)
- [x] Add offline mock fallback dictionary in case of API network failure during pitch recording

---

## Phase 8: Tool Executor (Simulated Actions) (Est. 1.0 Hour)
- [x] Create `backend/engine/executor.py`
- [x] Implement simulated tool execution methods:
  - [x] Payment API mock (retry execution, payment method update link dispatch)
  - [x] Messaging API mock (WhatsApp/Email abandoned checkout & invoice reminders)
  - [x] Escalation API mock (ticket creation for human operators)
- [x] Enforce cooldown checks (24h payment retry cooldown, 7-day message rate limit)

---

## Phase 9: Verifier Engine (Est. 0.5 Hour)
- [x] Create `backend/engine/verifier.py`
- [x] Implement outcome verification based on synthetic probabilities:
  - [x] 70% success rate for card expiration link updates
  - [x] 80% (1st retry) / 40% (2nd retry) success rate for temporary retries
  - [x] 35% conversion for high-intent abandoned checkouts
- [x] Update `recovery_cases` status (`RECOVERED`, `FAILED`, `ESCALATED`, `STOPPED`) and set `closed_at` timestamp

---

## Phase 10: Audit Logger (Est. 0.5 Hour)
- [x] Create `backend/engine/audit.py`
- [x] Implement structured audit logging function appending to SQLite `audit_log` table (`EVENT_INGESTED`, `CLASSIFIED`, `POLICY_CHECK`, `ACTION_EXECUTED`, `VERIFIED`, `ESCALATED`)


---

## Phase 11: FastAPI Layer (4 Core Endpoints) (Est. 1.5 Hours)
- [x] Create FastAPI app in `backend/api/main.py`
- [x] Implement 4 essential routes:
  - [x] `POST /events/ingest` (Ingest event & execute agent loop)
  - [x] `GET /cases` (List open cases sorted by expected value DESC)
  - [x] `GET /cases/{id}` (Case details + decisions + audit timeline)
  - [x] `GET /metrics/eval` (Trigger evaluation run against 200 holdout events)

---

## Phase 12: React Dashboard UI (Single-Page App) (Est. 3.0 Hours)
- [x] Initialize Next.js / Vite app in `frontend/dashboard/`
- [x] Build single-page UI containing:
  - [x] Header KPI Cards (Revenue at Risk, Recovered Revenue, Recovery Rate %)
  - [x] Open Cases Data Table (sorted by `expected_recovery_value`)
  - [x] Case Detail & "Why?" Decision Modal (visualizing LLM reasoning vs Policy Engine verdict & audit log)
- [x] Connect frontend to FastAPI endpoints

---

## Phase 13: Evaluation Suite & Submission Prep (Est. 1.5 Hours)
- [x] Create `eval/run_eval.py` running pipeline against `data/events_holdout.csv` (200 events)
- [x] Export evaluation report to `eval/report.json`
- [x] Document development resolutions in `BUILD_LOG.md`
- [ ] Record 5-minute unlisted pitch video demonstrating agent loop, policy override, and eval results
- [ ] Submit GitHub repository URL & Pitch video

---

## Phase 2 & Stretch Goals (Post-MVP / Optional)
- [ ] Scale dataset generator to 10,000 synthetic events
- [ ] Migrate database from SQLite to PostgreSQL server with Alembic migrations
- [ ] Implement `POST /cases/{id}/execute` manual operator override endpoint
- [ ] Implement `POST /cases/{id}/resolve` human escalation resolution API endpoint
- [ ] Build multi-page UI dashboard with custom filtering and manual escalation drawer
- [ ] Integrate live Twilio / WhatsApp messaging sandbox APIs
