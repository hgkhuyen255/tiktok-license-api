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

@app.route("/activate", methods=["POST"])
def activate():
    data = request.get_json(silent=True) or {}
    license_key = data.get("license_key", "").strip()
    machine_id = data.get("machine_id", "").strip()

    if not license_key or not machine_id:
        return jsonify({"ok": False, "message": "Thiếu license_key hoặc machine_id"}), 400

    lic_ref = db.collection("licenses").document(license_key)
    lic_doc = lic_ref.get()
    if not lic_doc.exists:
        return jsonify({"ok": False, "message": "License không tồn tại"}), 404

    lic = lic_doc.to_dict()

    status = lic.get("status", "active")
    if status != "active":
        return jsonify({"ok": False, "message": f"License không ở trạng thái active ({status})"}), 403

    expires_at = lic.get("expires_at")  # "YYYY-MM-DD"
    if not expires_at:
        return jsonify({"ok": False, "message": "License thiếu ngày hết hạn"}), 500

    remaining_days = calc_remaining_days(expires_at)
    if remaining_days < 0:
        lic_ref.update({"status": "expired"})
        return jsonify({"ok": False, "message": "License đã hết hạn"}), 403

    max_devices = int(lic.get("max_devices", 1))
    activated_devices = lic.get("activated_devices", [])

    # Đã có máy này?
    for dev in activated_devices:
        if dev.get("machine_id") == machine_id:
            dev["last_check"] = datetime.utcnow().isoformat() + "Z"
            lic_ref.update({"activated_devices": activated_devices})
            return jsonify({
                "ok": True,
                "message": "Đã kích hoạt trước đó",
                "remaining_days": remaining_days
            }), 200

    # Máy mới
    if len(activated_devices) < max_devices:
        activated_devices.append({
            "machine_id": machine_id,
            "activated_at": datetime.utcnow().isoformat() + "Z",
            "last_check": datetime.utcnow().isoformat() + "Z",
        })
    else:
        # Cho phép đổi máy: kick máy cũ nhất
        activated_devices.sort(key=lambda d: d.get("last_check", ""))
        activated_devices.pop(0)
        activated_devices.append({
            "machine_id": machine_id,
            "activated_at": datetime.utcnow().isoformat() + "Z",
            "last_check": datetime.utcnow().isoformat() + "Z",
        })

    lic_ref.update({"activated_devices": activated_devices})

    return jsonify({
        "ok": True,
        "message": "Kích hoạt thành công",
        "remaining_days": remaining_days
    }), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
