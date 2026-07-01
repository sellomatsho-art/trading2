from flask import Flask, jsonify
import os
from datetime import datetime

app = Flask(__name__)

try:
    with open('dashboard.html', 'r') as f:
        dashboard_html = f.read()
except:
    dashboard_html = '<h1>Dashboard</h1>'

trades = []
start_time = datetime.now()

@app.route('/')
def home():
    return '<h1>Bot</h1><a href="/dashboard.html">Dashboard</a>'

@app.route('/dashboard.html')
def dashboard():
    return dashboard_html

@app.route('/stats')
def stats():
    uptime = (datetime.now() - start_time).total_seconds()
    total_pnl = sum([t['pnl'] for t in trades]) if trades else 0
    wins = len([t for t in trades if t['pnl'] > 0])
    
    return jsonify({
        'total_profit': round(total_pnl, 2),
        'daily_avg': round(total_pnl / max(uptime / 86400, 1), 2),
        'win_rate': round((wins / len(trades)) * 100, 1) if trades else 0,
        'total_trades': len(trades),
        'active_positions': 0,
        'trades_per_hour': round(len(trades) / max(uptime / 3600, 1), 2) if uptime > 0 else 0,
        'uptime_seconds': int(uptime)
    })

@app.route('/trades')
def get_trades():
    return jsonify(trades[-20:] if trades else [])

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=False)
