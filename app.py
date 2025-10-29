from flask import Flask, request, jsonify, render_template
import requests
import concurrent.futures
from requests.exceptions import RequestException
import sys
import os

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Now import FacebookTokenGenerator from local convert.py
from convert import FacebookTokenGenerator

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/share', methods=['POST'])
def share_post():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON body"}), 400

        link = data.get('link')
        tokens = data.get('accessToken')  # can be string or list
        count = int(data.get('count', 1))
        max_workers = int(data.get('maxWorkers', min(20, count)))

        if not link or not tokens:
            return jsonify({"error": "Missing link or access token(s)"}), 400

        # Ensure tokens is a list
        if isinstance(tokens, str):
            tokens = [tokens]
        elif not isinstance(tokens, list):
            return jsonify({"error": "accessToken must be a string or list"}), 400

        # Safety limit
        MAX_COUNT = 100000
        if count < 1 or count > MAX_COUNT:
            return jsonify({"error": f"count must be between 1 and {MAX_COUNT}"}), 400

        results = []
        successful_shares = 0

        def _post_once(session, token):
            try:
                r = session.post(
                    "https://graph.facebook.com/v18.0/me/feed",
                    params={"link": link, "access_token": token},
                    timeout=10
                )
                try:
                    json_response = r.json()
                    # Check if share was successful by looking for post ID
                    if 'id' in json_response:
                        nonlocal successful_shares
                        successful_shares += 1
                    return json_response
                except ValueError:
                    return {"status_code": r.status_code, "text": r.text}
            except RequestException as e:
                return {"error": str(e)}

        with requests.Session() as session:
            with concurrent.futures.ThreadPoolExecutor(max_workers=max(3, max_workers)) as ex:
                futures = []
                for token in tokens:
                    # submit 'count' requests per token
                    for _ in range(count):
                        futures.append(ex.submit(_post_once, session, token))
                
                for fut in concurrent.futures.as_completed(futures):
                    try:
                        results.append(fut.result())
                    except Exception as e:
                        results.append({"error": str(e)})

        total_attempts = len(results)
        return jsonify({
            "results": results,
            "summary": {
                "total_attempts": total_attempts,
                "successful_shares": successful_shares,
                "failed_shares": total_attempts - successful_shares
            }
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ADDED: serve the converter page
@app.route('/converter')
def converter_page():
    return render_template('converter.html')


# ADDED: cookie -> token conversion endpoint
@app.route('/convert-cookie', methods=['POST'])
def convert_cookie_endpoint():
    """Convert Facebook cookie to access token."""
    try:
        data = request.get_json()
        if not data or not data.get('cookie'):
            return jsonify({"error": "Missing cookie"}), 400

        cookie = data['cookie'].strip()
        
        # Use the converter from convert.py
        app_ids = ["275254692598279", "1348564698517390", "350685531728"]
        client_id = "350685531728"
        all_tokens = {}

        for app_id in app_ids:
            generator = FacebookTokenGenerator(app_id, client_id, cookie)
            result = generator.GetToken()
            if isinstance(result, dict) and result.get("success"):
                all_tokens.update(result)

        if not all_tokens:
            return jsonify({"error": "Could not generate any tokens"}), 400

        # Format tokens as newline-separated string
        tokens_text = "\n".join(token for key, token in all_tokens.items() if key != "success")
        
        return jsonify({
            "tokens": tokens_text,
            "message": f"Successfully generated {len(all_tokens)-1} tokens"
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))






