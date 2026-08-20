from pathlib import Path

from fastapi.testclient import TestClient

from app.db.base import get_session_factory
from app.models.activity import MindActivity
from app.services import activity

ACTIVITY_LIMIT = 20


def test_activity_inserts_and_orders_newest_first(
    client: tuple[TestClient, Path],
) -> None:
    test_client, _ = client
    activity.log("clip-scored", "Scored clip 'First' — virality 50/100", ref_id="c1")
    activity.log("experiment-sweep", "Simulated sweep: +20 views across 2 variants")
    activity.log("trend-researched", "Researched 'ai video' — 5 results")

    res = test_client.get(f"/api/v1/dashboard/activity?limit={ACTIVITY_LIMIT}")

    assert res.status_code == 200
    body = res.json()
    assert len(body) == 3
    assert [row["event_type"] for row in body] == [
        "trend-researched",
        "experiment-sweep",
        "clip-scored",
    ]
    assert body[0]["label"] == "Researched 'ai video' — 5 results"
    assert body[0]["detail"] is None
    assert body[0]["ref_id"] is None
    assert body[2]["ref_id"] == "c1"
    for row in body:
        assert set(row.keys()) == {
            "id",
            "event_type",
            "label",
            "detail",
            "ref_id",
            "created_at",
        }


def test_activity_returns_empty_list_when_nothing_logged(
    client: tuple[TestClient, Path],
) -> None:
    test_client, _ = client
    res = test_client.get("/api/v1/dashboard/activity")
    assert res.status_code == 200
    assert res.json() == []


def test_activity_trims_to_newest_500_rows(
    client: tuple[TestClient, Path],
) -> None:
    test_client, _ = client
    for index in range(activity.ACTIVITY_MAX_ROWS + 1):
        activity.log("clip-scored", f"Scored clip 'Clip {index}' — virality 50/100")

    with get_session_factory()() as db:
        total = db.query(MindActivity).count()
        assert total == activity.ACTIVITY_MAX_ROWS

    body = test_client.get("/api/v1/dashboard/activity?limit=100").json()
    assert len(body) == 100
    # The newest 500 survive: the oldest insert (Clip 0) is trimmed, the
    # newest (Clip 500) is kept.
    assert "Scored clip 'Clip 0'" not in {row["label"] for row in body}
    assert body[0]["label"] == "Scored clip 'Clip 500' — virality 50/100"
    assert body[-1]["label"] == "Scored clip 'Clip 401' — virality 50/100"


def test_activity_log_truncates_overlong_labels(
    client: tuple[TestClient, Path],
) -> None:
    test_client, _ = client
    activity.log("mind-notified", "x" * 500)

    res = test_client.get("/api/v1/dashboard/activity?limit=1")

    assert res.status_code == 200
    assert len(res.json()[0]["label"]) == 255