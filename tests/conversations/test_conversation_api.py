from src.app.services import (
    ConversationService,
)


def test_conversation_crud(
    conversation_client,
):
    created = conversation_client.post(
        "/conversations",
        json={
            "title": "  Day6 Chat  ",
        },
    )

    assert created.status_code == 201

    conversation = created.json()
    conversation_id = conversation["id"]

    assert conversation["title"] == "Day6 Chat"

    loaded = conversation_client.get(
        f"/conversations/{conversation_id}"
    )

    assert loaded.status_code == 200
    assert loaded.json()["id"] == conversation_id

    listed = conversation_client.get(
        "/conversations",
        params={
            "limit": 10,
            "offset": 0,
        },
    )

    assert listed.status_code == 200
    assert [
        item["id"]
        for item in listed.json()["items"]
    ] == [
        conversation_id,
    ]

    renamed = conversation_client.patch(
        f"/conversations/{conversation_id}",
        json={
            "title": "Renamed",
        },
    )

    assert renamed.status_code == 200
    assert renamed.json()["title"] == "Renamed"

    deleted = conversation_client.delete(
        f"/conversations/{conversation_id}"
    )

    assert deleted.status_code == 200
    assert deleted.json() == {
        "id": conversation_id,
        "deleted": True,
    }

    missing = conversation_client.get(
        f"/conversations/{conversation_id}"
    )

    assert missing.status_code == 404


def test_messages_are_returned_by_sequence(
    conversation_client,
    conversation_session_factory,
):
    created = conversation_client.post(
        "/conversations",
        json={},
    )

    conversation_id = created.json()["id"]

    with conversation_session_factory() as session:
        service = ConversationService(
            session
        )

        service.add_message(
            conversation_id,
            role="user",
            content="first",
        )

        service.add_message(
            conversation_id,
            role="assistant",
            content="second",
            provider="mock",
            model="mock-model",
        )

    response = conversation_client.get(
        (
            f"/conversations/"
            f"{conversation_id}/messages"
        )
    )

    assert response.status_code == 200

    messages = response.json()["items"]

    assert [
        message["sequence_no"]
        for message in messages
    ] == [1, 2]

    assert [
        message["content"]
        for message in messages
    ] == [
        "first",
        "second",
    ]


def test_missing_conversation_returns_404(
    conversation_client,
):
    response = conversation_client.get(
        "/conversations/missing/messages"
    )

    assert response.status_code == 404
