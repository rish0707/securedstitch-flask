from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

SECURED_STITCH_BASE_URL = 'https://securedstitch-bfcuddejg4d8beaj.canadacentral-01.azurewebsites.net'
SECURED_STITCH_MEMBER_KEY = 'YOUR_MEMBER_KEY'  # <-- Replace with your key

# === Order Paid ===
@app.route('/webhook/order-paid', methods=['POST'])
def order_paid():
    order = request.json
    order_id = order.get('id')
    customer = order.get('customer', {})
    customer_name = f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip()
    address = order.get('shipping_address', {}).get('address1', '')

    # Find if Care+ is in line items
    has_care_plus = False
    quote_id = None

    for item in order.get('line_items', []):
        if 'Care+' in item.get('title', ''):
            has_care_plus = True
            # Ideally store quoteId in line item properties
            properties = item.get('properties', [])
            for prop in properties:
                if prop.get('name') == 'quoteId':
                    quote_id = prop.get('value')
            break

    if has_care_plus and quote_id:
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
            print(f"Error: {str(e)}")
            return jsonify({"status": "error"}), 500
    else:
        print(f"No Care+ or quoteId missing for Order: {order_id}")
        return jsonify({"status": "ignored"}), 200

# === Order Cancelled ===
@app.route('/webhook/order-cancelled', methods=['POST'])
def order_cancelled():
    order = request.json
    order_id = order.get('id')

    try:
        response = requests.delete(f"{SECURED_STITCH_BASE_URL}/sale/{order_id}")
        print(f"Secured Stitch Cancel Response: {response.text}")
        return jsonify({"status": "success"}), 200
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({"status": "error"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
