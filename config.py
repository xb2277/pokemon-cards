# Pokemon Cards Manager - Configuration

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Database
DATABASE_PATH = os.path.join(BASE_DIR, 'cards.db')

# Image upload
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'images')
MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5MB per image
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}

# Pokemon TCG API (free, no key required for basic use)
TCG_API_BASE = 'https://api.pokemontcg.io/v2'
TCG_API_KEY = ''  # Optional: get free API key at https://pokemontcg.io for higher rate limits

# Scraper settings
SCRAPER_USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
SCRAPER_TIMEOUT = 15  # seconds

# App config
SECRET_KEY = os.environ.get('SECRET_KEY', 'pokemon-cards-manager-dev-2026')
DEBUG = False  # Always off — Railway runs with debug=False via waitress

# WeChat Mini Program
WECHAT_APPID = os.environ.get('WECHAT_APPID', '')
WECHAT_SECRET = os.environ.get('WECHAT_SECRET', '')

# Admin account (for web login)
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'kapai2026')
