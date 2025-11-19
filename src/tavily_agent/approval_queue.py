"""
Approval Queue Manager for Human-in-the-Loop workflow.
Manages pending approvals, queue persistence, and approval state.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class ApprovalStatus(str, Enum):
    """Status of an approval request."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    MODIFIED = "modified"


class ApprovalType(str, Enum):
    """Type of approval request."""
    HIGH_RISK_FIELD = "high_risk_field"
    LOW_CONFIDENCE = "low_confidence"
    CONFLICTING_INFO = "conflicting_info"
    ENTITY_BATCH = "entity_batch"
    PRE_SAVE = "pre_save"


class ApprovalRequest:
    """Represents a single approval request."""
    
    def __init__(
        self,
        approval_id: str,
        company_name: str,
        approval_type: ApprovalType,
        field_name: str,
        extracted_value: Any,
        confidence: float,
        sources: List[str],
        reasoning: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.approval_id = approval_id
        self.company_name = company_name
        self.approval_type = approval_type
        self.field_name = field_name
        self.extracted_value = extracted_value
        self.confidence = confidence
        self.sources = sources
        self.reasoning = reasoning
        self.metadata = metadata or {}
        self.status = ApprovalStatus.PENDING
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.reviewed_at: Optional[str] = None
        self.reviewer_decision: Optional[str] = None
        self.approved_value: Any = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "approval_id": self.approval_id,
            "company_name": self.company_name,
            "approval_type": self.approval_type.value,
            "field_name": self.field_name,
            "extracted_value": self.extracted_value,
            "confidence": self.confidence,
            "sources": self.sources,
            "reasoning": self.reasoning,
            "metadata": self.metadata,
            "status": self.status.value,
            "created_at": self.created_at,
            "reviewed_at": self.reviewed_at,
            "reviewer_decision": self.reviewer_decision,
            "approved_value": self.approved_value
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ApprovalRequest":
        """Create from dictionary."""
        approval = cls(
            approval_id=data["approval_id"],
            company_name=data["company_name"],
            approval_type=ApprovalType(data["approval_type"]),
            field_name=data["field_name"],
            extracted_value=data["extracted_value"],
            confidence=data["confidence"],
            sources=data["sources"],
            reasoning=data["reasoning"],
            metadata=data.get("metadata", {})
        )
        approval.status = ApprovalStatus(data["status"])
        approval.created_at = data["created_at"]
        approval.reviewed_at = data.get("reviewed_at")
        approval.reviewer_decision = data.get("reviewer_decision")
        approval.approved_value = data.get("approved_value")
        return approval


class ApprovalQueueManager:
    """Manages the approval queue for HITL workflows."""
    
    def __init__(self, queue_file: Optional[Path] = None):
        """
        Initialize the approval queue manager.
        
        Args:
            queue_file: Path to queue JSON file (default: data/approval_queue.json)
        """
        if queue_file is None:
            from tavily_agent.config import DATA_DIR
            queue_file = DATA_DIR / "approval_queue.json"
        
        self.queue_file = queue_file
        self.queue_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize queue file if it doesn't exist
        if not self.queue_file.exists():
            self._save_queue([])
    
    def _load_queue(self) -> List[ApprovalRequest]:
        """Load queue from file."""
        try:
            with open(self.queue_file, 'r') as f:
                data = json.load(f)
            return [ApprovalRequest.from_dict(item) for item in data]
        except Exception as e:
            logger.error(f"Failed to load approval queue: {e}")
            return []
    
    def _save_queue(self, queue: List[ApprovalRequest]) -> bool:
        """Save queue to file."""
        try:
            with open(self.queue_file, 'w') as f:
                json.dump([item.to_dict() for item in queue], f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to save approval queue: {e}")
            return False
    
    def create_approval(
        self,
        company_name: str,
        approval_type: ApprovalType,
        field_name: str,
        extracted_value: Any,
        confidence: float,
        sources: List[str],
        reasoning: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create a new approval request.
        
        Returns:
            approval_id of the created request
        """
        approval_id = str(uuid.uuid4())
        
        approval = ApprovalRequest(
            approval_id=approval_id,
            company_name=company_name,
            approval_type=approval_type,
            field_name=field_name,
            extracted_value=extracted_value,
            confidence=confidence,
            sources=sources,
            reasoning=reasoning,
            metadata=metadata
        )
        
        queue = self._load_queue()
        queue.append(approval)
        self._save_queue(queue)
        
        logger.info(f"✅ [APPROVAL QUEUE] Created approval request: {approval_id}")
        logger.info(f"   Type: {approval_type.value}, Field: {field_name}, Confidence: {confidence:.2%}")
        
        return approval_id
    
    def get_approval(self, approval_id: str) -> Optional[ApprovalRequest]:
        """Get a specific approval request."""
        queue = self._load_queue()
        for approval in queue:
            if approval.approval_id == approval_id:
                return approval
        return None
    
    def get_pending_approvals(
        self,
        company_name: Optional[str] = None,
        approval_type: Optional[ApprovalType] = None
    ) -> List[ApprovalRequest]:
        """
        Get all pending approval requests.
        
        Args:
            company_name: Filter by company (optional)
            approval_type: Filter by approval type (optional)
        
        Returns:
            List of pending approvals
        """
        queue = self._load_queue()
        pending = [a for a in queue if a.status == ApprovalStatus.PENDING]
        
        if company_name:
            pending = [a for a in pending if a.company_name == company_name]
        
        if approval_type:
            pending = [a for a in pending if a.approval_type == approval_type]
        
        return pending
    
    def approve(
        self,
        approval_id: str,
        approved_value: Optional[Any] = None,
        reviewer_decision: Optional[str] = None
    ) -> bool:
        """
        Approve a request.
        
        Args:
            approval_id: ID of approval to approve
            approved_value: Modified value (if None, uses extracted_value)
            reviewer_decision: Optional note from reviewer
        
        Returns:
            True if successful
        """
        queue = self._load_queue()
        
        for approval in queue:
            if approval.approval_id == approval_id:
                approval.status = ApprovalStatus.APPROVED if approved_value is None else ApprovalStatus.MODIFIED
                approval.approved_value = approved_value if approved_value is not None else approval.extracted_value
                approval.reviewed_at = datetime.now(timezone.utc).isoformat()
                approval.reviewer_decision = reviewer_decision
                
                self._save_queue(queue)
                logger.info(f"✅ [APPROVAL] Approved: {approval_id} ({approval.field_name})")
                return True
        
        logger.warning(f"⚠️ [APPROVAL] Not found: {approval_id}")
        return False
    
    def reject(self, approval_id: str, reviewer_decision: Optional[str] = None) -> bool:
        """
        Reject a request.
        
        Args:
            approval_id: ID of approval to reject
            reviewer_decision: Optional note from reviewer
        
        Returns:
            True if successful
        """
        queue = self._load_queue()
        
        for approval in queue:
            if approval.approval_id == approval_id:
                approval.status = ApprovalStatus.REJECTED
                approval.reviewed_at = datetime.now(timezone.utc).isoformat()
                approval.reviewer_decision = reviewer_decision
                
                self._save_queue(queue)
                logger.info(f"❌ [APPROVAL] Rejected: {approval_id} ({approval.field_name})")
                return True
        
        logger.warning(f"⚠️ [APPROVAL] Not found: {approval_id}")
        return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        queue = self._load_queue()
        
        return {
            "total": len(queue),
            "pending": len([a for a in queue if a.status == ApprovalStatus.PENDING]),
            "approved": len([a for a in queue if a.status == ApprovalStatus.APPROVED]),
            "modified": len([a for a in queue if a.status == ApprovalStatus.MODIFIED]),
            "rejected": len([a for a in queue if a.status == ApprovalStatus.REJECTED]),
            "by_type": {
                at.value: len([a for a in queue if a.approval_type == at])
                for at in ApprovalType
            }
        }
    
    def clear_old_approvals(self, days: int = 7) -> int:
        """
        Clear approved/rejected approvals older than specified days.
        
        Args:
            days: Number of days to keep
        
        Returns:
            Number of approvals cleared
        """
        from datetime import timedelta
        
        queue = self._load_queue()
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        original_count = len(queue)
        queue = [
            a for a in queue
            if a.status == ApprovalStatus.PENDING or
            (a.reviewed_at and datetime.fromisoformat(a.reviewed_at) > cutoff)
        ]
        
        cleared = original_count - len(queue)
        if cleared > 0:
            self._save_queue(queue)
            logger.info(f"🗑️ [APPROVAL QUEUE] Cleared {cleared} old approvals")
        
        return cleared


# Global instance
_approval_queue: Optional[ApprovalQueueManager] = None


def get_approval_queue() -> ApprovalQueueManager:
    """Get or create the global approval queue manager."""
    global _approval_queue
    if _approval_queue is None:
        _approval_queue = ApprovalQueueManager()
    return _approval_queue
