# Pokemon Cards Manager - Main Application

import os
import uuid
from flask import Flask, render_template, request, jsonify, send_file, send_from_directory, redirect, url_for
from werkzeug.utils import secure_filename

import config
from db import init_db, create_card, get_all_cards, get_card, update_card, delete_card
from db import ensure_market_price_column
from db import add_price_record, get_card_prices, get_latest_price
from db import get_dashboard_data, get_rankings, get_snapshots, take_snapshot
from db import get_all_set_names
from db import (get_all_catalog, get_catalog_item, create_catalog_item,
                update_catalog_item, delete_catalog_item, get_catalog_sets, bulk_insert_catalog,
                ensure_card_from_catalog)


app = Flask(__name__)
app.config.from_object(config)


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in config.ALLOWED_EXTENSIONS


# ============ Page Routes ============

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')


@app.route('/price')
def price():
    return render_template('price.html')


@app.route('/card/<int:card_id>')
def card_detail(card_id):
    card = get_card(card_id)
    if not card:
        return "Card not found", 404
    return render_template('card_detail.html', card=card)


@app.route('/catalog')
def catalog():
    return render_template('catalog.html')


# ============ API: Cards ============

@app.route('/api/cards', methods=['GET'])
def api_list_cards():
    search = request.args.get('search', '')
    rarity = request.args.get('rarity', '')
    sort_by = request.args.get('sort_by', 'updated_at')
    cards = get_all_cards(search=search, rarity=rarity or None, sort_by=sort_by)
    return jsonify({'success': True, 'data': cards})


@app.route('/api/cards', methods=['POST'])
def api_create_card():
    data = request.get_json() or request.form.to_dict()
    if not data.get('name'):
        return jsonify({'success': False, 'message': 'Card name is required'}), 400

    # Handle image upload
    if 'file' in request.files:
        file = request.files['file']
        if file and file.filename and allowed_file(file.filename):
            ext = file.filename.rsplit('.', 1)[1].lower()
            filename = f'{uuid.uuid4().hex[:12]}.{ext}'
            filepath = os.path.join(config.UPLOAD_FOLDER, filename)
            file.save(filepath)
            data['image_path'] = f'/static/images/{filename}'

    # Convert numeric fields
    for key in ('quantity', 'cost_price', 'market_price'):
        if key in data and data[key]:
            try:
                data[key] = float(data[key]) if key in ('cost_price', 'market_price') else int(float(data[key]))
            except (ValueError, TypeError):
                if key != 'market_price':
                    del data[key]

    try:
        card = create_card(data)
        return jsonify({'success': True, 'data': card})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/cards/<int:card_id>', methods=['GET'])
def api_get_card(card_id):
    card = get_card(card_id)
    if not card:
        return jsonify({'success': False, 'message': 'Not found'}), 404
    return jsonify({'success': True, 'data': card})


@app.route('/api/cards/<int:card_id>', methods=['PUT'])
def api_update_card(card_id):
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'}), 400

    # Handle image upload in PUT (via form-data)
    if 'file' in request.files:
        file = request.files['file']
        if file and file.filename and allowed_file(file.filename):
            ext = file.filename.rsplit('.', 1)[1].lower()
            filename = f'{uuid.uuid4().hex[:12]}.{ext}'
            filepath = os.path.join(config.UPLOAD_FOLDER, filename)
            file.save(filepath)
            data['image_path'] = f'/static/images/{filename}'
            data.pop('file', None)

    # Convert numeric fields
    for key in ('quantity', 'cost_price', 'market_price'):
        if key in data and data[key] is not None:
            try:
                data[key] = float(data[key]) if key in ('cost_price', 'market_price') else int(float(data[key]))
            except (ValueError, TypeError):
                pass

    try:
        card = update_card(card_id, data)
        if not card:
            return jsonify({'success': False, 'message': 'Not found'}), 404
        return jsonify({'success': True, 'data': card})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/cards/<int:card_id>', methods=['DELETE'])
def api_delete_card(card_id):
    delete_card(card_id)
    return jsonify({'success': True})


@app.route('/api/upload', methods=['POST'])
def api_upload_image():
    """Upload a card image separately"""
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file uploaded'}), 400

    file = request.files['file']
    if not file.filename:
        return jsonify({'success': False, 'message': 'Empty filename'}), 400

    if not (file and allowed_file(file.filename)):
        return jsonify({'success': False, 'message': 'File type not allowed'}), 400

    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = f'{uuid.uuid4().hex[:12]}.{ext}'
    filepath = os.path.join(config.UPLOAD_FOLDER, filename)
    file.save(filepath)

    return jsonify({
        'success': True,
        'image_path': f'/static/images/{filename}',
        'url': f'/static/images/{filename}',
    })


# ============ API: Dashboard ============

@app.route('/api/dashboard', methods=['GET'])
def api_dashboard():
    dash = get_dashboard_data()
    rankings = get_rankings(top=10)
    snapshots = get_snapshots(days=90)
    dash.update(rankings)
    dash['snapshots'] = snapshots
    return jsonify({'success': True, 'data': dash})


# ============ API: Prices ============

@app.route('/api/prices')
def api_get_prices():
    card_id = request.args.get('card_id')
    if not card_id:
        return jsonify({'success': False, 'message': 'card_id required'}), 400

    prices = get_card_prices(int(card_id))
    latest = get_latest_price(int(card_id))
    return jsonify({
        'success': True,
        'data': {
            'history': prices,
            'latest': latest,
        }
    })


@app.route('/api/prices/manual', methods=['POST'])
def api_add_manual_price():
    """Manually input a price for a card"""
    data = request.get_json()
    card_id = data.get('card_id')
    platform = data.get('platform', 'manual')
    price = data.get('price')

    if not all([card_id, price]):
        return jsonify({'success': False, 'message': 'card_id and price required'}), 400

    try:
        add_price_record(int(card_id), platform, float(price))
        latest = get_latest_price(int(card_id))
        return jsonify({'success': True, 'data': {'latest': latest}})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/snapshots/take', methods=['POST'])
def api_take_snapshot():
    """Trigger a daily snapshot"""
    take_snapshot()
    return jsonify({'success': True})


# ============ API: TCG Search ============

@app.route('/api/search-tcg')
def api_search_tcg():
    """Search Pokemon TCG API for card info"""
    query = request.args.get('q', '').strip()
    if len(query) < 2:
        return jsonify({'success': False, 'message': 'Query too short'}), 400

    try:
        import requests as req_lib
        headers = {}
        if config.TCG_API_KEY:
            headers['X-Api-Key'] = config.TCG_API_KEY

        url = f"{config.TCG_API_BASE}/cards?q={query}"
        res = req_lib.get(url, headers=headers, timeout=10)

        if res.status_code == 200:
            result = res.json().get('data', [])
            cards = []
            for c in result[:20]:  # limit to 20 results
                images = c.get('images', {})
                card_data = {
                    'id': c.get('id'),
                    'name': c.get('name', ''),
                    'set_name': c.get('set', {}).get('name', ''),
                    'number': c.get('number', ''),
                    'rarity': c.get('rarity', ''),
                    'image_small': images.get('small', ''),
                    'image_large': images.get('large', ''),
                    'tcgplayer_prices': c.get('tcgplayer', {}).get('prices') or {},
                    'market_prices': c.get('cardmarket', {}).get('prices') or {},
                }
                cards.append(card_data)
            return jsonify({'success': True, 'data': cards})
        elif res.status_code == 429:
            return jsonify({
                'success': False,
                'message': 'API rate limited. Try again in a moment.',
                'code': 429
            }), 429
        else:
            return jsonify({
                'success': False,
                'message': f'TCG API error: {res.status_code}'
            }), res.status_code

    except ImportError:
        return jsonify({
            'success': False,
            'message': 'requests library not installed'
        }), 500
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/sets-info')
def api_sets_info():
    """Get available filter options"""
    sets = get_all_set_names()
    rarities = ['C', 'U', 'R', 'RR', 'SR', 'SAR', 'UR', 'CSR', 'HR']
    conditions = ['NM', 'LP', 'MP', 'HP', 'Damaged']
    return jsonify({
        'success': True,
        'data': {
            'sets': sets,
            'rarities': rarities,
            'conditions': conditions,
        }
    })


# ============ API: Card Catalog ============

@app.route('/api/catalog', methods=['GET'])
def api_catalog_list():
    search = request.args.get('search', '').strip()
    set_name = request.args.get('set_name', '')
    rarity = request.args.get('rarity', '')
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 60))
    items, total = get_all_catalog(search=search, set_name=set_name or None,
                                   rarity=rarity or None, page=page, per_page=per_page)
    return jsonify({'success': True, 'data': items, 'total': total, 'page': page, 'per_page': per_page})


@app.route('/api/catalog', methods=['POST'])
def api_catalog_create():
    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({'success': False, 'message': 'name is required'}), 400
    try:
        item = create_catalog_item(data)
        return jsonify({'success': True, 'data': item})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/catalog/<int:item_id>', methods=['GET'])
def api_catalog_get(item_id):
    item = get_catalog_item(item_id)
    if not item:
        return jsonify({'success': False, 'message': 'Not found'}), 404
    return jsonify({'success': True, 'data': item})


@app.route('/api/catalog/<int:item_id>', methods=['PUT'])
def api_catalog_update(item_id):
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'No data'}), 400
    item = update_catalog_item(item_id, data)
    if not item:
        return jsonify({'success': False, 'message': 'Not found'}), 404
    return jsonify({'success': True, 'data': item})


@app.route('/api/catalog/<int:item_id>', methods=['DELETE'])
def api_catalog_delete(item_id):
    delete_catalog_item(item_id)
    return jsonify({'success': True})


@app.route('/api/catalog/bulk', methods=['POST'])
def api_catalog_bulk():
    data = request.get_json()
    items = data.get('items', []) if data else []
    if not items:
        return jsonify({'success': False, 'message': 'items array required'}), 400
    result = bulk_insert_catalog(items)
    return jsonify({'success': True, 'data': result})


@app.route('/api/catalog/sets', methods=['GET'])
def api_catalog_sets():
    sets = get_catalog_sets()
    return jsonify({'success': True, 'data': sets})


@app.route('/api/cards/from-catalog', methods=['POST'])
def api_ensure_card_from_catalog():
    """Ensure a card exists from a catalog item; create if not present.
    Request body: { "catalog_id": <int> }
    Returns the card dict (existing or newly created).
    """
    data = request.get_json()
    catalog_id = data.get('catalog_id')
    if not catalog_id:
        return jsonify({'success': False, 'message': 'catalog_id is required'}), 400
    try:
        card = ensure_card_from_catalog(int(catalog_id))
        if not card:
            return jsonify({'success': False, 'message': 'Catalog item not found'}), 404
        return jsonify({'success': True, 'data': card})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# ============ Serve static images from custom path ============

@app.route('/static/images/<path:filename>')
def serve_images(filename):
    return send_from_directory(config.UPLOAD_FOLDER, filename)


# ============ Init & Run ============

# Always initialize DB when module loads
try:
    init_db()
    ensure_market_price_column()
except Exception as e:
    import sys
    print(f"[WARN] DB init error (non-fatal): {e}", file=sys.stderr)

# Ensure upload/images directory exists
os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)

# Health check endpoint (bypasses templates/DB for Railway)
@app.route('/health')
def health():
    return 'OK', 200, {'Content-Type': 'text/plain'}


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    is_production = port != 5001

    print('=' * 50)
    print('Pokemon Card Manager starting...')
    print(f'Mode:     {"PRODUCTION" if is_production else "DEVELOPMENT"}')
    print(f'Server:   {"waitress" if is_production else "Flask dev"}')
    print(f'Port:     {port}')
    print(f'Database: {config.DATABASE_PATH}')
    print(f'Images:   {config.UPLOAD_FOLDER}')
    print('=' * 50)

    if is_production:
        # Production: waitress — pure Python, robust, no forking issues
        from waitress import serve
        print(f'[waitress] Serving on 0.0.0.0:{port}')
        serve(app, host='0.0.0.0', port=port, threads=4)
    else:
        # Development: Flask built-in with debug reloader
        app.run(host='0.0.0.0', port=port, debug=True)
