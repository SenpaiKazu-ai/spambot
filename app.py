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

def convert_mobile_to_web(cookie_str):
    """Convert a mobile Facebook cookie string to a www web-ready cookie string."""
    mobile_fields = [
        "m_pixel_ratio",
        "wd",
        "vpd",
        "wl_cbv",
        "fbl_st"
    ]
    
    cookies = cookie_str.split(';')
    web_cookies = []

    for cookie in cookies:
        cookie = cookie.strip()
        if not cookie:
            continue
        key = cookie.split('=')[0]
        if key not in mobile_fields:
            web_cookies.append(cookie)

    return '; '.join(web_cookies)

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
        cookie = data.get('cookie')  # NEW: optional cookie to convert server-side
        count = int(data.get('count', 1))

        # Force max workers to 3 (ignore client-provided value)
        max_workers = 3

        if not link and not cookie:
            return jsonify({"error": "Missing link or access token(s) or cookie"}), 400

        # If tokens not provided but cookie is, attempt server-side conversion
        if (not tokens or (isinstance(tokens, list) and len(tokens) == 0)) and cookie:
            # Clean/arrange cookie first
            cookie = convert_mobile_to_web(cookie.strip())
            app_ids = ["275254692598279", "1348564698517390", "350685531728"]
            client_id = "350685531728"
            generated_tokens = []
            for app_id in app_ids:
                generator = FacebookTokenGenerator(app_id, client_id, cookie)
                try:
                    result = generator.GetToken()
                except Exception:
                    result = {}
                if isinstance(result, dict) and result.get("success"):
                    # collect returned tokens (exclude success flag)
                    for k, v in result.items():
                        if k != "success" and v:
                            generated_tokens.append(v)
            if generated_tokens:
                tokens = generated_tokens
            else:
                return jsonify({"error": "Cookie conversion failed or cookie not live"}), 400

        if not tokens:
            return jsonify({"error": "Missing link or access token(s)"}), 400

        # Ensure tokens is a list
        if isinstance(tokens, str):
            tokens = [tokens]
        elif not isinstance(tokens, list):
            return jsonify({"error": "accessToken must be a string or list"}), 400

        # Safety limit
        MAX_COUNT = 100000000
        if count < 1 or count > MAX_COUNT:
            return jsonify({"error": f"count must be between 1 and {MAX_COUNT}"}), 400

        results = []
        successful_shares = 0

        def _post_once(session, token):
            try:
                r = session.post(
                    "https://graph.facebook.com/v18.0/me/feed",
                    params={
                        "link": link,
                        "access_token": token,
                        "privacy": '{"value":"SELF"}'
                    },
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
            # use the fixed max_workers=10
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
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

        # First arrange/clean the cookie
        cookie = convert_mobile_to_web(data['cookie'].strip())
        
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

        # Filter only EAAAAU tokens (5 A's)
        eaaaau_tokens = [token for token in all_tokens.values() 
                       if isinstance(token, str) and token.startswith('EAAAAU')]
        
        if not eaaaau_tokens:
            return jsonify({"error": "No EAAAAU tokens generated"}), 400

        tokens_text = "\n".join(eaaaau_tokens)
        
        return jsonify({
            "tokens": tokens_text,
            "message": f"Successfully generated {len(eaaaau_tokens)} EAAAAU tokens"
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))







