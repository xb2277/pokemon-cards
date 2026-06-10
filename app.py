"""Minimal test app — verifies Railway can serve pages."""
import os
import sys
from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🎉 Railway 测试成功！</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            min-height: 100vh;
            display: flex; flex-direction: column;
            align-items: center; justify-content: center;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white; text-align: center; padding: 2rem;
        }
        h1 { font-size: 3rem; margin-bottom: 1rem; }
        p { font-size: 1.2rem; opacity: 0.9; margin-bottom: 0.5rem; }
        .badge {
            margin-top: 2rem; padding: 0.5rem 1.5rem;
            background: rgba(255,255,255,0.2); border-radius: 2rem;
            font-size: 0.9rem;
        }
    </style>
</head>
<body>
    <h1>🎉 测试成功！</h1>
    <p>Railway + Flask + Gunicorn 正常工作</p>
    <p>Pokemon Card Manager 即将上线</p>
    <div class="badge">PORT: {port} | Python: {python}</div>
</body>
</html>'''.format(
        port=os.environ.get('PORT', '?'),
        python=sys.version.split()[0]
    )

@app.route('/health')
def health():
    return 'OK', 200, {'Content-Type': 'text/plain'}

# Print startup info
print(f'✓ Minimal test app loaded (Python {sys.version.split()[0]})', flush=True)
print(f'✓ PORT env: {os.environ.get("PORT", "NOT SET")}', flush=True)
