from flask import Flask
import os
from datetime import datetime

app = Flask(__name__)
start_time = datetime.now()

# Read dashboard.html
try:
    with open('dashboard.html', 'r') as f:
        dashboard_content = f.read()
except:
    dashboard_content = '<h1>Dashboard not found</h1>'

@app.route('/')
def home():
    return '<h1>Bot Live</h1><a href="/dashboard.html">Dashboard</a>'

@app.route('/dashboard.html')
def dashboard():
    return dashboard_content

@app.route('/stats')
def stats():
    uptime = (datetime.now() - start_time).total_seconds()
    return {
        'total_profit': 0,
        'daily_avg': 0,
        'win_rate': 0.56,
        'total_trades': 0,
        'active_positions': 0,
        'trades_per_hour': 0,
        'uptime_seconds': uptime
    }

@app.route('/trades')
def trades():
    return []

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
