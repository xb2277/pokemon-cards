# Database operations for Pokemon Cards Manager

import sqlite3
import os
import secrets
from datetime import datetime
from config import DATABASE_PATH, UPLOAD_FOLDER


def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA busy_timeout=5000')
    return conn


def init_db():
    """Create tables if they don't exist"""
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    conn = get_db()
    c = conn.cursor()

    # Users table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            openid VARCHAR(100) DEFAULT '',
            username VARCHAR(50) DEFAULT '',
            email VARCHAR(120) DEFAULT '',
            password_hash VARCHAR(128) DEFAULT '',
            nick_name VARCHAR(50) DEFAULT '',
            avatar VARCHAR(255) DEFAULT '',
            phone VARCHAR(20) DEFAULT '',
            role VARCHAR(10) DEFAULT 'user',
            token VARCHAR(64) DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Cards table
    c.execute('''
        CREATE TABLE IF NOT EXISTS cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER DEFAULT 0,
            catalog_id INTEGER DEFAULT NULL,
            name VARCHAR(100) NOT NULL,
            name_en VARCHAR(100) DEFAULT '',
            set_name VARCHAR(80) DEFAULT '',
            card_number VARCHAR(20) DEFAULT '',
            rarity VARCHAR(20) DEFAULT 'C',
            condition VARCHAR(10) DEFAULT 'NM',
            quantity INTEGER DEFAULT 1,
            cost_price REAL DEFAULT 0,
            market_price REAL DEFAULT 0,
            image_path VARCHAR(255) DEFAULT '',
            tcg_id VARCHAR(50) DEFAULT '',
            notes TEXT DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Price records table
    c.execute('''
        CREATE TABLE IF NOT EXISTS price_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_id INTEGER DEFAULT NULL,
            catalog_id INTEGER DEFAULT NULL,
            platform VARCHAR(30) NOT NULL,
            price REAL NOT NULL,
            currency VARCHAR(3) DEFAULT 'CNY',
            recorded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (card_id) REFERENCES cards(id) ON DELETE CASCADE,
            FOREIGN KEY (catalog_id) REFERENCES card_catalog(id) ON DELETE CASCADE
        )
    ''')

    # Daily snapshots table
    c.execute('''
        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            total_value REAL DEFAULT 0,
            total_cost REAL DEFAULT 0,
            snapshot_date DATE UNIQUE
        )
    ''')

    # Card Catalog table (master card species database)
    c.execute('''
        CREATE TABLE IF NOT EXISTS card_catalog (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(100) NOT NULL,
            name_en VARCHAR(100) DEFAULT '',
            set_name VARCHAR(80) DEFAULT '',
            set_code VARCHAR(30) DEFAULT '',
            card_number VARCHAR(20) DEFAULT '',
            rarity VARCHAR(20) DEFAULT '',
            image_url VARCHAR(255) DEFAULT '',
            description TEXT DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Pipeline runs table (data acquisition execution history)
    c.execute('''
        CREATE TABLE IF NOT EXISTS pipeline_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            method_id VARCHAR(50) NOT NULL,
            method_name VARCHAR(100) DEFAULT '',
            status VARCHAR(20) DEFAULT 'running',
            dry_run INTEGER DEFAULT 0,
            stats TEXT DEFAULT '{}',
            message TEXT DEFAULT '',
            started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            finished_at DATETIME
        )
    ''')

    # Indexes
    c.execute('CREATE INDEX IF NOT EXISTS idx_cards_name ON cards(name)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_cards_set ON cards(set_name)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_cards_user ON cards(user_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_prices_card ON price_records(card_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_prices_date ON price_records(recorded_at)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_catalog_name ON card_catalog(name)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_catalog_set ON card_catalog(set_name)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_users_openid ON users(openid)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_users_token ON users(token)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)')

    # Migrations (must run BEFORE creating indexes on new columns)
    _migrate_add_column(c, 'cards', 'user_id', 'INTEGER DEFAULT 0')
    _migrate_add_column(c, 'users', 'email', 'VARCHAR(120) DEFAULT \'\'')
    _migrate_add_column(c, 'price_records', 'catalog_id', 'INTEGER DEFAULT NULL')
    _migrate_add_column(c, 'cards', 'catalog_id', 'INTEGER DEFAULT NULL')
    _migrate_add_column(c, 'card_catalog', 'tcg_id', 'VARCHAR(100) DEFAULT \'\'')
    # Expand card_catalog with TCG API fields
    _migrate_add_column(c, 'card_catalog', 'hp', 'INTEGER DEFAULT NULL')
    _migrate_add_column(c, 'card_catalog', 'types', 'TEXT DEFAULT NULL')
    _migrate_add_column(c, 'card_catalog', 'subtypes', 'TEXT DEFAULT NULL')
    _migrate_add_column(c, 'card_catalog', 'evolves_from', 'TEXT DEFAULT NULL')
    _migrate_add_column(c, 'card_catalog', 'abilities', 'TEXT DEFAULT NULL')
    _migrate_add_column(c, 'card_catalog', 'attacks', 'TEXT DEFAULT NULL')
    _migrate_add_column(c, 'card_catalog', 'weaknesses', 'TEXT DEFAULT NULL')
    _migrate_add_column(c, 'card_catalog', 'retreat_cost', 'INTEGER DEFAULT NULL')
    _migrate_add_column(c, 'card_catalog', 'artist', 'TEXT DEFAULT NULL')
    _migrate_add_column(c, 'card_catalog', 'flavor_text', 'TEXT DEFAULT NULL')
    _migrate_add_column(c, 'card_catalog', 'national_pokedex_numbers', 'TEXT DEFAULT NULL')
    _migrate_add_column(c, 'card_catalog', 'legalities', 'TEXT DEFAULT NULL')
    # Pipeline-related columns on card_catalog
    _migrate_add_column(c, 'card_catalog', 'market_price', 'REAL DEFAULT 0')
    _migrate_add_column(c, 'card_catalog', 'category', "TEXT DEFAULT 'PTCG-SC'")
    _migrate_add_column(c, 'card_catalog', 'language', "TEXT DEFAULT 'zh'")

    # Index on migrated column (only after migration ensures column exists)
    try:
        c.execute('CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)')
    except:
        pass
    try:
        c.execute('CREATE INDEX IF NOT EXISTS idx_prices_catalog ON price_records(catalog_id)')
    except:
        pass
    try:
        c.execute('CREATE INDEX IF NOT EXISTS idx_cards_catalog ON cards(catalog_id)')
    except:
        pass
    try:
        c.execute('CREATE INDEX IF NOT EXISTS idx_pipeline_method ON pipeline_runs(method_id)')
    except:
        pass

    conn.commit()
    conn.close()

    # Migrate: link existing cards to catalog
    _migrate_cards_catalog_link()


def _migrate_add_column(cursor, table, column, col_def):
    """Add a column if it doesn't exist"""
    try:
        cursor.execute(f'ALTER TABLE {table} ADD COLUMN {column} {col_def}')
    except:
        pass


def _migrate_cards_catalog_link():
    """One-time migration: link existing cards to card_catalog by name+set_name"""
    conn = get_db()
    unchecked = conn.execute('SELECT COUNT(*) as cnt FROM cards WHERE catalog_id IS NULL').fetchone()['cnt']
    if unchecked == 0:
        conn.close()
        return
    catalog_rows = conn.execute('SELECT id, name, set_name FROM card_catalog').fetchall()
    catalog_map = {}
    for r in catalog_rows:
        key = (r['name'], r['set_name'])
        catalog_map[key] = r['id']
    updated = 0
    for card in conn.execute('SELECT id, name, set_name FROM cards WHERE catalog_id IS NULL').fetchall():
        key = (card['name'], card['set_name'])
        if key in catalog_map:
            conn.execute('UPDATE cards SET catalog_id = ? WHERE id = ?', (catalog_map[key], card['id']))
            updated += 1
    if updated > 0:
        conn.commit()
    conn.close()


# ============ User Auth ============

def get_user_by_openid(openid):
    conn = get_db()
    row = conn.execute('SELECT * FROM users WHERE openid = ?', (openid,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_token(token):
    conn = get_db()
    row = conn.execute('SELECT * FROM users WHERE token = ?', (token,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_username(username):
    conn = get_db()
    row = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_email(email):
    conn = get_db()
    row = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
    conn.close()
    return dict(row) if row else None


def create_user(openid='', username='', email='', password_hash='', nick_name='', avatar='', phone='', role='user'):
    conn = get_db()
    token = secrets.token_hex(32)
    c = conn.cursor()
    c.execute('''
        INSERT INTO users (openid, username, email, password_hash, nick_name, avatar, phone, role, token)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (openid, username, email, password_hash, nick_name, avatar, phone, role, token))
    user_id = c.lastrowid
    conn.commit()
    conn.close()
    return token


def update_user_token(user_id):
    conn = get_db()
    token = secrets.token_hex(32)
    conn.execute('UPDATE users SET token = ? WHERE id = ?', (token, user_id))
    conn.commit()
    conn.close()
    return token


def update_user(user_id, data):
    conn = get_db()
    fields = []
    values = []
    for key in ('nick_name', 'avatar', 'phone', 'role', 'email', 'username', 'openid'):
        if key in data:
            fields.append(f'{key} = ?')
            values.append(data[key])
    if fields:
        values.append(user_id)
        conn.execute(f'UPDATE users SET {", ".join(fields)} WHERE id = ?', values)
        conn.commit()
    conn.close()


def get_all_users():
    conn = get_db()
    rows = conn.execute('SELECT id, openid, username, email, nick_name, avatar, phone, role, created_at FROM users ORDER BY created_at DESC').fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_user(user_id):
    conn = get_db()
    row = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def bind_wechat_to_user(user_id, openid):
    """Bind a WeChat openid to an existing user account"""
    conn = get_db()
    # Check if openid is already bound to another user
    existing = conn.execute('SELECT id FROM users WHERE openid = ? AND id != ?', (openid, user_id)).fetchone()
    if existing:
        conn.close()
        return False, '该微信已绑定其他账号'
    conn.execute('UPDATE users SET openid = ? WHERE id = ?', (openid, user_id))
    conn.commit()
    conn.close()
    return True, '微信绑定成功'


# ============ Card CRUD ============

def create_card(data):
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        INSERT INTO cards (user_id, catalog_id, name, name_en, set_name, card_number, rarity, condition,
                           quantity, cost_price, market_price, image_path, tcg_id, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (data.get('user_id', 0), data.get('catalog_id') or None, data['name'], data.get('name_en', ''), data.get('set_name', ''),
          data.get('card_number', ''), data.get('rarity', 'C'),
          data.get('condition', 'NM'), int(data.get('quantity', 1)),
          float(data.get('cost_price', 0)), float(data.get('market_price', 0)),
          data.get('image_path', ''),
          data.get('tcg_id', ''), data.get('notes', '')))
    card_id = c.lastrowid
    conn.commit()
    row = c.execute('SELECT * FROM cards WHERE id = ?', (card_id,)).fetchone()
    conn.close()
    return dict(row)


def get_all_cards(search='', rarity=None, sort_by='updated_at', user_id=None):
    conn = get_db()
    query = 'SELECT * FROM cards WHERE 1=1'
    params = []

    if user_id is not None:
        query += ' AND user_id = ?'
        params.append(user_id)

    if search:
        query += ' AND (name LIKE ? OR name_en LIKE ? OR card_number LIKE ? OR set_name LIKE ?)'
        s = f'%{search}%'
        params.extend([s, s, s, s])

    if rarity and rarity != 'all':
        query += ' AND rarity = ?'
        params.append(rarity)

    allowed_sorts = {'name', 'set_name', 'rarity', 'quantity', 'cost_price', 'created_at', 'updated_at'}
    if sort_by in allowed_sorts:
        query += f' ORDER BY {sort_by} DESC'
    else:
        query += ' ORDER BY updated_at DESC'

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_card(card_id):
    conn = get_db()
    row = conn.execute('SELECT * FROM cards WHERE id = ?', (card_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_card(card_id, data):
    conn = get_db()
    fields = []
    values = []
    for key in ('name', 'name_en', 'set_name', 'card_number', 'rarity',
                'condition', 'quantity', 'cost_price', 'market_price',
                'image_path', 'tcg_id', 'notes', 'catalog_id'):
        if key in data:
            fields.append(f'{key} = ?')
            values.append(data[key])
    if not fields:
        conn.close()
        return None

    fields.append('updated_at = ?')
    values.append(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    values.append(card_id)

    conn.execute(f'UPDATE cards SET {", ".join(fields)} WHERE id = ?', values)
    conn.commit()
    row = conn.execute('SELECT * FROM cards WHERE id = ?', (card_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_card(card_id):
    conn = get_db()
    # Set card_id to NULL in price_records (don't delete — prices tied to catalog survive)
    conn.execute('UPDATE price_records SET card_id = NULL WHERE card_id = ?', (card_id,))
    conn.execute('DELETE FROM cards WHERE id = ?', (card_id,))
    conn.commit()
    conn.close()


def get_all_set_names(user_id=None):
    conn = get_db()
    if user_id is not None:
        rows = conn.execute("SELECT DISTINCT set_name FROM cards WHERE set_name != '' AND user_id = ? ORDER BY set_name", (user_id,)).fetchall()
    else:
        rows = conn.execute("SELECT DISTINCT set_name FROM cards WHERE set_name != '' ORDER BY set_name").fetchall()
    conn.close()
    return [r['set_name'] for r in rows]


def ensure_market_price_column():
    """Add market_price column if it doesn't exist (for upgraded databases)"""
    try:
        conn = get_db()
        conn.execute('ALTER TABLE cards ADD COLUMN market_price REAL DEFAULT 0')
        conn.commit()
        conn.close()
    except:
        pass


# ============ Price Records ============

def add_price_record(card_id, platform, price, currency='CNY'):
    """Add a price record for a card"""
    conn = get_db()
    conn.execute('''
        INSERT INTO price_records (card_id, platform, price, currency, recorded_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (card_id, platform, price, currency, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    conn.close()


def get_card_prices(card_id, limit=60):
    """Get price history for a specific card (backward compatible)"""
    conn = get_db()
    rows = conn.execute(
        'SELECT * FROM price_records WHERE card_id = ? ORDER BY recorded_at DESC LIMIT ?',
        (card_id, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_latest_price(card_id):
    """Get the latest average price for a card (backward compatible)"""
    conn = get_db()
    row = conn.execute(
        '''SELECT AVG(price) as avg_price, MAX(price) as max_price, MIN(price) as min_price,
                  COUNT(*) as record_count
           FROM price_records WHERE card_id = ?
             AND recorded_at >= date('now', '-30 days')''',
        (card_id,)
    ).fetchone()
    conn.close()
    return {
        'avg': round(row['avg_price'], 2) if row['avg_price'] else None,
        'max': round(row['max_price'], 2) if row['max_price'] else None,
        'min': round(row['min_price'], 2) if row['min_price'] else None,
        'count': row['record_count']
    }


# ============ Catalog-based Price Records (primary model) ============

def add_catalog_price_record(catalog_id, platform, price, currency='CNY'):
    """Add a price record linked to a catalog item (shared across all users)"""
    conn = get_db()
    conn.execute('''
        INSERT INTO price_records (catalog_id, platform, price, currency, recorded_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (catalog_id, platform, price, currency, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    conn.close()


def get_catalog_prices(catalog_id, limit=60):
    """Get price history for a catalog item"""
    conn = get_db()
    rows = conn.execute(
        'SELECT * FROM price_records WHERE catalog_id = ? ORDER BY recorded_at DESC LIMIT ?',
        (catalog_id, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_catalog_latest_price(catalog_id):
    """Get the latest average price for a catalog item"""
    conn = get_db()
    row = conn.execute(
        '''SELECT AVG(price) as avg_price, MAX(price) as max_price, MIN(price) as min_price,
                  COUNT(*) as record_count
           FROM price_records WHERE catalog_id = ?
             AND recorded_at >= date('now', '-30 days')''',
        (catalog_id,)
    ).fetchone()
    conn.close()
    return {
        'avg': round(row['avg_price'], 2) if row['avg_price'] else None,
        'max': round(row['max_price'], 2) if row['max_price'] else None,
        'min': round(row['min_price'], 2) if row['min_price'] else None,
        'count': row['record_count']
    }


# ============ Dashboard / Statistics ============

def get_dashboard_data(user_id=None):
    """Compute dashboard summary statistics"""
    conn = get_db()
    if user_id is not None:
        cards = [dict(r) for r in conn.execute(
            'SELECT id, catalog_id, market_price, quantity, cost_price FROM cards WHERE user_id = ? ORDER BY id', (user_id,)
        ).fetchall()]
    else:
        cards = [dict(r) for r in conn.execute(
            'SELECT id, catalog_id, market_price, quantity, cost_price FROM cards ORDER BY id'
        ).fetchall()]

    total_quantity = sum(c['quantity'] for c in cards)
    total_cost = sum(c['cost_price'] * c['quantity'] for c in cards)

    # Get latest prices
    total_value = 0
    valued_cards = 0
    for card in cards:
        price_info = None
        if card.get('catalog_id'):
            price_info = get_catalog_latest_price(card['catalog_id'])
        if not price_info or not price_info['avg']:
            price_info = get_latest_price(card['id'])
        # Fallback to market_price
        if (not price_info or not price_info['avg']) and card.get('market_price'):
            price_info = {'avg': card['market_price'], 'max': None, 'min': None, 'count': 1}
        if price_info and price_info.get('avg'):
            card_value = price_info['avg'] * card['quantity']
            total_value += card_value
            valued_cards += 1

    profit = total_value - total_cost
    profit_pct = (profit / total_cost * 100) if total_cost > 0 else 0

    # Rarity distribution
    if user_id is not None:
        rarity_rows = conn.execute(
            'SELECT rarity, SUM(quantity) as qty, COUNT(*) as types FROM cards WHERE user_id = ? GROUP BY rarity ORDER BY qty DESC',
            (user_id,)
        ).fetchall()
        set_rows = conn.execute(
            "SELECT set_name, SUM(quantity) as qty FROM cards WHERE set_name != '' AND user_id = ? GROUP BY set_name ORDER BY qty DESC",
            (user_id,)
        ).fetchall()
    else:
        rarity_rows = conn.execute(
            'SELECT rarity, SUM(quantity) as qty, COUNT(*) as types FROM cards GROUP BY rarity ORDER BY qty DESC'
        ).fetchall()
        set_rows = conn.execute(
            "SELECT set_name, SUM(quantity) as qty FROM cards WHERE set_name != '' GROUP BY set_name ORDER BY qty DESC"
        ).fetchall()
    rarity_dist = [{'name': r['rarity'], 'value': r['qty'], 'types': r['types']} for r in rarity_rows]
    set_dist = [{'name': r['set_name'], 'value': r['qty']} for r in set_rows]

    conn.close()

    return {
        'total_cards': len(cards),
        'total_quantity': total_quantity,
        'total_cost': round(total_cost, 2),
        'total_value': round(total_value, 2),
        'profit': round(profit, 2),
        'profit_pct': round(profit_pct, 1),
        'valued_cards': valued_cards,
        'rarity_distribution': rarity_dist,
        'set_distribution': set_dist,
    }


def get_rankings(top=10, user_id=None):
    """Get top gainers/losers based on latest price vs cost"""
    conn = get_db()
    if user_id is not None:
        cards = [dict(r) for r in conn.execute(
            'SELECT id, catalog_id, market_price, name, cost_price, quantity, image_path FROM cards WHERE user_id = ?', (user_id,)
        ).fetchall()]
    else:
        cards = [dict(r) for r in conn.execute(
            'SELECT id, catalog_id, market_price, name, cost_price, quantity, image_path FROM cards'
        ).fetchall()]
    conn.close()

    rankings = []
    for card in cards:
        info = None
        if card.get('catalog_id'):
            info = get_catalog_latest_price(card['catalog_id'])
        if not info or not info['avg']:
            info = get_latest_price(card['id'])
        if (not info or not info.get('avg')) and card.get('market_price'):
            info = {'avg': card['market_price'], 'max': None, 'min': None, 'count': 1}
        if info and info.get('avg') and card['cost_price'] > 0:
            change_pct = ((info['avg'] - card['cost_price']) / card['cost_price']) * 100
            rankings.append({
                'id': card['id'],
                'name': card['name'],
                'cost': card['cost_price'],
                'current': info['avg'],
                'change_pct': round(change_pct, 1),
                'quantity': card['quantity'],
                'image_path': card['image_path'],
            })

    rankings.sort(key=lambda x: x['change_pct'], reverse=True)
    return {
        'top_gainers': rankings[:top],
        'top_losers': rankings[-top:][::-1],
    }


def get_snapshots(days=90):
    """Get daily snapshot history for chart"""
    conn = get_db()
    rows = conn.execute(
        'SELECT * FROM snapshots WHERE snapshot_date >= date("now", "-{} days") ORDER BY snapshot_date'.format(days)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def take_snapshot():
    """Record today's total value as a snapshot"""
    dash = get_dashboard_data()
    conn = get_db()
    today = datetime.now().strftime('%Y-%m-%d')
    try:
        conn.execute(
            'INSERT OR REPLACE INTO snapshots (snapshot_date, total_value, total_cost) VALUES (?, ?, ?)',
            (today, dash['total_value'], dash['total_cost'])
        )
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


# ============ Card Catalog CRUD ============

def get_all_catalog(search='', set_name=None, rarity=None, page=1, per_page=60):
    """Search the card catalog with optional filters"""
    conn = get_db()
    query = 'SELECT * FROM card_catalog WHERE 1=1'
    params = []

    if search:
        query += ' AND (name LIKE ? OR name_en LIKE ? OR card_number LIKE ? OR set_name LIKE ? OR set_code LIKE ?)'
        s = f'%{search}%'
        params.extend([s, s, s, s, s])

    if set_name and set_name != 'all':
        query += ' AND set_name = ?'
        params.append(set_name)

    if rarity and rarity != 'all':
        query += ' AND rarity = ?'
        params.append(rarity)

    # total count
    count_row = conn.execute('SELECT COUNT(*) as cnt FROM (' + query + ')', params).fetchone()
    total = count_row['cnt']

    query += ' ORDER BY set_name, card_number, name LIMIT ? OFFSET ?'
    params.extend([per_page, (page - 1) * per_page])

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows], total


def get_catalog_item(item_id):
    conn = get_db()
    row = conn.execute('SELECT * FROM card_catalog WHERE id = ?', (item_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def create_catalog_item(data):
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        INSERT INTO card_catalog (name, name_en, set_name, set_code, card_number, rarity, image_url, description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (data['name'], data.get('name_en', ''), data.get('set_name', ''),
          data.get('set_code', ''), data.get('card_number', ''),
          data.get('rarity', ''), data.get('image_url', ''),
          data.get('description', '')))
    item_id = c.lastrowid
    conn.commit()
    row = c.execute('SELECT * FROM card_catalog WHERE id = ?', (item_id,)).fetchone()
    conn.close()
    return dict(row)


def update_catalog_item(item_id, data):
    conn = get_db()
    fields = []
    values = []
    for key in ('name', 'name_en', 'set_name', 'set_code', 'card_number', 'rarity', 'image_url', 'description'):
        if key in data:
            fields.append(f'{key} = ?')
            values.append(data[key])
    if not fields:
        conn.close()
        return None
    fields.append('updated_at = ?')
    values.append(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    values.append(item_id)
    conn.execute(f'UPDATE card_catalog SET {", ".join(fields)} WHERE id = ?', values)
    conn.commit()
    row = conn.execute('SELECT * FROM card_catalog WHERE id = ?', (item_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_catalog_item(item_id):
    conn = get_db()
    conn.execute('DELETE FROM card_catalog WHERE id = ?', (item_id,))
    conn.commit()
    conn.close()



def ensure_card_from_catalog(catalog_id, user_id=0, quantity=1, cost_price=0, condition='NM', notes=''):
    """Ensure a card exists in `cards` table based on a catalog item.
    
    Returns:
        dict: existing or newly created card
    """
    catalog_item = get_catalog_item(catalog_id)
    if not catalog_item:
        return None

    conn = get_db()
    existing = conn.execute(
        'SELECT * FROM cards WHERE catalog_id = ? AND user_id = ?',
        (catalog_id, user_id)
    ).fetchone()

    if not existing:
        existing = conn.execute(
            'SELECT * FROM cards WHERE name = ? AND set_name = ? AND user_id = ?',
            (catalog_item['name'], catalog_item['set_name'], user_id)
        ).fetchone()

    if existing:
        card = dict(existing)
        conn.close()
        return card

    c = conn.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    c.execute('''
        INSERT INTO cards (user_id, catalog_id, name, name_en, set_name, card_number, rarity,
                          condition, quantity, cost_price, image_path, tcg_id, notes,
                          created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, catalog_id,
        catalog_item['name'], catalog_item['name_en'],
        catalog_item['set_name'], catalog_item['card_number'],
        catalog_item['rarity'] or 'C',
        condition,
        quantity, cost_price,
        catalog_item['image_url'] or '',
        catalog_item.get('tcg_id', '') or '',
        notes,
        now, now
    ))
    card_id = c.lastrowid
    row = conn.execute('SELECT * FROM cards WHERE id = ?', (card_id,)).fetchone()
    conn.commit()
    conn.close()
    return dict(row) if row else None


def get_catalog_sets():
    """Distinct set names in catalog"""
    conn = get_db()
    rows = conn.execute(
        "SELECT DISTINCT set_name FROM card_catalog WHERE set_name != '' ORDER BY set_name"
    ).fetchall()
    conn.close()
    return [r['set_name'] for r in rows]


def bulk_insert_catalog(items):
    """Batch insert catalog items, skip duplicates (same name+set_name+card_number)"""
    conn = get_db()
    c = conn.cursor()
    inserted = 0
    skipped = 0
    for data in items:
        existing = conn.execute(
            'SELECT id FROM card_catalog WHERE name=? AND set_name=? AND card_number=?',
            (data.get('name',''), data.get('set_name',''), data.get('card_number',''))
        ).fetchone()
        if existing:
            skipped += 1
            continue
        c.execute('''
            INSERT INTO card_catalog (name, name_en, set_name, set_code, card_number, rarity, image_url, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (data.get('name',''), data.get('name_en',''), data.get('set_name',''),
              data.get('set_code',''), data.get('card_number',''),
              data.get('rarity',''), data.get('image_url',''),
              data.get('description','')))
        inserted += 1
    conn.commit()
    conn.close()
    return {'inserted': inserted, 'skipped': skipped}
