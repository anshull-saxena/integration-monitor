import json
import logging
from typing import Any
from sqlalchemy.orm import Session
from src.common.models import DeadLetterModel

logger = logging.getLogger(__name__)


class DeadLetterQueue:
    """Manages recording of unparseable, corrupt, or failed records."""

    @staticmethod
    def record_failure(
        session: Session,
        source_service: str,
        endpoint: str,
        raw_payload: Any,
        error_message: str,
        error_type: str,
        retry_count: int = 0,
    ) -> DeadLetterModel:
        if not isinstance(raw_payload, str):
            try:
                payload_str = json.dumps(raw_payload)
            except Exception:
                payload_str = str(raw_payload)
        else:
            payload_str = raw_payload

        dlq_entry = DeadLetterModel(
            source_service=source_service,
            endpoint=endpoint,
            raw_payload=payload_str,
            error_message=str(error_message),
            error_type=error_type,
            retry_count=retry_count,
        )
        session.add(dlq_entry)
        session.flush()
        logger.warning(
            f"[DLQ] Logged failed record from {source_service} ({error_type}): {error_message}"
        )
        return dlq_entry
