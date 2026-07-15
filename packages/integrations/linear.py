# ContractLens — Linear/Jira integration adapter (sections 12.1, 12.2)
# Draft-then-commit pattern with idempotency keys.

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from packages.domain.schemas import ActionItem, ProviderCredentials


class LinearAdapter:
    """Linear integration for ticket creation.
    
    Section 12.2 rules:
    - Draft then commit
    - Idempotency key required
    - Retries only for transient failures
    - No ticket creation before reviewer approval if severity is critical
    """

    def __init__(self, credentials: Optional[ProviderCredentials] = None):
        self._api_key = (
            credentials.linear_api_key
            if credentials and credentials.linear_api_key
            else os.environ.get("LINEAR_API_KEY", "")
        )
        self._base_url = "https://api.linear.app/graphql"

    def create_idempotency_key(self, contract_id: str, action_type: str) -> str:
        """Generate a deterministic idempotency key.
        
        Uses SHA-256 of (contract_id, action_type, date) so replaying
        the same contract on the same day produces the same key.
        """
        raw = f"{contract_id}:{action_type}:{datetime.now(timezone.utc).date().isoformat()}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def draft_action_item(
        self,
        contract_id: str,
        title: str,
        description: str,
        priority: str = "medium",
    ) -> ActionItem:
        """Create a draft ActionItem for later commit.
        
        Draft-then-commit pattern (section 12.2):
        - Create draft action with idempotency key
        - Store locally
        - Commit only after approval (for critical severity)
        """
        key = self.create_idempotency_key(contract_id, "ticket")
        return ActionItem(
            contract_id=contract_id,
            action_type="TICKET",
            external_system="linear",
            idempotency_key=key,
            payload_json={
                "title": title,
                "description": description,
                "priority": priority,
                "team_id": os.environ.get("LINEAR_TEAM_ID", ""),
            },
            status="draft",
        )

    async def commit_action_item(self, action: ActionItem) -> str:
        """Commit a draft action item — create the Linear ticket.
        
        Idempotent: uses the idempotency key to avoid duplicates.
        Returns the external ticket ID.
        """
        if self._api_key == "":
            raise RuntimeError("LINEAR_API_KEY not configured")

        mutation = """
        mutation IssueCreate($input: IssueCreateInput!) {
            issueCreate(input: $input) {
                success
                issue {
                    id
                    identifier
                }
            }
        }
        """

        variables = {
            "input": {
                "title": action.payload_json["title"],
                "description": action.payload_json["description"],
                "priority": self._linear_priority(action.payload_json.get("priority", "medium")),
                "teamId": action.payload_json.get("team_id"),
                "idempotencyKey": action.idempotency_key,
            }
        }

        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                self._base_url,
                json={"query": mutation, "variables": variables},
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                timeout=30,
            )
            resp.raise_for_status()
            result = resp.json()

        if result.get("data", {}).get("issueCreate", {}).get("success"):
            return result["data"]["issueCreate"]["issue"]["id"]
        raise RuntimeError(f"Linear ticket creation failed: {result}")

    @staticmethod
    def _linear_priority(priority: str) -> int:
        mapping = {"urgent": 1, "high": 2, "medium": 3, "low": 4}
        return mapping.get(priority, 3)


class JiraAdapter:
    """Jira integration for ticket creation (section 12.1, 12.2).
    
    Same draft-then-commit pattern as LinearAdapter.
    """

    def __init__(self, credentials: Optional[ProviderCredentials] = None):
        self._api_key = (
            credentials.jira_api_key
            if credentials and credentials.jira_api_key
            else os.environ.get("JIRA_API_KEY", "")
        )
        self._base_url = os.environ.get("JIRA_BASE_URL", "")
        self._project_key = os.environ.get("JIRA_PROJECT_KEY", "")

    def create_idempotency_key(self, contract_id: str, action_type: str) -> str:
        raw = f"jira:{contract_id}:{action_type}:{datetime.now(timezone.utc).date().isoformat()}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def draft_action_item(
        self,
        contract_id: str,
        summary: str,
        description: str,
        priority: str = "Medium",
    ) -> ActionItem:
        key = self.create_idempotency_key(contract_id, "jira_ticket")
        return ActionItem(
            contract_id=contract_id,
            action_type="TICKET",
            external_system="jira",
            idempotency_key=key,
            payload_json={
                "summary": summary,
                "description": description,
                "priority": priority,
                "project_key": self._project_key,
            },
            status="draft",
        )

    async def commit_action_item(self, action: ActionItem) -> str:
        """Commit a draft — create Jira issue via REST API."""
        if not self._api_key or not self._base_url:
            raise RuntimeError("JIRA_API_KEY and JIRA_BASE_URL must be configured")

        url = f"{self._base_url}/rest/api/3/issue"
        body = {
            "fields": {
                "project": {"key": action.payload_json.get("project_key", self._project_key)},
                "summary": action.payload_json["summary"],
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [
                                {"type": "text", "text": action.payload_json["description"]}
                            ],
                        }
                    ],
                },
                "issuetype": {"name": "Task"},
                "priority": {"name": action.payload_json.get("priority", "Medium")},
            }
        }
        # Idempotency via X-Idempotency-Key header
        headers = {
            "Authorization": f"Basic {self._api_key}",
            "Content-Type": "application/json",
            "X-Idempotency-Key": action.idempotency_key,
        }

        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=body, headers=headers, timeout=30)
            resp.raise_for_status()
            result = resp.json()

        return result.get("id", "")
