from flask import Flask, jsonify, request, send_from_directory
import json
import os

app = Flask(__name__)
STAGING_FILE = "refined_paths_5090.json"
FINAL_FILE = "shiny-paths.json"

@app.route('/')
def index():
    return send_from_directory('.', 'staging.html')

# NEW ROUTE: This fixes the 404 for your Map
@app.route('/map')
def map_view():
    return send_from_directory('.', 'Map_Screener.html')

@app.route('/api/nodes', methods=['GET'])
def get_nodes():
    if not os.path.exists(STAGING_FILE): return jsonify([])
    with open(STAGING_FILE, 'r', encoding='utf-8') as f:
        try: return jsonify(json.load(f))
        except: return jsonify([])

@app.route('/api/approve', methods=['POST'])
def approve_node():
    node_id = request.json.get('id')
    with open(STAGING_FILE, 'r', encoding='utf-8') as f:
        nodes = json.load(f)
    approved_node = next((n for n in nodes if n['id'] == node_id), None)
    if approved_node:
        if not os.path.exists(FINAL_FILE):
            with open(FINAL_FILE, 'w', encoding='utf-8') as ff: json.dump([], ff)
        with open(FINAL_FILE, 'r+', encoding='utf-8') as ff:
            final_data = json.load(ff)
            approved_node['status'] = 'Parked'
            final_data.append(approved_node)
            ff.seek(0); json.dump(final_data, ff, indent=2); ff.truncate()
        remaining = [n for n in nodes if n['id'] != node_id]
        with open(STAGING_FILE, 'w', encoding='utf-8') as f:
            json.dump(remaining, f, indent=2)
    return jsonify({"status": "success"})

# NEW ROUTE: This allows the 'Import' button to work
@app.route('/api/final-paths', methods=['GET'])
def get_final_paths():
    if not os.path.exists(FINAL_FILE): return jsonify([])
    with open(FINAL_FILE, 'r', encoding='utf-8') as f:
        try: return jsonify(json.load(f))
        except: return jsonify([])

if __name__ == '__main__':
    # Binding to 0.0.0.0 ensures it's accessible across the local network
    app.run(host='0.0.0.0', port=8080, debug=False)