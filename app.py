from flask import Flask, jsonify
import os

app = Flask(__name__)

dashboard_html = None

def load_dashboard():
    global dashboard_html
    try:
        with open('dashboard.html', 'r') as f:
            dashboard_html = f.read()
    except:
        dashboard_html = '<h1>Dashboard file not found</h1>'

load_dashboard()

@app.route('/')
def home():
    return '<h1>Polymarket Bot</h1><p><a href="/dashboard.html">Open Dashboard</a></p>'

@app.route('/dashboard.html')
def dashboard():
    return dashboard_html

@app.route('/stats')
def stats():
    return jsonify({
        'total_profit': 0,
        'daily_avg': 0,
        'win_rate': 56.0,
        'total_trades': 0,
        'active_positions': 0,
        'trades_per_hour': 0,
        'uptime_seconds': 0
    })

@app.route('/trades')
def trades():
    return jsonify([])

if __name__ == '__main__':
    load_dashboard()
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
