#!/usr/bin/env python3
"""
End-to-end demo: detector output → geo calc → vision service → WebSocket broadcast.

This script simulates the complete pipeline for August 1-3 demo.
"""
import json
import time
from datetime import datetime, timezone
from backend.vision.vision_service import VisionService
from backend.vision.socket_handler import VisionSocketHandler
from backend.geo.geo_calculator import GeoCalculator, BBox
from backend.geo.geo_validation import GeoValidator
from backend.vision_contracts import TelemetrySnapshot


class DemoDetectorOutput:
    """Simulated detector output."""

    detections = [
        {"class": "Person", "conf": 0.92, "bbox": [350, 250, 450, 500], "desc": "Walking person"},
        {"class": "Car", "conf": 0.88, "bbox": [800, 400, 1000, 550], "desc": "Sedan"},
        {"class": "Person", "conf": 0.79, "bbox": [600, 300, 650, 450], "desc": "Person far away"},
        {"class": "Truck_Machinery", "conf": 0.85, "bbox": [1200, 350, 1400, 600], "desc": "Truck"},
        {"class": "Car", "conf": 0.91, "bbox": [500, 450, 700, 600], "desc": "Another car"},
    ]


def create_telemetry(altitude_m: float, yaw_deg: float = 0) -> TelemetrySnapshot:
    """Create telemetry snapshot for demo."""
    utc_now = datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
    return TelemetrySnapshot(
        timestamp=utc_now,
        latitude=37.7749,
        longitude=-122.4194,
        altitude_m=altitude_m,
        drone_yaw_deg=yaw_deg,
        camera_pitch_deg=-70,
        camera_yaw_deg=0,
        hfov_deg=62,
        vfov_deg=48,
        frame_width=1920,
        frame_height=1080,
    )


def broadcast_callback(payload):
    """Callback for WebSocket broadcast."""
    print(f"  📡 Broadcast: {payload['event_type']} at {payload['timestamp']}")
    print(f"     Class: {payload['data']['class_name']}, Conf: {payload['data']['confidence']}")
    print(f"     GPS: ({payload['data']['latitude']:.6f}, {payload['data']['longitude']:.6f})")


def main():
    """Run end-to-end demo."""
    print("=" * 70)
    print("AIS SITL CV MVP - End-to-End Demo")
    print("=" * 70)

    # Initialize components
    vision_service = VisionService()
    socket_handler = VisionSocketHandler(rate_limit_per_sec=10)
    calculator = GeoCalculator()
    validator = GeoValidator()

    # Subscribe socket handlers
    socket_handler.subscribe("vision_detection", broadcast_callback)
    socket_handler.subscribe("vision_alert", broadcast_callback)

    # Test scenarios at different altitudes
    altitudes = [50, 75, 100]

    for altitude in altitudes:
        print(f"\n{'=' * 70}")
        print(f"Scenario: {altitude}m altitude")
        print(f"{'=' * 70}")

        telemetry = create_telemetry(altitude)
        print(f"Telemetry: lat={telemetry.latitude}, lon={telemetry.longitude}, alt={altitude}m")

        # Process simulated detections
        for i, det in enumerate(DemoDetectorOutput.detections, 1):
            print(f"\n[{i}/{len(DemoDetectorOutput.detections)}] {det['desc']}")

            # Extract bbox center
            x1, y1, x2, y2 = det["bbox"]
            bbox = BBox(x1, y1, x2, y2)

            print(f"  Detector: {det['class']} @ ({bbox.center_x:.1f}, {bbox.center_y:.1f}) px")
            print(f"  Confidence: {det['conf']:.2f}")

            # Calculate GPS from pixel coordinates
            try:
                lat, lon = calculator.pixel_to_gps(
                    bbox_center=(bbox.center_x, bbox.center_y),
                    telemetry=telemetry,
                )
                print(f"  GPS: ({lat:.6f}, {lon:.6f})")

                # Create snapshot URL
                snapshot_url = f"/snapshots/{det['class'].lower()}_{i}.jpg"

                # Process through vision service
                event = vision_service.process_detection(
                    class_name=det["class"],
                    confidence=det["conf"],
                    bbox=det["bbox"],
                    latitude=lat,
                    longitude=lon,
                    snapshot_url=snapshot_url,
                    source_id="demo_file",
                    processing_latency_ms=35 + i * 5,
                )

                if event:
                    print(f"  ✓ Event created: {event.event_id[:8]}...")

                    # Broadcast via WebSocket
                    socket_handler.broadcast_detection(event.to_dict())
                else:
                    print(f"  ✗ Rate-limited")

            except ValueError as e:
                print(f"  ✗ Error: {e}")

        # Show stats after each altitude
        stats = vision_service.get_stats()
        print(f"\nStats at {altitude}m:")
        print(f"  Total events: {stats['total_events']}")
        print(f"  By class: {stats['events_by_class']}")

    # Final validation
    print(f"\n{'=' * 70}")
    print("Validation")
    print(f"{'=' * 70}")

    stats = vision_service.get_stats()
    print(f"✓ Total events processed: {stats['total_events']}")
    print(f"✓ Events by class: {stats['events_by_class']}")

    # Test API retrieval
    latest = vision_service.get_latest_events(5)
    print(f"✓ Latest 5 events retrievable: {len(latest)} events")

    # Test geo accuracy on control points
    print("\nGeo accuracy check:")
    control_points = validator.get_control_points()
    for cp in control_points[:3]:
        telemetry = create_telemetry(cp.altitude_m)
        try:
            lat, lon = calculator.pixel_to_gps((cp.pixel_x, cp.pixel_y), telemetry)
            error = validator.calculate_error_m(lat, lon, cp.expected_lat, cp.expected_lon)
            status = "✓" if error <= 10.0 else "✗"
            print(f"  {status} {cp.scenario_name}: {error:.1f}m error")
        except Exception as e:
            print(f"  ✗ {cp.scenario_name}: {e}")

    print(f"\n{'=' * 70}")
    print("Demo complete!")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
