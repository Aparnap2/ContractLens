# ContractLens — SendGrid email adapter (sections 12.1, 12.2)
# Draft-then-commit pattern for negotiation email drafts.

from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from typing import Optional

from packages.domain.schemas import ActionItem, ProviderCredentials


SENDGRID_BASE_URL = "https://api.sendgrid.com/v3"


class SendGridEmailAdapter:
    """SendGrid integration for sending negotiation-email drafts.
    
    Section 12.2 rules:
    - Draft then commit
    - Idempotency key required
    - No email sending before reviewer approval if severity is critical
    - Retries only for transient failures
    """

    def __init__(self, credentials: Optional[ProviderCredentials] = None):
        self._api_key = (
            credentials.sendgrid_api_key
            if credentials and credentials.sendgrid_api_key
            else os.environ.get("SENDGRID_API_KEY", "")
        )
        self._from_email = os.environ.get("SENDGRID_FROM_EMAIL", "noreply@contractlens.local")
        self._from_name = os.environ.get("SENDGRID_FROM_NAME", "ContractLens")

    def create_idempotency_key(self, contract_id: str, recipient: str) -> str:
        """Generate a deterministic idempotency key for email."""
        raw = f"email:{contract_id}:{recipient}:{datetime.now(timezone.utc).date().isoformat()}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def draft_email(
        self,
        contract_id: str,
        to_email: str,
        subject: str,
        body_text: str,
    ) -> ActionItem:
        """Create a draft email action item.
        
        Draft-then-commit pattern: the email is stored as a draft locally.
        It is only sent when commit_action_item() is called, which happens
        after approval for critical findings.
        """
        key = self.create_idempotency_key(contract_id, to_email)
        return ActionItem(
            contract_id=contract_id,
            action_type="EMAIL_DRAFT",
            external_system="sendgrid",
            idempotency_key=key,
            payload_json={
                "to_email": to_email,
                "subject": subject,
                "body_text": body_text,
                "from_email": self._from_email,
                "from_name": self._from_name,
            },
            status="draft",
        )

    async def commit_action_item(self, action: ActionItem) -> str:
        """Commit a draft — send the email via SendGrid API.
        
        Idempotent: uses the idempotency key in the SendGrid
        X-SendGrid-Idempotency-Value header to prevent duplicate sends.
        Returns the SendGrid message ID.
        """
        if self._api_key == "":
            raise RuntimeError("SENDGRID_API_KEY not configured")

        payload = action.payload_json
        body = {
            "personalizations": [
                {"to": [{"email": payload["to_email"]}]}
            ],
            "from": {
                "email": payload.get("from_email", self._from_email),
                "name": payload.get("from_name", self._from_name),
            },
            "subject": payload["subject"],
            "content": [
                {
                    "type": "text/plain",
                    "value": payload["body_text"],
                }
            ],
        }

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "X-SendGrid-Idempotency-Value": action.idempotency_key,
        }

        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{SENDGRID_BASE_URL}/mail/send",
                json=body,
                headers=headers,
                timeout=30,
            )
            resp.raise_for_status()
            # SendGrid returns 202 Accepted with no body on success
            # The message ID is in the X-Message-Id header
            return resp.headers.get("X-Message-Id", "sent")
