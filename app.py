from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os

app = Flask(__name__)
CORS(app, origins=["https://wearnou.com"])  # ✅ replace with your real domain or "*" for dev

SECURED_STITCH_BASE_URL = 'https://securedstitch-bfcuddejg4d8beaj.canadacentral-01.azurewebsites.net'
SECURED_STITCH_MEMBER_KEY = '30F5C69F-45F2-4650-99CB-0EF53DDD13F6'


@app.route("/", methods=["GET", "HEAD"])
def health():
    return "OK", 200

# === /get-quote ===
@app.route("/get-quote", methods=["POST"])
def get_quote():
    data = request.json

    # ✅ 1) Map lowercase input to PascalCase for Secured Stitch:
    payload = {
        "Member": SECURED_STITCH_MEMBER_KEY,
        "CurrencyCode": data.get("currencycode", "INR"),
        "Brand": data.get("brand", "GenericBrand"),
        "Price": data.get("price", 1000),
        "Name": data.get("name", "Generic Product"),
        "Size": data.get("size", "6"),
        "Product": data.get("product", "SNK")
    }

    print(f"[LOG] /get-quote → Secured Stitch payload: {payload}")

    try:
        response = requests.post(
            f"{SECURED_STITCH_BASE_URL}/quote",
            json=payload,
            headers={"Content-Type": "application/json"}
        )

        print(f"[LOG] Secured Stitch Quote Response: {response.status_code} | {response.text}")

        if not response.ok:
            # Bubble up Secured Stitch's error for debugging:
            return jsonify({
                "error": f"Secured Stitch returned {response.status_code}",
                "body": response.text
            }), response.status_code

        raw = response.json()

        # ✅ 2) Convert Secured Stitch response back to lowercase for your JS:
        result = {
            "quoteid": raw.get("quoteId"),
            "productprice": raw.get("ProductPrice"),
            "html": raw.get("html", "")
        }

        print(f"[LOG] Returning to JS: {result}")
        return jsonify(result), 200

    except Exception as e:
        print(f"[ERROR] /get-quote Exception: {str(e)}")
        return jsonify({"error": str(e)}), 500


# === /write-sale ===
@app.route("/write-sale", methods=["POST"])
def write_sale():
    data = request.json
    payload = {
        "member": SECURED_STITCH_MEMBER_KEY,
        "customerName": data.get("customername"),
        "sold": data.get("sold", False),
        "quoteId": data.get("quoteid"),
        "uniqueId": data.get("uniqueid")
    }
    print(f"[LOG] /write-sale payload: {payload}")
    try:
        response = requests.post(
            f"{SECURED_STITCH_BASE_URL}/sale",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        print(f"[LOG] Secured Stitch Sale: {response.status_code} | {response.text}")
        return response.text, response.status_code
    except Exception as e:
        print(f"[ERROR] /write-sale: {str(e)}")
        return jsonify({"error": str(e)}), 500

# === /cancel-sale/<sale_id> ===
@app.route("/cancel-sale/<sale_id>", methods=["DELETE"])
def cancel_sale(sale_id):
    print(f"[LOG] /cancel-sale for {sale_id}")
    try:
        response = requests.delete(f"{SECURED_STITCH_BASE_URL}/sale/{sale_id}")
        print(f"[LOG] Secured Stitch Cancel: {response.status_code} | {response.text}")
        return response.text, response.status_code
    except Exception as e:
        print(f"[ERROR] /cancel-sale: {str(e)}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
