"""
Telemetry Collection Tests

Tests 10 Hz telemetry collection:
- Position (GPS)
- Velocity
- Attitude
- Battery
- GPS status
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock
from collections import deque

from src.telemetry import TelemetryCollector
from src.models import TelemetrySnapshot


class TestTelemetryCollector:
    """Test telemetry collection system."""

    def test_telemetry_collector_init(self):
        """Test initialization."""
        collector = TelemetryCollector(rate_hz=10.0)

        assert collector._rate_hz == 10.0
        assert collector._rate_interval_sec == 0.1
        assert not collector._collecting
        assert collector.get_latest() is None

    def test_telemetry_collector_stub_mode(self):
        """Test stub mode (no MAVSDK)."""
        collector = TelemetryCollector(system=None)

        snapshot = collector._get_stub_telemetry()

        assert snapshot is not None
        assert snapshot.lat == 47.39770
        assert snapshot.lon == 8.54550
        assert snapshot.battery_percent == 100.0
        assert snapshot.gps_fix == "3d"

    @pytest.mark.asyncio
    async def test_start_stop(self):
        """Test start/stop lifecycle."""
        collector = TelemetryCollector(system=None)

        # Start
        await collector.start()
        assert collector._collecting is True
        assert collector._collection_task is not None

        # Give it time to collect
        await asyncio.sleep(0.2)

        # Stop
        await collector.stop()
        assert collector._collecting is False

    @pytest.mark.asyncio
    async def test_get_latest(self):
        """Test getting latest telemetry."""
        collector = TelemetryCollector(system=None)

        # Should be None before start
        assert collector.get_latest() is None

        # Start collection
        await collector.start()
        await asyncio.sleep(0.3)  # Wait for at least 1-2 updates

        # Should have data
        latest = collector.get_latest()
        assert latest is not None
        assert isinstance(latest, TelemetrySnapshot)

        await collector.stop()

    @pytest.mark.asyncio
    async def test_collection_rate(self):
        """Test 10 Hz collection rate."""
        collector = TelemetryCollector(system=None, rate_hz=10.0)

        await collector.start()
        await asyncio.sleep(1.0)  # Collect for 1 second
        await collector.stop()

        stats = collector.get_statistics()

        # Should have ~10 updates in 1 second (±20% tolerance)
        assert 8 <= stats["updates"] <= 12, f"Expected ~10 updates, got {stats['updates']}"

    @pytest.mark.asyncio
    async def test_history(self):
        """Test telemetry history."""
        collector = TelemetryCollector(system=None, history_size=5)

        await collector.start()
        await asyncio.sleep(0.6)  # Collect for 0.6 seconds
        await collector.stop()

        # Get history
        history = collector.get_history(count=10)

        # Should have at least 5 items (0.1 sec intervals)
        assert len(history) >= 5

        # Verify they're TelemetrySnapshot objects
        for snapshot in history:
            assert isinstance(snapshot, TelemetrySnapshot)
            assert snapshot.timestamp > 0

    @pytest.mark.asyncio
    async def test_callback(self):
        """Test telemetry callback."""
        collector = TelemetryCollector(system=None)

        received_snapshots = []

        def on_telemetry(snapshot):
            received_snapshots.append(snapshot)

        collector.on_telemetry(on_telemetry)

        await collector.start()
        await asyncio.sleep(0.3)  # Collect 2-3 updates
        await collector.stop()

        # Should have received callbacks
        assert len(received_snapshots) >= 2

    @pytest.mark.asyncio
    async def test_async_callback(self):
        """Test async telemetry callback."""
        collector = TelemetryCollector(system=None)

        received_snapshots = []

        async def on_telemetry(snapshot):
            received_snapshots.append(snapshot)
            await asyncio.sleep(0.01)

        collector.on_telemetry(on_telemetry)

        await collector.start()
        await asyncio.sleep(0.3)
        await collector.stop()

        assert len(received_snapshots) >= 2

    @pytest.mark.asyncio
    async def test_snapshot_fields(self):
        """Test telemetry snapshot has all fields."""
        collector = TelemetryCollector(system=None)

        await collector.start()
        await asyncio.sleep(0.15)
        await collector.stop()

        snapshot = collector.get_latest()
        assert snapshot is not None

        # Check required fields
        assert hasattr(snapshot, "timestamp")
        assert hasattr(snapshot, "lat")
        assert hasattr(snapshot, "lon")
        assert hasattr(snapshot, "altitude_m")
        assert hasattr(snapshot, "vx")
        assert hasattr(snapshot, "vy")
        assert hasattr(snapshot, "vz")
        assert hasattr(snapshot, "roll_deg")
        assert hasattr(snapshot, "pitch_deg")
        assert hasattr(snapshot, "yaw_deg")
        assert hasattr(snapshot, "battery_percent")
        assert hasattr(snapshot, "gps_fix")
        assert hasattr(snapshot, "satellites")
        assert hasattr(snapshot, "armed")
        assert hasattr(snapshot, "flight_mode")

    @pytest.mark.asyncio
    async def test_statistics(self):
        """Test collection statistics."""
        collector = TelemetryCollector(system=None, rate_hz=10.0)

        await collector.start()
        await asyncio.sleep(0.5)
        await collector.stop()

        stats = collector.get_statistics()

        assert "updates" in stats
        assert "actual_rate_hz" in stats
        assert "target_rate_hz" in stats
        assert "history_size" in stats
        assert "collecting" in stats

        assert stats["target_rate_hz"] == 10.0
        assert not stats["collecting"]

    @pytest.mark.asyncio
    async def test_double_start(self):
        """Test that double start is prevented."""
        collector = TelemetryCollector(system=None)

        await collector.start()
        await asyncio.sleep(0.1)

        # Try to start again (should be ignored)
        await collector.start()

        # Should still be collecting
        assert collector._collecting is True

        await collector.stop()

    @pytest.mark.asyncio
    async def test_snapshot_to_dict(self):
        """Test TelemetrySnapshot.to_dict()."""
        collector = TelemetryCollector(system=None)

        await collector.start()
        await asyncio.sleep(0.15)
        await collector.stop()

        snapshot = collector.get_latest()
        data = snapshot.to_dict()

        # Check structure
        assert "position" in data
        assert "velocity" in data
        assert "attitude" in data
        assert "battery" in data
        assert "gps" in data
        assert "state" in data

        # Check nested fields
        assert "lat" in data["position"]
        assert "alt_agl" in data["position"]
        assert "vx" in data["velocity"]
        assert "roll" in data["attitude"]
        assert "percent" in data["battery"]
        assert "satellites" in data["gps"]


class TestTelemetryIntegration:
    """Integration tests for telemetry system."""

    @pytest.mark.asyncio
    async def test_continuous_monitoring(self):
        """Test continuous monitoring for 1 second."""
        collector = TelemetryCollector(system=None, rate_hz=10.0)

        await collector.start()
        await asyncio.sleep(1.0)
        await collector.stop()

        stats = collector.get_statistics()
        history = collector.get_history(count=100)

        # Should have ~10 updates
        assert 9 <= stats["updates"] <= 11, f"Got {stats['updates']} updates"

        # History should match
        assert len(history) <= 10  # Limited by history_size

    @pytest.mark.asyncio
    async def test_telemetry_stability(self):
        """Test telemetry values are stable in stub mode."""
        collector = TelemetryCollector(system=None)

        await collector.start()
        await asyncio.sleep(0.5)
        await collector.stop()

        history = collector.get_history(count=10)

        # In stub mode, GPS should be constant
        assert all(s.lat == 47.39770 for s in history)
        assert all(s.lon == 8.54550 for s in history)
        assert all(s.battery_percent == 100.0 for s in history)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
