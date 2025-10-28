from flask import Flask, request, jsonify, render_template
import requests
import concurrent.futures
from requests.exceptions import RequestException

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
        access_token = data.get('accessToken')
        count = int(data.get('count', 1))
        max_workers = int(data.get('maxWorkers', min(20, count)))

        if not link or not access_token:
            return jsonify({"error": "Missing link or access token"}), 400

        # Safety limit to avoid accidental huge bursts
        MAX_COUNT = 200
        if count < 1 or count > MAX_COUNT:
            return jsonify({"error": f"count must be between 1 and {MAX_COUNT}"}), 400

        results = []
        def _post_once(session):
            try:
                r = session.post(
                    "https://graph.facebook.com/v18.0/me/feed",
                    params={
                        "link": link,
                        "access_token": access_token
                    },
                    timeout=10
                )
                # try to parse json, fallback to text if not json
                try:
                    return r.json()
                except ValueError:
                    return {"status_code": r.status_code, "text": r.text}
            except RequestException as e:
                return {"error": str(e)}

        # Use a session to reuse connections
        with requests.Session() as session:
            with concurrent.futures.ThreadPoolExecutor(max_workers=max(3, max_workers)) as ex:
                futures = [ex.submit(_post_once, session) for _ in range(count)]
                for fut in concurrent.futures.as_completed(futures):
                    try:
                        results.append(fut.result())
                    except Exception as e:
                        results.append({"error": str(e)})

        return jsonify({"results": results}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)


