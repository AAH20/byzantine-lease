"""
Data models and lease definitions for Byzantine-Lease.
Distributed Mutex & Fencing Token Lease Manager for Multi-Agent Swarm Concurrency.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any
import time


class LeaseState(str, Enum):
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    RELEASED = "RELEASED"


@dataclass
class LeaseRecord:
    resource_key: str
    holder_agent_id: str
    fencing_token: int
    granted_at: float = field(default_factory=time.time)
    ttl_seconds: float = 15.0
    expires_at: float = field(default_factory=lambda: time.time() + 15.0)
    heartbeat_count: int = 0
    state: LeaseState = LeaseState.ACTIVE

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at or self.state != LeaseState.ACTIVE


@dataclass
class WriteVerificationResult:
    accepted: bool
    current_fencing_token: int
    submitted_token: int
    reason: str


@dataclass
class LeaseMetrics:
    leases_granted: int = 0
    zombie_writes_rejected: int = 0
    heartbeats_processed: int = 0
    deadlocks_broken: int = 0
