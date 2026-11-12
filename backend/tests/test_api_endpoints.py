"""Public and account regressions against an isolated database."""
import zipfile
from backend.app.core.security import create_access_token
from backend.app.models.enums import UserTier


def auth(user):
    return {'Authorization': 'Bearer ' + create_access_token(user.id)}


def test_health(client):
    assert client.get('/api/v1/health').json()['status'] == 'healthy'


def test_catalog_and_taxonomy(client, asset):
    assert client.get('/api/v1/taxonomy').json()['total_assets'] == 1
    assert client.get('/api/v1/assets?section=prompts').json()['total'] == 1


def test_asset_detail_returns_deduplicated_preview_gallery(client, asset, db):
    asset.media_preview_url = '/media/preview.jpg'
    asset.gif_preview_url = '/media/demo.gif'
    asset.reference_media = [
        '/media/preview.jpg',
        '/media/demo.gif',
        {'url': '/media/alternate.png', 'kind': 'image'},
    ]
    db.commit()

    response = client.get(f'/api/v1/assets/{asset.slug}')
    assert response.status_code == 200
    assert response.json()['preview_media'] == [
        {'url': '/media/preview.jpg', 'kind': 'image'},
        {'url': '/media/demo.gif', 'kind': 'gif'},
        {'url': '/media/alternate.png', 'kind': 'image'},
    ]


def test_free_bundle_exposes_bounded_text_file_previews(client, asset, db, tmp_path):
    archive = tmp_path / 'bundle.zip'
    with zipfile.ZipFile(archive, 'w') as bundle:
        bundle.writestr('SKILL.md', '# Search skill\nUse the supplied query.')
        bundle.writestr('mcp.json', '{"mcpServers": {}}')
        bundle.writestr('image.png', b'not indexed as text')
    asset.is_paid = False
    asset.archive_path = str(archive)
    asset.file_name = 'bundle.zip'
    asset.file_extension = '.zip'
    db.commit()

    response = client.get(f'/api/v1/assets/{asset.slug}')
    assert response.status_code == 200
    assert response.json()['file_previews'] == [
        {'name': 'SKILL.md', 'content': '# Search skill\nUse the supplied query.'},
        {'name': 'mcp.json', 'content': '{"mcpServers": {}}'},
    ]


def test_signup_login_profile_password_and_device_limit(client, db):
    for i in range(3):
        response = client.post('/api/v1/auth/signup', json={'email': f'user{i}@example.com',
            'password':'password123', 'device_fingerprint':'device-one'})
        assert response.status_code == (201 if i < 2 else 403)
    response = client.post('/api/v1/auth/login', json={'email':'user0@example.com', 'password':'password123'})
    assert response.status_code == 200
    headers = {'Authorization': 'Bearer ' + response.json()['access_token']}
    assert client.get('/api/v1/users/me', headers=headers).json()['email'] == 'user0@example.com'
    from backend.app.models.registration import EmailOutbox
    from backend.app.services.crypto import decrypt_secret
    outbox = db.query(EmailOutbox).filter_by(user_id=response.json()['user']['id']).one()
    assert client.post('/api/v1/auth/verify-email', json={'token': decrypt_secret(outbox.token_enc)}).status_code == 200
    assert client.post('/api/v1/users/me/password', headers=headers,
        json={'current_password':'password123', 'new_password':'newpassword'}).status_code == 200
    assert client.post('/api/v1/auth/logout').status_code == 200


def test_collections_pro_gating_and_privacy(client, asset, users):
    seller,buyer=users
    assert client.post('/api/v1/collections',headers=auth(buyer),data={'title':'Denied'}).status_code == 403
    response=client.post('/api/v1/collections',headers=auth(seller),data={'title':'Private collection'})
    assert response.status_code == 201
    collection=response.json()
    assert client.post(f"/api/v1/collections/{collection['collection_id']}/items",headers=auth(seller),
        data={'asset_id':asset.id}).status_code == 200
    assert client.get('/api/v1/collections/'+collection['slug']).status_code == 403
    assert client.get('/api/v1/collections/'+collection['slug'],headers=auth(seller)).status_code == 200


def test_free_upload_copy_download_and_delete(client, asset, users):
    response=client.post('/api/v1/assets',headers=auth(users[1]),data={'heading':'Free prompt',
        'section_slug':'prompts','category_slug':'system-base-contexts','raw_text':'Free source'})
    assert response.status_code == 201
    data=response.json(); slug=data['slug']
    assert client.get(f'/api/v1/assets/{slug}/download').content == b'Free source'
    assert client.get(f'/api/v1/assets/{slug}/download?action=copy').text == 'Free source'
    assert client.delete('/api/v1/assets/'+data['asset_id'],headers=auth(users[1])).status_code == 200


def test_seo_discovery_and_admin(client, asset, users, db):
    for path in ('/llms.txt','/.well-known/mcp.json','/sitemap.xml'):
        assert client.get(path).status_code == 200
    assert client.get('/api/v1/admin/users',headers=auth(users[1])).status_code == 403
    users[1].tier=UserTier.ADMIN;db.commit()
    assert client.get('/api/v1/admin/users',headers=auth(users[1])).status_code == 200


def test_collection_frontend_contract(client, asset, users):
    headers=auth(users[0])
    created=client.post('/api/v1/collections',headers=headers,data={'title':'Frontend contract','visibility':'PUBLIC'})
    assert created.status_code==201
    assert created.headers['cache-control']=='private, no-store'
    collection=created.json()
    assert collection['collection_id']
    added=client.post(f"/api/v1/collections/{collection['collection_id']}/items",headers=headers,data={'asset_id':asset.id})
    assert added.status_code==200
    detail=client.get('/api/v1/collections/'+collection['slug'],headers=headers).json()
    item=detail['items'][0]
    assert item['asset_id']==asset.id and item['id']!=asset.id
    assert item['author']['id']==asset.author_id
    assert item['price_cents']==asset.price_cents
    assert {'reference_media','copy_count','download_count','is_indexable','canonical_path'} <= item.keys()
    removed=client.delete(f"/api/v1/collections/{collection['collection_id']}/items/{item['asset_id']}",headers=headers)
    assert removed.status_code==200
