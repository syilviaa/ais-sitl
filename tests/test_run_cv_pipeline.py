"""Tests for publishing pipeline events to the dashboard backend."""

from scripts.run_cv_pipeline import publish_event


class Event:
    def to_dict(self):
        return {"event_id": "event-1"}


class Response:
    def __init__(self):
        self.checked = False

    def raise_for_status(self):
        self.checked = True

    def json(self):
        return {"success": True}


class Session:
    def __init__(self):
        self.calls = []
        self.response = Response()

    def post(self, url, json, timeout):
        self.calls.append((url, json, timeout))
        return self.response


def test_publish_event_uses_canonical_endpoint_and_checks_response():
    session = Session()

    result = publish_event(Event(), "http://127.0.0.1:5001/", session)

    assert session.calls == [(
        "http://127.0.0.1:5001/api/vision/events",
        {"event_id": "event-1"},
        5,
    )]
    assert session.response.checked is True
    assert result == {"success": True}
