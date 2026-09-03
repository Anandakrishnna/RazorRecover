# RazorRecover — Development Build Log & Incident Record

**Project:** RazorRecover — Autonomous Revenue Recovery Agent  
**Track:** Razorpay AI Buildathon 2026 — Track 3: AI Revenue Recovery  
**Status:** MVP Sprint Complete (All 13 Phases Implemented & Verified)

---

## 1. Real Technical Incidents & Resolutions

### Incident 1: Gemini API Model Resolution 404 Error (`AQ...` Key)
- **What Broke:** The Gemini live API call threw `google.genai.errors.ClientError: 404 NOT_FOUND. 'This model models/gemini-2.0-flash is no longer available. Please update your code to use models/gemini-3.6-flash...'`.
- **How Diagnosed:** Ran direct SDK diagnostic script `python -c "from google import genai; ..."` to inspect the exact exception payload returned by the `google.genai` SDK. Discovered that the token starting with `AQ...` was authenticated by Google servers, but the requested model string `gemini-2.0-flash` was deprecated. Queried `client.models.list()` to fetch supported models (`gemini-2.5-flash`, `gemini-3.6-flash`, `gemini-flash-latest`).
- **How Fixed:** Updated `LLMRecommender.recommend()` in [`backend/engine/recommender.py`](file:///c:/Users/anandakrishna/Documents/RazorRecover/backend/engine/recommender.py) to use a resilient multi-model resolution loop trying `gemini-2.5-flash`, `gemini-flash-latest`, and `gemini-3.6-flash` sequentially before falling back to legacy SDKs.

### Incident 2: SQLite UNIQUE Constraint Failure on Re-running Pipeline (`audit_log.id`)
- **What Broke:** Re-executing the agent pipeline with an existing `transaction_id` crashed with `sqlite3.IntegrityError: UNIQUE constraint failed: audit_log.id`.
- **How Diagnosed:** Traced Python traceback to [`recovery_model.py`](file:///c:/Users/anandakrishna/Documents/RazorRecover/backend/engine/recovery_model.py) (`id=f"audit_prob_{case.id}"`) and [`policy_engine.py`](file:///c:/Users/anandakrishna/Documents/RazorRecover/backend/engine/policy_engine.py) (`id=f"audit_pol_{case.id}"`). The audit log primary keys were deterministically derived from `case.id`, causing primary key collisions on subsequent runs.
- **How Fixed:** Refactored [`recovery_model.py`](file:///c:/Users/anandakrishna/Documents/RazorRecover/backend/engine/recovery_model.py) and [`policy_engine.py`](file:///c:/Users/anandakrishna/Documents/RazorRecover/backend/engine/policy_engine.py) to use `AuditLogger.log_event()`, generating unique UUID strings (`audit_<uuid4_hex>`) for all audit entries across every pipeline run.

### Incident 3: In-Memory SQLite Session Persistence in FastAPI & Tests
- **What Broke:** FastAPI endpoint `GET /cases` returned `[]` and `GET /cases/{id}` returned `404` despite `POST /events/ingest` returning `200 OK`.
- **How Diagnosed:** In-memory SQLite databases (`sqlite:///:memory:`) create distinct isolated database instances per thread unless configured with static connection pooling. Furthermore, `run_agent_pipeline` executed `session.flush()` without calling `db.commit()`, keeping transactions uncommitted in session scopes.
- **How Fixed:** Added an explicit `db.commit()` at the end of `run_agent_pipeline()` in [`agent_loop.py`](file:///c:/Users/anandakrishna/Documents/RazorRecover/backend/engine/agent_loop.py), and configured `StaticPool` (`sqlalchemy.pool.StaticPool`) in test suite database engines.

### Incident 4: Recovery Probability Score Overflow (> 1.0)
- **What Broke:** Highly loyal customers with prior recovery successes calculated raw probability scores exceeding 1.0 (e.g., 1.07).
- **How Diagnosed:** Inspected tabular formula outputs in [`recovery_model.py`](file:///c:/Users/anandakrishna/Documents/RazorRecover/backend/engine/recovery_model.py) where baseline probability (0.75 for card expiration) plus cumulative bonuses (+0.10 for high LTV, +0.12 for prior recovery) summed above 1.0.
- **How Fixed:** Implemented strict hard-bounding `[0.05, 0.95]` in `RecoveryProbabilityModel.predict()`. Documented that no payment intervention has a 100% guarantee due to real-world gateway/network variances, and no attempt has zero probability.

### Incident 5: Windows Console UnicodeEncodingError (`\u20b9` Rupee Symbol)
- **What Broke:** Executing `python eval/run_eval.py` crashed at stdout formatting with `UnicodeEncodeError: 'charmap' codec can't encode character '\u20b9'`.
- **How Diagnosed:** Windows command prompt default encoding (`cp1252`) cannot render the UTF-8 Indian Rupee symbol `₹`.
- **How Fixed:** Updated terminal print formatting in [`eval/run_eval.py`](file:///c:/Users/anandakrishna/Documents/RazorRecover/eval/run_eval.py) to use `INR` text formatting (`INR 4,827,162.63`) while preserving UTF-8 JSON formatting in [`eval/report.json`](file:///c:/Users/anandakrishna/Documents/RazorRecover/eval/report.json).

### Incident 6: Vite Build Rolldown Failure for Unresolved `lucide-react` Package
- **What Broke:** Running `npm run build` in `frontend/dashboard` failed with `Rolldown failed to resolve import "lucide-react"`.
- **How Diagnosed:** `npm install lucide-react` was launched in a background task that was holding directory locks on `node_modules` when `npm run build` executed.
- **How Fixed:** Cancelled the background task, ran `npm install lucide-react` synchronously, and confirmed `npm run build` compiled 1,819 modules cleanly in 615ms.

---

## 2. Final Evaluation Metrics Summary (`eval/report.json`)

Evaluated across all 200 held-out events (`data/events_holdout.csv`) without post-eval tuning:

- **Total Held-out Events:** 200
- **Total Revenue at Risk:** INR 4,827,162.63
- **Potentially Recoverable Revenue:** INR 2,836,009.25
- **Successfully Recovered Revenue:** INR 2,025,090.68
- **Recovery Rate (%):** **41.95%**
- **Unnecessary Interventions (%):** **6.94%** (10 / 144 interventions)
- **Policy Violations (Target 0):** **0 (Zero Violations)**
- **Case Outcomes:** RECOVERED: 81 | FAILED: 63 | ESCALATED: 21 | STOPPED: 35

---

## 3. Workspace Test Suite Status

Command: `python -m unittest discover tests`

```
.............
----------------------------------------------------------------------
Ran 13 tests in 2.719s

OK
```
All **13 unit tests across all build phases passed with 0 errors**.
