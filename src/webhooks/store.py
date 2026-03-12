"""
Webhook Store Module.

This module implements storage for webhooks and webhook deliveries
using the SQLite database.

Supports Requirements 28.1, 28.2, 28.5.
"""

import json
import logging
from datetime import datetime
from typing import Optional

from src.database.connection import DatabaseConnection
from src.models.enterprise import WebhookDelivery, WebhookRegistration

logger = logging.getLogger(__name__)


class WebhookStore:
    """
    Storage for webhooks and delivery records.
    
    Provides persistence for webhook registrations and delivery tracking,
    supporting CRUD operations and delivery history queries.
    
    All dependencies are injected via constructor following DIP.
    
    Example:
        >>> store = WebhookStore(db=database_connection)
        >>> store.create_webhook(webhook)
        >>> deliveries = store.get_deliveries_for_webhook("wh_123")
    """
    
    # SQL statements for webhooks
    CREATE_WEBHOOK_SQL = """
        INSERT INTO webhooks 
        (webhook_id, url, events, secret, is_active, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """
    
    GET_WEBHOOK_SQL = """
        SELECT webhook_id, url, events, secret, is_active, created_at
        FROM webhooks
        WHERE webhook_id = ?
    """
    
    GET_ALL_WEBHOOKS_SQL = """
        SELECT webhook_id, url, events, secret, is_active, created_at
        FROM webhooks
        ORDER BY created_at DESC
    """
    
    GET_ACTIVE_WEBHOOKS_SQL = """
        SELECT webhook_id, url, events, secret, is_active, created_at
        FROM webhooks
        WHERE is_active = 1
        ORDER BY created_at DESC
    """
    
    UPDATE_WEBHOOK_SQL = """
        UPDATE webhooks
        SET url = ?, events = ?, secret = ?, is_active = ?, updated_at = ?
        WHERE webhook_id = ?
    """
    
    DELETE_WEBHOOK_SQL = """
        DELETE FROM webhooks
        WHERE webhook_id = ?
    """
    
    # SQL statements for deliveries
    CREATE_DELIVERY_SQL = """
        INSERT INTO webhook_deliveries
        (delivery_id, webhook_id, event_type, payload, status, attempts, 
         last_attempt_at, response_code, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    
    GET_DELIVERY_SQL = """
        SELECT delivery_id, webhook_id, event_type, payload, status, 
               attempts, last_attempt_at, response_code, created_at
        FROM webhook_deliveries
        WHERE delivery_id = ?
    """
    
    GET_DELIVERIES_FOR_WEBHOOK_SQL = """
        SELECT delivery_id, webhook_id, event_type, payload, status,
               attempts, last_attempt_at, response_code, created_at
        FROM webhook_deliveries
        WHERE webhook_id = ?
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
    """
    
    GET_PENDING_DELIVERIES_SQL = """
        SELECT delivery_id, webhook_id, event_type, payload, status,
               attempts, last_attempt_at, response_code, created_at
        FROM webhook_deliveries
        WHERE status = 'pending' AND attempts < ?
        ORDER BY created_at ASC
        LIMIT ?
    """
    
    UPDATE_DELIVERY_SQL = """
        UPDATE webhook_deliveries
        SET status = ?, attempts = ?, last_attempt_at = ?, response_code = ?
        WHERE delivery_id = ?
    """
    
    COUNT_DELIVERIES_FOR_WEBHOOK_SQL = """
        SELECT COUNT(*) as count
        FROM webhook_deliveries
        WHERE webhook_id = ?
    """
    
    def __init__(self, db: DatabaseConnection) -> None:
        """
        Initialize WebhookStore with database connection.
        
        Args:
            db: Database connection for persistence.
            
        Raises:
            ValueError: If db is None.
        """
        if db is None:
            raise ValueError("db is required")
        
        self._db = db
        
        logger.info("WebhookStore initialized")
    
    # =========================================================================
    # Webhook CRUD Operations
    # =========================================================================
    
    def create_webhook(self, webhook: WebhookRegistration) -> bool:
        """
        Create a new webhook registration.
        
        Args:
            webhook: WebhookRegistration to create.
            
        Returns:
            True if created successfully.
        """
        try:
            events_json = json.dumps(webhook.events)
            now = datetime.utcnow().isoformat()
            
            self._db.execute_insert(
                self.CREATE_WEBHOOK_SQL,
                (
                    webhook.webhook_id,
                    webhook.url,
                    events_json,
                    webhook.secret,
                    1 if webhook.is_active else 0,
                    now
                )
            )
            
            logger.debug(f"Created webhook: {webhook.webhook_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create webhook {webhook.webhook_id}: {e}")
            return False
    
    def get_webhook(self, webhook_id: str) -> Optional[WebhookRegistration]:
        """
        Get webhook by ID.
        
        Args:
            webhook_id: Unique webhook identifier.
            
        Returns:
            WebhookRegistration if found, None otherwise.
        """
        try:
            rows = self._db.execute_query(
                self.GET_WEBHOOK_SQL,
                (webhook_id,)
            )
            
            if not rows:
                return None
            
            return self._row_to_webhook(rows[0])
            
        except Exception as e:
            logger.error(f"Failed to get webhook {webhook_id}: {e}")
            return None
    
    def get_all_webhooks(self) -> list[WebhookRegistration]:
        """
        Get all webhook registrations.
        
        Returns:
            List of all WebhookRegistration objects.
        """
        try:
            rows = self._db.execute_query(self.GET_ALL_WEBHOOKS_SQL)
            return [self._row_to_webhook(row) for row in rows]
            
        except Exception as e:
            logger.error(f"Failed to get all webhooks: {e}")
            return []
    
    def get_active_webhooks(self) -> list[WebhookRegistration]:
        """
        Get all active webhook registrations.
        
        Returns:
            List of active WebhookRegistration objects.
        """
        try:
            rows = self._db.execute_query(self.GET_ACTIVE_WEBHOOKS_SQL)
            return [self._row_to_webhook(row) for row in rows]
            
        except Exception as e:
            logger.error(f"Failed to get active webhooks: {e}")
            return []
    
    def get_webhooks_for_event(self, event_type: str) -> list[WebhookRegistration]:
        """
        Get all active webhooks subscribed to a specific event.
        
        Args:
            event_type: Event type to filter by.
            
        Returns:
            List of WebhookRegistration objects subscribed to the event.
        """
        try:
            # Get all active webhooks and filter by event
            active_webhooks = self.get_active_webhooks()
            return [
                webhook for webhook in active_webhooks
                if event_type in webhook.events
            ]
            
        except Exception as e:
            logger.error(f"Failed to get webhooks for event {event_type}: {e}")
            return []
    
    def update_webhook(self, webhook: WebhookRegistration) -> bool:
        """
        Update an existing webhook.
        
        Args:
            webhook: WebhookRegistration with updated values.
            
        Returns:
            True if updated successfully.
        """
        try:
            events_json = json.dumps(webhook.events)
            now = datetime.utcnow().isoformat()
            
            rows_affected = self._db.execute_update(
                self.UPDATE_WEBHOOK_SQL,
                (
                    webhook.url,
                    events_json,
                    webhook.secret,
                    1 if webhook.is_active else 0,
                    now,
                    webhook.webhook_id
                )
            )
            
            return rows_affected > 0
            
        except Exception as e:
            logger.error(f"Failed to update webhook {webhook.webhook_id}: {e}")
            return False
    
    def delete_webhook(self, webhook_id: str) -> bool:
        """
        Delete a webhook and its delivery history.
        
        Args:
            webhook_id: ID of the webhook to delete.
            
        Returns:
            True if deleted successfully.
        """
        try:
            rows_affected = self._db.execute_update(
                self.DELETE_WEBHOOK_SQL,
                (webhook_id,)
            )
            
            return rows_affected > 0
            
        except Exception as e:
            logger.error(f"Failed to delete webhook {webhook_id}: {e}")
            return False
    
    # =========================================================================
    # Delivery CRUD Operations
    # =========================================================================
    
    def create_delivery(self, delivery: WebhookDelivery) -> bool:
        """
        Create a new delivery record.
        
        Args:
            delivery: WebhookDelivery to create.
            
        Returns:
            True if created successfully.
        """
        try:
            payload_json = json.dumps(delivery.payload)
            now = datetime.utcnow().isoformat()
            last_attempt = (
                delivery.last_attempt_at.isoformat() 
                if delivery.last_attempt_at else None
            )
            
            self._db.execute_insert(
                self.CREATE_DELIVERY_SQL,
                (
                    delivery.delivery_id,
                    delivery.webhook_id,
                    delivery.event_type,
                    payload_json,
                    delivery.status,
                    delivery.attempts,
                    last_attempt,
                    delivery.response_code,
                    now
                )
            )
            
            logger.debug(f"Created delivery: {delivery.delivery_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create delivery {delivery.delivery_id}: {e}")
            return False
    
    def get_delivery(self, delivery_id: str) -> Optional[WebhookDelivery]:
        """
        Get delivery by ID.
        
        Args:
            delivery_id: Unique delivery identifier.
            
        Returns:
            WebhookDelivery if found, None otherwise.
        """
        try:
            rows = self._db.execute_query(
                self.GET_DELIVERY_SQL,
                (delivery_id,)
            )
            
            if not rows:
                return None
            
            return self._row_to_delivery(rows[0])
            
        except Exception as e:
            logger.error(f"Failed to get delivery {delivery_id}: {e}")
            return None
    
    def get_deliveries_for_webhook(
        self,
        webhook_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> list[WebhookDelivery]:
        """
        Get delivery history for a webhook.
        
        Args:
            webhook_id: Webhook ID to get deliveries for.
            limit: Maximum number of deliveries to return.
            offset: Number of deliveries to skip.
            
        Returns:
            List of WebhookDelivery objects.
        """
        try:
            rows = self._db.execute_query(
                self.GET_DELIVERIES_FOR_WEBHOOK_SQL,
                (webhook_id, limit, offset)
            )
            
            return [self._row_to_delivery(row) for row in rows]
            
        except Exception as e:
            logger.error(
                f"Failed to get deliveries for webhook {webhook_id}: {e}"
            )
            return []
    
    def get_pending_deliveries(
        self,
        max_attempts: int = 3,
        limit: int = 100
    ) -> list[WebhookDelivery]:
        """
        Get pending deliveries that need retry.
        
        Args:
            max_attempts: Maximum attempts before giving up.
            limit: Maximum number of deliveries to return.
            
        Returns:
            List of pending WebhookDelivery objects.
        """
        try:
            rows = self._db.execute_query(
                self.GET_PENDING_DELIVERIES_SQL,
                (max_attempts, limit)
            )
            
            return [self._row_to_delivery(row) for row in rows]
            
        except Exception as e:
            logger.error(f"Failed to get pending deliveries: {e}")
            return []
    
    def update_delivery(self, delivery: WebhookDelivery) -> bool:
        """
        Update a delivery record.
        
        Args:
            delivery: WebhookDelivery with updated values.
            
        Returns:
            True if updated successfully.
        """
        try:
            last_attempt = (
                delivery.last_attempt_at.isoformat()
                if delivery.last_attempt_at else None
            )
            
            rows_affected = self._db.execute_update(
                self.UPDATE_DELIVERY_SQL,
                (
                    delivery.status,
                    delivery.attempts,
                    last_attempt,
                    delivery.response_code,
                    delivery.delivery_id
                )
            )
            
            return rows_affected > 0
            
        except Exception as e:
            logger.error(f"Failed to update delivery {delivery.delivery_id}: {e}")
            return False
    
    def count_deliveries_for_webhook(self, webhook_id: str) -> int:
        """
        Count total deliveries for a webhook.
        
        Args:
            webhook_id: Webhook ID to count deliveries for.
            
        Returns:
            Total number of deliveries.
        """
        try:
            rows = self._db.execute_query(
                self.COUNT_DELIVERIES_FOR_WEBHOOK_SQL,
                (webhook_id,)
            )
            
            return rows[0]["count"] if rows else 0
            
        except Exception as e:
            logger.error(
                f"Failed to count deliveries for webhook {webhook_id}: {e}"
            )
            return 0
    
    # =========================================================================
    # Helper Methods
    # =========================================================================
    
    def _row_to_webhook(self, row) -> WebhookRegistration:
        """Convert database row to WebhookRegistration."""
        events = json.loads(row["events"]) if row["events"] else []
        
        return WebhookRegistration(
            webhook_id=row["webhook_id"],
            url=row["url"],
            events=events,
            secret=row["secret"],
            is_active=bool(row["is_active"])
        )
    
    def _row_to_delivery(self, row) -> WebhookDelivery:
        """Convert database row to WebhookDelivery."""
        payload = json.loads(row["payload"]) if row["payload"] else {}
        
        # Parse last_attempt_at timestamp
        last_attempt_at = None
        if row["last_attempt_at"]:
            last_attempt_str = row["last_attempt_at"]
            if isinstance(last_attempt_str, str):
                last_attempt_at = datetime.fromisoformat(
                    last_attempt_str.replace('Z', '+00:00')
                )
            else:
                last_attempt_at = last_attempt_str
        
        return WebhookDelivery(
            delivery_id=row["delivery_id"],
            webhook_id=row["webhook_id"],
            event_type=row["event_type"],
            payload=payload,
            status=row["status"],
            attempts=row["attempts"],
            last_attempt_at=last_attempt_at,
            response_code=row["response_code"]
        )
