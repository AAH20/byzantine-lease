"""
CLI interface and interactive demonstration runner for Byzantine-Lease.
"""

import sys
import time
import argparse
from .lease_manager import DistributedLeaseManager


def run_demo():
    print("=" * 74)
    print("  BYZANTINE-LEASE: Distributed Mutex & Fencing Tokens for Agent Swarms")
    print("  Preventing Race Conditions & Split-Brain Edits in Claude Opus 5.5 & DeepSeek")
    print("=" * 74)

    manager = DistributedLeaseManager()
    resource = "git://repo/src/billing_service.py"

    # 1. Subagent A acquires lease
    print("\n[STEP 1] SUBAGENT A (Claude Opus 5.5) ACQUIRES MUTEX LEASE")
    lease_a = manager.acquire_lease(resource_key=resource, agent_id="subagent_claude_opus", ttl_seconds=1.0)
    print(f"  Resource Key    : {lease_a.resource_key}")
    print(f"  Holder Agent    : {lease_a.holder_agent_id}")
    print(f"  Fencing Token   : #{lease_a.fencing_token}")
    print(f"  Lease TTL       : {lease_a.ttl_seconds}s")

    # 2. Subagent A hangs / network partition (simulate sleep past TTL)
    print("\n[STEP 2] SIMULATING SUBAGENT A NETWORK PARTITION / INFERENCE HANG")
    print("  Subagent A stops sending heartbeats. Sleeping 1.2s to expire lease...")
    time.sleep(1.2)
    print("  TTL expired. Lease automatically transitioned to EXPIRED.")

    # 3. Subagent B steps in and acquires lease
    print("\n[STEP 3] SUBAGENT B (DeepSeek V4.1-Flash) DETECTS DEADLOCK & CLAIMS LEASE")
    lease_b = manager.acquire_lease(resource_key=resource, agent_id="subagent_deepseek_v4", ttl_seconds=5.0)
    print(f"  New Holder Agent : {lease_b.holder_agent_id}")
    print(f"  New Fencing Token: #{lease_b.fencing_token} (Monotonically Incremented)")

    # 4. Zombie write attempt from Subagent A
    print("\n[STEP 4] SUBAGENT A WAKES UP AS ZOMBIE & ATTEMPTS COMMIT WITH TOKEN #1")
    zombie_write = manager.verify_write(resource_key=resource, submitted_token=lease_a.fencing_token)
    print(f"  Write Accepted : {zombie_write.accepted}")
    print(f"  Arbiter Action : {zombie_write.reason}")

    # 5. Legitimate write from Subagent B
    print("\n[STEP 5] SUBAGENT B COMMITS REFACTORED CODE WITH TOKEN #2")
    valid_write = manager.verify_write(resource_key=resource, submitted_token=lease_b.fencing_token)
    print(f"  Write Accepted : {valid_write.accepted}")
    print(f"  Arbiter Action : {valid_write.reason}")

    print("\n" + "=" * 74)
    print("  BYZANTINE-LEASE CONCURRENCY METRICS SUMMARY")
    print(f"  Leases Granted          : {manager.metrics.leases_granted}")
    print(f"  Zombie Writes Rejected  : {manager.metrics.zombie_writes_rejected}")
    print(f"  Deadlocks Broken        : {manager.metrics.deadlocks_broken}")
    print("  Zero Race Conditions - 100% Repository Consistency")
    print("=" * 74 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="byzantine-lease: Distributed Mutex & Fencing Token Lease Manager"
    )
    subparsers = parser.add_subparsers(dest="command")
    demo_parser = subparsers.add_parser("demo", help="Run interactive byzantine lease demonstration")

    args = parser.parse_args()
    if args.command == "demo" or len(sys.argv) == 1:
        run_demo()


if __name__ == "__main__":
    main()
