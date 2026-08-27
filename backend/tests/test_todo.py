from pathlib import Path

from fastapi.testclient import TestClient

from app.models.todo import TodoItemType
from app.services import todo


# ---------------------------------------------------------------------------
# Service-level tests
# ---------------------------------------------------------------------------

def test_create_todo_persists_item(client: tuple[TestClient, Path]) -> None:
    item = todo.create_todo(
        type=TodoItemType.WEEKLY_DIGEST,
        title="Weekly digest",
        body="Summary of this week",
        action_url="/dashboard",
        action_label="View dashboard",
    )
    assert item.id is not None
    assert item.type == TodoItemType.WEEKLY_DIGEST
    assert item.title == "Weekly digest"
    assert item.body == "Summary of this week"
    assert item.action_url == "/dashboard"
    assert item.action_label == "View dashboard"
    assert item.is_read is False
    assert item.is_archived is False
    assert item.created_at is not None


def test_create_todo_without_optional_fields(client: tuple[TestClient, Path]) -> None:
    item = todo.create_todo(
        type=TodoItemType.TREND_ALERT,
        title="Trend detected",
        body="New trend in gaming content",
    )
    assert item.action_url is None
    assert item.action_label is None


def test_list_todos_returns_newest_first(client: tuple[TestClient, Path]) -> None:
    item1 = todo.create_todo(
        type=TodoItemType.CLIP_SUGGESTION, title="First", body="body"
    )
    item2 = todo.create_todo(
        type=TodoItemType.CLIP_SUGGESTION, title="Second", body="body"
    )
    items = todo.list_todos()
    assert len(items) >= 2
    ids = [i.id for i in items]
    assert ids.index(item2.id) < ids.index(item1.id)


def test_list_todos_filters_by_type(client: tuple[TestClient, Path]) -> None:
    todo.create_todo(type=TodoItemType.WEEKLY_DIGEST, title="digest", body="b")
    todo.create_todo(type=TodoItemType.TREND_ALERT, title="alert", body="b")
    items = todo.list_todos(type=TodoItemType.TREND_ALERT)
    assert all(i.type == TodoItemType.TREND_ALERT for i in items)


def test_list_todos_filters_unread(client: tuple[TestClient, Path]) -> None:
    item = todo.create_todo(type=TodoItemType.WEEKLY_DIGEST, title="t", body="b")
    todo.mark_read(item.id)
    unread = todo.list_todos(unread=True)
    assert all(i.is_read is False for i in unread)
    read_items = todo.list_todos(unread=False)
    assert any(i.id == item.id for i in read_items)


def test_list_todos_excludes_archived_by_default(client: tuple[TestClient, Path]) -> None:
    item = todo.create_todo(type=TodoItemType.WEEKLY_DIGEST, title="t", body="b")
    todo.archive(item.id)
    items = todo.list_todos()
    assert all(i.id != item.id for i in items)


def test_list_todos_can_include_archived(client: tuple[TestClient, Path]) -> None:
    item = todo.create_todo(type=TodoItemType.WEEKLY_DIGEST, title="t", body="b")
    todo.archive(item.id)
    items = todo.list_todos(archived=True)
    assert any(i.id == item.id for i in items)


def test_mark_read(client: tuple[TestClient, Path]) -> None:
    item = todo.create_todo(type=TodoItemType.WEEKLY_DIGEST, title="t", body="b")
    assert item.is_read is False
    updated = todo.mark_read(item.id)
    assert updated is not None
    assert updated.is_read is True


def test_mark_read_nonexistent_returns_none(client: tuple[TestClient, Path]) -> None:
    assert todo.mark_read("nonexistent-id") is None


def test_archive(client: tuple[TestClient, Path]) -> None:
    item = todo.create_todo(type=TodoItemType.WEEKLY_DIGEST, title="t", body="b")
    assert item.is_archived is False
    updated = todo.archive(item.id)
    assert updated is not None
    assert updated.is_archived is True


def test_archive_nonexistent_returns_none(client: tuple[TestClient, Path]) -> None:
    assert todo.archive("nonexistent-id") is None


def test_update_todo_sets_both_fields(client: tuple[TestClient, Path]) -> None:
    item = todo.create_todo(type=TodoItemType.WEEKLY_DIGEST, title="t", body="b")
    updated = todo.update_todo(item.id, is_read=True, is_archived=True)
    assert updated is not None
    assert updated.is_read is True
    assert updated.is_archived is True


def test_unread_count(client: tuple[TestClient, Path]) -> None:
    before = todo.unread_count()
    item1 = todo.create_todo(type=TodoItemType.WEEKLY_DIGEST, title="a", body="b")
    item2 = todo.create_todo(type=TodoItemType.WEEKLY_DIGEST, title="c", body="d")
    assert todo.unread_count() == before + 2
    todo.mark_read(item1.id)
    assert todo.unread_count() == before + 1
    todo.archive(item2.id)
    assert todo.unread_count() == before


# ---------------------------------------------------------------------------
# API integration tests
# ---------------------------------------------------------------------------

def test_post_todos_creates_item(client: tuple[TestClient, Path]) -> None:
    test_client, _ = client
    res = test_client.post(
        "/api/v1/todos",
        json={
            "type": "weekly_digest",
            "title": "Test digest",
            "body": "This is a test",
            "action_url": "/dashboard",
            "action_label": "View",
        },
    )
    assert res.status_code == 201
    body = res.json()
    assert body["type"] == "weekly_digest"
    assert body["title"] == "Test digest"
    assert body["is_read"] is False
    assert body["is_archived"] is False
    assert "id" in body
    assert "created_at" in body


def test_post_todos_minimal(client: tuple[TestClient, Path]) -> None:
    test_client, _ = client
    res = test_client.post(
        "/api/v1/todos",
        json={"type": "trend_alert", "title": "Alert", "body": "Something happened"},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["action_url"] is None
    assert body["action_label"] is None


def test_get_todos_returns_items_and_count(client: tuple[TestClient, Path]) -> None:
    test_client, _ = client
    test_client.post(
        "/api/v1/todos",
        json={"type": "weekly_digest", "title": "d1", "body": "b"},
    )
    test_client.post(
        "/api/v1/todos",
        json={"type": "trend_alert", "title": "a1", "body": "b"},
    )
    res = test_client.get("/api/v1/todos")
    assert res.status_code == 200
    body = res.json()
    assert "items" in body
    assert "unread_count" in body
    assert len(body["items"]) >= 2
    assert body["unread_count"] >= 2


def test_get_todos_filters_by_type(client: tuple[TestClient, Path]) -> None:
    test_client, _ = client
    test_client.post(
        "/api/v1/todos",
        json={"type": "weekly_digest", "title": "d", "body": "b"},
    )
    test_client.post(
        "/api/v1/todos",
        json={"type": "trend_alert", "title": "a", "body": "b"},
    )
    res = test_client.get("/api/v1/todos?type=trend_alert")
    assert res.status_code == 200
    items = res.json()["items"]
    assert all(i["type"] == "trend_alert" for i in items)


def test_get_todos_invalid_type_returns_400(client: tuple[TestClient, Path]) -> None:
    test_client, _ = client
    res = test_client.get("/api/v1/todos?type=invalid")
    assert res.status_code == 400


def test_get_todos_unread_filter(client: tuple[TestClient, Path]) -> None:
    test_client, _ = client
    res = test_client.post(
        "/api/v1/todos",
        json={"type": "weekly_digest", "title": "t", "body": "b"},
    )
    item_id = res.json()["id"]
    test_client.patch(f"/api/v1/todos/{item_id}", json={"is_read": True})

    res = test_client.get("/api/v1/todos?unread=true")
    assert res.status_code == 200
    ids = [i["id"] for i in res.json()["items"]]
    assert item_id not in ids


def test_patch_todos_mark_read(client: tuple[TestClient, Path]) -> None:
    test_client, _ = client
    res = test_client.post(
        "/api/v1/todos",
        json={"type": "weekly_digest", "title": "t", "body": "b"},
    )
    item_id = res.json()["id"]
    assert res.json()["is_read"] is False

    res = test_client.patch(f"/api/v1/todos/{item_id}", json={"is_read": True})
    assert res.status_code == 200
    assert res.json()["is_read"] is True


def test_patch_todos_archive(client: tuple[TestClient, Path]) -> None:
    test_client, _ = client
    res = test_client.post(
        "/api/v1/todos",
        json={"type": "weekly_digest", "title": "t", "body": "b"},
    )
    item_id = res.json()["id"]

    res = test_client.patch(f"/api/v1/todos/{item_id}", json={"is_archived": True})
    assert res.status_code == 200
    assert res.json()["is_archived"] is True


def test_patch_todos_not_found_returns_404(client: tuple[TestClient, Path]) -> None:
    test_client, _ = client
    res = test_client.patch("/api/v1/todos/nonexistent", json={"is_read": True})
    assert res.status_code == 404


def test_patch_todos_no_fields_returns_400(client: tuple[TestClient, Path]) -> None:
    test_client, _ = client
    res = test_client.post(
        "/api/v1/todos",
        json={"type": "weekly_digest", "title": "t", "body": "b"},
    )
    item_id = res.json()["id"]
    res = test_client.patch(f"/api/v1/todos/{item_id}", json={})
    assert res.status_code == 400


def test_get_unread_count(client: tuple[TestClient, Path]) -> None:
    test_client, _ = client
    before = test_client.get("/api/v1/todos/unread-count").json()["count"]
    test_client.post(
        "/api/v1/todos",
        json={"type": "weekly_digest", "title": "t", "body": "b"},
    )
    res = test_client.get("/api/v1/todos/unread-count")
    assert res.status_code == 200
    assert res.json()["count"] == before + 1


def test_get_todos_archived_filter(client: tuple[TestClient, Path]) -> None:
    test_client, _ = client
    res = test_client.post(
        "/api/v1/todos",
        json={"type": "weekly_digest", "title": "t", "body": "b"},
    )
    item_id = res.json()["id"]
    test_client.patch(f"/api/v1/todos/{item_id}", json={"is_archived": True})

    res = test_client.get("/api/v1/todos")
    assert all(i["id"] != item_id for i in res.json()["items"])

    res = test_client.get("/api/v1/todos?archived=true")
    assert any(i["id"] == item_id for i in res.json()["items"])
