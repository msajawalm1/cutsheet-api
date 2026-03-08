"""
Fabric Cut Sheet — Flask API
POST /generate-pdf  →  returns JSON with base64-encoded PDF (Bubble-compatible)
GET  /health        →  health check
"""

import io
import base64
import traceback
from flask import Flask, request, jsonify
from flask_cors import CORS
from pdf_engine import build_pdf_from_data

app = Flask(__name__)
CORS(app)


@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "service": "Fabric Cut Sheet API"})


@app.route('/generate-pdf', methods=['POST'])
def generate_pdf():
    if not request.is_json:
        return jsonify({"success": False, "error": "Content-Type must be application/json"}), 400

    data = request.get_json()

    if not data.get('order'):
        return jsonify({"success": False, "error": "Missing 'order' field"}), 400
    if not data.get('lineItems'):
        return jsonify({"success": False, "error": "Missing 'lineItems' field"}), 400

    try:
        pdf_buffer = io.BytesIO()
        build_pdf_from_data(
            order       = data['order'],
            line_items  = data['lineItems'],
            accessories = data.get('accessories', []),
            output      = pdf_buffer
        )
        pdf_buffer.seek(0)
        pdf_base64 = base64.b64encode(pdf_buffer.read()).decode('utf-8')
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

    order_name = data['order'].get('orderName', 'Cut_Sheet')
    filename   = f"Fabric_Cut_Sheet_{order_name.replace(' ', '_')}.pdf"

    return jsonify({
        "success":    True,
        "filename":   filename,
        "pdf_base64": pdf_base64,
        "mime_type":  "application/pdf"
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
