import os

import google
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
import pickle
from google.auth.transport.requests import Request
from PIL import Image, ImageDraw, ImageFont

from dotenv import load_dotenv
from googleapiclient.http import MediaFileUpload
import time

load_dotenv()

scopes = [
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.force-ssl"
]
thumbnail_dir = "thumbnail.png"

def create_youtube_client():
    # Disable OAuthlib's HTTPS verification when running locally.
    # *DO NOT* leave this option enabled in production.
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

    api_service_name = "youtube"
    api_version = "v3"
    client_secrets_file = "clients.json"
    token_file = 'youtube_token.pickle'
    credentials = None

    if os.path.exists(token_file):
        with open(token_file, 'rb') as token:
            credentials = pickle.load(token)

    # Get credentials and create an API client
    # Update : Improvements with support for refreshing token and saving token, to reuse it if always valid
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            try:
                credentials.refresh(Request())
            except google.auth.exceptions.RefreshError:
                credentials = create_credentials(client_secrets_file, token_file)
        else:
            credentials = create_credentials(client_secrets_file, token_file)

    return googleapiclient.discovery.build(
        api_service_name, api_version, credentials=credentials)

def create_credentials(client_secrets_file, token_file):
    flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
        client_secrets_file, scopes)
    credentials = flow.run_local_server(
        port=int(os.getenv("PORT", "10100")),
        open_browser=False
    )

    with open(token_file, 'wb') as token:
        pickle.dump(credentials, token)

    return credentials

def create_thumbnail(views_count=1000):
    width, height = 1280, 720

    text_color = (0, 0, 0)
    shadow_color = (153, 152, 145)
    shadow_offset = (8, 8)
    font_size = 100
    font_path = "OpenSans-Bold.ttf"
    unicode_font = ImageFont.truetype(font_path, font_size)
    text_to_draw = f"Cette vidéo\n a fait\n {views_count} vues"
    text_position = (50, height / 2 - ((font_size * 3) / 2))


    with Image.open("base_image.png") as thumbnail:
        draw = ImageDraw.Draw(thumbnail)

        draw.text(
            (text_position[0] + shadow_offset[0], text_position[1] + shadow_offset[1]),
            text_to_draw,
            fill=shadow_color,
            font=unicode_font,
            align="center"
        )
        draw.text(
            (text_position[0], text_position[1]),
            text_to_draw,
            fill=text_color,
            font=unicode_font,
            align="center"
          )


        thumbnail.save(thumbnail_dir)


def get_view_count(youtube):
    request = youtube.videos().list(
        part="snippet,statistics",
        id=os.getenv("VIDEO_ID")
    )
    response = request.execute()

    return (response['items'][0]['statistics']['viewCount'],
            response['items'][0]['snippet']['categoryId'],
            response['items'][0]['snippet']['description'])


def update_video_title(youtube, category_id, description, views_count=1000):
    title = f"Cette vidéo a fait {views_count} vues"
    request = youtube.videos().update(
        part="snippet",
        body={
            "id": os.getenv("VIDEO_ID"),
            "snippet": {
                "title": title,
                "categoryId": category_id,
                "description": description,
            },
        }
    )

    response = request.execute()
    return response.get('channelId') is not None

def update_video_thumbnail(youtube):
    request = youtube.thumbnails().set(
        videoId=os.getenv("VIDEO_ID"),
        media_body=MediaFileUpload(thumbnail_dir,)
    )
    response = request.execute()

    return response.get('items') is not None

if __name__ == '__main__':
    old_view_count = -1
    while True:
        youtube = create_youtube_client()
        view_count, category_id, description = get_view_count(youtube)
        print(f"View count: {view_count}")
        print(f"Category ID: {category_id}")

        if view_count != old_view_count:
            print("Updating video...")
            if bool(int(os.getenv("UPDATE_TITLE", 1))):
                update_video_title(youtube, category_id, description, view_count)
            if bool(int(os.getenv("UPDATE_THUMBNAIL", 1))):
                create_thumbnail(view_count)
                update_video_thumbnail(youtube)
            old_view_count = view_count
            print("Update complete.")
        else:
            print("No update.")
        print(f"Waiting {os.getenv('COOLDOWN_SECONDS')} seconds...")
        time.sleep(int(os.getenv("COOLDOWN_SECONDS")))

