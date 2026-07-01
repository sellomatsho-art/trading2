from flask import Flask, jsonify
from datetime import datetime

app = Flask(__name__)

start_time = datetime.now()
trades = []

@app.route('/')
def home():
    return '<h1>Bot Running</h1><p><a href="/dashboard.html">Dashboard</a></p>'

@app.route('/stats')
def stats():
    uptime = (datetime.now() - start_time).total_seconds()
    total_pnl = sum([t['pnl'] for t in trades]) if trades else 0
    
    return jsonify({
        'total_profit': total_pnl,
        'daily_avg': total_pnl / max(uptime / 86400, 1),
        'win_rate': 0.56,
        'total_trades': len(trades),
        'active_positions': 0,
        'trades_per_hour': len(trades) / max(uptime / 3600, 1),
        'uptime_seconds': uptime
    })

@app.route('/trades')
def get_trades():
    return jsonify(trades[-20:] if trades else [])

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
