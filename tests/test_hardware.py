"""
tests/test_hardware.py

Unit tests for hardware/reader.py — covers the LLRPReader class.
All tests mock the sllurp library so no live reader is required.
"""

import sys
import pytest
from unittest.mock import MagicMock, patch

from hardware.reader import LLRPReader


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _mock_sllurp():
    """
    Return (mock_sllurp_pkg, mock_llrp_module, mock_llrp_client) triple.
    Patch sys.modules with both 'sllurp' and 'sllurp.llrp'.
    """
    mock_client = MagicMock()
    mock_llrp = MagicMock()
    mock_llrp.LLRPReaderConfig.return_value = MagicMock()
    mock_llrp.LLRPClient.return_value = mock_client

    mock_pkg = MagicMock()
    mock_pkg.llrp = mock_llrp

    return mock_pkg, mock_llrp, mock_client


# ------------------------------------------------------------------ #
# Tests
# ------------------------------------------------------------------ #

def test_llrp_reader_init_host_and_port():
    """LLRPReader stores host and port and does not crash on init."""
    mock_pkg, mock_llrp, _ = _mock_sllurp()
    with patch.dict(sys.modules, {"sllurp": mock_pkg, "sllurp.llrp": mock_llrp}):
        reader = LLRPReader(host="192.168.1.100", port=5084)
    assert reader.host == "192.168.1.100"
    assert reader.port == 5084


def test_llrp_reader_default_port():
    """LLRPReader defaults to port 5084 when not specified."""
    mock_pkg, mock_llrp, _ = _mock_sllurp()
    with patch.dict(sys.modules, {"sllurp": mock_pkg, "sllurp.llrp": mock_llrp}):
        reader = LLRPReader(host="10.0.0.50")
    assert reader.port == 5084


def test_llrp_reader_tag_callback_epc():
    """Tag read event calls on_tag with the correct EPC hex string."""
    mock_pkg, mock_llrp, _ = _mock_sllurp()
    with patch.dict(sys.modules, {"sllurp": mock_pkg, "sllurp.llrp": mock_llrp}):
        received = []
        reader = LLRPReader(host="192.168.1.100", on_tag=received.append)

    # Simulate sllurp firing a tag report
    epc_bytes = bytes.fromhex("E2004700000000000000001A")
    reader._handle_tags(None, [{"EPC-96": epc_bytes}])

    assert len(received) == 1
    assert received[0] == "E2004700000000000000001A"


def test_llrp_reader_tag_callback_multiple_tags():
    """Multiple tags in a single report all invoke on_tag."""
    mock_pkg, mock_llrp, _ = _mock_sllurp()
    with patch.dict(sys.modules, {"sllurp": mock_pkg, "sllurp.llrp": mock_llrp}):
        received = []
        reader = LLRPReader(host="192.168.1.100", on_tag=received.append)

    tags = [
        {"EPC-96": bytes.fromhex("AABBCCDD00000000AABBCCDD")},
        {"EPC-96": bytes.fromhex("112233440000000011223344")},
    ]
    reader._handle_tags(None, tags)

    assert len(received) == 2
    assert "AABBCCDD00000000AABBCCDD" in received
    assert "112233440000000011223344" in received


def test_llrp_reader_connection_failure_raises():
    """Connection failure from sllurp propagates out of _make_client."""
    mock_pkg, mock_llrp, mock_client = _mock_sllurp()
    mock_client.connect.side_effect = ConnectionRefusedError("Reader not reachable")

    with patch.dict(sys.modules, {"sllurp": mock_pkg, "sllurp.llrp": mock_llrp}):
        reader = LLRPReader(host="192.168.1.100")

    with pytest.raises(ConnectionRefusedError, match="Reader not reachable"):
        reader._make_client()


def test_llrp_reader_stop_disconnects_client():
    """stop() calls disconnect() on the sllurp client and clears _running."""
    mock_pkg, mock_llrp, mock_client = _mock_sllurp()

    with patch.dict(sys.modules, {"sllurp": mock_pkg, "sllurp.llrp": mock_llrp}):
        reader = LLRPReader(host="192.168.1.100")

    reader._client = mock_client
    reader._running = True
    reader.stop()

    assert reader._running is False
    mock_client.disconnect.assert_called_once()


def test_llrp_reader_stop_without_client():
    """stop() when no client is connected does not raise."""
    mock_pkg, mock_llrp, _ = _mock_sllurp()

    with patch.dict(sys.modules, {"sllurp": mock_pkg, "sllurp.llrp": mock_llrp}):
        reader = LLRPReader(host="192.168.1.100")

    reader._client = None
    reader._running = True
    reader.stop()  # Must not raise

    assert reader._running is False


def test_llrp_reader_missing_sllurp_raises_import_error():
    """ImportError is raised with a helpful message when sllurp is not installed."""
    # Temporarily hide sllurp from the import system
    with patch.dict(sys.modules, {"sllurp": None, "sllurp.llrp": None}):
        with pytest.raises(ImportError, match="sllurp"):
            LLRPReader(host="192.168.1.100")
