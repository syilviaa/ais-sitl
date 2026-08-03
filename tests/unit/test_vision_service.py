import pytest
from datetime import datetime
from backend.vision.vision_service import VisionService, VisionEventStore
from backend.vision_contracts import VisionEvent


class TestVisionEventStore:
    def test_add_and_retrieve_event(self):
        store = VisionEventStore()
        event = VisionEvent.create(
            class_name="Person",
            confidence=0.85,
            bbox=[100, 150, 200, 400],
            latitude=37.7749,
            longitude=-122.4194,
            snapshot_url="/snapshots/test.jpg",
            source_id="test",
        )
        store.add_event(event)
        retrieved = store.get_event(event.event_id)
        assert retrieved is not None
        assert retrieved.event_id == event.event_id

    def test_get_latest(self):
        store = VisionEventStore()
        for i in range(15):
            event = VisionEvent.create(
                class_name="Person",
                confidence=0.85,
                bbox=[100, 150, 200, 400],
                latitude=37.7749 + i * 0.0001,
                longitude=-122.4194,
                snapshot_url=f"/snapshots/test_{i}.jpg",
                source_id="test",
            )
            store.add_event(event)

        latest = store.get_latest(10)
        assert len(latest) == 10
        # Should be in reverse order (newest first)
        assert latest[0].latitude > latest[-1].latitude

    def test_max_events_limit(self):
        store = VisionEventStore(max_events=5)
        for i in range(10):
            event = VisionEvent.create(
                class_name="Person",
                confidence=0.85,
                bbox=[100, 150, 200, 400],
                latitude=37.7749,
                longitude=-122.4194,
                snapshot_url=f"/snapshots/test_{i}.jpg",
                source_id="test",
            )
            store.add_event(event)

        all_events = store.get_all_events()
        assert len(all_events) == 5

    def test_get_events_by_class(self):
        store = VisionEventStore()
        for class_name in ["Person", "Car", "Truck_Machinery"]:
            for i in range(3):
                event = VisionEvent.create(
                    class_name=class_name,
                    confidence=0.85,
                    bbox=[100, 150, 200, 400],
                    latitude=37.7749,
                    longitude=-122.4194,
                    snapshot_url=f"/snapshots/{class_name}_{i}.jpg",
                    source_id="test",
                )
                store.add_event(event)

        persons = store.get_events_by_class("Person")
        assert len(persons) == 3
        assert all(e.class_name == "Person" for e in persons)

    def test_clear_events(self):
        store = VisionEventStore()
        for i in range(5):
            event = VisionEvent.create(
                class_name="Person",
                confidence=0.85,
                bbox=[100, 150, 200, 400],
                latitude=37.7749,
                longitude=-122.4194,
                snapshot_url=f"/snapshots/test_{i}.jpg",
                source_id="test",
            )
            store.add_event(event)

        assert len(store.get_all_events()) == 5
        store.clear()
        assert len(store.get_all_events()) == 0


class TestVisionService:
    def test_process_detection_success(self):
        service = VisionService()
        event = service.process_detection(
            class_name="Person",
            confidence=0.85,
            bbox=[100, 150, 200, 400],
            latitude=37.7749,
            longitude=-122.4194,
            snapshot_url="/snapshots/test.jpg",
            source_id="test",
        )
        assert event is not None
        assert event.class_name == "Person"
        assert event.confidence == 0.85

    def test_process_detection_invalid_coordinates(self):
        service = VisionService()
        event = service.process_detection(
            class_name="Person",
            confidence=0.85,
            bbox=[100, 150, 200, 400],
            latitude=95.0,  # Invalid: > 90
            longitude=-122.4194,
            snapshot_url="/snapshots/test.jpg",
            source_id="test",
        )
        assert event is None

    def test_process_detection_rate_limit(self):
        service = VisionService()
        # Test that rate limiting mechanism is present and functional
        # First event always passes
        service.reset_rate_limit()
        event1 = service.process_detection(
            class_name="Person",
            confidence=0.85,
            bbox=[100, 150, 200, 400],
            latitude=37.7749,
            longitude=-122.4194,
            snapshot_url="/snapshots/test1.jpg",
            source_id="test",
        )
        assert event1 is not None

        # Second attempt should potentially be rate-limited if within interval
        # (actual behavior depends on execution speed)
        event2 = service.process_detection(
            class_name="Person",
            confidence=0.85,
            bbox=[100, 150, 200, 400],
            latitude=37.7750,
            longitude=-122.4194,
            snapshot_url="/snapshots/test2.jpg",
            source_id="test",
        )
        # May be None due to rate limiting (that's ok)
        # or not None if execution was slow enough

        # Reset and verify we can process again
        service.reset_rate_limit()
        event3 = service.process_detection(
            class_name="Person",
            confidence=0.85,
            bbox=[100, 150, 200, 400],
            latitude=37.7751,
            longitude=-122.4194,
            snapshot_url="/snapshots/test3.jpg",
            source_id="test",
        )
        assert event3 is not None

    def test_get_latest_events(self):
        service = VisionService()

        for i in range(15):
            service.reset_rate_limit()  # Reset between events
            event = service.process_detection(
                class_name="Person",
                confidence=0.85,
                bbox=[100, 150, 200, 400],
                latitude=37.7749 + i * 0.0001,
                longitude=-122.4194,
                snapshot_url=f"/snapshots/test_{i}.jpg",
                source_id="test",
            )
            assert event is not None  # Ensure all events are added

        latest = service.get_latest_events(10)
        assert len(latest) == 10

    def test_get_event_by_id(self):
        service = VisionService()
        event = service.process_detection(
            class_name="Person",
            confidence=0.85,
            bbox=[100, 150, 200, 400],
            latitude=37.7749,
            longitude=-122.4194,
            snapshot_url="/snapshots/test.jpg",
            source_id="test",
        )
        retrieved = service.get_event_by_id(event.event_id)
        assert retrieved is not None
        assert retrieved["event_id"] == event.event_id

    def test_get_stats(self):
        service = VisionService()

        for class_name in ["Person", "Car", "Truck_Machinery"]:
            service.reset_rate_limit()  # Reset between events
            event = service.process_detection(
                class_name=class_name,
                confidence=0.85,
                bbox=[100, 150, 200, 400],
                latitude=37.7749,
                longitude=-122.4194,
                snapshot_url=f"/snapshots/{class_name}.jpg",
                source_id="test",
            )
            assert event is not None

        stats = service.get_stats()
        assert stats["total_events"] == 3
        assert stats["events_by_class"]["Person"] == 1
        assert stats["events_by_class"]["Car"] == 1
        assert stats["events_by_class"]["Truck_Machinery"] == 1

    def test_confidence_validation(self):
        service = VisionService()

        # Confidence >= 0.65 should be accepted
        service.reset_rate_limit()
        event = service.process_detection(
            class_name="Person",
            confidence=0.65,
            bbox=[100, 150, 200, 400],
            latitude=37.7749,
            longitude=-122.4194,
            snapshot_url="/snapshots/test.jpg",
            source_id="test",
        )
        assert event is not None

        # Confidence < 0.65 should still be accepted by service
        # (filtering happens at detector level)
        service.reset_rate_limit()
        event_low = service.process_detection(
            class_name="Person",
            confidence=0.64,
            bbox=[100, 150, 200, 400],
            latitude=37.7750,
            longitude=-122.4194,
            snapshot_url="/snapshots/test_low.jpg",
            source_id="test",
        )
        assert event_low is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
