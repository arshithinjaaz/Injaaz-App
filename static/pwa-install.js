// PWA Installation and Service Worker Registration
// Injaaz App v1.0.0

let deferredPrompt;
let installButton;

// Register Service Worker
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/static/service-worker.js')
      .then((registration) => {
        console.log('✅ Service Worker registered:', registration.scope);
        
        // Check for updates every hour
        setInterval(() => {
          registration.update();
        }, 60 * 60 * 1000);
        
        // Handle updates
        registration.addEventListener('updatefound', () => {
          const newWorker = registration.installing;
          
          newWorker.addEventListener('statechange', () => {
            if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
              // New service worker available
              showUpdateNotification();
            }
          });
        });
      })
      .catch((error) => {
        console.error('❌ Service Worker registration failed:', error);
      });
  });
}

// Show update notification
function showUpdateNotification() {
  if (confirm('A new version of Injaaz is available. Reload to update?')) {
    window.location.reload();
  }
}

// Listen for beforeinstallprompt event
window.addEventListener('beforeinstallprompt', (e) => {
  console.log('💾 Install prompt available');
  
  // Prevent the default prompt
  e.preventDefault();
  
  // Store the event for later use
  deferredPrompt = e;
  
  // Show custom install button
  showInstallButton();
});

// Show install button in UI
function showInstallButton() {
  // Create install button if it doesn't exist
  if (!document.getElementById('pwa-install-btn')) {
    const installBtn = document.createElement('button');
    installBtn.id = 'pwa-install-btn';
    installBtn.innerHTML = `
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
        <polyline points="7 10 12 15 17 10"></polyline>
        <line x1="12" y1="15" x2="12" y2="3"></line>
      </svg>
      <span>Install App</span>
    `;
    installBtn.style.cssText = `
      position: fixed;
      bottom: 20px;
      right: 20px;
      background: #125435;
      color: white;
      border: none;
      padding: 12px 24px;
      border-radius: 50px;
      font-family: 'Inter', sans-serif;
      font-size: 14px;
      font-weight: 600;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 8px;
      box-shadow: 0 4px 12px rgba(18, 84, 53, 0.3);
      z-index: 9999;
      transition: all 0.3s ease;
      animation: slideInUp 0.5s ease;
    `;
    
    installBtn.addEventListener('mouseenter', () => {
      installBtn.style.transform = 'translateY(-2px)';
      installBtn.style.boxShadow = '0 6px 16px rgba(18, 84, 53, 0.4)';
    });
    
    installBtn.addEventListener('mouseleave', () => {
      installBtn.style.transform = 'translateY(0)';
      installBtn.style.boxShadow = '0 4px 12px rgba(18, 84, 53, 0.3)';
    });
    
    installBtn.addEventListener('click', installApp);
    
    document.body.appendChild(installBtn);
    installButton = installBtn;
    
    // Add animation keyframes
    if (!document.getElementById('pwa-animations')) {
      const style = document.createElement('style');
      style.id = 'pwa-animations';
      style.textContent = `
        @keyframes slideInUp {
          from {
            transform: translateY(100px);
            opacity: 0;
          }
          to {
            transform: translateY(0);
            opacity: 1;
          }
        }
        
        @keyframes fadeOut {
          to {
            opacity: 0;
            transform: translateY(20px);
          }
        }
        
        #pwa-install-btn.hiding {
          animation: fadeOut 0.3s ease forwards;
        }
        
        @media (max-width: 768px) {
          #pwa-install-btn {
            bottom: 15px;
            right: 15px;
            padding: 10px 20px;
            font-size: 13px;
          }
        }
      `;
      document.head.appendChild(style);
    }
  }
}

// Install the app
async function installApp() {
  if (!deferredPrompt) {
    console.log('Install prompt not available');
    return;
  }
  
  // Show the install prompt
  deferredPrompt.prompt();
  
  // Wait for user response
  const { outcome } = await deferredPrompt.userChoice;
  
  console.log(`User response: ${outcome}`);
  
  if (outcome === 'accepted') {
    console.log('✅ App installed successfully');
    hideInstallButton();
  }
  
  // Clear the prompt
  deferredPrompt = null;
}

// Hide install button
function hideInstallButton() {
  if (installButton) {
    installButton.classList.add('hiding');
    setTimeout(() => {
      installButton.remove();
    }, 300);
  }
}

// Check if already installed
window.addEventListener('appinstalled', () => {
  console.log('✅ Injaaz has been installed');
  hideInstallButton();
  
  // Track installation
  if (typeof gtag !== 'undefined') {
    gtag('event', 'pwa_install', {
      event_category: 'engagement',
      event_label: 'PWA Installation'
    });
  }
});

// Check if running as installed PWA
if (window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true) {
  console.log('✅ Running as installed PWA');
  document.body.classList.add('pwa-installed');
  
  // Hide install button if shown
  hideInstallButton();
}

// Handle offline/online status
window.addEventListener('online', () => {
  console.log('🟢 Back online');
  showConnectionStatus('Online', '#10b981', 2000);
});

window.addEventListener('offline', () => {
  console.log('🔴 Offline mode - Forms require internet connection');
  showConnectionStatus('Offline - Please connect to internet', '#ef4444', 0); // 0 = stays visible
});

// Show connection status message
function showConnectionStatus(message, color, duration) {
  // Remove existing status
  const existing = document.getElementById('connection-status');
  if (existing) {
    existing.remove();
  }
  
  const status = document.createElement('div');
  status.id = 'connection-status';
  status.textContent = message;
  status.style.cssText = `
    position: fixed;
    top: 20px;
    left: 50%;
    transform: translateX(-50%) translateY(-20px);
    background: ${color};
    color: white;
    padding: 12px 24px;
    border-radius: 8px;
    font-family: 'Inter', sans-serif;
    font-size: 14px;
    font-weight: 500;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
    z-index: 10000;
    animation: slideDown 0.3s ease forwards;
  `;
  
  // Add slide animation
  const style = document.createElement('style');
  style.textContent = `
    @keyframes slideDown {
      to { transform: translateX(-50%) translateY(0); }
    }
  `;
  document.head.appendChild(style);
  
  document.body.appendChild(status);
  
  setTimeout(() => {
    status.style.animation = 'slideDown 0.3s ease reverse';
    setTimeout(() => status.remove(), 300);
  }, duration);
}

// Expose API for manual cache management
window.InjaazPWA = {
  update: () => {
    navigator.serviceWorker.ready.then((registration) => {
      registration.update();
    });
  },
  
  unregister: () => {
    navigator.serviceWorker.ready.then((registration) => {
      registration.unregister();
    });
  },
  
  getInstallStatus: () => {
    return window.matchMedia('(display-mode: standalone)').matches;
  },
  
  clearCache: async () => {
    const cacheNames = await caches.keys();
    await Promise.all(cacheNames.map(name => caches.delete(name)));
    console.log('✅ Cache cleared');
  }
};

console.log('✅ PWA install script loaded');
