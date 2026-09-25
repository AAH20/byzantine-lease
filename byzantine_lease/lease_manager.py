"""
Distributed Mutex & Fencing Token Lease Manager for Byzantine-Lease.
Prevents split-brain file collisions and stale writes in autonomous agent swarms.
"""

import time
from typing import Dict, Optional, List
from .models import LeaseState, LeaseRecord, WriteVerificationResult, LeaseMetrics


class DistributedLeaseManager:
    """Consensus lock manager with monotonically increasing fencing tokens."""

    def __init__(self):
        # resource_key -> LeaseRecord
        self.leases: Dict[str, LeaseRecord] = {}
        # resource_key -> highest fencing token ever issued
        self.highest_fencing_tokens: Dict[str, int] = {}
        self.metrics = LeaseMetrics()

    def acquire_lease(
        self,
        resource_key: str,
        agent_id: str,
        ttl_seconds: float = 15.0
    ) -> Optional[LeaseRecord]:
        """
        Acquires exclusive lease for resource_key.
        If held by an active unexpired lease, returns None.
        If free or prior lease expired, grants new lease with incremented fencing token.
        """
        now = time.time()
        curr_lease = self.leases.get(resource_key)

        # Check if existing lease is still valid
        if curr_lease and curr_lease.state == LeaseState.ACTIVE:
            if now < curr_lease.expires_at:
                if curr_lease.holder_agent_id == agent_id:
                    # Idempotent re-acquisition
                    curr_lease.expires_at = now + ttl_seconds
                    return curr_lease
                return None  # Busy
            else:
                # Expired lease: automatic deadlock eviction
                curr_lease.state = LeaseState.EXPIRED
                self.metrics.deadlocks_broken += 1

        # Allocate new fencing token
        prev_token = self.highest_fencing_tokens.get(resource_key, 0)
        new_token = prev_token + 1
        self.highest_fencing_tokens[resource_key] = new_token

        new_lease = LeaseRecord(
            resource_key=resource_key,
            holder_agent_id=agent_id,
            fencing_token=new_token,
            granted_at=now,
            ttl_seconds=ttl_seconds,
            expires_at=now + ttl_seconds,
            state=LeaseState.ACTIVE
        )

        self.leases[resource_key] = new_lease
        self.metrics.leases_granted += 1
        return new_lease

    def renew_heartbeat(
        self,
        resource_key: str,
        agent_id: str,
        fencing_token: int,
        extend_seconds: float = 15.0
    ) -> bool:
        """Extends TTL lease for active holder."""
        now = time.time()
        lease = self.leases.get(resource_key)

        if not lease or lease.state != LeaseState.ACTIVE:
            return False

        if lease.holder_agent_id != agent_id or lease.fencing_token != fencing_token:
            return False

        if now > lease.expires_at:
            lease.state = LeaseState.EXPIRED
            return False

        lease.expires_at = now + extend_seconds
        lease.heartbeat_count += 1
        self.metrics.heartbeats_processed += 1
        return True

    def release_lease(
        self,
        resource_key: str,
        agent_id: str,
        fencing_token: int
    ) -> bool:
        """Voluntarily releases mutex lock."""
        lease = self.leases.get(resource_key)
        if not lease:
            return False

        if lease.holder_agent_id == agent_id and lease.fencing_token == fencing_token:
            lease.state = LeaseState.RELEASED
            return True
        return False

    def verify_write(self, resource_key: str, submitted_token: int) -> WriteVerificationResult:
        """
        Verifies whether an agent's write operation is legally permitted.
        Rejects stale writes from zombie agents whose lease expired while newer lease was issued!
        """
        highest_token = self.highest_fencing_tokens.get(resource_key, 0)

        if submitted_token < highest_token:
            self.metrics.zombie_writes_rejected += 1
            return WriteVerificationResult(
                accepted=False,
                current_fencing_token=highest_token,
                submitted_token=submitted_token,
                reason=f"FencingTokenStale: Submitted token #{submitted_token} is obsolete. Active token is #{highest_token}. Zombie write blocked."
            )

        lease = self.leases.get(resource_key)
        if not lease or lease.fencing_token != submitted_token:
            return WriteVerificationResult(
                accepted=False,
                current_fencing_token=highest_token,
                submitted_token=submitted_token,
                reason="No matching active lease record found for this resource."
            )

        if lease.is_expired:
            return WriteVerificationResult(
                accepted=False,
                current_fencing_token=highest_token,
                submitted_token=submitted_token,
                reason="Lease expired prior to write verification. Deadlock prevention triggered."
            )

        return WriteVerificationResult(
            accepted=True,
            current_fencing_token=highest_token,
            submitted_token=submitted_token,
            reason="Write verified legally. Fencing token valid and active."
        )

    def evict_expired_leases(self) -> int:
        """Evicts expired leases and returns count."""
        now = time.time()
        evicted = 0
        for lease in self.leases.values():
            if lease.state == LeaseState.ACTIVE and now > lease.expires_at:
                lease.state = LeaseState.EXPIRED
                evicted += 1
                self.metrics.deadlocks_broken += 1
        return evicted
