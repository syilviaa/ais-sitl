"""
Failsafe monitoring tests

Tests RTL triggering on:
- Low battery (< 20%)
- Critical battery (< 5%)
- Link loss (> 3 seconds)
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from dataclasses import dataclass

from src.failsafe import (
    FailsafeMonitor,
    BatteryMonitor,
    LinkMonitor,
)
from src.models import FailsafeReason, TelemetrySnapshot


# Mock telemetry (use TelemetrySnapshot)
def create_mock_telemetry(
    battery_percent: float = 50.0,
    altitude_m: float = 50.0,
    lat: float = 47.39,
    lon: float = 8.54,
    armed: bool = True,
) -> TelemetrySnapshot:
    """Create mock telemetry snapshot."""
    return TelemetrySnapshot(
        timestamp=time.time(),
        battery_percent=battery_percent,
        altitude_m=altitude_m,
        lat=lat,
        lon=lon,
        armed=armed,
    )


class TestBatteryMonitor:
    """Test battery monitoring."""

    def test_battery_ok(self):
        """Test normal battery level."""
        monitor = BatteryMonitor(warning_percent=20, critical_percent=5)
        result = monitor.check(50.0)
        assert result is None

    def test_battery_warning(self):
        """Test warning threshold."""
        monitor = BatteryMonitor(warning_percent=20, critical_percent=5)
        result = monitor.check(19.0)
        assert result == FailsafeReason.BATTERY_LOW

    def test_battery_critical(self):
        """Test critical threshold."""
        monitor = BatteryMonitor(warning_percent=20, critical_percent=5)
        result = monitor.check(4.0)
        assert result == FailsafeReason.BATTERY_CRITICAL

    def test_battery_status(self):
        """Test battery status reporting."""
        monitor = BatteryMonitor(warning_percent=20, critical_percent=5)
        monitor.check(50.0)
        status = monitor.get_battery_status()

        assert status["percent"] == 50.0
        assert status["status"] == "OK"
        assert status["warning_threshold"] == 20
        assert status["critical_threshold"] == 5


class TestLinkMonitor:
    """Test link loss detection."""

    def test_link_healthy(self):
        """Test healthy link."""
        monitor = LinkMonitor(timeout_sec=3.0)
        monitor.update_heartbeat()
        assert monitor.is_link_healthy() is True

    def test_link_loss(self):
        """Test link loss after timeout."""
        monitor = LinkMonitor(timeout_sec=0.1)
        monitor.update_heartbeat()

        # Wait for timeout
        time.sleep(0.2)

        assert monitor.is_link_healthy() is False

    def test_link_recovery(self):
        """Test link recovery after loss."""
        monitor = LinkMonitor(timeout_sec=0.1)
        monitor.update_heartbeat()

        # Wait for timeout
        time.sleep(0.2)
        assert monitor.is_link_healthy() is False

        # Recover
        monitor.update_heartbeat()
        assert monitor.is_link_healthy() is True

    def test_link_status(self):
        """Test link status details."""
        monitor = LinkMonitor(timeout_sec=3.0)
        monitor.update_heartbeat()
        status = monitor.get_link_status()

        assert status["healthy"] is True
        assert status["timeout_sec"] == 3.0
        assert status["elapsed_sec"] >= 0


class TestFailsafeMonitor:
    """Test failsafe monitoring."""

    @pytest.fixture
    def mock_drone(self):
        """Create mock drone."""
        drone = AsyncMock()
        drone.hold_position = AsyncMock()
        drone.return_to_launch = AsyncMock()
        return drone

    @pytest.fixture
    def mock_telemetry_collector(self):
        """Create mock telemetry collector."""
        collector = Mock()
        collector.get_latest = Mock(return_value=None)
        return collector

    @pytest.mark.asyncio
    async def test_failsafe_init(self, mock_drone, mock_telemetry_collector):
        """Test failsafe initialization."""
        monitor = FailsafeMonitor(
            mock_drone,
            mock_telemetry_collector,
            battery_warning_percent=20.0,
            battery_critical_percent=5.0,
            link_loss_timeout_sec=3.0,
        )

        assert monitor.battery_warning == 20.0
        assert monitor.battery_critical == 5.0
        assert monitor.link_loss_timeout == 3.0
        assert monitor._monitoring is False

    @pytest.mark.asyncio
    async def test_battery_low_triggers_rtl(self, mock_drone, mock_telemetry_collector):
        """Test RTL triggered on low battery."""
        monitor = FailsafeMonitor(
            mock_drone,
            mock_telemetry_collector,
            battery_warning_percent=20.0,
        )

        # Setup telemetry with low battery
        mock_telemetry_collector.get_latest.return_value = create_mock_telemetry(
            battery_percent=19.0,
        )

        # Callback to track RTL
        rtl_triggered = []

        def on_failsafe(reason):
            rtl_triggered.append(reason)

        monitor.on_failsafe(on_failsafe)

        # Check battery condition
        await monitor._check_battery(19.0)

        assert monitor._rtl_triggered is True

    @pytest.mark.asyncio
    async def test_battery_critical_triggers_rtl(self, mock_drone, mock_telemetry_collector):
        """Test RTL triggered on critical battery."""
        monitor = FailsafeMonitor(
            mock_drone,
            mock_telemetry_collector,
            battery_critical_percent=5.0,
        )

        rtl_triggered = []

        def on_failsafe(reason):
            rtl_triggered.append(reason)

        monitor.on_failsafe(on_failsafe)

        await monitor._check_battery(4.0)

        assert monitor._rtl_triggered is True

    @pytest.mark.asyncio
    async def test_link_loss_triggers_rtl(self, mock_drone, mock_telemetry_collector):
        """Test RTL triggered on link loss."""
        monitor = FailsafeMonitor(
            mock_drone,
            mock_telemetry_collector,
            link_loss_timeout_sec=0.1,  # Short timeout for testing
        )

        rtl_triggered = []

        def on_failsafe(reason):
            rtl_triggered.append(reason)

        monitor.on_failsafe(on_failsafe)

        # Simulate link loss (no telemetry for 0.2 seconds)
        monitor._last_telemetry_time = time.time() - 0.2

        await monitor._check_link_health()

        assert monitor._rtl_triggered is True

    @pytest.mark.asyncio
    async def test_rtl_triggered_once(self, mock_drone, mock_telemetry_collector):
        """Test RTL only triggered once."""
        monitor = FailsafeMonitor(
            mock_drone,
            mock_telemetry_collector,
            battery_warning_percent=20.0,
        )

        call_count = []

        async def on_failsafe(reason):
            call_count.append(reason)

        monitor.on_failsafe(on_failsafe)

        # Trigger RTL first time
        await monitor._check_battery(19.0)
        assert len(call_count) == 1

        # Try to trigger again (should be ignored)
        await monitor._check_battery(18.0)
        assert len(call_count) == 1  # Still 1, not 2

    @pytest.mark.asyncio
    async def test_failsafe_sequence(self, mock_drone, mock_telemetry_collector):
        """Test complete RTL sequence."""
        monitor = FailsafeMonitor(
            mock_drone,
            mock_telemetry_collector,
            battery_warning_percent=20.0,
        )

        # Mock landing (altitude reaches 0)
        call_sequence = []

        async def mock_hold_position():
            call_sequence.append("hold")

        async def mock_return_to_launch(reason):
            call_sequence.append("rtl")

        mock_drone.hold_position = mock_hold_position
        mock_drone.return_to_launch = mock_return_to_launch
        mock_telemetry_collector.get_latest = Mock(
            return_value=create_mock_telemetry(
                battery_percent=50.0,
                altitude_m=0.2,
            )
        )

        with patch("asyncio.sleep", new=AsyncMock()):
            await monitor._trigger_rtl(FailsafeReason.BATTERY_LOW)

        # Verify sequence
        assert "hold" in call_sequence
        assert "rtl" in call_sequence


class TestFailsafeIntegration:
    """Integration tests for failsafe system."""

    @pytest.mark.asyncio
    async def test_monitoring_loop(self):
        """Test failsafe monitoring loop."""
        # Create mocks
        drone = AsyncMock()
        drone.hold_position = AsyncMock()
        drone.return_to_launch = AsyncMock()

        telemetry_collector = Mock()
        telemetry_snapshot = create_mock_telemetry(
            battery_percent=50.0,
        )
        telemetry_collector.get_latest = Mock(return_value=telemetry_snapshot)

        telemetry_collector.get_latest = Mock(return_value=telemetry_snapshot)

        monitor = FailsafeMonitor(drone, telemetry_collector)
        monitor._monitoring = True

        for _ in range(3):
            await monitor._check_conditions()

        assert telemetry_collector.get_latest.call_count >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
