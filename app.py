from flask import Flask, request, jsonify
import requests
import hmac
import hashlib
import base64
import os

app = Flask(__name__)

SECURED_STITCH_BASE_URL = 'https://securedstitch-bfcuddejg4d8beaj.canadacentral-01.azurewebsites.net'
SECURED_STITCH_MEMBER_KEY = '30F5C69F-45F2-4650-99CB-0EF53DDD13F6'
SHOPIFY_WEBHOOK_SECRET = os.getenv('SHOPIFY_WEBHOOK_SECRET')

# === HMAC VERIFY ===
def verify_shopify_webhook(data, hmac_header):
    digest = hmac.new(
        SHOPIFY_WEBHOOK_SECRET.encode('utf-8'),
        data,
        hashlib.sha256
    ).digest()
    computed_hmac = base64.b64encode(digest).decode()
    return hmac.compare_digest(computed_hmac, hmac_header)

# === /get-quote (robust) ===
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

    print(f"\n[LOG] Calling Secured Stitch /quote with payload:\n{payload}")

    try:
        response = requests.post(
            f"{SECURED_STITCH_BASE_URL}/quote",
            json=payload,
            headers={"Content-Type": "application/json"}
        )

        print(f"[LOG] Secured Stitch Quote Response: {response.status_code} | {response.text}")

        # If Secured Stitch returns error, bubble it up clearly
        if not response.ok:
            return jsonify({
                "error": f"Secured Stitch responded with {response.status_code}",
                "body": response.text
            }), response.status_code

        return jsonify(response.json()), 200

    except Exception as e:
        print(f"[ERROR] Exception in /get-quote: {str(e)}")
        return jsonify({"error": str(e)}), 500

# === /webhook/order-paid ===
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
            for prop in item.get('properties', []):
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

        print(f"[LOG] Sending to Secured Stitch /sale: {payload}")

        try:
            response = requests.post(
                f"{SECURED_STITCH_BASE_URL}/sale",
                json=payload
            )
            print(f"[LOG] Secured Stitch Sale Response: {response.status_code} | {response.text}")
            return jsonify({"status": "success"}), 200
        except Exception as e:
            print(f"[ERROR] Exception in /webhook/order-paid: {str(e)}")
            return jsonify({"status": "error"}), 500
    else:
        print(f"[LOG] No Care+ or missing quoteId for Order: {order_id}")
        return jsonify({"status": "ignored"}), 200

# === /webhook/order-cancelled ===
@app.route('/webhook/order-cancelled', methods=['POST'])
def order_cancelled():
    hmac_header = request.headers.get('X-Shopify-Hmac-Sha256')
    data = request.data

    if SHOPIFY_WEBHOOK_SECRET and not verify_shopify_webhook(data, hmac_header):
        return jsonify({"status": "unauthorized"}), 401

    order = request.json
    order_id = order.get('id')

    print(f"[LOG] Cancelling Secured Stitch Sale for Order: {order_id}")

    try:
        response = requests.delete(f"{SECURED_STITCH_BASE_URL}/sale/{order_id}")
        print(f"[LOG] Secured Stitch Cancel Response: {response.status_code} | {response.text}")
        return jsonify({"status": "success"}), 200
    except Exception as e:
        print(f"[ERROR] Exception in /webhook/order-cancelled: {str(e)}")
        return jsonify({"status": "error"}), 500

# === Run ===
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
