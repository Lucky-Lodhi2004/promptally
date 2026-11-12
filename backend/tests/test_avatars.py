from pathlib import Path

from backend.app.core.avatars import DEFAULT_AVATAR_URL
from backend.tests.test_payments import auth


def test_default_avatar_is_served_by_backend_and_matches_frontend(client):
    response = client.get(DEFAULT_AVATAR_URL)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")
    frontend = Path(__file__).resolve().parents[2] / "frontend/public/avatars/default-avatar.svg"
    assert response.content == frontend.read_bytes()


def test_existing_empty_avatar_uses_default_in_profile_and_author_responses(client, users, asset, db):
    users[0].avatar_url = "  "
    db.commit()
    assert client.get('/api/v1/users/me', headers=auth(users[0])).json()['avatar_url'] == DEFAULT_AVATAR_URL
    cards = client.get('/api/v1/assets').json()['items']
    assert cards[0]['author']['avatar_url'] == DEFAULT_AVATAR_URL
    detail = client.get('/api/v1/assets/' + asset.slug).json()
    assert detail['author']['avatar_url'] == DEFAULT_AVATAR_URL


def test_custom_avatar_is_preserved(client, users, db):
    users[0].avatar_url = '/uploads/avatars/custom.webp'
    db.commit()
    assert client.get('/api/v1/users/me', headers=auth(users[0])).json()['avatar_url'] == '/uploads/avatars/custom.webp'
