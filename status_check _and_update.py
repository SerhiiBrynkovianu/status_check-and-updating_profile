from quart import Quart, request, jsonify
from telethon import TelegramClient, functions, types
from telethon.tl.functions.photos import UploadProfilePhotoRequest
import asyncio
import uvicorn
import socks
from PIL import Image
import os
import json

app = Quart(__name__)

UPLOAD_FOLDER = "./session_files"
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

async def initialize_client(session_string, api_id,api_hash,proxy=None):
    client = TelegramClient(f"session_files/{session_string}", api_id, api_hash, proxy=proxy)
    await client.connect()
    if not await client.is_user_authorized():
        raise Exception("Authorization required for this account.")
    return client

def parse_proxy(proxy_string):
    """Parse proxy string of format: IP:Port:Username:Password"""
    proxy_parts = proxy_string.split(':')
    if len(proxy_parts) == 4:
        proxy_ip, proxy_port, proxy_user, proxy_pass = proxy_parts
        return (socks.SOCKS5, proxy_ip, int(proxy_port), True, proxy_user, proxy_pass)
    return None

@app.route('/account/check', methods=['POST'])
async def check_account():
    data = await request.form
    phone_number = data.get('phone_number')
    proxy = parse_proxy(data.get('proxy'))
    session_string = data.get("session_string")
    files = await request.files
    uploaded_session_file = files.get('session_file')  # 'file' should match the name attribute in the form data
    uploade_json_file = files.get("json_file")
    if uploaded_session_file:
        file_path = os.path.join(UPLOAD_FOLDER, uploaded_session_file.filename)
        await uploaded_session_file.save(file_path)

    uploaded_json_string = uploade_json_file.read() if uploade_json_file else None
    if uploaded_json_string:
        # Decode the binary string
        decoded_json = uploaded_json_string.decode('utf-8')
        
        # Parse JSON
        json_data = json.loads(decoded_json)
        
        # Access specific fields
        app_id = int(json_data.get("api_id"))
        app_hash = json_data.get("api_hash")
    try:
        client = await initialize_client(session_string,app_id,app_hash,proxy)
        try:
            # Get basic information
            user = await client.get_me()
            response = {
                "isValid": True,
                "errorCode": None,
                "errorMessage": f"Account with the number {phone_number} was successfully checked.",
                "firstName": user.first_name,
                "lastName": user.last_name,
                "username": user.username,
                "profilePicture": None  # Add handling for profile picture if required
            }
        finally:
            await client.disconnect()
    except Exception as e:
        response = {
            "isValid": False,
            "errorCode": "CHECK_FAILED",
            "errorMessage": str(e),
            "firstName": None,
            "lastName": None,
            "username": None,
            "profilePicture": None
        }

    return jsonify(response)
@app.route('/account/update-details', methods=['POST'])
async def update_account_details():
    data = await request.form
    image_is_changed = data.get('image_is_changed') == 'true'
    phone_number = data.get('phone_number')
    session_string = data.get('session_string')
    proxy = parse_proxy(data.get('proxy'))
    first_name = data.get('first_name')
    last_name = data.get('last_name')
    if last_name == "null":
        last_name=""
    username = data.get('username')
    
    files = await request.files
    uploaded_session_file = files.get('session_file')  # 'file' should match the name attribute in the form data
    uploade_json_file = files.get("json_file")
    if uploaded_session_file:
        file_path = os.path.join(UPLOAD_FOLDER, uploaded_session_file.filename)
        await uploaded_session_file.save(file_path)

    uploaded_json_string = uploade_json_file.read() if uploade_json_file else None
    if uploaded_json_string:
        # Decode the binary string
        decoded_json = uploaded_json_string.decode('utf-8')
        
        # Parse JSON
        json_data = json.loads(decoded_json)
        
        # Access specific fields
        app_id = int(json_data.get("app_id"))
        app_hash = json_data.get("app_hash")
    # Files (if provided)
    profile_picture =files.get('profile_picture')

    try:
        client = await initialize_client(session_string,app_id,app_hash,proxy)

        if image_is_changed and profile_picture:
            # Save profile picture temporarily
            picture_path = os.path.join(UPLOAD_FOLDER, "temp_profile_pic.jpg")
            await profile_picture.save(picture_path)

            temp_image_path = 'temp_profile_pic.jpg'
            with Image.open(picture_path) as img:
                img = img.convert("RGB")  # Ensure image is RGB for JPEG
                img = img.resize((512, 512))  # Resize to 512x512 pixels
                img.save(temp_image_path, format="JPEG")  # Save as JPEG format
            with open(temp_image_path, 'rb') as file:
                uploaded_photo = await client.upload_file(file)

                # Use the uploaded file to change the profile photo
            await client(functions.photos.UploadProfilePhotoRequest(file=uploaded_photo))

            print("Profile picture updated successfully")
            # Remove temporary file after upload
            os.remove(temp_image_path)
        # Update profile details
        await client(functions.account.UpdateProfileRequest(first_name=first_name,last_name=last_name,about=None))

        # Update username with UpdateUsernameRequest
        await client(functions.account.UpdateUsernameRequest(username=username))

        response = {
            "isValid": True,
            "errorCode": None,
            "errorMessage": None,
            "sessionString": session_string,
            "firstName": first_name,
            "lastName": last_name,
            "username": username,
            "profilePicture": None
        }
    except Exception as e:
        response = {
            "isValid": False,
            "errorCode": "UPDATE_FAILED",
            "errorMessage": str(e),
            "sessionString": None,
            "firstName": None,
            "lastName": None,
            "username": None,
            "profilePicture": None
        }
    finally:
        await client.disconnect()

    return jsonify(response)

if __name__ == '__main__':
    uvicorn.run(app, host="127.0.0.1", port=5000, log_level="debug")
