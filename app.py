from flask import Flask, render_template, request, jsonify
import instaloader
import os
import requests
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["instagram_reels"]
collection = db["reels"]

INSTAGRAM_GRAPH_API_URL = "https://graph.facebook.com/v17.0/me/media"
ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN")

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/download", methods=["POST"])
def download_reel():
    data = request.get_json()
    url = data.get("url")
    if not url:
        return jsonify({"error": "No URL provided"}), 400
    
    try:
        L = instaloader.Instaloader()
        shortcode = url.split("/")[-2]
        post = instaloader.Post.from_shortcode(L.context, shortcode)

        if post.is_video:
            L.download_post(post, target=shortcode)
            video_path = f"{shortcode}/{shortcode}.mp4"
            collection.insert_one({"shortcode": shortcode, "file_path": video_path, "status": "downloaded"})
            return jsonify({"message": "Reel downloaded successfully"}), 200
        return jsonify({"error": "The provided URL is not a reel."}), 400
    except Exception as e:
        return jsonify({"error": f"Failed to download reel: {str(e)}"}), 500

@app.route("/upload", methods=["POST"])
def upload_reel():
    reel = collection.find_one({"status": "downloaded"})
    if not reel:
        return jsonify({"error": "No reels to upload"}), 404

    try:
        video_path = reel["file_path"]
        params = {"caption": "Uploaded via Flask", "access_token": ACCESS_TOKEN}
        files = {"video": open(video_path, "rb")}
        response = requests.post(INSTAGRAM_GRAPH_API_URL, files=files, params=params)

        if response.status_code == 200:
            collection.update_one({"_id": reel["_id"]}, {"$set": {"status": "uploaded"}})
            return jsonify({"message": "Reel uploaded successfully"}), 200
        return jsonify({"error": "Upload failed", "details": response.json()}), 500
    except Exception as e:
        return jsonify({"error": f"Upload error: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(debug=True)
