from datetime import datetime, date
from flask import Flask, request, jsonify
import requests
import json

app = Flask(__name__)

# URL RAW của Gist chứa dữ liệu máy
# Ví dụ: https://gist.githubusercontent.com/USERNAME/ID/raw/machines.json
GIST_RAW_URL = "https://gist.github.com/hgkhuyen255/8a3b40053089341ad248e9f948e12237"   # TODO: sửa thành URL thật

def load_machines_from_gist():
    """
    Đọc file JSON từ Gist:
    {
      "MA_MAY_1": { "status": "active", "expires_at": "2025-12-31", "note": "Khách A" },
      "MA_MAY_2": { ... }
    }
    """
    try:
        r = requests.get(GIST_RAW_URL, timeout=10)
        r.raise_for_status()
        data = r.text.strip()
        if not data:
            return {}
        return json.loads(data)
    except Exception as e:
        print(f"[GIST] Lỗi đọc Gist: {e}")
        return {}

def calc_remaining_days(expiry_str: str) -> int:
    # expiry_str: "YYYY-MM-DD"
    expiry_date = datetime.strptime(expiry_str, "%Y-%m-%d").date()
    today = date.today()
    return (expiry_date - today).days

@app.route("/check_machine", methods=["POST"])
def check_machine():
    data = request.get_json(silent=True) or {}
    machine_id = data.get("machine_id", "").strip().upper()

    if not machine_id:
        return jsonify({"ok": False, "message": "Thiếu machine_id", "remaining_days": 0}), 400

    machines = load_machines_from_gist()
    lic = machines.get(machine_id)

    if not lic:
        return jsonify({"ok": False, "message": "Máy này chưa được cấp phép", "remaining_days": 0}), 200

    status = lic.get("status", "active")
    if status != "active":
        return jsonify({
            "ok": False,
            "message": f"License không ở trạng thái active ({status})",
            "remaining_days": 0
        }), 200

    expires_at = lic.get("expires_at")
    if not expires_at:
        return jsonify({"ok": False, "message": "Thiếu expires_at", "remaining_days": 0}), 200

    remaining = calc_remaining_days(expires_at)
    if remaining < 0:
        return jsonify({"ok": False, "message": "License đã hết hạn", "remaining_days": 0}), 200

    return jsonify({
        "ok": True,
        "message": "OK",
        "remaining_days": remaining
    }), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
