# Pokemon Cards Manager - Main Application

import os
import uuid
import hashlib
import re
from functools import wraps
from flask import Flask, render_template, request, jsonify, send_from_directory

import config
from db import (init_db, _migrate_add_column, get_db,
                create_card, get_all_cards, get_card, update_card, delete_card,
                add_price_record, get_card_prices, get_latest_price,
                add_catalog_price_record, get_catalog_prices, get_catalog_latest_price,
                get_dashboard_data, get_rankings, get_snapshots, take_snapshot,
                get_all_set_names,
                get_all_catalog, get_catalog_item, create_catalog_item,
                update_catalog_item, delete_catalog_item, get_catalog_sets, bulk_insert_catalog,
                ensure_card_from_catalog,
                get_user_by_openid, get_user_by_token, get_user_by_username, get_user_by_email,
                create_user, update_user_token, update_user, get_all_users, get_user,
                bind_wechat_to_user)
import data_pipeline


app = Flask(__name__)
app.config.from_object(config)


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in config.ALLOWED_EXTENSIONS


# ============ Auth Helpers ============

def hash_password(password):
    return hashlib.sha256((password + config.SECRET_KEY).encode()).hexdigest()


def get_request_user():
    """Extract user from Authorization header. Returns user dict or None."""
    auth = request.headers.get('Authorization', '')
    if auth.startswith('Bearer '):
        token = auth[7:]
        return get_user_by_token(token)
    return None


def login_required(f):
    """Decorator: require valid auth token"""
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_request_user()
        if not user:
            return jsonify({'success': False, 'message': '请先登录'}), 401
        request.current_user = user
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """Decorator: require admin role"""
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_request_user()
        if not user:
            return jsonify({'success': False, 'message': '请先登录'}), 401
        if user['role'] != 'admin':
            return jsonify({'success': False, 'message': '需要管理员权限'}), 403
        request.current_user = user
        return f(*args, **kwargs)
    return decorated


# ============ Auth Routes ============

@app.route('/api/auth/wechat-login', methods=['POST'])
def api_wechat_login():
    """WeChat Mini Program login: exchange code for openid, create user if new"""
    data = request.get_json()
    code = data.get('code', '')
    nick_name = data.get('nickName', '')
    avatar = data.get('avatar', '')
    phone = data.get('phone', '')

    openid = ''
    # Exchange code for openid via WeChat API
    if code and config.WECHAT_APPID and config.WECHAT_SECRET:
        try:
            import requests as req_lib
            wx_url = f'https://api.weixin.qq.com/sns/jscode2session?appid={config.WECHAT_APPID}&secret={config.WECHAT_SECRET}&js_code={code}&grant_type=authorization_code'
            wx_res = req_lib.get(wx_url, timeout=10).json()
            openid = wx_res.get('openid', '')
        except Exception:
            pass

    # Fallback: use code as openid for dev/test without WeChat config
    if not openid and code:
        openid = 'wx_dev_' + code[:20]

    if not openid:
        return jsonify({'success': False, 'message': '微信登录失败，请重试'}), 400

    user = get_user_by_openid(openid)
    if user:
        # Update profile
        if nick_name or avatar or phone:
            update_data = {}
            if nick_name: update_data['nick_name'] = nick_name
            if avatar: update_data['avatar'] = avatar
            if phone: update_data['phone'] = phone
            update_user(user['id'], update_data)
        token = update_user_token(user['id'])
    else:
        token = create_user(openid=openid, nick_name=nick_name, avatar=avatar, phone=phone)

    return jsonify({'success': True, 'data': {'token': token}})


@app.route('/api/auth/register', methods=['POST'])
def api_register():
    """Web registration: email + username + password"""
    data = request.get_json()
    email = (data.get('email') or '').strip().lower()
    username = (data.get('username') or '').strip()
    password = (data.get('password') or '').strip()
    confirm_password = (data.get('confirm_password') or '').strip()

    # Validation
    errors = []
    if not email:
        errors.append('请输入邮箱')
    elif not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
        errors.append('邮箱格式不正确')

    if not username:
        errors.append('请输入用户名')
    elif len(username) < 2:
        errors.append('用户名至少2个字符')
    elif len(username) > 30:
        errors.append('用户名不能超过30个字符')

    if not password:
        errors.append('请输入密码')
    elif len(password) < 6:
        errors.append('密码至少6个字符')

    if password != confirm_password:
        errors.append('两次输入的密码不一致')

    if errors:
        return jsonify({'success': False, 'message': '；'.join(errors)}), 400

    # Check uniqueness
    if get_user_by_email(email):
        return jsonify({'success': False, 'message': '该邮箱已被注册'}), 409

    if get_user_by_username(username):
        return jsonify({'success': False, 'message': '该用户名已被使用'}), 409

    # Check admin username conflict
    if username == config.ADMIN_USERNAME:
        return jsonify({'success': False, 'message': '该用户名已被使用'}), 409

    try:
        token = create_user(
            email=email,
            username=username,
            password_hash=hash_password(password),
            nick_name=username,
            role='user'
        )
        return jsonify({'success': True, 'data': {'token': token}, 'message': '注册成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'注册失败: {str(e)}'}), 500


@app.route('/api/auth/web-login', methods=['POST'])
def api_web_login():
    """Web login: email + password"""
    data = request.get_json()
    email_or_username = (data.get('email') or data.get('username') or '').strip()
    password = (data.get('password') or '').strip()

    if not email_or_username or not password:
        return jsonify({'success': False, 'message': '请输入邮箱和密码'}), 400

    # Try email first, then username (backward compat)
    user = get_user_by_email(email_or_username)
    if not user:
        user = get_user_by_username(email_or_username)

    if not user:
        # Check if admin from config (backward compat)
        if email_or_username == config.ADMIN_USERNAME and password == config.ADMIN_PASSWORD:
            existing_admin = get_user_by_username(config.ADMIN_USERNAME)
            if existing_admin:
                token = update_user_token(existing_admin['id'])
            else:
                token = create_user(
                    username=config.ADMIN_USERNAME,
                    email=f"{config.ADMIN_USERNAME}@admin.local",
                    password_hash=hash_password(config.ADMIN_PASSWORD),
                    nick_name='管理员',
                    role='admin'
                )
            return jsonify({'success': True, 'data': {'token': token, 'role': 'admin'}})
        return jsonify({'success': False, 'message': '邮箱或密码错误'}), 401

    if user['password_hash'] != hash_password(password):
        return jsonify({'success': False, 'message': '邮箱或密码错误'}), 401

    token = update_user_token(user['id'])
    return jsonify({'success': True, 'data': {'token': token, 'role': user['role']}})


@app.route('/api/auth/bind-wechat', methods=['POST'])
@login_required
def api_bind_wechat():
    """Bind WeChat to current web user account"""
    data = request.get_json()
    code = data.get('code', '')

    if not code:
        return jsonify({'success': False, 'message': '缺少微信授权码'}), 400

    openid = ''
    # Exchange code for openid via WeChat API
    if config.WECHAT_APPID and config.WECHAT_SECRET:
        try:
            import requests as req_lib
            wx_url = f'https://api.weixin.qq.com/sns/jscode2session?appid={config.WECHAT_APPID}&secret={config.WECHAT_SECRET}&js_code={code}&grant_type=authorization_code'
            wx_res = req_lib.get(wx_url, timeout=10).json()
            openid = wx_res.get('openid', '')
        except Exception:
            pass

    # Fallback: use code as openid for dev/test
    if not openid and code:
        openid = 'wx_dev_' + code[:20]

    if not openid:
        return jsonify({'success': False, 'message': '微信授权失败，请重试'}), 400

    success, msg = bind_wechat_to_user(request.current_user['id'], openid)
    if success:
        return jsonify({'success': True, 'message': msg})
    else:
        return jsonify({'success': False, 'message': msg}), 409


@app.route('/api/auth/me', methods=['GET'])
@login_required
def api_auth_me():
    u = request.current_user
    return jsonify({'success': True, 'data': {
        'id': u['id'], 'nick_name': u['nick_name'], 'avatar': u['avatar'],
        'phone': u['phone'], 'role': u['role'], 'email': u.get('email', ''),
        'username': u.get('username', ''), 'openid': u.get('openid', '')
    }})


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


@app.route('/login')
def login_page():
    return render_template('login.html')


@app.route('/register')
def register_page():
    return render_template('register.html')


@app.route('/admin')
def admin_page():
    return render_template('admin.html')


# ============ API: Cards ============

@app.route('/api/cards', methods=['GET'])
@login_required
def api_list_cards():
    search = request.args.get('search', '')
    rarity = request.args.get('rarity', '')
    sort_by = request.args.get('sort_by', 'updated_at')
    uid = request.current_user['id']
    cards = get_all_cards(search=search, rarity=rarity or None, sort_by=sort_by, user_id=uid)
    return jsonify({'success': True, 'data': cards})


@app.route('/api/cards', methods=['POST'])
@login_required
def api_create_card():
    data = request.get_json() or request.form.to_dict()
    if not data.get('name'):
        return jsonify({'success': False, 'message': 'Card name is required'}), 400

    data['user_id'] = request.current_user['id']

    if 'file' in request.files:
        file = request.files['file']
        if file and file.filename and allowed_file(file.filename):
            ext = file.filename.rsplit('.', 1)[1].lower()
            filename = f'{uuid.uuid4().hex[:12]}.{ext}'
            filepath = os.path.join(config.UPLOAD_FOLDER, filename)
            file.save(filepath)
            data['image_path'] = f'/static/images/{filename}'

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
@login_required
def api_get_card(card_id):
    card = get_card(card_id)
    if not card:
        return jsonify({'success': False, 'message': 'Not found'}), 404
    return jsonify({'success': True, 'data': card})


@app.route('/api/cards/<int:card_id>', methods=['PUT'])
@login_required
def api_update_card(card_id):
    card = get_card(card_id)
    if not card:
        return jsonify({'success': False, 'message': 'Not found'}), 404
    if card.get('user_id') and card['user_id'] != request.current_user['id'] and request.current_user['role'] != 'admin':
        return jsonify({'success': False, 'message': '无权限'}), 403

    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'}), 400

    if 'file' in request.files:
        file = request.files['file']
        if file and file.filename and allowed_file(file.filename):
            ext = file.filename.rsplit('.', 1)[1].lower()
            filename = f'{uuid.uuid4().hex[:12]}.{ext}'
            filepath = os.path.join(config.UPLOAD_FOLDER, filename)
            file.save(filepath)
            data['image_path'] = f'/static/images/{filename}'
            data.pop('file', None)

    for key in ('quantity', 'cost_price', 'market_price'):
        if key in data and data[key] is not None:
            try:
                data[key] = float(data[key]) if key in ('cost_price', 'market_price') else int(float(data[key]))
            except (ValueError, TypeError):
                pass

    try:
        card = update_card(card_id, data)
        return jsonify({'success': True, 'data': card})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/cards/<int:card_id>', methods=['DELETE'])
@login_required
def api_delete_card(card_id):
    card = get_card(card_id)
    if not card:
        return jsonify({'success': False, 'message': 'Not found'}), 404
    if card.get('user_id') and card['user_id'] != request.current_user['id'] and request.current_user['role'] != 'admin':
        return jsonify({'success': False, 'message': '无权限'}), 403
    delete_card(card_id)
    return jsonify({'success': True})


@app.route('/api/upload', methods=['POST'])
@login_required
def api_upload_image():
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
    return jsonify({'success': True, 'image_path': f'/static/images/{filename}'})


# ============ API: Dashboard ============

@app.route('/api/dashboard', methods=['GET'])
@login_required
def api_dashboard():
    uid = request.current_user['id']
    role = request.current_user.get('role', 'user')
    # Admin sees all data
    dash = get_dashboard_data(user_id=None if role == 'admin' else uid)
    rankings = get_rankings(top=10, user_id=None if role == 'admin' else uid)
    snapshots = get_snapshots(days=90)
    dash.update(rankings)
    dash['snapshots'] = snapshots
    return jsonify({'success': True, 'data': dash})


# ============ API: Prices ============

@app.route('/api/prices')
@login_required
def api_get_prices():
    catalog_id = request.args.get('catalog_id')
    if catalog_id:
        prices = get_catalog_prices(int(catalog_id))
        latest = get_catalog_latest_price(int(catalog_id))
        return jsonify({'success': True, 'data': {'history': prices, 'latest': latest}})

    # backward compat: card_id → resolve to catalog_id
    card_id = request.args.get('card_id')
    if card_id:
        conn = get_db()
        card = conn.execute(
            'SELECT catalog_id FROM cards WHERE id = ?', (int(card_id),)
        ).fetchone()
        conn.close()
        if card and card['catalog_id']:
            prices = get_catalog_prices(card['catalog_id'])
            latest = get_catalog_latest_price(card['catalog_id'])
            return jsonify({'success': True, 'data': {'history': prices, 'latest': latest}})
        # fallback: old records that have price_records.card_id
        prices = get_card_prices(int(card_id))
        latest = get_latest_price(int(card_id))
        return jsonify({'success': True, 'data': {'history': prices, 'latest': latest}})

    return jsonify({'success': False, 'message': 'catalog_id or card_id required'}), 400


@app.route('/api/prices/manual', methods=['POST'])
@login_required
def api_add_manual_price():
    data = request.get_json()
    catalog_id = data.get('catalog_id')
    platform = data.get('platform', 'manual')
    price = data.get('price')

    if catalog_id:
        if not price:
            return jsonify({'success': False, 'message': 'catalog_id and price required'}), 400
        try:
            add_catalog_price_record(int(catalog_id), platform, float(price))
            latest = get_catalog_latest_price(int(catalog_id))
            return jsonify({'success': True, 'data': {'latest': latest}})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 500

    # backward compat: card_id → resolve to catalog_id
    card_id = data.get('card_id')
    if not all([card_id, price]):
        return jsonify({'success': False, 'message': 'catalog_id or card_id required'}), 400
    try:
        # Try to resolve card_id → catalog_id
        conn = get_db()
        card = conn.execute(
            'SELECT catalog_id FROM cards WHERE id = ?', (int(card_id),)
        ).fetchone()
        if card and card['catalog_id']:
            conn.close()
            add_catalog_price_record(int(card['catalog_id']), platform, float(price))
            latest = get_catalog_latest_price(int(card['catalog_id']))
            return jsonify({'success': True, 'data': {'latest': latest}})
        conn.close()
        # fallback: old card_id-based record
        add_price_record(int(card_id), platform, float(price))
        latest = get_latest_price(int(card_id))
        return jsonify({'success': True, 'data': {'latest': latest}})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/prices/fetch', methods=['POST'])
@login_required
def api_fetch_price():
    """Trigger price fetch for a catalog item"""
    data = request.get_json()
    catalog_id = data.get('catalog_id')
    source = data.get('source', 'tcg')
    
    if not catalog_id:
        return jsonify({'success': False, 'message': 'catalog_id required'}), 400
    
    try:
        from price_fetcher import fetch_catalog_price
        result = fetch_catalog_price(int(catalog_id), source=source)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/prices/fetch-all', methods=['POST'])
@login_required
def api_fetch_all_prices():
    """Trigger batch price fetch for all catalog items"""
    data = request.get_json() or {}
    limit = data.get('limit')
    source = data.get('source', 'tcg')
    
    try:
        from price_fetcher import fetch_all_catalog_prices
        # Run in background (simple implementation)
        import threading
        def do_fetch():
            fetch_all_catalog_prices(limit=limit, source=source)
        
        thread = threading.Thread(target=do_fetch)
        thread.start()
        
        return jsonify({'success': True, 'message': 'Price fetch started in background'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/snapshots/take', methods=['POST'])
@login_required
def api_take_snapshot():
    take_snapshot()
    return jsonify({'success': True})


# ============ API: TCG Search ============

@app.route('/api/search-tcg')
def api_search_tcg():
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
            for c in result[:20]:
                images = c.get('images', {})
                cards.append({
                    'id': c.get('id'), 'name': c.get('name', ''),
                    'set_name': c.get('set', {}).get('name', ''),
                    'number': c.get('number', ''), 'rarity': c.get('rarity', ''),
                    'image_small': images.get('small', ''), 'image_large': images.get('large', ''),
                    'tcgplayer_prices': c.get('tcgplayer', {}).get('prices') or {},
                    'market_prices': c.get('cardmarket', {}).get('prices') or {},
                })
            return jsonify({'success': True, 'data': cards})
        elif res.status_code == 429:
            return jsonify({'success': False, 'message': 'API rate limited', 'code': 429}), 429
        else:
            return jsonify({'success': False, 'message': f'TCG API error: {res.status_code}'}), res.status_code
    except ImportError:
        return jsonify({'success': False, 'message': 'requests library not installed'}), 500
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/sets-info')
def api_sets_info():
    user = get_request_user()
    uid = user['id'] if user else None
    sets = get_all_set_names(user_id=uid)
    rarities = ['C', 'U', 'R', 'RR', 'SR', 'SAR', 'UR', 'CSR', 'HR']
    conditions = ['NM', 'LP', 'MP', 'HP', 'Damaged']
    return jsonify({'success': True, 'data': {'sets': sets, 'rarities': rarities, 'conditions': conditions}})


# ============ API: Card Catalog (read: all users, write: admin) ============

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
@admin_required
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
@admin_required
def api_catalog_update(item_id):
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'No data'}), 400
    item = update_catalog_item(item_id, data)
    if not item:
        return jsonify({'success': False, 'message': 'Not found'}), 404
    return jsonify({'success': True, 'data': item})


@app.route('/api/catalog/<int:item_id>', methods=['DELETE'])
@admin_required
def api_catalog_delete(item_id):
    delete_catalog_item(item_id)
    return jsonify({'success': True})


@app.route('/api/catalog/bulk', methods=['POST'])
@admin_required
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


@app.route('/api/catalog/<int:catalog_id>/card', methods=['GET'])
@login_required
def api_lookup_card_by_catalog(catalog_id):
    """仅查找用户是否已拥有该 catalog 卡牌，不自动创建"""
    from db import get_catalog_item
    catalog_item = get_catalog_item(catalog_id)
    if not catalog_item:
        return jsonify({'success': False, 'message': 'Catalog item not found'}), 404

    # Check if user already has this card
    conn = get_db()
    row = conn.execute(
        'SELECT * FROM cards WHERE name = ? AND set_name = ? AND user_id = ?',
        (catalog_item['name'], catalog_item['set_name'], request.current_user['id'])
    ).fetchone()
    conn.close()

    return jsonify({'success': True, 'data': {
        'catalog': catalog_item,
        'card': dict(row) if row else None
    }})


@app.route('/api/cards/from-catalog', methods=['POST'])
@login_required
def api_ensure_card_from_catalog():
    data = request.get_json()
    catalog_id = data.get('catalog_id')
    if not catalog_id:
        return jsonify({'success': False, 'message': 'catalog_id is required'}), 400
    try:
        quantity   = int(data.get('quantity', 1))
        cost_price = float(data.get('cost_price', 0))
        condition  = data.get('condition', 'NM')
        notes      = data.get('notes', '')
        card = ensure_card_from_catalog(
            int(catalog_id),
            user_id=request.current_user['id'],
            quantity=quantity,
            cost_price=cost_price,
            condition=condition,
            notes=notes
        )
        if not card:
            return jsonify({'success': False, 'message': 'Catalog item not found'}), 404
        return jsonify({'success': True, 'data': card})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# ============ API: Admin ============

@app.route('/api/admin/users', methods=['GET'])
@admin_required
def api_admin_users():
    users = get_all_users()
    for u in users:
        card_count = len(get_all_cards(user_id=u['id']))
        u['card_count'] = card_count
    return jsonify({'success': True, 'data': users})


@app.route('/api/admin/users/<int:user_id>', methods=['PUT'])
@admin_required
def api_admin_update_user(user_id):
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'No data'}), 400
    update_user(user_id, data)
    return jsonify({'success': True})


@app.route('/api/admin/stats', methods=['GET'])
@admin_required
def api_admin_stats():
    users = get_all_users()
    total_cards = 0
    total_items = 0
    for u in users:
        cards = get_all_cards(user_id=u['id'])
        total_cards += len(cards)
    catalog_items, _ = get_all_catalog(page=1, per_page=1)
    conn = get_db()
    total_catalog = conn.execute('SELECT COUNT(*) as cnt FROM card_catalog').fetchone()['cnt']
    conn.close()
    return jsonify({'success': True, 'data': {
        'user_count': len(users),
        'total_cards': total_cards,
        'total_catalog': total_catalog
    }})


# ============ Pipeline Management (Admin) ============

@app.route('/api/pipeline/methods', methods=['GET'])
@admin_required
def api_pipeline_methods():
    """列出所有已注册的数据管道方法"""
    methods = data_pipeline.list_methods()
    return jsonify({'success': True, 'data': methods})


@app.route('/api/pipeline/run', methods=['POST'])
@admin_required
def api_pipeline_run():
    """执行指定的管道方法"""
    data = request.get_json() or {}
    method_id = data.get('method_id')
    dry_run = data.get('dry_run', False)

    if not method_id:
        return jsonify({'success': False, 'message': 'method_id 必填'}), 400

    result = data_pipeline.run_method(method_id, dry_run=dry_run)
    return jsonify({'success': result.get('success', True), 'data': result})


@app.route('/api/pipeline/run-all', methods=['POST'])
@admin_required
def api_pipeline_run_all():
    """按顺序执行所有管道方法"""
    data = request.get_json() or {}
    dry_run = data.get('dry_run', False)

    results = data_pipeline.run_all(dry_run=dry_run)
    return jsonify({'success': True, 'data': results})


@app.route('/api/pipeline/history', methods=['GET'])
@admin_required
def api_pipeline_history():
    """查看管道执行历史"""
    limit = request.args.get('limit', 20, type=int)
    history = data_pipeline.get_run_history(limit=limit)
    return jsonify({'success': True, 'data': history})


# ============ Serve static images ============

@app.route('/static/images/<path:filename>')
def serve_images(filename):
    return send_from_directory(config.UPLOAD_FOLDER, filename)


# ============ Init & Run ============

try:
    init_db()
except Exception as e:
    import sys
    print(f"[WARN] DB init error (non-fatal): {e}", file=sys.stderr)

os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)


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
        from waitress import serve
        print(f'[waitress] Serving on 0.0.0.0:{port}')
        serve(app, host='0.0.0.0', port=port, threads=4)
    else:
        app.run(host='0.0.0.0', port=port, debug=True)
