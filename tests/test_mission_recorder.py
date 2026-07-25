"""
Tests for Mission Recorder - Flight telemetry capture.
"""

import pytest
from datetime import datetime

from src.backend.services.mission_recorder import MissionRecorder, TelemetrySnapshot


@pytest.fixture
def recorder():
    """Create a mission recorder."""
    return MissionRecorder("mission-001")


class TestTelemetrySnapshot:
    """Test telemetry snapshot data structure."""

    def test_snapshot_creation(self):
        """Test creating a snapshot."""
        snapshot = TelemetrySnapshot(
            timestamp=1721938284.0,
            lat=47.3977,
            lon=8.5455,
            altitude=50.2,
            battery=85.5,
        )

        assert snapshot.lat == 47.3977
        assert snapshot.battery == 85.5

    def test_snapshot_to_dict(self):
        """Test snapshot serialization."""
        snapshot = TelemetrySnapshot(
            timestamp=1721938284.0,
            lat=47.3977,
            lon=8.5455,
            altitude=50.2,
            battery=85.5,
        )

        data = snapshot.to_dict()

        assert data["t"] == 1721938284.0
        assert data["lat"] == 47.3977
        assert data["bat"] == 85.5

    def test_snapshot_from_dict(self):
        """Test snapshot deserialization."""
        data = {
            "t": 1721938284.0,
            "lat": 47.3977,
            "lon": 8.5455,
            "alt": 50.2,
            "bat": 85.5,
        }

        snapshot = TelemetrySnapshot.from_dict(data)

        assert snapshot.timestamp == 1721938284.0
        assert snapshot.lat == 47.3977


class TestMissionRecorderBasics:
    """Test basic recorder operations."""

    @pytest.mark.asyncio
    async def test_start_recording(self, recorder):
        """Test starting a recording."""
        await recorder.start()

        assert recorder.is_recording is True
        assert recorder.start_time is not None

    @pytest.mark.asyncio
    async def test_stop_recording(self, recorder):
        """Test stopping a recording."""
        await recorder.start()
        await recorder.stop()

        assert recorder.is_recording is False
        assert recorder.end_time is not None

    @pytest.mark.asyncio
    async def test_add_snapshot_while_recording(self, recorder):
        """Test adding snapshots during recording."""
        await recorder.start()

        snapshot = TelemetrySnapshot(
            timestamp=1721938284.0,
            lat=47.3977,
            lon=8.5455,
            altitude=50.2,
        )

        await recorder.add_snapshot(snapshot)
        await recorder.stop()

        assert len(recorder.snapshots) == 1

    @pytest.mark.asyncio
    async def test_add_snapshot_not_recording(self, recorder):
        """Test adding snapshots when not recording."""
        snapshot = TelemetrySnapshot(
            timestamp=1721938284.0,
            lat=47.3977,
            lon=8.5455,
            altitude=50.2,
        )

        await recorder.add_snapshot(snapshot)

        assert len(recorder.snapshots) == 0


class TestMissionRecorderStatistics:
    """Test mission statistics calculation."""

    @pytest.mark.asyncio
    async def test_get_duration(self, recorder):
        """Test duration calculation."""
        await recorder.start()

        import time
        time.sleep(0.1)  # 100ms

        await recorder.stop()

        duration = recorder.get_duration()
        assert duration >= 0.1

    @pytest.mark.asyncio
    async def test_get_max_altitude(self, recorder):
        """Test maximum altitude calculation."""
        await recorder.start()

        for alt in [10.0, 50.0, 25.0]:
            snapshot = TelemetrySnapshot(
                timestamp=1721938284.0,
                lat=47.3977,
                lon=8.5455,
                altitude=alt,
            )
            await recorder.add_snapshot(snapshot)

        await recorder.stop()

        max_alt = recorder.get_max_altitude()
        assert max_alt == 50.0

    @pytest.mark.asyncio
    async def test_get_battery_range(self, recorder):
        """Test battery range calculation."""
        await recorder.start()

        for bat in [100.0, 85.0, 70.0]:
            snapshot = TelemetrySnapshot(
                timestamp=1721938284.0,
                lat=47.3977,
                lon=8.5455,
                altitude=50.0,
                battery=bat,
            )
            await recorder.add_snapshot(snapshot)

        await recorder.stop()

        battery = recorder.get_battery_range()
        assert battery["start"] == 100.0
        assert battery["end"] == 70.0
        assert battery["min"] == 70.0
        assert battery["max"] == 100.0

    @pytest.mark.asyncio
    async def test_get_distance(self, recorder):
        """Test distance calculation using Haversine."""
        await recorder.start()

        # Add snapshots along a path (50m apart)
        positions = [
            (47.3977, 8.5455),
            (47.3982, 8.5460),
            (47.3987, 8.5465),
        ]

        for lat, lon in positions:
            snapshot = TelemetrySnapshot(
                timestamp=1721938284.0,
                lat=lat,
                lon=lon,
                altitude=50.0,
            )
            await recorder.add_snapshot(snapshot)

        await recorder.stop()

        distance = recorder.get_distance()
        assert distance > 0  # Should have non-zero distance

    @pytest.mark.asyncio
    async def test_get_statistics(self, recorder):
        """Test full statistics generation."""
        await recorder.start()

        snapshot = TelemetrySnapshot(
            timestamp=1721938284.0,
            lat=47.3977,
            lon=8.5455,
            altitude=50.2,
            battery=85.5,
        )
        await recorder.add_snapshot(snapshot)

        await recorder.stop()

        stats = recorder.get_statistics()

        assert stats["mission_id"] == "mission-001"
        assert stats["frame_count"] == 1
        assert stats["duration_seconds"] >= 0
        assert stats["max_altitude"] == 50.2


class TestMissionRecorderCompression:
    """Test compression and decompression."""

    @pytest.mark.asyncio
    async def test_get_compressed_data(self, recorder):
        """Test compression to JSON."""
        await recorder.start()

        snapshot = TelemetrySnapshot(
            timestamp=1721938284.0,
            lat=47.3977,
            lon=8.5455,
            altitude=50.2,
        )
        await recorder.add_snapshot(snapshot)

        await recorder.stop()

        compressed = recorder.get_compressed_data()

        assert isinstance(compressed, str)
        assert len(compressed) > 0

    @pytest.mark.asyncio
    async def test_from_compressed_data(self, recorder):
        """Test decompression from JSON."""
        await recorder.start()

        snapshot = TelemetrySnapshot(
            timestamp=1721938284.0,
            lat=47.3977,
            lon=8.5455,
            altitude=50.2,
        )
        await recorder.add_snapshot(snapshot)

        await recorder.stop()

        compressed = recorder.get_compressed_data()

        # Recreate from compressed
        new_recorder = MissionRecorder.from_compressed_data("mission-001", compressed)

        assert len(new_recorder.snapshots) == 1
        assert new_recorder.snapshots[0].lat == 47.3977


class TestMissionRecorderPlayback:
    """Test playback timeline generation."""

    @pytest.mark.asyncio
    async def test_playback_timeline_speed_1x(self, recorder):
        """Test playback at 1x speed."""
        await recorder.start()

        for i in range(3):
            snapshot = TelemetrySnapshot(
                timestamp=1721938284.0 + i,
                lat=47.3977 + i * 0.0001,
                lon=8.5455,
                altitude=50.0 + i,
            )
            await recorder.add_snapshot(snapshot)

        await recorder.stop()

        timeline = recorder.playback_timeline(playback_speed=1.0)

        assert len(timeline) == 3
        assert "playback_time" in timeline[0]

    @pytest.mark.asyncio
    async def test_playback_timeline_speed_2x(self, recorder):
        """Test playback at 2x speed (faster)."""
        await recorder.start()

        for i in range(3):
            snapshot = TelemetrySnapshot(
                timestamp=1721938284.0 + i,
                lat=47.3977,
                lon=8.5455,
                altitude=50.0,
            )
            await recorder.add_snapshot(snapshot)

        await recorder.stop()

        timeline = recorder.playback_timeline(playback_speed=2.0)

        assert len(timeline) == 3
        # At 2x speed, time differences should be halved
        assert timeline[1]["playback_time"] < 1.0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
