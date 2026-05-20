from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from uuid import UUID

import asyncpg


POLL_INTERVAL_SECONDS = 5 # how long to sleep between empty polls
NOTIFICATION_BATCH_SIZE = 50 # max events processed per poll cycle


async def _dispatch_notification(
    notification_id: UUID,
    customer_id: UUID,
    notification_category: str,
    notification_message: str,
) -> None:
    """
    Dispatch one methane-emissions notification.
    * replace with real downstream dispatch in production.
        Examples:
            1. await http_client.post("https://alerts.internal/emit", json=payload)
            2. await kafka_producer.send("emissions.events", payload)
            3. await sqs.send_message(QueueUrl=QUEUE_URL, MessageBody=json.dumps(payload))
    
    * For the take-home, we just log the dispatch attempt.
    """
    payload = {
        "notification_id": str(notification_id),
        "customer_id": str(customer_id),
        "notification_category": notification_category,
        "notification_message": notification_message,
    }

    print(
        "[emission-notifications] dispatch "
        f"{notification_category} for customer {customer_id}: "
        f"{json.dumps(payload, separators=(',', ':'))}"
    )

    await asyncio.sleep(0)


async def run_emission_notification_processor(pool: asyncpg.Pool) -> None:
    """
    Long-running background task.
    """
    print(
        "[emission-notifications] processor started "
        f"(poll interval: {POLL_INTERVAL_SECONDS}s, "
        f"batch size: {NOTIFICATION_BATCH_SIZE})"
    )

    while True:
        try:
            await _poll_once(pool)

        except asyncio.CancelledError:
            print("[emission-notifications] processor shutting down")
            break

        except Exception as exc:
            print(f"[emission-notifications] processor error; will retry: {exc}")

        await asyncio.sleep(POLL_INTERVAL_SECONDS)


async def _poll_once(pool: asyncpg.Pool) -> None:
    """
    Process one batch of pending notification rows.
    """
    async with pool.acquire() as conn:
        async with conn.transaction():
            rows = await conn.fetch(
                """
                SELECT
                    notification_id,
                    customer_id,
                    notification_category,
                    notification_message
                FROM emission_notifications
                WHERE is_acknowledged = FALSE
                ORDER BY created_at
                LIMIT $1
                FOR UPDATE SKIP LOCKED
                """,
                NOTIFICATION_BATCH_SIZE,
            )

            if not rows:
                return

            for row in rows:
                notification_id = row["notification_id"]

                try:
                    await _dispatch_notification(
                        notification_id=notification_id,
                        customer_id=row["customer_id"],
                        notification_category=row["notification_category"],
                        notification_message=row["notification_message"],
                    )

                    await conn.execute(
                        """
                        UPDATE emission_notifications
                        SET
                            is_acknowledged = TRUE,
                            acknowledged_at = $1
                        WHERE notification_id = $2
                        """,
                        datetime.now(timezone.utc),
                        notification_id,
                    )

                except Exception as exc:
                    print(
                        "[emission-notifications] dispatch failed for "
                        f"{notification_id}; will retry later: {exc}"
                    )