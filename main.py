from datetime import datetime, date
from flask import Flask, request, jsonify
from google.cloud import firestore

app = Flask(__name__)
db = firestore.Client()

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
        return jsonify({"ok": False, "message": "Thiếu machine_id"}), 400

    doc_ref = db.collection("machines").document(machine_id)
    doc = doc_ref.get()
    if not doc.exists:
        return jsonify({"ok": False, "message": "Máy này chưa được cấp phép", "remaining_days": 0}), 200

    lic = doc.to_dict()
    status = lic.get("status", "active")
    if status != "active":
        return jsonify({"ok": False, "message": f"License không ở trạng thái active ({status})", "remaining_days": 0}), 200

    expires_at = lic.get("expires_at")  # "YYYY-MM-DD"
    if not expires_at:
        return jsonify({"ok": False, "message": "Thiếu expires_at", "remaining_days": 0}), 200

    remaining = calc_remaining_days(expires_at)
    if remaining < 0:
        # có thể update status thành expired
        doc_ref.update({"status": "expired"})
        return jsonify({"ok": False, "message": "License đã hết hạn", "remaining_days": 0}), 200

    return jsonify({
        "ok": True,
        "message": "OK",
        "remaining_days": remaining
    }), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
