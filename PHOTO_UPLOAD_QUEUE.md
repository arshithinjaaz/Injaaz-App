# Photo Upload Queue Integration Guide

## Implementation Summary

The Photo Upload Queue system has been created with the following components:

### 1. Core Files Created
- **`static/photo_upload_queue.js`** - Reusable upload queue manager class
- **`static/photo_upload_queue.css`** - Styling for upload indicators and progress

### 2. Features Implemented

#### Upload Queue Manager (`PhotoUploadQueue`)
- ✅ Concurrent upload limiting (default: 3 simultaneous uploads)
- ✅ Optimistic UI (photos show immediately with preview)
- ✅ Real-time progress tracking (per photo and overall)
- ✅ Status indicators (queued, uploading, completed, failed)
- ✅ Retry functionality (individual or all failed)
- ✅ Photo removal from queue
- ✅ Memory management (blob URL cleanup)
- ✅ Comprehensive statistics and callbacks

#### Key Methods:
```javascript
// Initialize queue
const queue = new PhotoUploadQueue({
  maxConcurrent: 3,
  uploadEndpoint: '/module/upload-photo',
  onProgress: (stats) => { /* update UI */ },
  onItemComplete: (item, success) => { /* handle completion */ },
  onQueueComplete: (stats) => { /* all done */ }
});

// Add photos (returns items with preview immediately)
const photoItems = queue.addPhotos(fileList);

// Retry failed upload
queue.retryUpload(photoId);

// Get all successful URLs
const urls = queue.getUploadedUrls();

// Get statistics
const stats = queue.getStats();
// Returns: { total, completed, failed, uploading, queued, isComplete }
```

### 3. Integration Steps for Each Form

#### Current State:
- **HVAC/MEP**: Has basic progressive upload (compression + batch upload)
- **Civil**: Has basic photo upload
- **Cleaning**: Needs progressive upload implementation

#### To Integrate Queue System:

**Step 1: Add Script Tags**
```html
<link rel="stylesheet" href="{{ url_for('static', filename='photo_upload_queue.css') }}">
<script src="{{ url_for('static', filename='photo_upload_queue.js') }}"></script>
```

**Step 2: Replace `handleFiles` Function**
```javascript
// Initialize queue
const photoQueue = new PhotoUploadQueue({
  maxConcurrent: 3,
  uploadEndpoint: '{{ blueprint_prefix }}/upload-photo',
  onProgress: updateProgressUI,
  onItemComplete: handlePhotoComplete,
  onQueueComplete: handleQueueComplete
});

// Handle file selection
async function handleFiles(files) {
  // Validate files
  const validFiles = Array.from(files).filter(f => 
    f.type.startsWith('image/') && f.size <= MAX_FILE_SIZE
  );
  
  // Add to queue (photos show immediately with preview)
  const photoItems = photoQueue.addPhotos(validFiles);
  
  // Render photos immediately (optimistic UI)
  renderPhotos(photoItems);
}
```

**Step 3: Add Progress UI**
```html
<div class="upload-queue-container" id="uploadQueueStatus" style="display:none;">
  <div class="upload-progress-bar">
    <div class="upload-progress-fill" id="queueProgressFill" style="width: 0%">
      0%
    </div>
  </div>
  <div class="upload-stats" id="uploadStats">
    <strong>0</strong> completed | <strong>0</strong> uploading | <strong>0</strong> queued | <strong>0</strong> failed
  </div>
  <button class="retry-all-btn" id="retryAllBtn" style="display:none;" onclick="retryAllFailed()">
    Retry All Failed
  </button>
</div>
```

**Step 4: Update UI Callbacks**
```javascript
function updateProgressUI(stats) {
  if (stats.total === 0) {
    document.getElementById('uploadQueueStatus').style.display = 'none';
    return;
  }
  
  document.getElementById('uploadQueueStatus').style.display = 'block';
  
  const percentComplete = Math.round((stats.completed / stats.total) * 100);
  const progressFill = document.getElementById('queueProgressFill');
  progressFill.style.width = percentComplete + '%';
  progressFill.textContent = `${percentComplete}% (${stats.completed}/${stats.total})`;
  
  document.getElementById('uploadStats').innerHTML = `
    <strong>${stats.completed}</strong> completed | 
    <strong>${stats.uploading}</strong> uploading | 
    <strong>${stats.queued}</strong> queued | 
    <strong>${stats.failed}</strong> failed
  `;
  
  document.getElementById('retryAllBtn').style.display = 
    stats.failed > 0 ? 'inline-block' : 'none';
}

function handlePhotoComplete(item, success) {
  // Update photo status icon
  const photoElement = document.querySelector(`[data-photo-id="${item.id}"]`);
  if (!photoElement) return;
  
  if (success) {
    photoElement.querySelector('.photo-status-overlay').innerHTML = `
      <div class="photo-status-icon">✓</div>
      <div>Uploaded</div>
    `;
    photoElement.querySelector('.photo-status-overlay').className = 
      'photo-status-overlay status-completed';
  } else {
    photoElement.querySelector('.photo-status-overlay').innerHTML = `
      <div class="photo-status-icon">✗</div>
      <div>Failed - Click to retry</div>
    `;
    photoElement.querySelector('.photo-status-overlay').className = 
      'photo-status-overlay status-failed';
    photoElement.querySelector('.photo-status-overlay').onclick = () => {
      photoQueue.retryUpload(item.id);
    };
  }
}

function handleQueueComplete(stats) {
  console.log(`Queue complete: ${stats.completed} uploaded, ${stats.failed} failed`);
  
  if (stats.failed === 0) {
    setTimeout(() => {
      document.getElementById('uploadQueueStatus').style.display = 'none';
    }, 3000);
  }
}
```

**Step 5: Render Photos with Status**
```javascript
function renderPhotos(photoItems) {
  const container = document.getElementById('photoPreviewContainer');
  
  photoItems.forEach(item => {
    const div = document.createElement('div');
    div.className = 'photo-item';
    div.dataset.photoId = item.id;
    
    div.innerHTML = `
      <img src="${item.preview}" alt="Photo">
      <div class="photo-status-overlay status-queued">
        <div class="photo-status-icon">⏸</div>
        <div>Queued</div>
      </div>
      <div class="photo-progress">
        <div class="photo-progress-fill" style="width: 0%"></div>
      </div>
      <button class="photo-remove-btn" onclick="removePhoto('${item.id}')">×</button>
    `;
    
    container.appendChild(div);
  });
}
```

### 4. Benefits of New System

**For Users:**
- ✅ Photos appear instantly (no waiting for upload)
- ✅ Can see upload progress per photo
- ✅ Clear indication of failures with retry option
- ✅ Can continue filling form while uploads happen
- ✅ No browser blocking or freezing

**For Developers:**
- ✅ Reusable across all forms
- ✅ Handles Cloudinary rate limits automatically
- ✅ Memory efficient (cleans up blob URLs)
- ✅ Comprehensive error handling
- ✅ Easy to customize (callbacks for everything)

**For System:**
- ✅ Controls concurrent uploads (prevents overwhelming server)
- ✅ Retry logic prevents data loss
- ✅ Graceful degradation on failures
- ✅ Better Cloudinary API utilization

### 5. Testing Checklist

After integration, test:
- [ ] Upload 1 photo (should upload immediately)
- [ ] Upload 10 photos (should show progress for each)
- [ ] Upload 30+ photos (should queue and process 3 at a time)
- [ ] Simulate network failure (disconnect mid-upload, should show failed state)
- [ ] Click retry on failed photo (should re-upload)
- [ ] Remove photo before upload complete (should cancel and remove)
- [ ] Submit form with all photos uploaded
- [ ] Submit form with some photos still uploading (should wait/warn)

### 6. Next Steps

1. ✅ Core queue system created
2. ⏳ Integrate into HVAC/MEP form
3. ⏳ Integrate into Civil form
4. ⏳ Integrate into Cleaning form
5. ⏳ Test with 30+ photos on each form
6. ⏳ Deploy to Render and test in production

### 7. Configuration Options

The queue can be customized:

```javascript
const queue = new PhotoUploadQueue({
  maxConcurrent: 3,        // Max simultaneous uploads
  uploadEndpoint: '/url',  // Upload endpoint
  onProgress: callback,    // Progress updates
  onItemComplete: callback,// Individual photo done
  onQueueComplete: callback// All photos done
});
```

### 8. Memory Management

The queue automatically:
- Revokes blob URLs when photos are removed
- Cleans up completed uploads
- Prevents memory leaks on long-running forms

### 9. Error Handling

The queue handles:
- Network errors (timeout, connection loss)
- Server errors (HTTP 4xx, 5xx)
- Invalid responses (parsing errors)
- File size violations (caught before upload)
- Cloudinary API errors (rate limits, etc.)

All errors are captured and presented to user with retry option.

---

## Current Implementation Status

✅ **Completed:**
- Photo upload queue manager class
- CSS styling for status indicators
- Progress tracking system
- Retry logic
- Memory management

⏳ **Pending:**
- Integration into HVAC/MEP form
- Integration into Civil form
- Integration into Cleaning form
- End-to-end testing
- Production deployment

**Estimated Time to Complete:** 1-2 hours for full integration and testing
