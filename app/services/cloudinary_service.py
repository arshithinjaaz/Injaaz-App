import cloudinary
import cloudinary.uploader
import os
import time
from flask import current_app

def init_cloudinary():
    cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME', '')
    api_key = os.environ.get('CLOUDINARY_API_KEY', '')
    api_secret = os.environ.get('CLOUDINARY_API_SECRET', '')
    if not cloud_name or not api_key or not api_secret:
        return False
    cloudinary.config(
        cloud_name=cloud_name,
        api_key=api_key,
        api_secret=api_secret,
        secure=True
    )
    return True

def upload_base64_signature(data_uri, public_id_prefix):
    if not data_uri:
        return None
    if not init_cloudinary():
        return None
    try:
        res = cloudinary.uploader.upload(
            file=data_uri,
            folder="signatures",
            public_id=f"{public_id_prefix}_{int(time.time())}"
        )
        return res.get('secure_url')
    except Exception:
        current_app.logger.exception("Cloudinary signature upload failed")
        return None

def upload_local_file(path, public_id_prefix):
    if not init_cloudinary():
        return None
    try:
        res = cloudinary.uploader.upload(path, folder="injaaz_reports", public_id=public_id_prefix, resource_type='auto')
        return res.get('secure_url')
    except Exception:
        current_app.logger.exception("Cloudinary file upload failed")
        return None