import os
import sys
import sqlite3
import shutil
import threading
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

app = Flask(__name__, template_folder=resource_path("templates"), static_folder=resource_path("static"))
app.secret_key = "ramdev_pro_secure_key"

def get_db():
    conn = sqlite3.connect('ramdev_transport.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS parcels 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, receipt TEXT, 
                  receiver TEXT, weight REAL, bale_no TEXT, parcel_count INTEGER)''')
    c.execute('CREATE INDEX IF NOT EXISTS idx_receipt ON parcels(receipt)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_receiver ON parcels(receiver)')
    
    c.execute('''CREATE TABLE IF NOT EXISTS clients 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, 
                  gstin TEXT, address TEXT, default_rate REAL DEFAULT 0.0)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS invoices 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, client_name TEXT, month TEXT, 
                  amount REAL, status TEXT DEFAULT 'Pending', date_gen TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

@app.route('/')
def dashboard():
    conn = get_db()
    res = conn.execute("SELECT COUNT(*), SUM(weight) FROM parcels").fetchone()
    pending = conn.execute("SELECT SUM(amount) FROM invoices WHERE status='Pending'").fetchone()[0] or 0
    recent = conn.execute("SELECT * FROM parcels ORDER BY id DESC LIMIT 5").fetchall()
    conn.close()
    return render_template('dashboard.html', total=res[0], weight=res[1] or 0, pending=pending, parcels=recent)

@app.route('/add', methods=['GET', 'POST'])
def add_entry():
    if request.method == 'POST':
        conn = get_db()
        conn.execute("INSERT INTO parcels (date, receipt, receiver, weight, bale_no, parcel_count) VALUES (?,?,?,?,?,?)",
                     (request.form['date'], request.form['lr'], request.form['receiver'], 
                      float(request.form['weight']), request.form['bale_no'], int(request.form['parcel_count'])))
        conn.commit()
        conn.close()
        flash("Entry Saved Successfully!", "success")
        return redirect(url_for('ledger'))
    conn = get_db()
    clients = conn.execute("SELECT name FROM clients ORDER BY name ASC").fetchall()
    conn.close()
    return render_template('entry.html', clients=clients)

@app.route('/ledger')
def ledger():
    page = request.args.get('page', 1, type=int)
    per_page = 50
    offset = (page - 1) * per_page
    search = request.args.get('search', '')
    conn = get_db()
    if search:
        query = "SELECT * FROM parcels WHERE receipt LIKE ? OR receiver LIKE ? ORDER BY date DESC LIMIT ? OFFSET ?"
        parcels = conn.execute(query, (f'%{search}%', f'%{search}%', per_page, offset)).fetchall()
        total_rows = conn.execute("SELECT COUNT(*) FROM parcels WHERE receipt LIKE ? OR receiver LIKE ?", (f'%{search}%', f'%{search}%')).fetchone()[0]
    else:
        query = "SELECT * FROM parcels ORDER BY date DESC LIMIT ? OFFSET ?"
        parcels = conn.execute(query, (per_page, offset)).fetchall()
        total_rows = conn.execute("SELECT COUNT(*) FROM parcels").fetchone()[0]
    total_pages = max((total_rows + per_page - 1) // per_page, 1)
    conn.close()
    return render_template('ledger.html', parcels=parcels, search_query=search, page=page, total_pages=total_pages)

@app.route('/directory', methods=['GET', 'POST'])
def directory():
    conn = get_db()
    if request.method == 'POST':
        name = request.form['name'].strip().upper()
        existing = conn.execute("SELECT id FROM clients WHERE name = ?", (name,)).fetchone()
        if existing:
            flash(f"ERROR: Client '{name}' already exists in Directory!", "danger")
        else:
            conn.execute("INSERT INTO clients (name, gstin, address, default_rate) VALUES (?,?,?,?)", 
                         (name, request.form['gstin'].upper(), request.form['address'], float(request.form.get('default_rate', 0))))
            conn.commit()
            flash(f"Client '{name}' Registered Successfully!", "success")
    clients = conn.execute("SELECT * FROM clients ORDER BY name ASC").fetchall()
    conn.close()
    return render_template('directory.html', clients=clients)

@app.route('/delete_client/<int:id>')
def delete_client(id):
    conn = get_db()
    conn.execute("DELETE FROM clients WHERE id=?", (id,))
    conn.commit()
    conn.close()
    flash("Client Deleted Successfully!", "success")
    return redirect(url_for('directory'))

@app.route('/backup_action')
def backup_action():
    try:
        db_path = 'ramdev_transport.db'
        backup_name = f"Ramdev_Backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        dest = os.path.join(os.path.expanduser("~"), "Desktop", backup_name)
        shutil.copy2(db_path, dest)
        flash(f"Backup Saved to Desktop as {backup_name}", "success")
    except Exception as e:
        flash(f"Backup Failed: {str(e)}", "danger")
    return redirect(url_for('directory'))

@app.route('/get_rate/<client_name>')
def get_rate(client_name):
    conn = get_db()
    client = conn.execute("SELECT default_rate FROM clients WHERE name = ?", (client_name,)).fetchone()
    conn.close()
    return jsonify({"rate": client['default_rate'] if client else 0.0})

@app.route('/billing', methods=['GET', 'POST'])
def billing():
    conn = get_db()
    clients = conn.execute("SELECT * FROM clients ORDER BY name ASC").fetchall()
    report, summary = [], {'total_bill': 0, 'client_name': "", 'month': ""}
    invoice_date_to_show = ""
    
    if request.method == 'POST':
        client_name = request.form.get('client')
        month = request.form.get('month')
        rate = float(request.form.get('rate', 0))
        min_chg = float(request.form.get('min_charge', 0))
        invoice_date_to_show = request.form.get('invoice_date')
        
        client_info = conn.execute("SELECT * FROM clients WHERE name = ?", (client_name,)).fetchone()
        rows = conn.execute("SELECT * FROM parcels WHERE receiver = ? AND date LIKE ? ORDER BY date ASC", (client_name, f"{month}%")).fetchall()
        for row in rows:
            p = dict(row)
            p['cost'] = max(p['weight'] * rate, min_chg)
            p['is_min'] = (p['cost'] == min_chg)
            report.append(p)
        total = sum(p['cost'] for p in report)
        
        # Save invoice to database for dashboard tracking
        conn.execute("INSERT INTO invoices (client_name, month, amount, status) VALUES (?,?,?,?)",
                     (client_name, month, total, 'Pending'))
        conn.commit()
        
        summary.update({'client_name': client_name, 'client_gst': client_info['gstin'], 'client_addr': client_info['address'], 'month': month, 'total_bill': total})
    
    invoices = conn.execute("SELECT * FROM invoices ORDER BY date_gen DESC LIMIT 10").fetchall()
    conn.close()
    return render_template('billing.html', clients=clients, report=report, summary=summary, invoice_date=invoice_date_to_show, invoices=invoices)

if __name__ == '__main__':
    init_db()
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=5000), daemon=True).start()
    webview.create_window('RAMDEV SUPER SERVICE', 'http://127.0.0.1:5000', width=1300, height=850)
    webview.start()
