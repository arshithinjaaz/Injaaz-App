# Cloud Storage Configuration Guide

## Overview
The Injaaz app now uses **Cloudinary** for cloud-based storage of images and signatures instead of local filesystem storage. This makes the application scalable for multiple users and hosted environments.

## Why Cloud Storage?

### Problems with Local Storage:
- ❌ Files stored on server disk (limited space)
- ❌ Lost when server restarts or redeploys
- ❌ Doesn't scale across multiple server instances
- ❌ Backup and disaster recovery complexity

### Benefits of Cloud Storage:
- ✅ Unlimited scalable storage
- ✅ Global CDN for fast image delivery
- ✅ Automatic backups and redundancy
- ✅ Works with multiple server instances
- ✅ Professional image optimization

## How It Works

### Upload Flow:
1. User submits form with images/signatures
2. System attempts to upload to Cloudinary
3. If Cloudinary configured: Images stored in cloud, URLs saved in database
4. If Cloudinary not configured: Falls back to local storage

### PDF Generation:
- PDF generators automatically fetch images from URLs or local paths
- Uses `common.utils.get_image_for_pdf()` for unified handling
- Works seamlessly with both cloud and local storage

## Configuration

### 1. Get Cloudinary Credentials
Sign up at [cloudinary.com](https://cloudinary.com) (free tier available)

### 2. Set Environment Variables
Add to your `.env` file:
```env
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret
```

### 3. Verify Configuration
When the app starts, check logs:
- ✅ "Uploaded to Cloudinary: https://..." = Cloud storage active
- ⚠️ "Cloudinary not configured, falling back to local storage" = Using local fallback

## Storage Folders

Images are organized in Cloudinary folders:

- **signatures/** - Technician and manager signatures
- **hvac_photos/** - HVAC/MEP inspection photos
- **civil_photos/** - Civil works photos
- **cleaning_photos/** - Cleaning assessment photos

## Code Implementation

### Upload Utilities (`common/utils.py`):
- `save_uploaded_file_cloud()` - Upload files to cloud or local
- `upload_base64_to_cloud()` - Upload base64 signatures to cloud
- `get_image_for_pdf()` - Fetch images for PDF generation (handles URLs and paths)

### Module Updates:
All three modules (HVAC, Civil, Cleaning) now use cloud storage:
- **module_hvac_mep/routes.py** - Cloud uploads for photos and signatures
- **module_civil/routes.py** - Cloud uploads for attachments
- **module_cleaning/routes.py** - Cloud uploads for photos and signatures

### PDF Generators:
- **module_hvac_mep/hvac_generators.py** - Loads images from URLs or paths
- **module_civil/civil_generators.py** - (Uses placeholder generators)
- **module_cleaning/cleaning_generators.py** - Loads images from URLs or paths

## Testing

### Test Cloud Upload:
1. Set Cloudinary credentials in `.env`
2. Submit a form with images
3. Check logs for "✅ Uploaded to Cloudinary: https://..."
4. Verify PDF contains images

### Test Fallback:
1. Remove Cloudinary credentials from `.env`
2. Submit a form with images
3. Check logs for "⚠️ Using local storage fallback"
4. Verify images saved to `generated/uploads/`

## Troubleshooting

### Images not uploading to cloud:
- Check Cloudinary credentials are correct
- Verify network connectivity
- Check logs for error messages

### PDFs missing images:
- Verify image URLs are accessible
- Check PDF generator logs for fetch errors
- Ensure `requests` library is installed

### Local fallback not working:
- Verify `generated/uploads/` directory exists
- Check file permissions
- Review `common/utils.py` error logs

## Migration from Local to Cloud

Existing local files are NOT automatically migrated. Two options:

### Option 1: Keep Existing Files Local
- Old submissions keep local paths
- New submissions use cloud storage
- PDF generators handle both automatically

### Option 2: Migrate Existing Files
```python
# TODO: Create migration script to upload existing files to Cloudinary
# and update submission JSONs with new URLs
```

## Cost Considerations

### Cloudinary Free Tier:
- 25 GB storage
- 25 GB bandwidth/month
- 25,000 transformations/month
- Suitable for small-medium deployments

### Paid Plans:
- More storage and bandwidth
- Advanced features (AI, video)
- Check [cloudinary.com/pricing](https://cloudinary.com/pricing)

## Security

### API Credentials:
- Never commit `.env` to git
- Use environment variables in production
- Rotate keys if compromised

### Access Control:
- Cloudinary URLs are public by default
- Consider signed URLs for sensitive content
- Configure upload restrictions in Cloudinary dashboard

## Production Deployment

### Render/Heroku:
Set environment variables in dashboard:
```
CLOUDINARY_CLOUD_NAME=xxx
CLOUDINARY_API_KEY=xxx
CLOUDINARY_API_SECRET=xxx
```

### Docker:
Pass environment variables in docker-compose.yml:
```yaml
environment:
  - CLOUDINARY_CLOUD_NAME=${CLOUDINARY_CLOUD_NAME}
  - CLOUDINARY_API_KEY=${CLOUDINARY_API_KEY}
  - CLOUDINARY_API_SECRET=${CLOUDINARY_API_SECRET}
```

## Support

For issues or questions:
1. Check application logs for detailed errors
2. Review Cloudinary dashboard for upload status
3. Test with fallback mode to isolate cloud issues
4. Contact development team with log excerpts
