from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

# Store latest locations
latest = {
    "gps": None,      # {"lat": ..., "lng": ...}
    "tower": None     # {"lat": ..., "lng": ...}
}

VERIFY_TOKEN = "GPS" ("VERIFY_TOKEN", "mytoken123")
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN", "")
UNWIREDLABS_TOKEN = os.environ.get("UNWIREDLABS_TOKEN", "")


# ─── SIM7600 sends location here ───────────────────────────────────────────────

@app.route("/update", methods=["POST"])
def update_location():
    data = request.json

    # GPS location
    if "gps_lat" in data and "gps_lng" in data:
        latest["gps"] = {"lat": data["gps_lat"], "lng": data["gps_lng"]}

    # Cell Tower → convert to coordinates via UnwiredLabs
    if "mcc" in data and "mnc" in data and "lac" in data and "cid" in data:
        tower_location = get_tower_location(
            data["mcc"], data["mnc"], data["lac"], data["cid"]
        )
        if tower_location:
            latest["tower"] = tower_location

    return jsonify({"status": "ok"})


def get_tower_location(mcc, mnc, lac, cid):
    try:
        res = requests.post("https://us1.unwiredlabs.com/v2/process.php", json={
            "token": UNWIREDLABS_TOKEN,
            "radio": "gsm",
            "mcc": mcc,
            "mnc": mnc,
            "cells": [{"lac": lac, "cid": cid}]
        })
        data = res.json()
        if data.get("status") == "ok":
            return {"lat": data["lat"], "lng": data["lon"]}
    except:
        pass
    return None


# ─── Facebook Webhook ───────────────────────────────────────────────────────────

@app.route("/webhook", methods=["GET"])
def verify():
    if request.args.get("hub.verify_token") == VERIFY_TOKEN:
        return request.args.get("hub.challenge")
    return "Invalid token", 403


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    for entry in data.get("entry", []):
        for event in entry.get("messaging", []):
            sender_id = event["sender"]["id"]

            if "message" in event:
                text = event["message"].get("text", "").lower()
                if "location" in text or "gps" in text or "kahan" in text:
                    send_location_buttons(sender_id)

            elif "postback" in event:
                payload = event["postback"]["payload"]
                if payload == "GET_GPS":
                    send_map_link(sender_id, "gps")
                elif payload == "GET_TOWER":
                    send_map_link(sender_id, "tower")

    return "OK", 200


def send_location_buttons(sender_id):
    msg = {
        "recipient": {"id": sender_id},
        "message": {
            "attachment": {
                "type": "template",
                "payload": {
                    "template_type": "button",
                    "text": "Kaunsi location chahiye?",
                    "buttons": [
                        {
                            "type": "postback",
                            "title": "📡 GPS (Exact)",
                            "payload": "GET_GPS"
                        },
                        {
                            "type": "postback",
                            "title": "📶 Tower (Approximate)",
                            "payload": "GET_TOWER"
                        }
                    ]
                }
            }
        }
    }
    send_message(msg)


def send_map_link(sender_id, loc_type):
    loc = latest.get(loc_type)
    if not loc:
        send_text(sender_id, "Abhi location available nahi hai.")
        return

    label = "GPS (Exact)" if loc_type == "gps" else "Tower (Approximate)"
    maps_link = f"https://maps.google.com/?q={loc['lat']},{loc['lng']}"
    send_text(sender_id, f"📍 {label} Location:\n{maps_link}")


def send_text(sender_id, text):
    msg = {
        "recipient": {"id": sender_id},
        "message": {"text": text}
    }
    send_message(msg)


def send_message(payload):
    requests.post(
        f"https://graph.facebook.com/v18.0/me/messages?access_token={PAGE_ACCESS_TOKEN}",
        json=payload
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
