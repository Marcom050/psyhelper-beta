from __future__ import annotations

from datetime import datetime, timezone


class FakeBillingAdapter:
    provider = "fake"

    def create_checkout_session(self, tenant_id: str, therapist_username: str) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        return {
            "provider": self.provider,
            "checkout_session_id": f"fake_cs_{tenant_id}",
            "billing_customer_id": f"fake_cus_{therapist_username}",
            "billing_subscription_id": f"fake_sub_{tenant_id}",
            "created_at": now,
        }

    def cancel_subscription(self, metadata: dict) -> dict:
        return self.mark_subscription_canceled(metadata)

    def mark_subscription_active(self, metadata: dict) -> dict:
        metadata.update({"billing_status": "active", "subscription_status": "active", "billing_provider": self.provider, "billing_updated_at": datetime.now(timezone.utc).isoformat()})
        return metadata

    def mark_subscription_past_due(self, metadata: dict) -> dict:
        metadata.update({"billing_status": "past_due", "subscription_status": "past_due", "billing_provider": self.provider, "billing_updated_at": datetime.now(timezone.utc).isoformat()})
        return metadata

    def mark_subscription_canceled(self, metadata: dict) -> dict:
        metadata.update({"billing_status": "canceled", "subscription_status": "canceled", "billing_provider": self.provider, "billing_updated_at": datetime.now(timezone.utc).isoformat()})
        return metadata
