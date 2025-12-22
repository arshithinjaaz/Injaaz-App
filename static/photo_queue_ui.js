/**
 * Photo Queue UI Helper - Shared UI components for all forms
 * Works with PhotoUploadQueue to provide consistent UI across forms
 */

class PhotoQueueUI {
  constructor(containerId, options = {}) {
    this.container = document.getElementById(containerId);
    this.options = {
      maxPhotos: options.maxPhotos || 100,
      showOverallProgress: options.showOverallProgress !== false,
      showRetryButton: options.showRetryButton !== false,
      onRetryAll: options.onRetryAll || (() => {}),
      onRemove: options.onRemove || (() => {})
    };
    
    this.photoElements = new Map(); // photoId -> DOM element
  }

  /**
   * Create and show progress container
   */
  createProgressContainer() {
    const existing = document.getElementById('uploadQueueStatus');
    if (existing) return existing;
    
    const progressHTML = `
      <div class="upload-queue-container" id="uploadQueueStatus" style="display:none;">
        <div class="upload-progress-bar">
          <div class="upload-progress-fill" id="queueProgressFill" style="width: 0%">
            0%
          </div>
        </div>
        <div class="upload-stats" id="uploadStats">
          <strong>0</strong> completed | <strong>0</strong> uploading | <strong>0</strong> queued | <strong>0</strong> failed
        </div>
        ${this.options.showRetryButton ? '<button class="retry-all-btn" id="retryAllBtn" style="display:none;">Retry All Failed</button>' : ''}
      </div>
    `;
    
    this.container.insertAdjacentHTML('beforebegin', progressHTML);
    
    if (this.options.showRetryButton) {
      document.getElementById('retryAllBtn').addEventListener('click', () => {
        this.options.onRetryAll();
      });
    }
    
    return document.getElementById('uploadQueueStatus');
  }

  /**
   * Update overall progress bar
   */
  updateProgress(stats) {
    const progressContainer = document.getElementById('uploadQueueStatus');
    if (!progressContainer) return;
    
    if (stats.total === 0) {
      progressContainer.style.display = 'none';
      return;
    }
    
    progressContainer.style.display = 'block';
    
    const percentComplete = stats.total > 0 ? Math.round((stats.completed / stats.total) * 100) : 0;
    const progressFill = document.getElementById('queueProgressFill');
    
    if (progressFill) {
      progressFill.style.width = percentComplete + '%';
      progressFill.textContent = `${percentComplete}% (${stats.completed}/${stats.total})`;
    }
    
    const statsEl = document.getElementById('uploadStats');
    if (statsEl) {
      statsEl.innerHTML = `
        <strong>${stats.completed}</strong> completed | 
        <strong>${stats.uploading}</strong> uploading | 
        <strong>${stats.queued}</strong> queued | 
        <strong>${stats.failed}</strong> failed
      `;
    }
    
    const retryBtn = document.getElementById('retryAllBtn');
    if (retryBtn) {
      retryBtn.style.display = stats.failed > 0 ? 'inline-block' : 'none';
    }
    
    // Hide progress bar after completion if no failures
    if (stats.isComplete && stats.failed === 0) {
      setTimeout(() => {
        progressContainer.style.display = 'none';
      }, 3000);
    }
  }

  /**
   * Render a photo item with status overlay
   */
  renderPhotoItem(item) {
    const photoDiv = document.createElement('div');
    photoDiv.className = 'photo-item';
    photoDiv.dataset.photoId = item.id;
    
    photoDiv.innerHTML = `
      <img src="${item.preview}" alt="Photo">
      <div class="photo-status-overlay status-${item.status}">
        ${this.getStatusContent(item.status, item.progress)}
      </div>
      <div class="photo-progress">
        <div class="photo-progress-fill" style="width: ${item.progress}%"></div>
      </div>
      <button class="photo-remove-btn" title="Remove photo">×</button>
    `;
    
    // Add remove button handler
    const removeBtn = photoDiv.querySelector('.photo-remove-btn');
    removeBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      this.options.onRemove(item.id);
    });
    
    this.container.appendChild(photoDiv);
    this.photoElements.set(item.id, photoDiv);
    
    return photoDiv;
  }

  /**
   * Get status overlay content based on status
   */
  getStatusContent(status, progress = 0) {
    switch (status) {
      case 'queued':
        return `<div class="photo-status-icon">⏸</div><div>Queued</div>`;
      case 'uploading':
        return `<div class="photo-status-icon spinning">↻</div><div>Uploading ${progress}%</div>`;
      case 'completed':
        return `<div class="photo-status-icon">✓</div><div>Uploaded</div>`;
      case 'failed':
        return `<div class="photo-status-icon">✗</div><div>Failed - Click to retry</div>`;
      default:
        return '';
    }
  }

  /**
   * Update photo item status
   */
  updatePhotoStatus(item) {
    const photoDiv = this.photoElements.get(item.id);
    if (!photoDiv) return;
    
    const overlay = photoDiv.querySelector('.photo-status-overlay');
    if (overlay) {
      overlay.className = `photo-status-overlay status-${item.status}`;
      overlay.innerHTML = this.getStatusContent(item.status, item.progress);
      
      // Add retry handler for failed items
      if (item.status === 'failed') {
        overlay.style.cursor = 'pointer';
        overlay.onclick = () => {
          const event = new CustomEvent('photo-retry', { detail: { photoId: item.id } });
          document.dispatchEvent(event);
        };
      }
    }
    
    const progressFill = photoDiv.querySelector('.photo-progress-fill');
    if (progressFill) {
      progressFill.style.width = item.progress + '%';
    }
  }

  /**
   * Remove photo from UI
   */
  removePhoto(photoId) {
    const photoDiv = this.photoElements.get(photoId);
    if (photoDiv) {
      photoDiv.remove();
      this.photoElements.delete(photoId);
    }
  }

  /**
   * Clear all photos
   */
  clearAll() {
    this.photoElements.forEach((div) => div.remove());
    this.photoElements.clear();
  }

  /**
   * Get count of displayed photos
   */
  getPhotoCount() {
    return this.photoElements.size;
  }
}

// Export for use in forms
if (typeof module !== 'undefined' && module.exports) {
  module.exports = PhotoQueueUI;
}
