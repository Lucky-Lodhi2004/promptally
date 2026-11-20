"""SEO / AEO behaviour: crawl signals, caching, internal links, markdown twins, MCP, sitemaps."""
from backend.app.core.config import settings
from backend.app.core.security import create_access_token
from backend.app.models import Asset, Category, Section, User
from backend.app.models.collection import Collection, CollectionItem
from backend.app.models.enums import AssetType, CollectionVisibility, UserTier
from backend.app.models.redirect import SlugRedirect
from backend.app.services import related
from backend.app.services.seo import (
    approx_token_count, build_faq, evaluate_indexability, extract_variable_schema,
    generate_tldr_summary, interpolate_variables)


def auth(user):
    return {'Authorization': 'Bearer ' + create_access_token(user.id)}


def make_asset(db, slug, title, body='x' * 600, **extra):
    asset = Asset(id=slug, slug=slug, seo_title=title, short_description='A useful description of the prompt',
                  section_id='section', category_id='category', asset_type=AssetType.PROMPT, raw_content=body,
                  file_name=slug + '.md', file_extension='.md', **extra)
    db.add(asset)
    db.commit()
    return asset


# ---------- pure helpers ----------

def test_paid_summary_never_claims_free_access():
    free = generate_tldr_summary('T', 'Desc', 'PROMPT', 'Cat')
    paid = generate_tldr_summary('T', 'Desc', 'PROMPT', 'Cat', is_paid=True, price_usd=5)
    assert 'zero authentication' in free
    assert 'zero authentication' not in paid and '$5.00' in paid


def test_variable_extraction_and_interpolation():
    schema = extract_variable_schema('Explain {{ topic }} to a {{level}} student. {{topic}} again')
    assert [v['name'] for v in schema] == ['topic', 'level']
    filled = interpolate_variables('Explain {{topic}} to {{level}}',
                                   [{'name': 'topic', 'default_value': 'Raft'}, {'name': 'level', 'default': 'Expert'}])
    assert filled == 'Explain Raft to Expert'


def test_indexability_gate_rejects_duplicates_and_thin_pages():
    assert evaluate_indexability('x' * 500, None, 0.0, 'd')
    assert not evaluate_indexability('x' * 500, None, 0.95, 'd')
    assert not evaluate_indexability('short', None, 0.0, 'd')


def test_faq_is_page_specific_and_truthful_for_paid():
    faq = build_faq('Raft Tutor', 'PROMPT', 'Prompts', ['topic'], True, 5.0, 'MIT', 'raft.md')
    text = ' '.join(f['answer'] for f in faq)
    assert 'paid creator blueprint' in text and 'free to view' not in text
    assert approx_token_count('a' * 400) == 100


# ---------- related links / duplicate gate ----------

def rows(n, shared=False):
    return [{'slug': f'item-{i:02d}', 'title': f'Distinct topic{i} guide' + (' shared words' if shared else ''),
             'description': f'about subject{i}', 'section_id': 's', 'category_id': 'c', 'section_slug': 'prompts',
             'content': f'unique body {i} ' * 20} for i in range(n)]


def test_ring_gives_every_page_inbound_links():
    index = related.RelatedIndex(rows(30))
    inbound = {r['slug']: 0 for r in rows(30)}
    for row in rows(30):
        links = index.related(row['slug'], row['title'], row['description'], 's', 'c')
        assert 4 <= len(links) <= 12 and row['slug'] not in [l['slug'] for l in links]
        assert len({l['slug'] for l in links}) == len(links)
        for link in links:
            inbound[link['slug']] += 1
    assert min(inbound.values()) >= 4, 'no orphan pages'


def test_semantic_neighbours_rank_first():
    data = rows(20)
    data[3]['title'], data[3]['description'] = 'FastAPI async database tutorial', 'fastapi sqlalchemy async'
    data[7]['title'], data[7]['description'] = 'FastAPI async database patterns', 'fastapi sqlalchemy async'
    index = related.RelatedIndex(data)
    links = index.related('item-03', data[3]['title'], data[3]['description'], 's', 'c')
    assert links[0]['slug'] == 'item-07'


def test_near_duplicate_detection():
    data = rows(10)
    index = related.RelatedIndex(data)
    copy = f"{data[2]['title']} {data[2]['description']} {data[2]['content']}"
    assert index.max_duplicate_similarity(copy) > 0.9
    assert index.max_duplicate_similarity('completely different vocabulary nothing shared whatsoever here') < 0.5


# ---------- catalog endpoints ----------

def test_unknown_section_and_subcategory_are_real_404s(client, asset):
    assert client.get('/api/v1/assets?section=nope').status_code == 404
    assert client.get('/api/v1/assets?section=prompts&subcategory=nope').status_code == 404
    ok = client.get('/api/v1/assets?section=prompts&subcategory=system-base-contexts')
    assert ok.status_code == 200 and ok.json()['items'][0]['canonical_path'] == '/directory/prompts/system-base-contexts'


def test_anonymous_detail_is_edge_cacheable_with_etag_304(client, asset):
    first = client.get('/api/v1/assets/' + asset.slug)
    assert first.status_code == 200
    assert 's-maxage=3600' in first.headers['cache-control'] and 'private' not in first.headers['cache-control']
    etag = first.headers['etag']
    again = client.get('/api/v1/assets/' + asset.slug, headers={'If-None-Match': etag})
    assert again.status_code == 304 and again.headers['etag'] == etag


def test_authenticated_detail_stays_private(client, asset, users):
    response = client.get('/api/v1/assets/' + asset.slug, headers=auth(users[0]))
    assert response.headers['cache-control'] == 'private, no-store'
    assert response.json()['raw_content'] == 'SECRET PAYLOAD'
    # a conditional request from a signed-in viewer never short-circuits to a shared 304
    assert client.get('/api/v1/assets/' + asset.slug, headers={**auth(users[0]), 'If-None-Match': response.headers['etag']}).status_code == 200


def test_views_count_only_on_request_and_do_not_move_etag(client, asset, db):
    etag = client.get('/api/v1/assets/' + asset.slug).headers['etag']
    for _ in range(3):
        client.get('/api/v1/assets/' + asset.slug)
    db.refresh(asset)
    assert asset.view_count == 0
    client.get('/api/v1/assets/' + asset.slug + '?view=1')
    client.get('/api/v1/assets/' + asset.slug + '/download?action=copy', headers={})  # paid: 403, no change
    db.refresh(asset)
    assert asset.view_count == 1
    assert client.get('/api/v1/assets/' + asset.slug).headers['etag'] == etag


def test_paid_payload_exposes_proof_of_work_but_not_the_secret(client, asset):
    data = client.get('/api/v1/assets/' + asset.slug).json()
    assert data['raw_content'] is None and data['prefilled_preview_text'] is None
    assert data['token_count'] == approx_token_count('SECRET PAYLOAD')
    assert 'zero authentication' not in data['tldr_summary'] and len(data['faq']) == 3
    graph = {n['@type']: n for n in data['json_ld']['@graph']}
    assert graph['SoftwareSourceCode']['isAccessibleForFree'] is False
    assert graph['SoftwareSourceCode']['hasPart']['isAccessibleForFree'] is False
    assert graph['SoftwareSourceCode']['offers']['price'] == '5.00'
    assert set(graph) == {'BreadcrumbList', 'SoftwareSourceCode', 'FAQPage'}
    crumbs = [i['item'] for i in graph['BreadcrumbList']['itemListElement']]
    assert crumbs[2].endswith('/directory/prompts/system-base-contexts')
    assert 'SECRET PAYLOAD' not in str(data)


def test_markdown_twin_paid_is_locked_and_includes_spec_table(client, asset):
    md = client.get(f'/api/v1/assets/{asset.slug}.md')
    assert md.headers['content-type'].startswith('text/markdown')
    assert 'SECRET PAYLOAD' not in md.text and 'Approx. Token Length' in md.text and '| Property | Value |' in md.text
    assert settings.SITE_URL.rstrip('/') + '/p/' + asset.slug in md.text
    assert 's-maxage' in md.headers['cache-control']
    negotiated = client.get('/api/v1/assets/' + asset.slug, headers={'Accept': 'text/markdown'})
    assert negotiated.text == md.text


# ---------- uploads: variables, mesh, redirects ----------

def test_upload_extracts_variables_builds_mesh_and_links_back(client, asset, users, db):
    peers = [make_asset(db, f'peer-{i}', f'Peer prompt number {i} about agents', body=f'peer body {i} ' * 80) for i in range(5)]
    response = client.post('/api/v1/assets', headers=auth(users[1]), data={
        'heading': 'First principles tutor', 'section_slug': 'prompts', 'category_slug': 'system-base-contexts',
        'raw_text': 'Explain {{topic}} to a {{level}} student from first principles. ' * 12})
    assert response.status_code == 201, response.text
    new = db.query(Asset).filter_by(slug=response.json()['slug']).one()
    assert [v['name'] for v in new.variables_schema] == ['topic', 'level']
    assert new.is_indexable and len(new.related_artifacts) >= 4
    assert any(any(r['slug'] == new.slug for r in (p.related_artifacts or [])) for p in peers), 'inbound link added'
    assert 'zero authentication' in new.tldr_summary


def test_duplicate_upload_is_kept_out_of_the_index(client, asset, users, db):
    body = 'Explain recursion using a stack of plates and a recursive base case. ' * 10
    for i in range(2):
        make_asset(db, f'seed-{i}', 'Recursion explained with plates', body=body + f'v{i}')
    response = client.post('/api/v1/assets', headers=auth(users[1]), data={
        'heading': 'Recursion explained with plates', 'section_slug': 'prompts',
        'category_slug': 'system-base-contexts', 'raw_text': body, 'description': 'A useful description of the prompt'})
    assert response.status_code == 201
    assert db.query(Asset).filter_by(slug=response.json()['slug']).one().is_indexable is False


def test_rename_records_slug_redirect_and_old_url_301s(client, asset, users, db):
    created = client.post('/api/v1/assets', headers=auth(users[1]), data={
        'heading': 'Old title', 'section_slug': 'prompts', 'category_slug': 'system-base-contexts', 'raw_text': 'body ' * 100}).json()
    response = client.patch('/api/v1/assets/' + created['asset_id'], headers=auth(users[1]), data={'heading': 'Brand new title'})
    assert response.status_code == 200 and response.json()['slug'] == 'brand-new-title'
    assert db.get(SlugRedirect, 'old-title').asset_id == created['asset_id']
    old = client.get('/api/v1/assets/old-title', follow_redirects=False)
    assert old.status_code == 301 and old.headers['location'] == '/api/v1/assets/brand-new-title'
    assert client.get('/api/v1/assets/brand-new-title').status_code == 200
    assert client.patch('/api/v1/assets/' + created['asset_id'], headers=auth(users[0]), data={'heading': 'x'}).status_code == 403


def test_rename_back_prefers_live_slug_over_stale_redirect(client, asset, users, db):
    created = client.post('/api/v1/assets', headers=auth(users[1]), data={
        'heading': 'Alpha', 'section_slug': 'prompts', 'category_slug': 'system-base-contexts', 'raw_text': 'body ' * 100}).json()
    client.patch('/api/v1/assets/' + created['asset_id'], headers=auth(users[1]), data={'heading': 'Beta'})
    client.patch('/api/v1/assets/' + created['asset_id'], headers=auth(users[1]), data={'heading': 'Alpha'})
    assert client.get('/api/v1/assets/alpha', follow_redirects=False).status_code == 200
    assert client.get('/api/v1/assets/beta', follow_redirects=False).status_code == 301


# ---------- sitemaps, llms, mcp ----------

def test_sitemaps_list_hubs_assets_and_public_collections(client, asset, users, db):
    good = make_asset(db, 'indexed-one', 'Indexed one', is_indexable=True)
    make_asset(db, 'thin-one', 'Thin one', is_indexable=False)
    db.query(Asset).filter_by(id='asset').update({'is_indexable': True}); db.commit()
    seller = users[0]
    collection = Collection(slug='best-prompts', title='Best', owner_id=seller.id,
                            visibility=CollectionVisibility.PUBLIC, item_count=3, is_indexable=True)
    thin = Collection(slug='thin-collection', title='Thin', owner_id=seller.id,
                      visibility=CollectionVisibility.PUBLIC, item_count=1, is_indexable=True)
    db.add_all([collection, thin]); db.commit()
    index = client.get('/sitemap.xml').text
    assert 'sitemaps/pages.xml' in index and 'sitemaps/prompts-0.xml' in index and 'collections-0.xml' in index
    pages = client.get('/api/v1/seo/sitemaps/pages.xml').text
    base = settings.SITE_URL.rstrip('/')
    assert f'{base}/directory/prompts<' in pages and f'{base}/directory/prompts/system-base-contexts<' in pages
    chunk = client.get('/api/v1/seo/sitemaps/prompts-0.xml').text
    assert '/p/indexed-one' in chunk and '/p/thin-one' not in chunk
    assert 'best-prompts' in client.get('/api/v1/seo/sitemaps/collections-0.xml').text
    assert 'thin-collection' not in client.get('/api/v1/seo/sitemaps/collections-0.xml').text
    assert client.get('/api/v1/seo/sitemaps/ghost-0.xml').status_code == 404


def test_llms_files(client, asset):
    short, full = client.get('/llms.txt'), client.get('/llms-full.txt')
    assert short.status_code == full.status_code == 200
    assert '/directory/prompts' in short.text and 'llms-full.txt' in short.text
    assert '/directory/prompts/system-base-contexts' in full.text
    assert 'SECRET PAYLOAD' not in short.text + full.text


def rpc(client, method, params=None, rpc_id=1, **kw):
    body = {'jsonrpc': '2.0', 'method': method, **({'params': params} if params is not None else {})}
    if rpc_id is not None:
        body['id'] = rpc_id
    return client.post('/api/v1/mcp', json=body, **kw)


def test_mcp_json_rpc_handshake_tools_and_gating(client, asset, users, db, mcp_access):
    init = rpc(client, 'initialize', {'protocolVersion': '2025-03-26'}).json()
    assert init['jsonrpc'] == '2.0' and init['id'] == 1 and init['result']['capabilities']['tools'] == {'listChanged': False}
    assert rpc(client, 'notifications/initialized', rpc_id=None).status_code == 202
    tools = rpc(client, 'tools/list').json()['result']['tools']
    assert {t['name'] for t in tools} == {'search_promptally', 'get_free_artifact', 'preview_marketplace_artifact'}
    assert all('inputSchema' in t for t in tools)
    make_asset(db, 'free-one', 'Free recursion prompt', is_indexable=True)

    search = rpc(client, 'tools/call', {'name': 'search_promptally', 'arguments': {'query': 'recursion', 'modality': 'prompts'}}).json()
    import json
    assert json.loads(search['result']['content'][0]['text'])[0]['slug'] == 'free-one'
    assert json.loads(rpc(client, 'tools/call', {'name': 'search_promptally', 'arguments': {'query': 'recursion', 'modality': 'skills'}}).json()['result']['content'][0]['text']) == []

    locked = rpc(client, 'tools/call', {'name': 'get_free_artifact', 'arguments': {'slug': asset.slug}}).json()['result']
    assert locked['isError'] and 'SECRET PAYLOAD' not in str(locked)
    preview = rpc(client, 'tools/call', {'name': 'preview_marketplace_artifact', 'arguments': {'slug': asset.slug}}).json()['result']
    assert 'SECRET PAYLOAD' not in str(preview) and 'approx_token_count' in preview['content'][0]['text']
    wrong = rpc(client, 'tools/call', {'name': 'preview_marketplace_artifact', 'arguments': {'slug': 'free-one'}}).json()['result']
    assert wrong['isError']
    assert rpc(client, 'nope').json()['error']['code'] == -32601
    assert client.post('/api/v1/mcp', content=b'{bad', headers={'content-type': 'application/json'}).status_code == 400


def test_mcp_legacy_shape_still_works(client, asset, mcp_access):
    legacy = client.post('/api/v1/mcp', json={'method': 'tools/list'}).json()
    assert 'tools' in legacy and 'jsonrpc' not in legacy
    result = client.post('/api/v1/mcp', json={'method': 'tools/call', 'params': {'name': 'search_promptally', 'arguments': {'query': 'paid'}}}).json()
    assert result['content'][0]['type'] == 'text'


def test_discover_collections_requires_enough_public_items(client, asset, users, db):
    db.add_all([Collection(slug='hub', title='Hub', owner_id=users[0].id, visibility=CollectionVisibility.PUBLIC, item_count=4, is_indexable=True),
                Collection(slug='tiny', title='Tiny', owner_id=users[0].id, visibility=CollectionVisibility.PUBLIC, item_count=1, is_indexable=True),
                Collection(slug='secret', title='Secret', owner_id=users[0].id, visibility=CollectionVisibility.PRIVATE, item_count=9, is_indexable=False)])
    db.commit()
    assert [c['slug'] for c in client.get('/api/v1/discover/collections').json()['items']] == ['hub']


def test_collection_matrix_has_models_variables_and_site_urls(client, asset, users, db):
    headers = auth(users[0])
    made = client.post('/api/v1/collections', headers=headers, data={'title': 'Matrix', 'visibility': 'PUBLIC'}).json()
    client.post(f"/api/v1/collections/{made['collection_id']}/items", headers=headers, data={'asset_id': asset.id})
    row = client.get('/api/v1/collections/' + made['slug'], headers=headers).json()['comparison_matrix'][0]
    assert {'name', 'modality', 'category', 'use_case', 'variables', 'approx_tokens', 'access', 'url'} <= row.keys()
    assert row['url'].startswith(settings.SITE_URL.rstrip('/'))


def test_internal_render_token_bypasses_only_the_read_budget(monkeypatch, redis_url):
    monkeypatch.setattr(settings, 'TRUSTED_PROXY_TOKEN', 'test-ingress-secret')
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.app.core.rate_limit import RateLimitMiddleware
    monkeypatch.setattr(settings, 'RATE_LIMIT_ENABLED', True)
    monkeypatch.setattr(settings, 'REDIS_URL', redis_url)
    monkeypatch.setattr(settings, 'TRUSTED_PROXY_CIDRS', ['127.0.0.1/32'])
    monkeypatch.setattr(settings, 'INTERNAL_RENDER_TOKEN', 'render-secret')
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, max_requests=1, window_seconds=60, max_read_requests=1)
    @app.get('/page')
    def page(): return {'ok': True}
    @app.post('/write')
    def write(): return {'ok': True}
    with TestClient(app, client=('127.0.0.1', 1)) as c:
        headers = {'CF-Connecting-IP': '203.0.113.77', 'X-Proxy-Token': 'test-ingress-secret'}
        assert c.get('/page', headers=headers).status_code == 200
        assert c.get('/page', headers=headers).status_code == 429
        assert all(c.get('/page', headers={**headers, 'X-Internal-Render': 'render-secret'}).status_code == 200 for _ in range(5))
        assert c.get('/page', headers={**headers, 'X-Internal-Render': 'wrong'}).status_code == 429
        assert c.post('/write', headers={**headers, 'X-Internal-Render': 'render-secret'}).status_code == 200
        assert c.post('/write', headers={**headers, 'X-Internal-Render': 'render-secret'}).status_code == 429
