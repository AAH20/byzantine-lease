"""
Unit tests for Byzantine-Lease distributed mutex and fencing token validation.
"""

import time
import unittest
from byzantine_lease.models import LeaseState
from byzantine_lease.lease_manager import DistributedLeaseManager


class TestByzantineLease(unittest.TestCase):

    def setUp(self):
        self.mgr = DistributedLeaseManager()

    def test_exclusive_lease_acquisition(self):
        lease1 = self.mgr.acquire_lease("file.py", "agent_1", ttl_seconds=10.0)
        self.assertIsNotNone(lease1)
        self.assertEqual(lease1.fencing_token, 1)

        # Agent 2 attempts to acquire active lease -> None
        lease2 = self.mgr.acquire_lease("file.py", "agent_2", ttl_seconds=10.0)
        self.assertIsNone(lease2)

    def test_fencing_token_monotonic_increment(self):
        l1 = self.mgr.acquire_lease("db_row", "agent_1", ttl_seconds=0.1)
        self.assertEqual(l1.fencing_token, 1)
        time.sleep(0.15)  # wait for expiration

        l2 = self.mgr.acquire_lease("db_row", "agent_2", ttl_seconds=5.0)
        self.assertIsNotNone(l2)
        self.assertEqual(l2.fencing_token, 2)
        self.assertGreater(l2.fencing_token, l1.fencing_token)

    def test_zombie_write_rejection(self):
        l1 = self.mgr.acquire_lease("service.py", "agent_1", ttl_seconds=0.1)
        time.sleep(0.15)  # Expire lease 1

        l2 = self.mgr.acquire_lease("service.py", "agent_2", ttl_seconds=5.0)

        # Stale write attempt with token 1
        res_stale = self.mgr.verify_write("service.py", submitted_token=1)
        self.assertFalse(res_stale.accepted)
        self.assertIn("FencingTokenStale", res_stale.reason)
        self.assertEqual(self.mgr.metrics.zombie_writes_rejected, 1)

        # Valid write attempt with token 2
        res_valid = self.mgr.verify_write("service.py", submitted_token=2)
        self.assertTrue(res_valid.accepted)

    def test_heartbeat_renewal(self):
        l = self.mgr.acquire_lease("task_lock", "agent_1", ttl_seconds=1.0)
        initial_exp = l.expires_at

        time.sleep(0.2)
        self.assertTrue(self.mgr.renew_heartbeat("task_lock", "agent_1", l.fencing_token, extend_seconds=5.0))
        self.assertGreater(l.expires_at, initial_exp)
        self.assertEqual(l.heartbeat_count, 1)

    def test_voluntary_release(self):
        l = self.mgr.acquire_lease("resource_x", "agent_1", ttl_seconds=10.0)
        self.assertTrue(self.mgr.release_lease("resource_x", "agent_1", l.fencing_token))

        # Agent 2 can immediately acquire
        l2 = self.mgr.acquire_lease("resource_x", "agent_2", ttl_seconds=10.0)
        self.assertIsNotNone(l2)


if __name__ == "__main__":
    unittest.main()
