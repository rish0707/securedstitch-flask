from flask import Flask, request, jsonify
import requests
import hmac
import hashlib
import base64
import os

app = Flask(__name__)

SECURED_STITCH_BASE_URL = 'https://securedstitch-bfcuddejg4d8beaj.canadacentral-01.azurewebsites.net'
SECURED_STITCH_MEMBER_KEY = '30F5C69F-45F2-4650-99CB-0EF53DDD13F6'
SHOPIFY_WEBHOOK_SECRET = os.getenv('SHOPIFY_WEBHOOK_SECRET')  # Recommended: set in Render

# === 1️⃣ Optional: verify Shopify HMAC ===
def verify_shopify_webhook(data, hmac_header):
    digest = hmac.new(
        SHOPIFY_WEBHOOK_SECRET.encode('utf-8'),
        data,
        hashlib.sha256
    ).digest()
    computed_hmac = base64.b64encode(digest).decode()
    return hmac.compare_digest(computed_hmac, hmac_header)

# === 2️⃣ NEW: Backend proxy for front-end to securely get a quote ===
@app.route('/get-quote', methods=['POST'])
def get_quote():
    data = request.json

    payload = {
        "Member": SECURED_STITCH_MEMBER_KEY,
        "CurrencyCode": data.get("CurrencyCode", "INR"),
        "Brand": data.get("Brand", "GenericBrand"),
        "Price": data.get("Price", 1000),
        "Name": data.get("Name", "Generic Product"),
        "Size": data.get("Size", "6"),
        "Product": data.get("Product", "SNK")
    }

    print(f"Calling Secured Stitch /quote with payload: {payload}")

    try:
        response = requests.post(
            f"{SECURED_STITCH_BASE_URL}/quote",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        print(f"Secured Stitch Quote Response: {response.text}")
        return jsonify(response.json()), response.status_code

    except Exception as e:
        print(f"Error in /get-quote: {str(e)}")
        return jsonify({"error": str(e)}), 500

# === 3️⃣ Order Paid Webhook ===
@app.route('/webhook/order-paid', methods=['POST'])
def order_paid():
    hmac_header = request.headers.get('X-Shopify-Hmac-Sha256')
    data = request.data

    if SHOPIFY_WEBHOOK_SECRET and not verify_shopify_webhook(data, hmac_header):
        return jsonify({"status": "unauthorized"}), 401

    order = request.json
    order_id = order.get('id')
    customer = order.get('customer', {})
    customer_name = f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip()
    address = order.get('shipping_address', {}).get('address1', '')

    quote_id = None

    for item in order.get('line_items', []):
        if 'Care+' in item.get('title', ''):
            properties = item.get('properties', [])
            for prop in properties:
                if prop.get('name') == 'quoteId' or prop.get('key') == 'quoteId':
                    quote_id = prop.get('value')
            break

    if quote_id:
        payload = {
            "QuoteId": quote_id,
            "UniqueId": str(order_id),
            "CustomerName": customer_name,
            "Sold": True,
            "Address": address,
            "Member": SECURED_STITCH_MEMBER_KEY
        }
        try:
            response = requests.post(f"{SECURED_STITCH_BASE_URL}/sale", json=payload)
            print(f"Secured Stitch Sale Response: {response.text}")
            return jsonify({"status": "success"}), 200
        except Exception as e:
            print(f"Error in /webhook/order-paid: {str(e)}")
            return jsonify({"status": "error"}), 500
    else:
        print(f"No Care+ or quoteId missing for Order: {order_id}")
        return jsonify({"status": "ignored"}), 200

# === 4️⃣ Order Cancelled Webhook ===
@app.route('/webhook/order-cancelled', methods=['POST'])
def order_cancelled():
    hmac_header = request.headers.get('X-Shopify-Hmac-Sha256')
    data = request.data

    if SHOPIFY_WEBHOOK_SECRET and not verify_shopify_webhook(data, hmac_header):
        return jsonify({"status": "unauthorized"}), 401

    order = request.json
    order_id = order.get('id')

    try:
        response = requests.delete(f"{SECURED_STITCH_BASE_URL}/sale/{order_id}")
        print(f"Secured Stitch Cancel Response: {response.text}")
        return jsonify({"status": "success"}), 200
    except Exception as e:
        print(f"Error in /webhook/order-cancelled: {str(e)}")
        return jsonify({"status": "error"}), 500

# === 5️⃣ Flask entry point ===
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
