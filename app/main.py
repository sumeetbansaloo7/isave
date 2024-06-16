from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import instaloader
import re
import base64
import requests
import os

app = FastAPI()

class PostUrl(BaseModel):
    url: str
    password: str  # New field for password in the request

def download_instagram_media(post_url: str,password):
    # Read Instagram username and password from environment variables
    insta_username = os.getenv('INSTAGRAM_USERNAME')
    insta_password = password

    if not insta_username or not insta_password:
        raise ValueError("Instagram credentials not provided as environment variables")

    # Initialize Instaloader with username and password
    L = instaloader.Instaloader(download_videos=True, download_video_thumbnails=False)
    
    L.login(insta_username, insta_password)

    match = re.search(r'/(p|reel)/([A-Za-z0-9_-]+)/', post_url)
    if not match:
        raise ValueError("Invalid Instagram post URL")

    shortcode = match.group(2)
    post = instaloader.Post.from_shortcode(L.context, shortcode)
    media = []

    if post.typename == 'GraphImage':
        image_url = post.url
        response = requests.get(image_url)
        img = base64.b64encode(response.content).decode('utf-8')
        media.append({"type": "image", "data": img, "url": image_url})
    elif post.typename == 'GraphSidecar':
        for node in post.get_sidecar_nodes():
            if node.is_video:
                video_url = node.video_url
                response = requests.get(video_url)
                vid = base64.b64encode(response.content).decode('utf-8')
                media.append({"type": "video", "data": vid, "url": video_url})
            else:
                media_url = node.display_url
                response = requests.get(media_url)
                img = base64.b64encode(response.content).decode('utf-8')
                media.append({"type": "image", "data": img, "url": media_url})
    elif post.typename == 'GraphVideo' or post.typename == 'Reel':
        video_url = post.video_url
        response = requests.get(video_url)
        vid = base64.b64encode(response.content).decode('utf-8')
        media.append({"type": "video", "data": vid, "url": video_url})
    else:
        raise ValueError("Unsupported post type")

    return media

@app.post("/download_media/")
async def download_media(post_data: PostUrl):
    try:
        media = download_instagram_media(post_data.url,post_data.password)
        return {"message": "Media downloaded successfully", "media": media}
    except instaloader.exceptions.InstaloaderException as e:
        raise HTTPException(status_code=400, detail=f"Instaloader error: {e}")
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=400, detail=f"Request error: {e}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Value error: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    with open("templates/index.html", "r", encoding="utf-8") as index_file:
        html_content = index_file.read()
    return html_content
