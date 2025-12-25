import cloudinary
import cloudinary.uploader
import os
import time
import logging

logger = logging.getLogger(__name__)

def init_cloudinary():
    cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME', '')
    api_key = os.environ.get('CLOUDINARY_API_KEY', '')
    api_secret = os.environ.get('CLOUDINARY_API_SECRET', '')
    if not cloud_name or not api_key or not api_secret:
        logger.error(f"Cloudinary credentials missing: cloud_name={bool(cloud_name)}, api_key={bool(api_key)}, api_secret={bool(api_secret)}")
        return False
    cloudinary.config(
        cloud_name=cloud_name,
        api_key=api_key,
        api_secret=api_secret,
        secure=True
    )
    logger.info(f"Cloudinary configured: {cloud_name}")
    return True

def upload_base64_signature(data_uri, public_id_prefix):
    if not data_uri:
        logger.error("No data_uri provided")
        return None
    if not init_cloudinary():
        logger.error("Cloudinary initialization failed")
        return None
    try:
        logger.info(f"Attempting Cloudinary upload for {public_id_prefix}")
        res = cloudinary.uploader.upload(
            file=data_uri,
            folder="signatures",
            public_id=f"{public_id_prefix}_{int(time.time())}",
            access_mode='public'  # Make publicly accessible
        )
        url = res.get('secure_url')
        logger.info(f"Cloudinary upload success: {url}")
        return url
    except Exception as e:
        logger.error(f"Cloudinary signature upload failed: {str(e)}", exc_info=True)
        return None

def upload_local_file(path, public_id_prefix):
    if not init_cloudinary():
        logger.error("Cloudinary initialization failed")
        return None
    try:
        logger.info(f"Attempting Cloudinary file upload: {path}")
        res = cloudinary.uploader.upload(
            path, 
            folder="injaaz_reports", 
            public_id=public_id_prefix, 
            resource_type='auto',
            access_mode='public',  # Make publicly accessible
            flags='attachment'  # Force download instead of display
        )
        url = res.get('secure_url')
        logger.info(f"Cloudinary file upload success: {url}")
        return url
    except Exception as e:
        logger.error(f"Cloudinary file upload failed: {str(e)}", exc_info=True)
        return None