import os
import json
import unittest
from eval.run_eval import run_evaluation, REPORT_JSON

class TestPhase13Eval(unittest.TestCase):
    def test_run_evaluation(self):
        report = run_evaluation()

        self.assertTrue(os.path.exists(REPORT_JSON))
        self.assertEqual(report["evaluation_metadata"]["total_heldout_events"], 200)
        self.assertGreater(report["financial_metrics"]["revenue_at_risk_inr"], 0)
        self.assertGreater(report["financial_metrics"]["successfully_recovered_inr"], 0)
        self.assertGreater(report["financial_metrics"]["recovery_rate_pct"], 0)
        self.assertEqual(report["agent_performance_metrics"]["policy_violations_count"], 0)

if __name__ == "__main__":
    unittest.main()
