"""Kafka producer for real earthquake events from the USGS GeoJSON API.

Pipeline: USGS API -> Python producer -> Kafka -> Spark -> MongoDB -> Streamlit.

Example:
    python producer.py --bootstrap-servers localhost:9092 \
        --topic earthquake_stream --rate 0.0166667

The rate is in API polls per second; default is one poll every 60 seconds.
"""

import argparse
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests
from kafka import KafkaProducer
from kafka.errors import KafkaError

USGS_API_URL = (
    "https://earthquake.usgs.gov/earthquakes/feed/v1.0/"
    "summary/all_day.geojson"
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


class StreamingDataProducer:
    """Fetch real USGS earthquake events and publish them to Kafka."""

    def __init__(
        self,
        bootstrap_servers: str = "localhost:9092",
        topic: str = "earthquake_stream",
    ) -> None:
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.session = requests.Session()
        self.sent_versions: Dict[str, int] = {}
        self.producer: Optional[KafkaProducer] = None

        try:
            self.producer = KafkaProducer(
                bootstrap_servers=bootstrap_servers,
                acks="all",
                retries=3,
                request_timeout_ms=30000,
                value_serializer=self.serialize_data,
            )
            logger.info("Connected to Kafka at %s, topic=%s", bootstrap_servers, topic)
        except NoBrokersAvailable as exc:
            raise RuntimeError(
                f"Cannot connect to Kafka at {bootstrap_servers}: {exc}"
            ) from exc

    def generate_sample_data(self) -> List[Dict[str, Any]]:
        """Fetch and normalize earthquakes from the USGS daily GeoJSON feed.

        Retains the template method name for compatibility; no data is simulated.
        """
        response = self.session.get(USGS_API_URL, timeout=30)
        response.raise_for_status()
        payload = response.json()

        if not isinstance(payload.get("features"), list):
            raise ValueError("Unexpected USGS response: missing features list")

        records: List[Dict[str, Any]] = []
        for feature in payload["features"]:
            properties = feature.get("properties") or {}
            geometry = feature.get("geometry") or {}
            coords = geometry.get("coordinates") or []

            event_id = feature.get("id")
            time_ms = properties.get("time")
            if not event_id or not isinstance(time_ms, (int, float)) or len(coords) < 3:
                continue

            longitude, latitude, depth_km = coords[:3]
            if not isinstance(latitude, (int, float)) or not isinstance(longitude, (int, float)):
                continue

            timestamp = datetime.fromtimestamp(
                time_ms / 1000, tz=timezone.utc
            ).isoformat().replace("+00:00", "Z")
            updated_ms = properties.get("updated")
            if not isinstance(updated_ms, (int, float)):
                updated_ms = time_ms
            magnitude = properties.get("mag")
            place = properties.get("place") or "Unknown location"

            records.append({
                "event_id": str(event_id),
                "timestamp": timestamp,
                "updated_ms": int(updated_ms),
                "magnitude": magnitude,
                "place": place,
                "latitude": float(latitude),
                "longitude": float(longitude),
                "depth_km": depth_km,
                "tsunami": properties.get("tsunami", 0),
                "source": "USGS",
                # Fields compatible with the original generic dashboard template:
                "metric_type": "earthquake_magnitude",
                "value": magnitude,
                "sensor_id": str(event_id),
                "location": place,
                "unit": "magnitude",
            })

        return records

    @staticmethod
    def serialize_data(data: Dict[str, Any]) -> bytes:
        """Serialize a record as UTF-8 JSON for Kafka."""
        return json.dumps(data, allow_nan=False).encode("utf-8")

    def send_message(self, data: Dict[str, Any]) -> bool:
        """Send one earthquake record, waiting for broker acknowledgement."""
        if self.producer is None:
            logger.error("Kafka producer is not initialized")
            return False
        try:
            future = self.producer.send(self.topic, value=data)
            future.get(timeout=30)
            return True
        except (KafkaError, ValueError, TypeError) as exc:
            logger.error("Failed to publish event %s: %s", data.get("event_id"), exc)
            return False

    def produce_stream(
        self, messages_per_second: float = 1 / 60,
        duration: Optional[int] = None,
    ) -> None:
        """Poll USGS and send only unseen or updated event versions.

        Note: deduplication here is per process. MongoDB must use event_id
        as a unique key and upsert records to deduplicate across restarts.
        """
        if messages_per_second <= 0:
            raise ValueError("--rate must be greater than zero")
        if duration is not None and duration <= 0:
            raise ValueError("--duration must be greater than zero")

        poll_interval = max(60.0, 1.0 / messages_per_second)
        started = time.monotonic()
        sent_count = 0
        logger.info("Polling USGS every %.1f seconds", poll_interval)

        try:
            while duration is None or time.monotonic() - started < duration:
                try:
                    events = self.generate_sample_data()
                    new_count = 0
                    # Oldest first for a more natural history on first import.
                    for event in reversed(events):
                        event_id = event["event_id"]
                        version = event["updated_ms"]
                        if version <= self.sent_versions.get(event_id, -1):
                            continue
                        if self.send_message(event):
                            self.sent_versions[event_id] = version
                            new_count += 1
                            sent_count += 1
                    logger.info(
                        "USGS returned %d events; published %d new/updated events; "
                        "total published=%d",
                        len(events), new_count, sent_count,
                    )
                except (requests.RequestException, ValueError) as exc:
                    logger.error("USGS fetch or parse error: %s", exc)

                elapsed = time.monotonic() - started
                if duration is not None and elapsed >= duration:
                    break
                sleep_seconds = poll_interval
                if duration is not None:
                    sleep_seconds = min(poll_interval, duration - elapsed)
                if sleep_seconds > 0:
                    time.sleep(sleep_seconds)
        except KeyboardInterrupt:
            logger.info("Stopped by user")
        finally:
            self.close()
            logger.info("Producer stopped. Sent %d messages", sent_count)

    def close(self) -> None:
        """Flush and close Kafka connection and HTTP session."""
        if self.producer is not None:
            try:
                self.producer.flush(timeout=15)
                self.producer.close(timeout=15)
            except KafkaError as exc:
                logger.warning("Kafka shutdown warning: %s", exc)
        self.session.close()


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="USGS earthquake API -> Kafka producer"
    )
    parser.add_argument(
        "--bootstrap-servers", default="localhost:9092",
        help="Kafka broker address (default: localhost:9092)",
    )
    parser.add_argument(
        "--topic", default="earthquake_stream",
        help="Kafka topic (default: earthquake_stream)",
    )
    parser.add_argument(
        "--rate", type=float, default=1 / 60,
        help="API polls per second; max once per 60 seconds (default: 1/60)",
    )
    parser.add_argument(
        "--duration", type=int, default=None,
        help="Optional run duration in seconds; omit to run continuously",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    logger.info("Starting real USGS earthquake producer")
    try:
        producer = StreamingDataProducer(
            bootstrap_servers=args.bootstrap_servers,
            topic=args.topic,
        )
        producer.produce_stream(
            messages_per_second=args.rate,
            duration=args.duration,
        )
    except (RuntimeError, ValueError) as exc:
        logger.error("Producer failed: %s", exc)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()


