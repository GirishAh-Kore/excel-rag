"""
Webhook Manager Module.

This module implements webhook management for event notifications,
including registration, delivery with retries, and delivery tracking.

Key Features:
- Support registration for events: indexing_complete, query_failed,
  low_confidence_answer, batch_complete
- Implement delivery with retry (3 attempts, exponential backoff)
- Track delivery history and status

Supports Requirements 28.1, 28.2, 28.3, 28.4, 28.5.
"""

import asyncio
import hashlib
import hmac
import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional, Protocol, runtime_checkable

import requests

from src.exceptions import WebhookError
from src.models.enterprise import (
    VALID_WEBHOOK_EVENTS,
    WebhookDelivery,
    WebhookRegistration,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Maximum retry attempts for webhook delivery
MAX_RETRY_ATTEMPTS = 3

# Base delay for exponential backoff (seconds)
BASE_RETRY_DELAY_SECONDS = 1.0

# Maximum delay between retries (seconds)
MAX_RETRY_DELAY_SECONDS = 30.0

# HTTP timeout for webhook requests (seconds)
WEBHOOK_TIMEOUT_SECONDS = 10.0

# Signature header name
SIGNATURE_HEADER = "X-Webhook-Signature"

# Timestamp header name
TIMESTAMP_HEADER = "X-Webhook-Timestamp"


# =============================================================================
# Protocols
# =============================================================================


@runtime_checkable
class WebhookStoreProtocol(Protocol):
    """
    Protocol for webhook storage.
    
    Implementations must provide methods for CRUD operations on webhooks
    and delivery records.
    """
    
    def create_webhook(self, webhook: WebhookRegistration) -> bool:
        """Create a new webhook registration."""
        ...
    
    def get_webhook(self, webhook_id: str) -> Optional[WebhookRegistration]:
        """Get webhook by ID."""
        ...
    
    def get_all_webhooks(self) -> list[WebhookRegistration]:
        """Get all webhook registrations."""
        ...
    
    def get_active_webhooks(self) -> list[WebhookRegistration]:
        """Get all active webhook registrations."""
        ...
    
    def get_webhooks_for_event(
        self, event_type: str
    ) -> list[WebhookRegistration]:
        """Get webhooks subscribed to an event."""
        ...
    
    def update_webhook(self, webhook: WebhookRegistration) -> bool:
        """Update an existing webhook."""
        ...
    
    def delete_webhook(self, webhook_id: str) -> bool:
        """Delete a webhook."""
        ...
    
    def create_delivery(self, delivery: WebhookDelivery) -> bool:
        """Create a delivery record."""
        ...
    
    def get_delivery(self, delivery_id: str) -> Optional[WebhookDelivery]:
        """Get delivery by ID."""
        ...
    
    def get_deliveries_for_webhook(
        self,
        webhook_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> list[WebhookDelivery]:
        """Get delivery history for a webhook."""
        ...
    
    def get_pending_deliveries(
        self,
        max_attempts: int = 3,
        limit: int = 100
    ) -> list[WebhookDelivery]:
        """Get pending deliveries that need retry."""
        ...
    
    def update_delivery(self, delivery: WebhookDelivery) -> bool:
        """Update a delivery record."""
        ...
    
    def count_deliveries_for_webhook(self, webhook_id: str) -> int:
        """Count total deliveries for a webhook."""
        ...


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class DeliveryResult:
    """
    Result of a webhook delivery attempt.
    
    Attributes:
        delivery_id: Unique delivery identifier.
        success: Whether delivery was successful.
        status_code: HTTP response status code.
        error_message: Error message if delivery failed.
        attempts: Number of attempts made.
    """
    delivery_id: str
    success: bool
    status_code: Optional[int]
    error_message: Optional[str]
    attempts: int


@dataclass
class WebhookDeliveryHistory:
    """
    Paginated delivery history for a webhook.
    
    Attributes:
        webhook_id: Webhook ID.
        deliveries: List of delivery records.
        total_count: Total number of deliveries.
        page: Current page number.
        page_size: Number of items per page.
        has_more: Whether more pages exist.
    """
    webhook_id: str
    deliveries: list[WebhookDelivery]
    total_count: int
    page: int
    page_size: int
    has_more: bool


# =============================================================================
# Webhook Manager
# =============================================================================


class WebhookManager:
    """
    Manages webhook registrations and event delivery.
    
    Provides functionality for registering webhooks, delivering events
    with retry logic, and tracking delivery history.
    
    All dependencies are injected via constructor following DIP.
    
    Implements Requirements:
    - 28.1: Support registration for events: indexing_complete, query_failed,
            low_confidence_answer, batch_complete
    - 28.2: Expose POST endpoint for registering webhook URLs with event filters
    - 28.3: Retry failed webhook deliveries up to 3 times with exponential backoff
    - 28.4: Include event payload with relevant details
    - 28.5: Expose GET endpoint for delivery history and status
    
    Example:
        >>> manager = WebhookManager(webhook_store=store)
        >>> webhook = manager.register_webhook(
        ...     url="https://example.com/webhook",
        ...     events=["indexing_complete", "query_failed"]
        ... )
        >>> result = await manager.trigger_event(
        ...     event_type="indexing_complete",
        ...     payload={"file_id": "file_123", "chunks_created": 42}
        ... )
    """
    
    def __init__(
        self,
        webhook_store: WebhookStoreProtocol,
        max_retry_attempts: int = MAX_RETRY_ATTEMPTS,
        base_retry_delay: float = BASE_RETRY_DELAY_SECONDS,
        timeout_seconds: float = WEBHOOK_TIMEOUT_SECONDS
    ) -> None:
        """
        Initialize WebhookManager with injected dependencies.
        
        Args:
            webhook_store: Service for storing webhooks and deliveries.
            max_retry_attempts: Maximum retry attempts for delivery.
            base_retry_delay: Base delay for exponential backoff.
            timeout_seconds: HTTP timeout for webhook requests.
            
        Raises:
            ValueError: If any required dependency is None.
        """
        if webhook_store is None:
            raise ValueError("webhook_store is required")
        
        self._webhook_store = webhook_store
        self._max_retry_attempts = max_retry_attempts
        self._base_retry_delay = base_retry_delay
        self._timeout_seconds = timeout_seconds
        
        logger.info(
            f"WebhookManager initialized with max_retries={max_retry_attempts}"
        )
    
    # =========================================================================
    # Webhook Registration
    # =========================================================================
    
    def register_webhook(
        self,
        url: str,
        events: list[str],
        secret: Optional[str] = None
    ) -> WebhookRegistration:
        """
        Register a new webhook for event notifications.
        
        Validates the URL and event types, then creates the webhook
        registration.
        
        Args:
            url: URL to receive webhook POST requests.
            events: List of event types to subscribe to.
            secret: Optional secret for signature verification.
            
        Returns:
            Created WebhookRegistration.
            
        Raises:
            WebhookError: If validation fails or registration fails.
        """
        # Validate URL
        self._validate_url(url)
        
        # Validate events
        self._validate_events(events)
        
        # Generate webhook ID
        webhook_id = f"wh_{uuid.uuid4().hex[:16]}"
        
        # Create webhook object
        webhook = WebhookRegistration(
            webhook_id=webhook_id,
            url=url,
            events=events,
            secret=secret,
            is_active=True
        )
        
        # Store webhook
        success = self._webhook_store.create_webhook(webhook)
        if not success:
            raise WebhookError(
                "Failed to register webhook",
                details={"url": url, "events": events}
            )
        
        logger.info(
            f"Registered webhook {webhook_id} for events: {events}"
        )
        
        return webhook
    
    def get_webhook(self, webhook_id: str) -> Optional[WebhookRegistration]:
        """
        Get a webhook by ID.
        
        Args:
            webhook_id: Unique webhook identifier.
            
        Returns:
            WebhookRegistration if found, None otherwise.
        """
        return self._webhook_store.get_webhook(webhook_id)
    
    def get_all_webhooks(self) -> list[WebhookRegistration]:
        """
        Get all registered webhooks.
        
        Returns:
            List of all WebhookRegistration objects.
        """
        return self._webhook_store.get_all_webhooks()
    
    def update_webhook(
        self,
        webhook_id: str,
        url: Optional[str] = None,
        events: Optional[list[str]] = None,
        secret: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> WebhookRegistration:
        """
        Update an existing webhook.
        
        Args:
            webhook_id: ID of the webhook to update.
            url: Optional new URL.
            events: Optional new event list.
            secret: Optional new secret.
            is_active: Optional new active status.
            
        Returns:
            Updated WebhookRegistration.
            
        Raises:
            WebhookError: If webhook not found or update fails.
        """
        # Get existing webhook
        webhook = self._webhook_store.get_webhook(webhook_id)
        if webhook is None:
            raise WebhookError(
                f"Webhook not found: {webhook_id}",
                details={"webhook_id": webhook_id}
            )
        
        # Validate and update fields
        new_url = webhook.url
        if url is not None:
            self._validate_url(url)
            new_url = url
        
        new_events = webhook.events
        if events is not None:
            self._validate_events(events)
            new_events = events
        
        new_secret = webhook.secret if secret is None else secret
        new_is_active = webhook.is_active if is_active is None else is_active
        
        # Create updated webhook
        updated_webhook = WebhookRegistration(
            webhook_id=webhook_id,
            url=new_url,
            events=new_events,
            secret=new_secret,
            is_active=new_is_active
        )
        
        # Store updated webhook
        success = self._webhook_store.update_webhook(updated_webhook)
        if not success:
            raise WebhookError(
                "Failed to update webhook",
                details={"webhook_id": webhook_id}
            )
        
        logger.info(f"Updated webhook {webhook_id}")
        return updated_webhook
    
    def delete_webhook(self, webhook_id: str) -> bool:
        """
        Delete a webhook.
        
        Args:
            webhook_id: ID of the webhook to delete.
            
        Returns:
            True if deleted successfully.
            
        Raises:
            WebhookError: If webhook not found.
        """
        # Verify webhook exists
        webhook = self._webhook_store.get_webhook(webhook_id)
        if webhook is None:
            raise WebhookError(
                f"Webhook not found: {webhook_id}",
                details={"webhook_id": webhook_id}
            )
        
        success = self._webhook_store.delete_webhook(webhook_id)
        if success:
            logger.info(f"Deleted webhook {webhook_id}")
        
        return success
    
    # =========================================================================
    # Event Triggering and Delivery
    # =========================================================================
    
    async def trigger_event(
        self,
        event_type: str,
        payload: dict[str, Any]
    ) -> list[DeliveryResult]:
        """
        Trigger an event and deliver to all subscribed webhooks.
        
        Finds all active webhooks subscribed to the event type and
        delivers the payload with retry logic.
        
        Args:
            event_type: Type of event to trigger.
            payload: Event payload to deliver.
            
        Returns:
            List of DeliveryResult for each webhook.
            
        Raises:
            WebhookError: If event type is invalid.
        """
        # Validate event type
        if event_type not in VALID_WEBHOOK_EVENTS:
            raise WebhookError(
                f"Invalid event type: {event_type}",
                details={
                    "event_type": event_type,
                    "valid_events": sorted(VALID_WEBHOOK_EVENTS)
                }
            )
        
        # Get webhooks subscribed to this event
        webhooks = self._webhook_store.get_webhooks_for_event(event_type)
        
        if not webhooks:
            logger.debug(f"No webhooks subscribed to event: {event_type}")
            return []
        
        logger.info(
            f"Triggering event {event_type} to {len(webhooks)} webhooks"
        )
        
        # Deliver to all webhooks concurrently
        tasks = [
            self._deliver_to_webhook(webhook, event_type, payload)
            for webhook in webhooks
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        delivery_results = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Delivery failed with exception: {result}")
                delivery_results.append(DeliveryResult(
                    delivery_id="unknown",
                    success=False,
                    status_code=None,
                    error_message=str(result),
                    attempts=0
                ))
            else:
                delivery_results.append(result)
        
        return delivery_results
    
    def trigger_event_sync(
        self,
        event_type: str,
        payload: dict[str, Any]
    ) -> list[DeliveryResult]:
        """
        Synchronous wrapper for trigger_event.
        
        Args:
            event_type: Type of event to trigger.
            payload: Event payload to deliver.
            
        Returns:
            List of DeliveryResult for each webhook.
        """
        return asyncio.run(self.trigger_event(event_type, payload))
    
    async def _deliver_to_webhook(
        self,
        webhook: WebhookRegistration,
        event_type: str,
        payload: dict[str, Any]
    ) -> DeliveryResult:
        """
        Deliver an event to a single webhook with retry logic.
        
        Implements exponential backoff for retries.
        
        Args:
            webhook: Webhook to deliver to.
            event_type: Type of event.
            payload: Event payload.
            
        Returns:
            DeliveryResult with delivery status.
        """
        # Generate delivery ID
        delivery_id = f"del_{uuid.uuid4().hex[:16]}"
        
        # Create initial delivery record
        delivery = WebhookDelivery(
            delivery_id=delivery_id,
            webhook_id=webhook.webhook_id,
            event_type=event_type,
            payload=payload,
            status="pending",
            attempts=0,
            last_attempt_at=None,
            response_code=None
        )
        
        self._webhook_store.create_delivery(delivery)
        
        # Prepare request payload
        request_payload = {
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "delivery_id": delivery_id,
            "data": payload
        }
        
        # Attempt delivery with retries
        last_error: Optional[str] = None
        last_status_code: Optional[int] = None
        
        for attempt in range(1, self._max_retry_attempts + 1):
            try:
                status_code = await self._send_webhook_request(
                    webhook=webhook,
                    payload=request_payload
                )
                
                last_status_code = status_code
                
                # Check if successful (2xx status code)
                if 200 <= status_code < 300:
                    # Update delivery as successful
                    delivery = WebhookDelivery(
                        delivery_id=delivery_id,
                        webhook_id=webhook.webhook_id,
                        event_type=event_type,
                        payload=payload,
                        status="delivered",
                        attempts=attempt,
                        last_attempt_at=datetime.utcnow(),
                        response_code=status_code
                    )
                    self._webhook_store.update_delivery(delivery)
                    
                    logger.info(
                        f"Webhook delivery {delivery_id} succeeded "
                        f"on attempt {attempt}"
                    )
                    
                    return DeliveryResult(
                        delivery_id=delivery_id,
                        success=True,
                        status_code=status_code,
                        error_message=None,
                        attempts=attempt
                    )
                
                # Non-2xx status code
                last_error = f"HTTP {status_code}"
                logger.warning(
                    f"Webhook delivery {delivery_id} attempt {attempt} "
                    f"failed with status {status_code}"
                )
                
            except Exception as e:
                last_error = str(e)
                logger.warning(
                    f"Webhook delivery {delivery_id} attempt {attempt} "
                    f"failed with error: {e}"
                )
            
            # Update delivery with attempt info
            delivery = WebhookDelivery(
                delivery_id=delivery_id,
                webhook_id=webhook.webhook_id,
                event_type=event_type,
                payload=payload,
                status="pending",
                attempts=attempt,
                last_attempt_at=datetime.utcnow(),
                response_code=last_status_code
            )
            self._webhook_store.update_delivery(delivery)
            
            # Calculate backoff delay if not last attempt
            if attempt < self._max_retry_attempts:
                delay = self._calculate_backoff_delay(attempt)
                logger.debug(
                    f"Waiting {delay:.2f}s before retry {attempt + 1}"
                )
                await asyncio.sleep(delay)
        
        # All retries exhausted
        delivery = WebhookDelivery(
            delivery_id=delivery_id,
            webhook_id=webhook.webhook_id,
            event_type=event_type,
            payload=payload,
            status="failed",
            attempts=self._max_retry_attempts,
            last_attempt_at=datetime.utcnow(),
            response_code=last_status_code
        )
        self._webhook_store.update_delivery(delivery)
        
        logger.error(
            f"Webhook delivery {delivery_id} failed after "
            f"{self._max_retry_attempts} attempts: {last_error}"
        )
        
        return DeliveryResult(
            delivery_id=delivery_id,
            success=False,
            status_code=last_status_code,
            error_message=last_error,
            attempts=self._max_retry_attempts
        )
    
    async def _send_webhook_request(
        self,
        webhook: WebhookRegistration,
        payload: dict[str, Any]
    ) -> int:
        """
        Send HTTP POST request to webhook URL.
        
        Args:
            webhook: Webhook to send to.
            payload: Request payload.
            
        Returns:
            HTTP status code.
            
        Raises:
            Exception: If request fails.
        """
        # Prepare headers
        headers = {
            "Content-Type": "application/json",
            TIMESTAMP_HEADER: payload.get("timestamp", ""),
        }
        
        # Add signature if secret is configured
        body = json.dumps(payload)
        if webhook.secret:
            signature = self._generate_signature(body, webhook.secret)
            headers[SIGNATURE_HEADER] = signature
        
        # Send request using requests library in executor to avoid blocking
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: requests.post(
                webhook.url,
                data=body,
                headers=headers,
                timeout=self._timeout_seconds
            )
        )
        return response.status_code
    
    def _calculate_backoff_delay(self, attempt: int) -> float:
        """
        Calculate exponential backoff delay.
        
        Uses formula: base_delay * 2^(attempt-1)
        
        Args:
            attempt: Current attempt number (1-based).
            
        Returns:
            Delay in seconds.
        """
        delay = self._base_retry_delay * (2 ** (attempt - 1))
        return min(delay, MAX_RETRY_DELAY_SECONDS)
    
    @staticmethod
    def _generate_signature(payload: str, secret: str) -> str:
        """
        Generate HMAC-SHA256 signature for payload.
        
        Args:
            payload: JSON payload string.
            secret: Webhook secret.
            
        Returns:
            Hex-encoded signature.
        """
        signature = hmac.new(
            secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return f"sha256={signature}"
    
    # =========================================================================
    # Delivery History
    # =========================================================================
    
    def get_delivery_history(
        self,
        webhook_id: str,
        page: int = 1,
        page_size: int = 20
    ) -> WebhookDeliveryHistory:
        """
        Get delivery history for a webhook.
        
        Args:
            webhook_id: Webhook ID to get history for.
            page: Page number (1-based).
            page_size: Number of items per page.
            
        Returns:
            WebhookDeliveryHistory with paginated deliveries.
            
        Raises:
            WebhookError: If webhook not found.
        """
        # Verify webhook exists
        webhook = self._webhook_store.get_webhook(webhook_id)
        if webhook is None:
            raise WebhookError(
                f"Webhook not found: {webhook_id}",
                details={"webhook_id": webhook_id}
            )
        
        # Calculate offset
        offset = (page - 1) * page_size
        
        # Get deliveries
        deliveries = self._webhook_store.get_deliveries_for_webhook(
            webhook_id=webhook_id,
            limit=page_size,
            offset=offset
        )
        
        # Get total count
        total_count = self._webhook_store.count_deliveries_for_webhook(
            webhook_id
        )
        
        # Calculate has_more
        has_more = (offset + len(deliveries)) < total_count
        
        return WebhookDeliveryHistory(
            webhook_id=webhook_id,
            deliveries=deliveries,
            total_count=total_count,
            page=page,
            page_size=page_size,
            has_more=has_more
        )
    
    def get_delivery(self, delivery_id: str) -> Optional[WebhookDelivery]:
        """
        Get a specific delivery by ID.
        
        Args:
            delivery_id: Unique delivery identifier.
            
        Returns:
            WebhookDelivery if found, None otherwise.
        """
        return self._webhook_store.get_delivery(delivery_id)
    
    # =========================================================================
    # Retry Processing
    # =========================================================================
    
    async def process_pending_deliveries(self) -> list[DeliveryResult]:
        """
        Process all pending deliveries that need retry.
        
        Finds pending deliveries with attempts < max_retry_attempts
        and attempts to deliver them.
        
        Returns:
            List of DeliveryResult for processed deliveries.
        """
        pending = self._webhook_store.get_pending_deliveries(
            max_attempts=self._max_retry_attempts
        )
        
        if not pending:
            logger.debug("No pending deliveries to process")
            return []
        
        logger.info(f"Processing {len(pending)} pending deliveries")
        
        results = []
        for delivery in pending:
            # Get webhook for this delivery
            webhook = self._webhook_store.get_webhook(delivery.webhook_id)
            if webhook is None or not webhook.is_active:
                # Mark as failed if webhook no longer exists or is inactive
                failed_delivery = WebhookDelivery(
                    delivery_id=delivery.delivery_id,
                    webhook_id=delivery.webhook_id,
                    event_type=delivery.event_type,
                    payload=delivery.payload,
                    status="failed",
                    attempts=delivery.attempts,
                    last_attempt_at=datetime.utcnow(),
                    response_code=None
                )
                self._webhook_store.update_delivery(failed_delivery)
                
                results.append(DeliveryResult(
                    delivery_id=delivery.delivery_id,
                    success=False,
                    status_code=None,
                    error_message="Webhook not found or inactive",
                    attempts=delivery.attempts
                ))
                continue
            
            # Retry delivery
            result = await self._retry_delivery(webhook, delivery)
            results.append(result)
        
        return results
    
    async def _retry_delivery(
        self,
        webhook: WebhookRegistration,
        delivery: WebhookDelivery
    ) -> DeliveryResult:
        """
        Retry a single pending delivery.
        
        Args:
            webhook: Webhook to deliver to.
            delivery: Delivery record to retry.
            
        Returns:
            DeliveryResult with retry status.
        """
        # Prepare request payload
        request_payload = {
            "event_type": delivery.event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "delivery_id": delivery.delivery_id,
            "data": delivery.payload
        }
        
        attempt = delivery.attempts + 1
        
        try:
            status_code = await self._send_webhook_request(
                webhook=webhook,
                payload=request_payload
            )
            
            # Check if successful
            if 200 <= status_code < 300:
                updated_delivery = WebhookDelivery(
                    delivery_id=delivery.delivery_id,
                    webhook_id=delivery.webhook_id,
                    event_type=delivery.event_type,
                    payload=delivery.payload,
                    status="delivered",
                    attempts=attempt,
                    last_attempt_at=datetime.utcnow(),
                    response_code=status_code
                )
                self._webhook_store.update_delivery(updated_delivery)
                
                logger.info(
                    f"Retry delivery {delivery.delivery_id} succeeded "
                    f"on attempt {attempt}"
                )
                
                return DeliveryResult(
                    delivery_id=delivery.delivery_id,
                    success=True,
                    status_code=status_code,
                    error_message=None,
                    attempts=attempt
                )
            
            # Non-2xx status code
            error_message = f"HTTP {status_code}"
            
        except Exception as e:
            status_code = None
            error_message = str(e)
        
        # Update delivery with attempt info
        new_status = (
            "failed" if attempt >= self._max_retry_attempts else "pending"
        )
        
        updated_delivery = WebhookDelivery(
            delivery_id=delivery.delivery_id,
            webhook_id=delivery.webhook_id,
            event_type=delivery.event_type,
            payload=delivery.payload,
            status=new_status,
            attempts=attempt,
            last_attempt_at=datetime.utcnow(),
            response_code=status_code
        )
        self._webhook_store.update_delivery(updated_delivery)
        
        logger.warning(
            f"Retry delivery {delivery.delivery_id} attempt {attempt} "
            f"failed: {error_message}"
        )
        
        return DeliveryResult(
            delivery_id=delivery.delivery_id,
            success=False,
            status_code=status_code,
            error_message=error_message,
            attempts=attempt
        )
    
    # =========================================================================
    # Validation Helpers
    # =========================================================================
    
    def _validate_url(self, url: str) -> None:
        """Validate webhook URL."""
        if not url or not url.strip():
            raise WebhookError(
                "Webhook URL cannot be empty",
                details={"url": url}
            )
        
        if not url.startswith(('http://', 'https://')):
            raise WebhookError(
                "Webhook URL must start with http:// or https://",
                details={"url": url}
            )
    
    def _validate_events(self, events: list[str]) -> None:
        """Validate event types."""
        if not events:
            raise WebhookError(
                "At least one event type is required",
                details={"events": events}
            )
        
        invalid_events = [e for e in events if e not in VALID_WEBHOOK_EVENTS]
        if invalid_events:
            raise WebhookError(
                f"Invalid event types: {', '.join(invalid_events)}",
                details={
                    "invalid_events": invalid_events,
                    "valid_events": sorted(VALID_WEBHOOK_EVENTS)
                }
            )
