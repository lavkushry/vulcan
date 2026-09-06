"""Unit tests for Multi-Step Workflow Engine and Distributed Cron Scheduler."""

import unittest
from app.adapters.workflow_manager import workflow_engine


class TestWorkflowManager(unittest.TestCase):
    def test_list_workflows(self):
        wfs = workflow_engine.list_workflows()
        self.assertGreaterEqual(len(wfs), 3)
        ids = [w["workflow_id"] for w in wfs]
        self.assertIn("wf-zero-downtime-patching", ids)
        self.assertIn("wf-ssl-cert-renewal", ids)
        self.assertIn("wf-db-maintenance", ids)

    def test_get_workflow(self):
        wf = workflow_engine.get_workflow("wf-zero-downtime-patching")
        self.assertIsNotNone(wf)
        self.assertEqual(wf["risk_tier"], "HIGH")
        step_ids = [s["step_id"] for s in wf["steps"]]
        self.assertIn("step-1", step_ids)
        self.assertIn("step-rollback", step_ids)

    def test_trigger_workflow_execution(self):
        result = workflow_engine.trigger_workflow("wf-zero-downtime-patching")
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "RUNNING")
        self.assertIn("WF-EXEC-", result["correlation_id"])
        self.assertEqual(result["total_steps"], 7)

    def test_list_and_toggle_schedules(self):
        scheds = workflow_engine.list_schedules()
        self.assertGreaterEqual(len(scheds), 4)
        target = scheds[0]
        original_status = target["status"]

        # Toggle schedule
        updated = workflow_engine.toggle_schedule(target["schedule_id"])
        self.assertTrue(updated["ok"])
        expected_status = "PAUSED" if original_status == "ACTIVE" else "ACTIVE"
        self.assertEqual(updated["status"], expected_status)

        # Toggle back
        restored = workflow_engine.toggle_schedule(target["schedule_id"])
        self.assertTrue(restored["ok"])
        self.assertEqual(restored["status"], original_status)


if __name__ == "__main__":
    unittest.main()
