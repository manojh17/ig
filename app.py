from flask import Flask, request, jsonify
from instagrapi import Client
import os
import time
import threading
import requests
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Instagram Credentials
FIRST_IG_USERNAME = os.getenv("FIRST_IG_USERNAME")  # First IG account (receives DMs)
FIRST_IG_PASSWORD = os.getenv("FIRST_IG_PASSWORD")
SECOND_IG_USERNAME = os.getenv("SECOND_IG_USERNAME")  # Second IG account (uploads reels)
SECOND_IG_PASSWORD = os.getenv("SECOND_IG_PASSWORD")

# MongoDB Setup
MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["instagram_reels"]
collection = db["reels"]

# Initialize Flask app
app = Flask(__name__)

# Initialize Instagram Clients
cl1 = Client()
cl2 = Client()

# Login Function for IG Accounts
def login_ig():
    try:
        cl1.load_settings("session1.json")  
        cl1.login(FIRST_IG_USERNAME, FIRST_IG_PASSWORD)
        cl2.load_settings("session2.json")  
        cl2.login(SECOND_IG_USERNAME, SECOND_IG_PASSWORD)
        print("[✅] Both Instagram accounts logged in successfully!")
    except Exception as e:
        print(f"[⚠️] Login failed: {e}")
        cl1.login(FIRST_IG_USERNAME, FIRST_IG_PASSWORD)
        cl1.dump_settings("session1.json")
        cl2.login(SECOND_IG_USERNAME, SECOND_IG_PASSWORD)
        cl2.dump_settings("session2.json")

# Function to Fetch Reel Links from DMs
def fetch_reel_links():
    print("[📩] Checking DMs for reel links...")
    inbox = cl1.direct_threads()
    
    reel_links = []
    for thread in inbox:
        for msg in thread.messages:
            if "https://www.instagram.com/reel/" in msg.text:
                reel_links.append(msg.text)
    
    return reel_links

# Function to Download Reel
def download_reel(url):
    shortcode = url.split('/')[-2]
    try:
        post = cl1.media_info_from_url(url)
        video_url = post.video_url

        if not video_url:
            return None

        video_path = f"downloads/{shortcode}.mp4"
        os.makedirs("downloads", exist_ok=True)
        with open(video_path, "wb") as f:
            f.write(requests.get(video_url).content)

        print(f"[✅] Reel {shortcode} downloaded successfully!")
        return video_path, post.caption
    except Exception as e:
        print(f"[❌] Error downloading reel: {e}")
        return None, None

# Function to Upload Reel
def upload_reel(video_path, caption):
    try:
        hashtags = "#viral #reels #instagram"
        caption_with_tags = f"{caption} {hashtags}"
        
        cl2.video_upload(video_path, caption=caption_with_tags)
        print("[✅] Reel uploaded successfully!")
        return True
    except Exception as e:
        print(f"[❌] Error uploading reel: {e}")
        return False

# Function to Delete Reel after 5 Minutes
def schedule_deletion(video_path):
    time.sleep(300)  # 5 minutes
    if os.path.exists(video_path):
        os.remove(video_path)
        print(f"[🗑️] Deleted {video_path} to save storage.")

# API to Process Reels from DM and Upload
@app.route('/process_reels', methods=['GET'])
def process_reels():
    login_ig()
    
    reel_links = fetch_reel_links()
    if not reel_links:
        return jsonify({"message": "No reels found in DMs"}), 404
    
    for url in reel_links:
        video_path, caption = download_reel(url)
        if video_path:
            upload_success = upload_reel(video_path, caption)
            if upload_success:
                threading.Thread(target=schedule_deletion, args=(video_path,)).start()
    
    return jsonify({"message": "Processed reels successfully!"}), 200

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=False)
