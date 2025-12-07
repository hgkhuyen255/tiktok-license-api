from datetime import datetime, date
from flask import Flask, request, jsonify
import requests
import json
import os

app = Flask(__name__)

# --------- CẤU HÌNH GIST ----------
# Gist của bạn: https://gist.github.com/hgkhuyen255/8a3b40053089341ad248e9f948e12237
GIST_ID = "8a3b40053089341ad248e9f948e12237"
GIST_OWNER = "hgkhuyen255"
GIST_FILENAME = "machines.json"  # tên file trong Gist (bạn tự đặt cho khớp)

# URL RAW để đọc JSON
GIST_RAW_URL = f"https://gist.githubusercontent.com/{GIST_OWNER}/{GIST_ID}/raw/{GIST_FILENAME}"

# URL API để cập nhật Gist
GIST_API_URL = f"https://api.github.com/gists/{GIST_ID}"

# Token GitHub (PAT) chỉ dùng trên server, không để trong code client!
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")  # set ở Cloud Run env vars


def load_machines_from_gist() -> dict:
    """
    Đọc file JSON từ Gist:
    {
      "MA_MAY_1": { "status": "active", "expires_at": "2025-12-31", "note": "Khách A" },
      "MA_MAY_2": { "status": "pending", "expires_at": null, "note": "Yêu cầu kích hoạt" }
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


def save_machines_to_gist(machines: dict) -> bool:
    """
    Ghi lại toàn bộ dict machines lên Gist (overwrite file).
    Yêu cầu:
      - GITHUB_TOKEN phải có scope gist.
    """
    if not GITHUB_TOKEN:
        print("[GIST] Thiếu GITHUB_TOKEN, không thể update Gist.")
        return False

    content = json.dumps(machines, ensure_ascii=False, indent=2)
    payload = {
        "files": {
            GIST_FILENAME: {
                "content": content
            }
        }
    }
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {GITHUB_TOKEN}",
    }
    try:
        resp = requests.patch(GIST_API_URL, headers=headers, json=payload, timeout=15)
        resp.raise_for_status()
        print("[GIST] Đã cập nhật Gist thành công.")
        return True
    except Exception as e:
        print(f"[GIST] Lỗi cập nhật Gist: {e}")
        return False


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

    # ----- CASE 1: MÁY CHƯA TỪNG GHI VÀO GIST -----
    if not lic:
        # Tự động thêm dòng "pending" vào Gist
        machines[machine_id] = {
            "status": "pending",
            "expires_at": None,
            "note": f"Request from machine at {datetime.utcnow().isoformat()}Z"
        }
        save_machines_to_gist(machines)

        return jsonify({
            "ok": False,
            "message": "Máy chưa được active. Yêu cầu đã gửi lên admin.",
            "remaining_days": 0
        }), 200

    # ----- CASE 2: ĐÃ CÓ MÁY TRONG GIST -----
    status = (lic.get("status") or "pending").lower()

    if status == "pending":
        return jsonify({
            "ok": False,
            "message": "Máy đang ở trạng thái chờ kích hoạt. Liên hệ admin.",
            "remaining_days": 0
        }), 200

    if status != "active":
        # Ví dụ: blocked, banned ...
        return jsonify({
            "ok": False,
            "message": f"License không ở trạng thái active ({status})",
            "remaining_days": 0
        }), 200

    expires_at = lic.get("expires_at")
    if not expires_at:
        return jsonify({
            "ok": False,
            "message": "Máy đã được active nhưng chưa có expires_at. Liên hệ admin.",
            "remaining_days": 0
        }), 200

    remaining = calc_remaining_days(expires_at)
    if remaining < 0:
        return jsonify({
            "ok": False,
            "message": "License đã hết hạn, cần gia hạn.",
            "remaining_days": 0
        }), 200

    return jsonify({
        "ok": True,
        "message": "OK",
        "remaining_days": remaining
    }), 200


if __name__ == "__main__":
    # chạy local để test
    app.run(host="0.0.0.0", port=8080, debug=True)
