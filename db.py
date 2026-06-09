# Database operations for Pokemon Cards Manager

import sqlite3
import os
from datetime import datetime
from config import DATABASE_PATH, UPLOAD_FOLDER


def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist"""
    # Ensure upload folder exists
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    conn = get_db()
    c = conn.cursor()

    # Cards table
    c.execute('''
        CREATE TABLE IF NOT EXISTS cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            card_id INTEGER NOT NULL,
            platform VARCHAR(30) NOT NULL,
            price REAL NOT NULL,
            currency VARCHAR(3) DEFAULT 'CNY',
            recorded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (card_id) REFERENCES cards(id) ON DELETE CASCADE
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

    # Indexes for faster queries
    c.execute('CREATE INDEX IF NOT EXISTS idx_cards_name ON cards(name)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_cards_set ON cards(set_name)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_prices_card ON price_records(card_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_prices_date ON price_records(recorded_at)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_catalog_name ON card_catalog(name)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_catalog_set ON card_catalog(set_name)')

    conn.commit()
    conn.close()


# ============ Card CRUD ============

def create_card(data):
    """Insert a new card and return it with its ID"""
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        INSERT INTO cards (name, name_en, set_name, card_number, rarity, condition,
                           quantity, cost_price, market_price, image_path, tcg_id, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (data['name'], data.get('name_en', ''), data.get('set_name', ''),
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


def ensure_market_price_column():
    """Add market_price column if it doesn't exist (for upgraded databases)"""
    try:
        conn = get_db()
        conn.execute('ALTER TABLE cards ADD COLUMN market_price REAL DEFAULT 0')
        conn.commit()
        conn.close()
    except:
        pass

def get_all_cards(search='', rarity=None, sort_by='updated_at'):
    """Get all cards with optional search/filter/sort"""
    conn = get_db()
    query = 'SELECT * FROM cards WHERE 1=1'
    params = []

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

    rows = c = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_card(card_id):
    """Get a single card by ID"""
    conn = get_db()
    row = conn.execute('SELECT * FROM cards WHERE id = ?', (card_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_card(card_id, data):
    """Update a card"""
    conn = get_db()
    fields = []
    values = []
    for key in ('name', 'name_en', 'set_name', 'card_number', 'rarity',
                'condition', 'quantity', 'cost_price', 'market_price',
                'image_path', 'tcg_id', 'notes'):
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
    """Delete a card and its price records"""
    conn = get_db()
    conn.execute('DELETE FROM price_records WHERE card_id = ?', (card_id,))
    conn.execute('DELETE FROM cards WHERE id = ?', (card_id,))
    conn.commit()
    conn.close()


def get_all_set_names():
    """Get distinct set names for filter dropdown"""
    conn = get_db()
    rows = conn.execute("SELECT DISTINCT set_name FROM cards WHERE set_name != '' ORDER BY set_name").fetchall()
    conn.close()
    return [r['set_name'] for r in rows]


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
    """Get price history for a specific card"""
    conn = get_db()
    rows = conn.execute(
        'SELECT * FROM price_records WHERE card_id = ? ORDER BY recorded_at DESC LIMIT ?',
        (card_id, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_latest_price(card_id):
    """Get the latest average price for a card"""
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


# ============ Dashboard / Statistics ============

def get_dashboard_data():
    """Compute dashboard summary statistics"""
    conn = get_db()
    cards = [dict(r) for r in conn.execute(
        'SELECT id, quantity, cost_price FROM cards ORDER BY id'
    ).fetchall()]

    total_quantity = sum(c['quantity'] for c in cards)
    total_cost = sum(c['cost_price'] * c['quantity'] for c in cards)

    # Get latest prices
    total_value = 0
    valued_cards = 0
    for card in cards:
        price_info = get_latest_price(card['id'])
        if price_info['avg']:
            card_value = price_info['avg'] * card['quantity']
            total_value += card_value
            valued_cards += 1

    profit = total_value - total_cost
    profit_pct = (profit / total_cost * 100) if total_cost > 0 else 0

    # Rarity distribution
    rarity_rows = conn.execute(
        'SELECT rarity, SUM(quantity) as qty, COUNT(*) as types FROM cards GROUP BY rarity ORDER BY qty DESC'
    ).fetchall()
    rarity_dist = [{'name': r['rarity'], 'value': r['qty'], 'types': r['types']} for r in rarity_rows]

    # Set distribution
    set_rows = conn.execute(
        "SELECT set_name, SUM(quantity) as qty FROM cards WHERE set_name != '' GROUP BY set_name ORDER BY qty DESC"
    ).fetchall()
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


def get_rankings(top=10):
    """Get top gainers/losers based on latest price vs cost"""
    conn = get_db()
    cards = [dict(r) for r in conn.execute(
        'SELECT id, name, cost_price, quantity, image_path FROM cards'
    ).fetchall()]
    conn.close()

    rankings = []
    for card in cards:
        info = get_latest_price(card['id'])
        if info['avg'] and card['cost_price'] > 0:
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



def ensure_card_from_catalog(catalog_id):
    """Ensure a card exists in `cards` table based on a catalog item.
    If it already exists (matched by name + set_name), return existing card.
    Otherwise, create it from catalog data.
    Returns the card dict, or None if catalog item not found.
    """
    catalog_item = get_catalog_item(catalog_id)
    if not catalog_item:
        return None

    conn = get_db()
    existing = conn.execute(
        'SELECT * FROM cards WHERE name = ? AND set_name = ?',
        (catalog_item['name'], catalog_item['set_name'])
    ).fetchone()

    if existing:
        card = dict(existing)
        conn.close()
        return card

    c = conn.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    c.execute('''
        INSERT INTO cards (name, name_en, set_name, card_number, rarity,
                          quantity, cost_price, image_path, tcg_id, notes,
                          created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, 1, 0, ?, '', '', ?, ?)
    ''', (
        catalog_item['name'],
        catalog_item['name_en'],
        catalog_item['set_name'],
        catalog_item['card_number'],
        catalog_item['rarity'] or 'C',
        catalog_item['image_url'] or '',
        now,
        now,
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
