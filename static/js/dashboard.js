/**
 * Injaaz Dashboard JavaScript
 * Extracted from inline scripts for better maintainability and caching
 */

// ===========================================
// Utility Functions
// ===========================================

// Global escapeHtml function
function escapeHtml(text) {
  if (!text) return '';
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// Token refresh state - prevents multiple simultaneous refresh attempts
let isRefreshing = false;
let refreshPromise = null;

// Helper function to refresh access token using refresh token
async function refreshAccessToken() {
  // If already refreshing, wait for the existing refresh to complete
  if (isRefreshing && refreshPromise) {
    return refreshPromise;
  }
  
  isRefreshing = true;
  
  refreshPromise = (async () => {
    try {
      const refreshToken = localStorage.getItem('refresh_token');
      if (!refreshToken) {
        return null;
      }
      
      const response = await fetch('/api/auth/refresh', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${refreshToken}`
        },
        credentials: 'include'
      });
      
      if (!response.ok) {
        if (response.status === 401 || response.status === 422) {
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
          localStorage.removeItem('user');
        }
        return null;
      }
      
      const data = await response.json();
      if (data.access_token) {
        localStorage.setItem('access_token', data.access_token);
        return data.access_token;
      }
      return null;
    } catch (error) {
      return null;
    } finally {
      isRefreshing = false;
      refreshPromise = null;
    }
  })();
  
  return refreshPromise;
}

// Helper function to make authenticated fetch with automatic token refresh
async function authenticatedFetch(url, options = {}) {
  let token = localStorage.getItem('access_token');
  if (!token) {
    return { ok: false, status: 401 };
  }
  
  // Make initial request
  const response = await fetch(url, {
    ...options,
    headers: {
      ...options.headers,
      'Authorization': `Bearer ${token}`
    }
  });
  
  // If 401, try to refresh token and retry once
  if (response.status === 401) {
    const newToken = await refreshAccessToken();
    if (newToken) {
      // Retry with new token
      return fetch(url, {
        ...options,
        headers: {
          ...options.headers,
          'Authorization': `Bearer ${newToken}`
        }
      });
    } else {
      // Refresh failed, redirect to login
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      localStorage.removeItem('user');
      window.location.href = '/login';
      return { ok: false, status: 401 };
    }
  }
  
  return response;
}

// ===========================================
// User & Authentication Functions
// ===========================================

// Load and display user welcome message
function loadUserWelcome() {
  try {
    const userData = localStorage.getItem('user');
    if (userData) {
      const user = JSON.parse(userData);
      const displayName = user.full_name || user.username;
      
      const welcomeText = document.getElementById('welcome-text');
      if (welcomeText) {
        welcomeText.textContent = `Welcome, ${displayName}!`;
      }
      
      checkAndShowAdminMenu(user);
      updateModuleVisibility(user);
      if (typeof loadPendingCount === 'function') {
        loadPendingCount(user);
      }
    } else {
      const token = localStorage.getItem('access_token');
      if (token) {
        fetch('/api/auth/me', {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        })
        .then(response => response.json())
        .then(data => {
          if (data.user) {
            localStorage.setItem('user', JSON.stringify(data.user));
            const displayName = data.user.full_name || data.user.username;
            const welcomeText = document.getElementById('welcome-text');
            if (welcomeText) {
              welcomeText.textContent = `Welcome, ${displayName}!`;
            }
            
            checkAndShowAdminMenu(data.user);
            updateModuleVisibility(data.user);
            if (typeof loadPendingCount === 'function') {
              loadPendingCount(data.user);
            }
          }
        })
        .catch(error => {
          console.error('Failed to fetch user:', error);
        });
      } else {
        const userStr = localStorage.getItem('user');
        if (userStr) {
          try {
            const user = JSON.parse(userStr);
            checkAndShowAdminMenu(user);
            updateModuleVisibility(user);
            if (typeof loadPendingCount === 'function') {
              loadPendingCount(user);
            }
          } catch (e) {
            console.error('Error parsing user from localStorage:', e);
          }
        }
      }
    }
  } catch (error) {
    console.error('Error loading user welcome:', error);
  }
}

// Function to check and show admin menu
function checkAndShowAdminMenu(user) {
  if (user && user.role === 'admin') {
    const adminMenuItem = document.getElementById('admin-menu-item');
    if (adminMenuItem) {
      adminMenuItem.style.display = 'list-item';
      console.log('Admin menu item shown');
    }
    const reportGenMenuItem = document.getElementById('report-gen-menu-item');
    if (reportGenMenuItem) {
      reportGenMenuItem.style.display = 'list-item';
    }
  }
  
  const workflowDesignations = ['operations_manager', 'business_development', 'procurement', 'general_manager'];
  if (user && (user.role === 'admin' || (user.designation && workflowDesignations.includes(user.designation)))) {
    const historyMenuItem = document.getElementById('review-history-menu-item');
    if (historyMenuItem) {
      historyMenuItem.style.display = 'list-item';
      console.log('Review History shown for:', user.designation || 'admin');
    }
  }
  
  if (user && !user.role) {
    const token = localStorage.getItem('access_token');
    if (token) {
      fetch('/api/auth/me', {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })
      .then(response => response.json())
      .then(data => {
        if (data.user) {
          localStorage.setItem('user', JSON.stringify(data.user));
          checkAndShowAdminMenu(data.user);
          updateModuleVisibility(data.user);
          if (typeof loadPendingCount === 'function') {
            loadPendingCount(data.user);
          }
        }
      })
      .catch(error => {
        console.error('Failed to fetch user role:', error);
      });
    }
  }
}

// ===========================================
// Module Visibility Functions
// ===========================================

function updateModuleVisibility(user) {
  if (!user) return;
  
  const isAdmin = user.role === 'admin';
  
  // Check HVAC access
  const hvacCard = document.getElementById('module-hvac');
  if (hvacCard) {
    const hasHvacAccess = isAdmin || user.access_hvac === true;
    hvacCard.style.display = hasHvacAccess ? 'block' : 'none';
    hvacCard.style.visibility = hasHvacAccess ? 'visible' : 'hidden';
  }
  
  // Check Civil access
  const civilCard = document.getElementById('module-civil');
  if (civilCard) {
    const hasCivilAccess = isAdmin || user.access_civil === true;
    civilCard.style.display = hasCivilAccess ? 'block' : 'none';
    civilCard.style.visibility = hasCivilAccess ? 'visible' : 'hidden';
  }
  
  // Check Cleaning access
  const cleaningCard = document.getElementById('module-cleaning');
  if (cleaningCard) {
    const hasCleaningAccess = isAdmin || user.access_cleaning === true;
    cleaningCard.style.display = hasCleaningAccess ? 'block' : 'none';
    cleaningCard.style.visibility = hasCleaningAccess ? 'visible' : 'hidden';
  }
  
  // Check Submitted Forms access (Supervisors only)
  const submittedFormsCard = document.getElementById('module-submitted-forms');
  const submittedFormsMenuItem = document.getElementById('submitted-forms-menu-item');
  if (submittedFormsCard) {
    const isSupervisor = user.designation === 'supervisor';
    submittedFormsCard.style.display = isSupervisor ? 'block' : 'none';
    submittedFormsCard.style.visibility = isSupervisor ? 'visible' : 'hidden';
    
    // Also show/hide the nav menu item
    if (submittedFormsMenuItem) {
      submittedFormsMenuItem.style.display = isSupervisor ? 'inline-block' : 'none';
    }
    
    if (isSupervisor) {
      if (typeof loadSubmittedFormsCount === 'function') {
        loadSubmittedFormsCount(user);
      }
    }
  }

  // Check BD Email Module access (BD only)
  const bdEmailCard = document.getElementById('module-bd-email');
  if (bdEmailCard) {
    const isBD = user.designation === 'business_development';
    bdEmailCard.style.display = isBD ? 'block' : 'none';
    bdEmailCard.style.visibility = isBD ? 'visible' : 'hidden';
  }

  const bdEmailMenuItem = document.getElementById('bd-email-menu-item');
  if (bdEmailMenuItem) {
    const isBD = user.designation === 'business_development';
    bdEmailMenuItem.style.display = isBD ? 'inline-block' : 'none';
  }

  // Check HR Module access
  const hrCard = document.getElementById('module-hr');
  if (hrCard) {
    const hasHrAccess = isAdmin || user.access_hr === true;
    hrCard.style.display = hasHrAccess ? 'block' : 'none';
    hrCard.style.visibility = hasHrAccess ? 'visible' : 'hidden';
  }

  // Check Procurement Module access
  const procurementCard = document.getElementById('module-procurement');
  if (procurementCard) {
    const hasProcurementAccess = isAdmin || user.access_procurement_module === true;
    procurementCard.style.display = hasProcurementAccess ? 'block' : 'none';
    procurementCard.style.visibility = hasProcurementAccess ? 'visible' : 'hidden';
  }
  
  // Update grid layout based on visible modules
  const modulesGrid = document.getElementById('modulesGrid');
  const modulesSection = document.getElementById('modules');
  
  if (modulesGrid) {
    const visibleModules = Array.from(modulesGrid.children).filter(card => 
      card.style.display !== 'none' && card.style.visibility !== 'hidden'
    );
    
    const isMobile = window.innerWidth <= 768;
    
    if (isMobile) {
      modulesGrid.style.gridTemplateColumns = '1fr';
      modulesGrid.style.maxWidth = '100%';
      modulesGrid.style.margin = '0';
    } else {
      if (visibleModules.length === 1) {
        modulesGrid.style.gridTemplateColumns = '1fr';
        modulesGrid.style.maxWidth = '600px';
        modulesGrid.style.margin = '0 auto';
      } else if (visibleModules.length === 2) {
        modulesGrid.style.gridTemplateColumns = 'repeat(2, 1fr)';
        modulesGrid.style.maxWidth = 'none';
        modulesGrid.style.margin = '0';
      } else {
        modulesGrid.style.gridTemplateColumns = 'repeat(3, 1fr)';
        modulesGrid.style.maxWidth = 'none';
        modulesGrid.style.margin = '0';
      }
    }
    
    if (modulesSection && visibleModules.length === 0) {
      const existingMsg = modulesSection.querySelector('.no-access-message');
      if (existingMsg) {
        existingMsg.remove();
      }
      
      const noAccessMsg = document.createElement('div');
      noAccessMsg.className = 'no-access-message';
      noAccessMsg.style.cssText = 'text-align: center; padding: 3rem; color: var(--text-light);';
      noAccessMsg.innerHTML = `
        <h3 style="margin-bottom: 1rem; color: var(--text-dark);">No Module Access</h3>
        <p>You don't have access to any modules yet. Please contact an administrator to grant access.</p>
      `;
      modulesSection.appendChild(noAccessMsg);
    } else if (modulesSection) {
      const existingMsg = modulesSection.querySelector('.no-access-message');
      if (existingMsg) {
        existingMsg.remove();
      }
    }
  }
}

// Helper function to update module grid layout
function updateModuleGridLayout() {
  const modulesGrid = document.getElementById('modulesGrid');
  if (!modulesGrid) return;
  
  const visibleModules = Array.from(modulesGrid.children).filter(card => 
    card.style.display !== 'none' && card.style.visibility !== 'hidden'
  );
  
  const isMobile = window.innerWidth <= 768;
  
  if (isMobile) {
    modulesGrid.style.gridTemplateColumns = '1fr';
  } else {
    if (visibleModules.length === 1) {
      modulesGrid.style.gridTemplateColumns = '1fr';
      modulesGrid.style.maxWidth = '600px';
      modulesGrid.style.margin = '0 auto';
    } else if (visibleModules.length === 2) {
      modulesGrid.style.gridTemplateColumns = 'repeat(2, 1fr)';
      modulesGrid.style.maxWidth = 'none';
      modulesGrid.style.margin = '0';
    } else if (visibleModules.length === 3) {
      modulesGrid.style.gridTemplateColumns = 'repeat(3, 1fr)';
      modulesGrid.style.maxWidth = 'none';
      modulesGrid.style.margin = '0';
    } else {
      modulesGrid.style.gridTemplateColumns = 'repeat(2, 1fr)';
      modulesGrid.style.maxWidth = 'none';
      modulesGrid.style.margin = '0';
    }
  }
}

// ===========================================
// Workflow Functions
// ===========================================

// Flag to prevent duplicate calls
let submittedFormsLoading = false;

// Load submitted forms count for supervisors
async function loadSubmittedFormsCount(user) {
  if (!user || user.designation !== 'supervisor') return;
  
  // Prevent duplicate simultaneous calls
  if (submittedFormsLoading) return;
  submittedFormsLoading = true;
  
  try {
    const response = await authenticatedFetch('/api/workflow/submissions/my-submissions');
    
    if (!response || !response.ok) return;
    
    const data = await response.json();
    const submissions = data.submissions || [];
    
    // Update module card badge
    const badge = document.getElementById('submittedFormsCount');
    if (badge) {
      if (submissions.length > 0) {
        badge.textContent = submissions.length > 99 ? '99+' : submissions.length;
        badge.style.display = 'inline-block';
      } else {
        badge.style.display = 'none';
      }
    }
    
    // Update navigation badge
    const navBadge = document.getElementById('navSubmittedBadge');
    if (navBadge) {
      if (submissions.length > 0) {
        navBadge.textContent = submissions.length > 99 ? '99+' : submissions.length;
        navBadge.style.display = 'inline';
      } else {
        navBadge.style.display = 'none';
      }
    }
    
  } catch (error) {
    console.error('Error loading submitted forms count:', error);
  } finally {
    submittedFormsLoading = false;
  }
}

// Load pending count and show pending review module card
async function loadPendingCount(user) {
  const pendingModule = document.getElementById('module-pending-review');
  const reviewHistoryModule = document.getElementById('module-review-history');
  const moduleBadge = document.getElementById('modulePendingBadge');
  
  if (user && user.role === 'admin') {
    if (pendingModule) {
      pendingModule.style.display = 'none';
      pendingModule.style.visibility = 'hidden';
    }
    if (reviewHistoryModule) {
      reviewHistoryModule.style.display = 'block';
      reviewHistoryModule.style.visibility = 'visible';
    }
    return;
  }
  
  const reviewerDesignations = ['operations_manager', 'business_development', 'procurement', 'general_manager'];
  const isReviewer = user && (user.designation && reviewerDesignations.includes(user.designation));
  
  if (reviewHistoryModule) {
    reviewHistoryModule.style.display = 'none';
    reviewHistoryModule.style.visibility = 'hidden';
  }
  
  if (!isReviewer) {
    if (pendingModule) {
      pendingModule.style.display = 'none';
      pendingModule.style.visibility = 'hidden';
    }
    return;
  }
  
  try {
    const response = await authenticatedFetch('/api/workflow/submissions/pending');
    
    if (!response || !response.ok) {
      return;
    }
    
    const data = await response.json();
    const submissions = data.submissions || [];
    
    if (pendingModule) {
      pendingModule.style.display = 'block';
      pendingModule.style.visibility = 'visible';
    }
    
    const navBadge = document.getElementById('navPendingBadge');
    if (navBadge) {
      if (submissions.length > 0) {
        navBadge.textContent = submissions.length;
        navBadge.style.display = 'inline-block';
      } else {
        navBadge.style.display = 'none';
      }
    }
    
    if (moduleBadge) {
      if (submissions.length > 0) {
        moduleBadge.textContent = submissions.length;
        moduleBadge.style.display = 'inline-block';
      } else {
        moduleBadge.style.display = 'none';
      }
    }
    
    updateModuleGridLayout();
    
  } catch (error) {
    console.error('Error loading pending count:', error);
  }
}

// Helper function to get workflow action text
function getWorkflowAction(designation) {
  const actionMap = {
    'operations_manager': 'Operations Manager Review',
    'business_development': 'Business Development Review',
    'procurement': 'Procurement Review',
    'general_manager': 'General Manager Approval'
  };
  return actionMap[designation] || 'Your Review';
}

// Open submission for supervisor review
window.openSubmissionForReview = async function(submissionId, moduleUrl) {
  try {
    const token = localStorage.getItem('access_token');
    
    await fetch(`/api/workflow/submissions/${submissionId}/start-review`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    });
    
    window.location.href = `/${moduleUrl}/form?edit=${submissionId}&review=true`;
  } catch (error) {
    console.error('Error starting review:', error);
    alert('Failed to start review. Please try again.');
  }
};

// ===========================================
// Profile Modal Functions
// ===========================================

window.openProfileModal = function() {
  const modal = document.getElementById('profileModal');
  if (modal) {
    modal.classList.add('active');
    document.body.style.overflow = 'hidden';
    loadProfileData();
  }
};

window.closeProfileModal = function() {
  const modal = document.getElementById('profileModal');
  if (modal) {
    modal.classList.remove('active');
    document.body.style.overflow = '';
  }
};

function loadProfileData() {
  const profileContent = document.getElementById('profileContent');
  const token = localStorage.getItem('access_token');
  const cachedUser = localStorage.getItem('user');
  
  if (!token) {
    if (cachedUser) {
      try {
        const user = JSON.parse(cachedUser);
        displayProfileData(user);
        return;
      } catch (e) {
        console.warn('Failed to parse cached user data');
      }
    }
    profileContent.innerHTML = '<div style="text-align: center; padding: 2rem;"><p style="color: var(--text-light);">Please log in to view your profile.</p></div>';
    return;
  }

  profileContent.innerHTML = '<div style="text-align: center; padding: 2rem;"><div class="spinner" style="border: 4px solid rgba(18, 84, 53, 0.1); border-top: 4px solid var(--primary); border-radius: 50%; width: 40px; height: 40px; animation: spin 1s linear infinite; margin: 0 auto;"></div><p style="margin-top: 1rem; color: var(--text-light);">Loading profile...</p></div>';

  fetch('/api/auth/me', {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  })
  .then(response => {
    if (!response.ok) {
      if (response.status === 401 && cachedUser) {
        try {
          const user = JSON.parse(cachedUser);
          console.log('Using cached user data due to 401');
          displayProfileData(user);
          return null;
        } catch (e) {
          console.warn('Failed to parse cached user data');
        }
      }
      throw new Error('Failed to fetch profile');
    }
    return response.json();
  })
  .then(data => {
    if (data === null) return;
    if (data && data.user) {
      localStorage.setItem('user', JSON.stringify(data.user));
      displayProfileData(data.user);
    } else {
      throw new Error('No user data received');
    }
  })
  .catch(error => {
    console.error('Error loading profile:', error);
    if (cachedUser) {
      try {
        const user = JSON.parse(cachedUser);
        console.log('Using cached user data as fallback');
        displayProfileData(user);
        return;
      } catch (e) {
        console.warn('Failed to parse cached user data');
      }
    }
    profileContent.innerHTML = `<div style="text-align: center; padding: 2rem;"><p style="color: #dc3545;">Error loading profile. Please try again or re-login.</p><button class="btn btn-primary btn-sm mt-2" onclick="window.location.href='/login'">Login</button></div>`;
  });
}

function displayProfileData(user) {
  const profileContent = document.getElementById('profileContent');
  
  const formatDate = (dateStr) => {
    if (!dateStr) return 'Never';
    try {
      let utcDateString = dateStr;
      if (!utcDateString.endsWith('Z') && !utcDateString.includes('+') && !utcDateString.includes('-', 10)) {
        utcDateString = utcDateString + 'Z';
      }
      const date = new Date(utcDateString);
      return date.toLocaleString('en-US', { 
        year: 'numeric', 
        month: 'long', 
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        timeZone: 'Asia/Dubai'
      }) + ' (GST)';
    } catch {
      return dateStr;
    }
  };

  const getModuleAccess = () => {
    const modules = [];
    if (user.role === 'admin' || user.access_hvac) modules.push('HVAC & MEP');
    if (user.role === 'admin' || user.access_civil) modules.push('Civil Works');
    if (user.role === 'admin' || user.access_cleaning) modules.push('Cleaning');
    if (user.role === 'admin' || user.access_hr) modules.push('HR');
    if (user.role === 'admin' || user.access_procurement_module) modules.push('Procurement');
    return modules.length > 0 ? modules.join(', ') : 'None';
  };

  const getRoleDisplay = () => {
    const roleMap = {
      'admin': 'Administrator',
      'inspector': 'Inspector',
      'user': 'User'
    };
    return roleMap[user.role] || user.role;
  };

  const getDesignationDisplay = () => {
    if (!user.designation) return 'Not assigned';
    const designationMap = {
      'supervisor': 'Supervisor',
      'operations_manager': 'Operations Manager',
      'business_development': 'Business Development',
      'procurement': 'Procurement',
      'general_manager': 'General Manager'
    };
    return designationMap[user.designation] || user.designation;
  };

  const getInitials = () => {
    if (user.full_name) {
      return user.full_name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
    }
    return user.username ? user.username.slice(0, 2).toUpperCase() : 'U';
  };

  const html = getProfileCardHTML(user, getInitials, getDesignationDisplay, getRoleDisplay, getModuleAccess, formatDate);
  profileContent.innerHTML = html;
  initProfileSignatureDefaults(user);
}

function getProfileCardHTML(user, getInitials, getDesignationDisplay, getRoleDisplay, getModuleAccess, formatDate) {
  const modules = [];
  if (user.role === 'admin' || user.access_hvac) modules.push({ name: 'HVAC & MEP', icon: '🔧', color: '#3b82f6' });
  if (user.role === 'admin' || user.access_civil) modules.push({ name: 'Civil Works', icon: '🏢', color: '#8b5cf6' });
  if (user.role === 'admin' || user.access_cleaning) modules.push({ name: 'Cleaning', icon: '🧹', color: '#10b981' });
  if (user.role === 'admin' || user.access_hr) modules.push({ name: 'HR', icon: '👤', color: '#f59e0b' });
  if (user.role === 'admin' || user.access_procurement_module) modules.push({ name: 'Procurement', icon: '📦', color: '#7c3aed' });
  
  const moduleBadges = modules.length > 0 
    ? modules.map(m => `<span class="pro-module-badge" style="--badge-color: ${m.color}">${m.icon} ${m.name}</span>`).join('')
    : '<span class="pro-no-access">No modules assigned</span>';

  return `
    <style>
      /* Modern Profile Modal Styles - Enhanced */
      .pro-container {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        width: 100%;
        max-width: 100%;
        padding: 0 1.25rem 1.25rem;
        box-sizing: border-box;
      }
      
      /* Hero Section */
      .pro-hero {
        position: relative;
        padding: 2rem 1.5rem 1.5rem;
        background: linear-gradient(135deg, #0f4a2a 0%, #1a6b3d 50%, #22885a 100%);
        border-radius: 0;
        margin: 0 -1.25rem;
        overflow: hidden;
      }
      
      .pro-hero::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0; bottom: 0;
        background: url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='0.03'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E");
        opacity: 0.5;
      }
      
      .pro-hero-content {
        position: relative;
        z-index: 1;
        display: flex;
        flex-direction: column;
        align-items: center;
        text-align: center;
      }
      
      .pro-avatar {
        width: 85px;
        height: 85px;
        border-radius: 50%;
        background: rgba(255,255,255,0.15);
        backdrop-filter: blur(10px);
        border: 3px solid rgba(255,255,255,0.3);
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.85rem;
        font-weight: 700;
        color: white;
        margin-bottom: 0.875rem;
        box-shadow: 0 8px 32px rgba(0,0,0,0.2);
        position: relative;
      }
      
      .pro-avatar::after {
        content: '';
        position: absolute;
        bottom: 2px;
        right: 2px;
        width: 16px;
        height: 16px;
        background: ${user.is_active ? '#22c55e' : '#ef4444'};
        border: 2px solid white;
        border-radius: 50%;
        box-shadow: 0 2px 8px rgba(0,0,0,0.2);
      }
      
      .pro-name {
        font-size: 1.35rem;
        font-weight: 700;
        color: white;
        margin: 0 0 0.5rem;
        letter-spacing: -0.5px;
      }
      
      .pro-role-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        background: rgba(255,255,255,0.15);
        backdrop-filter: blur(10px);
        padding: 0.45rem 1rem;
        border-radius: 100px;
        font-size: 0.75rem;
        font-weight: 500;
        color: rgba(255,255,255,0.95);
        border: 1px solid rgba(255,255,255,0.2);
      }
      
      .pro-role-badge svg {
        width: 13px;
        height: 13px;
        opacity: 0.8;
      }
      
      /* Tabs */
      .pro-tabs {
        display: flex;
        gap: 0.375rem;
        padding: 0.625rem 1rem;
        background: #f8fafc;
        border-bottom: 1px solid #e2e8f0;
        margin: 0 -1.25rem;
      }
      
      .pro-tab {
        flex: 1;
        padding: 0.6rem 0.75rem;
        border: none;
        background: transparent;
        font-size: 0.8rem;
        font-weight: 600;
        color: #64748b;
        cursor: pointer;
        border-radius: 8px;
        transition: all 0.2s ease;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 0.35rem;
      }
      
      .pro-tab:hover {
        background: #e2e8f0;
        color: #334155;
      }
      
      .pro-tab.active {
        background: white;
        color: #125435;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
      }
      
      .pro-tab svg {
        width: 14px;
        height: 14px;
      }
      
      /* Tab Content */
      .pro-tab-content {
        display: none;
        padding: 1rem 0;
        animation: fadeIn 0.3s ease;
      }
      
      .pro-tab-content.active {
        display: block;
      }
      
      @keyframes fadeIn {
        from { opacity: 0; transform: translateY(8px); }
        to { opacity: 1; transform: translateY(0); }
      }
      
      /* Info List */
      .pro-info-list {
        display: flex;
        flex-direction: column;
        gap: 0.75rem;
      }
      
      .pro-info-item {
        display: flex;
        align-items: center;
        gap: 0.875rem;
        padding: 0.75rem 0.875rem;
        background: #f8fafc;
        border-radius: 12px;
        border: 1px solid #e2e8f0;
        transition: all 0.2s ease;
      }
      
      .pro-info-item:hover {
        background: #f1f5f9;
        border-color: #cbd5e1;
      }
      
      .pro-info-icon {
        width: 40px;
        height: 40px;
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.1rem;
        background: linear-gradient(135deg, #125435 0%, #1a7a4d 100%);
        color: white;
        flex-shrink: 0;
      }
      
      .pro-info-content {
        flex: 1;
        min-width: 0;
      }
      
      .pro-info-label {
        font-size: 0.7rem;
        font-weight: 600;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 0.125rem;
      }
      
      .pro-info-value {
        font-size: 0.95rem;
        font-weight: 600;
        color: #1e293b;
        word-break: break-word;
      }
      
      /* Module Badges */
      .pro-modules-wrap {
        padding: 0.875rem;
        background: #f8fafc;
        border-radius: 12px;
        border: 1px solid #e2e8f0;
      }
      
      .pro-modules-title {
        font-size: 0.7rem;
        font-weight: 600;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 0.625rem;
      }
      
      .pro-modules-list {
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
      }
      
      .pro-module-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.3rem;
        padding: 0.45rem 0.75rem;
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 100px;
        font-size: 0.8rem;
        font-weight: 500;
        color: #334155;
        transition: all 0.2s ease;
      }
      
      .pro-module-badge:hover {
        border-color: var(--badge-color, #125435);
        background: color-mix(in srgb, var(--badge-color, #125435) 8%, white);
      }
      
      .pro-no-access {
        color: #94a3b8;
        font-size: 0.8rem;
        font-style: italic;
      }
      
      /* Footer / Member Since */
      .pro-footer, .pro-member-since {
        text-align: center;
        padding: 0.875rem 0 0.5rem;
        margin-top: 0.875rem;
        font-size: 0.8rem;
        color: #94a3b8;
        border-top: 1px solid #e2e8f0;
      }
      
      .pro-member-since strong {
        color: #64748b;
      }
      
      .pro-footer-text {
        font-size: 0.8rem;
        color: #94a3b8;
      }
      
      /* Security Section */
      .pro-security-card {
        padding: 0.875rem;
        border-radius: 10px;
        border: 1px solid;
        margin-bottom: 0.625rem;
        display: flex;
        align-items: center;
        gap: 0.875rem;
      }
      
      .pro-security-card.success {
        background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%);
        border-color: #86efac;
      }
      
      .pro-security-card.warning {
        background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%);
        border-color: #fcd34d;
      }
      
      .pro-security-icon {
        width: 38px;
        height: 38px;
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.1rem;
        flex-shrink: 0;
      }
      
      .pro-security-card.success .pro-security-icon {
        background: #22c55e;
        color: white;
      }
      
      .pro-security-card.warning .pro-security-icon {
        background: #f59e0b;
        color: white;
      }
      
      .pro-security-content {
        flex: 1;
        min-width: 0;
      }
      
      .pro-security-title {
        font-size: 0.875rem;
        font-weight: 600;
        color: #1e293b;
        margin-bottom: 0.125rem;
      }
      
      .pro-security-desc {
        font-size: 0.75rem;
        color: #64748b;
      }
      
      .pro-security-action {
        flex-shrink: 0;
      }
      
      .pro-btn {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 0.375rem;
        padding: 0.5rem 1rem;
        font-size: 0.8rem;
        font-weight: 600;
        border-radius: 8px;
        border: none;
        cursor: pointer;
        transition: all 0.2s ease;
      }
      
      .pro-btn-primary {
        background: linear-gradient(135deg, #125435 0%, #1a7a4d 100%);
        color: white;
        box-shadow: 0 2px 8px rgba(18,84,53,0.25);
      }
      
      .pro-btn-primary:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(18,84,53,0.35);
      }
      
      .pro-btn-outline {
        background: white;
        color: #125435;
        border: 1.5px solid #125435;
      }
      
      .pro-btn-outline:hover {
        background: #f0fdf4;
      }
      
      .pro-btn-sm {
        padding: 0.375rem 0.75rem;
        font-size: 0.75rem;
      }
      
      .pro-btn-danger {
        background: white;
        color: #dc2626;
        border: 1.5px solid #fecaca;
      }
      
      .pro-btn-danger:hover {
        background: #fef2f2;
        border-color: #dc2626;
      }
      
      .pro-btn-success {
        background: linear-gradient(135deg, #16a34a 0%, #22c55e 100%);
        color: white;
        box-shadow: 0 2px 8px rgba(22,163,74,0.25);
      }
      
      .pro-btn-success:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(22,163,74,0.35);
      }
      
      /* Signature Section */
      .pro-sig-section {
        background: #f8fafc;
        border-radius: 10px;
        border: 1px solid #e2e8f0;
        overflow: hidden;
      }
      
      .pro-sig-header {
        padding: 0.875rem;
        border-bottom: 1px solid #e2e8f0;
        display: flex;
        align-items: center;
        gap: 0.625rem;
      }
      
      .pro-sig-header-icon {
        width: 32px;
        height: 32px;
        background: linear-gradient(135deg, #125435 0%, #1a7a4d 100%);
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-size: 0.9rem;
      }
      
      .pro-sig-header-text h4 {
        margin: 0;
        font-size: 0.875rem;
        font-weight: 600;
        color: #1e293b;
      }
      
      .pro-sig-header-text p {
        margin: 0;
        font-size: 0.7rem;
        color: #64748b;
      }
      
      .pro-sig-body {
        padding: 0.875rem;
      }
      
      .pro-sig-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 0.75rem;
      }
      
      /* Mobile Responsive - Profile Modal */
      @media (max-width: 480px) {
        .pro-sig-grid {
          grid-template-columns: 1fr;
        }
        
        .pro-container {
          padding: 0 1rem 1.5rem;
        }
        
        .pro-hero {
          margin: 0 -1rem;
          padding: 2rem 1rem 1.5rem;
        }
        
        .pro-avatar {
          width: 70px;
          height: 70px;
          font-size: 1.5rem;
        }
        
        .pro-avatar::after {
          width: 14px;
          height: 14px;
        }
        
        .pro-name {
          font-size: 1.2rem;
        }
        
        .pro-role-badge {
          font-size: 0.7rem;
          padding: 0.375rem 0.75rem;
        }
        
        .pro-tabs {
          margin: 0 -1rem;
          padding: 0.625rem 0.5rem;
          gap: 0.25rem;
        }
        
        .pro-tab {
          padding: 0.5rem 0.375rem;
          font-size: 0.7rem;
          gap: 0.25rem;
        }
        
        .pro-tab svg {
          width: 12px;
          height: 12px;
        }
        
        .pro-tab-content {
          padding: 1rem 0;
        }
        
        .pro-info-list {
          gap: 0.625rem;
        }
        
        .pro-info-item {
          padding: 0.625rem 0.75rem;
          gap: 0.625rem;
        }
        
        .pro-info-icon {
          width: 36px;
          height: 36px;
          font-size: 0.95rem;
          border-radius: 8px;
        }
        
        .pro-info-label {
          font-size: 0.625rem;
        }
        
        .pro-info-value {
          font-size: 0.85rem;
        }
        
        .pro-modules-wrap {
          padding: 0.75rem;
        }
        
        .pro-modules-title {
          font-size: 0.625rem;
          margin-bottom: 0.5rem;
        }
        
        .pro-module-badge {
          padding: 0.375rem 0.625rem;
          font-size: 0.7rem;
        }
        
        .pro-security-card {
          padding: 0.625rem;
          gap: 0.625rem;
        }
        
        .pro-security-icon {
          width: 32px;
          height: 32px;
          font-size: 0.95rem;
        }
        
        .pro-security-title {
          font-size: 0.8rem;
        }
        
        .pro-security-desc {
          font-size: 0.7rem;
        }
        
        .pro-btn {
          padding: 0.375rem 0.75rem;
          font-size: 0.7rem;
        }
        
        .pro-sig-header {
          padding: 0.625rem;
        }
        
        .pro-sig-body {
          padding: 0.625rem;
        }
        
        .pro-sig-preview {
          min-height: 70px;
        }
        
        .pro-sig-comment {
          min-height: 70px;
          padding: 0.625rem;
          font-size: 0.75rem;
        }
        
        .pro-member-since {
          font-size: 0.75rem;
          padding: 0.75rem 0 0.25rem;
        }
      }
      
      .pro-sig-preview {
        background: white;
        border: 2px dashed #cbd5e1;
        border-radius: 10px;
        min-height: 80px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        transition: all 0.2s ease;
        position: relative;
        overflow: hidden;
      }
      
      .pro-sig-preview:hover {
        border-color: #125435;
        background: #f0fdf4;
      }
      
      .pro-sig-preview.has-sig {
        border-style: solid;
        border-color: #22c55e;
      }
      
      .pro-sig-preview img {
        max-width: 90%;
        max-height: 70px;
        object-fit: contain;
      }
      
      .pro-sig-empty {
        text-align: center;
        color: #94a3b8;
      }
      
      .pro-sig-empty-icon {
        font-size: 1.5rem;
        margin-bottom: 0.375rem;
        opacity: 0.5;
      }
      
      .pro-sig-empty-text {
        font-size: 0.75rem;
        font-weight: 500;
      }
      
      .pro-sig-comment {
        width: 100%;
        min-height: 80px;
        border: 2px solid #e2e8f0;
        border-radius: 10px;
        padding: 0.75rem;
        font-family: inherit;
        font-size: 0.8rem;
        resize: none;
        transition: all 0.2s ease;
        background: white;
      }
      
      .pro-sig-comment:focus {
        outline: none;
        border-color: #125435;
        box-shadow: 0 0 0 3px rgba(18,84,53,0.1);
      }
      
      .pro-sig-comment::placeholder {
        color: #94a3b8;
      }
      
      .pro-sig-footer {
        padding: 0.875rem;
        border-top: 1px solid #e2e8f0;
        display: flex;
        justify-content: flex-end;
        gap: 0.5rem;
        background: white;
      }
      
      /* Signature Popup */
      .pro-popup-overlay {
        display: none;
        position: fixed;
        inset: 0;
        background: rgba(15,23,42,0.5);
        backdrop-filter: blur(4px);
        z-index: 10000;
        align-items: center;
        justify-content: center;
        padding: 1rem;
      }
      
      .pro-popup-overlay.active {
        display: flex;
      }
      
      .pro-popup {
        background: white;
        border-radius: 20px;
        width: 100%;
        max-width: 440px;
        box-shadow: 0 25px 50px rgba(0,0,0,0.25);
        animation: popUp 0.3s ease;
        overflow: hidden;
      }
      
      @keyframes popUp {
        from { opacity: 0; transform: scale(0.95) translateY(20px); }
        to { opacity: 1; transform: scale(1) translateY(0); }
      }
      
      .pro-popup-header {
        padding: 1.25rem;
        border-bottom: 1px solid #e2e8f0;
        display: flex;
        align-items: center;
        justify-content: space-between;
      }
      
      .pro-popup-title {
        font-size: 1.1rem;
        font-weight: 700;
        color: #1e293b;
        margin: 0;
        display: flex;
        align-items: center;
        gap: 0.5rem;
      }
      
      .pro-popup-close {
        width: 36px;
        height: 36px;
        border-radius: 10px;
        border: none;
        background: #f1f5f9;
        color: #64748b;
        font-size: 1.25rem;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: all 0.2s ease;
      }
      
      .pro-popup-close:hover {
        background: #fee2e2;
        color: #dc2626;
      }
      
      .pro-popup-body {
        padding: 1.25rem;
      }
      
      .pro-popup-canvas {
        border: 2px solid #e2e8f0;
        border-radius: 12px;
        overflow: hidden;
        background: white;
      }
      
      .pro-popup-canvas canvas {
        width: 100%;
        height: 180px;
        display: block;
      }
      
      .pro-popup-hint {
        text-align: center;
        font-size: 0.75rem;
        color: #94a3b8;
        margin-top: 0.75rem;
      }
      
      .pro-popup-footer {
        padding: 1rem 1.25rem;
        border-top: 1px solid #e2e8f0;
        display: flex;
        justify-content: flex-end;
        gap: 0.5rem;
        background: #f8fafc;
      }
      
      /* Member Since */
      .pro-member-since {
        text-align: center;
        padding: 1.25rem;
        margin-top: 0.5rem;
        color: #64748b;
        font-size: 0.9rem;
        border-top: 1px solid #e2e8f0;
      }
      
      .pro-member-since strong {
        color: #334155;
      }
      
      /* Responsive */
      @media (max-width: 480px) {
        .pro-hero {
          padding: 2rem 1rem 1.25rem;
          margin: -1.75rem -1.75rem 0;
        }
        
        .pro-avatar {
          width: 76px;
          height: 76px;
          font-size: 1.75rem;
        }
        
        .pro-name {
          font-size: 1.3rem;
        }
        
        .pro-tabs {
          padding: 0.5rem 0.75rem;
          margin: 0 -1.75rem;
        }
        
        .pro-tab {
          padding: 0.5rem;
          font-size: 0.75rem;
        }
        
        .pro-tab span {
          display: none;
        }
        
        .pro-info-item {
          padding: 0.75rem;
        }
        
        .pro-info-icon {
          width: 36px;
          height: 36px;
          font-size: 1rem;
        }
        
        .pro-security-card {
          flex-direction: column;
          text-align: center;
          gap: 0.75rem;
        }
        
        .pro-security-action {
          width: 100%;
        }
        
        .pro-security-action .pro-btn {
          width: 100%;
        }
      }
    </style>
    
    <div class="pro-container">
      <!-- Hero Section -->
      <div class="pro-hero">
        <div class="pro-hero-content">
          <div class="pro-avatar">${getInitials()}</div>
          <h2 class="pro-name">${escapeHtml(user.full_name || user.username)}</h2>
          <div class="pro-role-badge">
            <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"/></svg>
            ${escapeHtml(getDesignationDisplay())} • ${escapeHtml(getRoleDisplay())}
          </div>
        </div>
      </div>
      
      <!-- Tabs -->
      <div class="pro-tabs">
        <button class="pro-tab active" data-tab="profile" onclick="switchProfileTab('profile')">
          <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/></svg>
          <span>Profile</span>
        </button>
        <button class="pro-tab" data-tab="security" onclick="switchProfileTab('security')">
          <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"/></svg>
          <span>Security</span>
        </button>
        <button class="pro-tab" data-tab="signature" onclick="switchProfileTab('signature')">
          <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"/></svg>
          <span>Signature</span>
        </button>
      </div>
      
      <!-- Profile Tab -->
      <div class="pro-tab-content active" data-content="profile">
        <div class="pro-info-list">
          <div class="pro-info-item">
            <div class="pro-info-icon">👤</div>
            <div class="pro-info-content">
              <div class="pro-info-label">Username</div>
              <div class="pro-info-value">${escapeHtml(user.username)}</div>
            </div>
          </div>
          <div class="pro-info-item">
            <div class="pro-info-icon">✉️</div>
            <div class="pro-info-content">
              <div class="pro-info-label">Email Address</div>
              <div class="pro-info-value">${escapeHtml(user.email || 'Not provided')}</div>
            </div>
          </div>
        </div>
        
        <div class="pro-modules-wrap" style="margin-top: 1rem;">
          <div class="pro-modules-title">Module Access</div>
          <div class="pro-modules-list">
            ${moduleBadges}
          </div>
        </div>
        
        <div class="pro-member-since">
          Member since <strong>${formatDate(user.created_at).replace(' (GST)', '').split(',')[0]}</strong>
        </div>
      </div>
      
      <!-- Security Tab -->
      <div class="pro-tab-content" data-content="security">
        <div class="pro-security-card ${user.password_changed ? 'success' : 'warning'}">
          <div class="pro-security-icon">${user.password_changed ? '✓' : '⚠️'}</div>
          <div class="pro-security-content">
            <div class="pro-security-title">${user.password_changed ? 'Password is secure' : 'Password change required'}</div>
            <div class="pro-security-desc">${user.password_changed ? 'Your password meets security requirements' : 'Please update your password for security'}</div>
          </div>
          <div class="pro-security-action">
            <button class="pro-btn ${user.password_changed ? 'pro-btn-outline' : 'pro-btn-primary'} pro-btn-sm" onclick="showChangePasswordForm()">
              ${user.password_changed ? 'Change' : 'Update Now'}
            </button>
          </div>
        </div>
        
        <div class="pro-info-list">
          <div class="pro-info-item">
            <div class="pro-info-icon">🛡️</div>
            <div class="pro-info-content">
              <div class="pro-info-label">Account Status</div>
              <div class="pro-info-value" style="color: ${user.is_active ? '#16a34a' : '#dc2626'}">
                ${user.is_active ? '● Active' : '● Inactive'}
              </div>
            </div>
          </div>
          <div class="pro-info-item">
            <div class="pro-info-icon">👑</div>
            <div class="pro-info-content">
              <div class="pro-info-label">Role</div>
              <div class="pro-info-value">${escapeHtml(getRoleDisplay())}</div>
            </div>
          </div>
        </div>
      </div>
      
      <!-- Signature Tab -->
      <div class="pro-tab-content" data-content="signature">
        <div class="pro-sig-section">
          <div class="pro-sig-header">
            <div class="pro-sig-header-icon">✍️</div>
            <div class="pro-sig-header-text">
              <h4>Default Signature</h4>
              <p>Used for automatic form signing</p>
            </div>
          </div>
          <div class="pro-sig-body">
            <div class="pro-sig-grid">
              <div class="pro-sig-preview" id="profileSigPreview" title="Click to draw signature">
                <div class="pro-sig-empty" id="profileSigEmpty">
                  <div class="pro-sig-empty-icon">✍️</div>
                  <div class="pro-sig-empty-text">Tap to sign</div>
                </div>
                <img id="profileSigImage" style="display: none;" alt="Signature">
              </div>
              <textarea class="pro-sig-comment" id="profileDefaultComment" placeholder="Enter default comment for reviews..."></textarea>
            </div>
          </div>
          <div class="pro-sig-footer">
            <button type="button" class="pro-btn pro-btn-danger pro-btn-sm" id="profileRemoveSignature">Remove</button>
            <button type="button" class="pro-btn pro-btn-success pro-btn-sm" id="profileSaveSignature">Save Defaults</button>
          </div>
        </div>
      </div>
      
      <!-- Signature Popup -->
      <div class="pro-popup-overlay" id="sigPopupOverlay">
        <div class="pro-popup">
          <div class="pro-popup-header">
            <h3 class="pro-popup-title">✍️ Draw Signature</h3>
            <button class="pro-popup-close" id="sigPopupClose">×</button>
          </div>
          <div class="pro-popup-body">
            <div class="pro-popup-canvas">
              <canvas id="profileSignaturePad"></canvas>
            </div>
            <p class="pro-popup-hint">Use mouse or finger to draw your signature</p>
          </div>
          <div class="pro-popup-footer">
            <button type="button" class="pro-btn pro-btn-outline pro-btn-sm" id="profileClearSignature">Clear</button>
            <button type="button" class="pro-btn pro-btn-success pro-btn-sm" id="sigPopupDone">Done</button>
          </div>
        </div>
      </div>
    </div>
  `;
}

// Tab switching function
window.switchProfileTab = function(tabName) {
  document.querySelectorAll('.pro-tab').forEach(tab => {
    tab.classList.toggle('active', tab.dataset.tab === tabName);
  });
  document.querySelectorAll('.pro-tab-content').forEach(content => {
    content.classList.toggle('active', content.dataset.content === tabName);
  });
}

// ===========================================
// Profile Signature Functions
// ===========================================

let profileSignaturePad = null;
let currentSignatureDataUrl = null;

function initProfileSignatureDefaults(user) {
  const canvas = document.getElementById('profileSignaturePad');
  const sigPreview = document.getElementById('profileSigPreview');
  const sigImage = document.getElementById('profileSigImage');
  const sigEmpty = document.getElementById('profileSigEmpty');
  const sigPopupOverlay = document.getElementById('sigPopupOverlay');
  const sigPopupClose = document.getElementById('sigPopupClose');
  const sigPopupDone = document.getElementById('sigPopupDone');
  
  if (!canvas || typeof SignaturePad === 'undefined') return;
  
  profileSignaturePad = new SignaturePad(canvas, {
    backgroundColor: 'rgb(255, 255, 255)',
    penColor: 'rgb(0, 0, 0)',
    minWidth: 1,
    maxWidth: 3,
    throttle: 16
  });

  function resizeCanvas() {
    const ratio = Math.max(window.devicePixelRatio || 1, 1);
    const rect = canvas.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    canvas.width = rect.width * ratio;
    canvas.height = rect.height * ratio;
    const ctx = canvas.getContext('2d');
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.fillStyle = 'rgb(255, 255, 255)';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    if (currentSignatureDataUrl) {
      profileSignaturePad.fromDataURL(currentSignatureDataUrl);
    }
  }

  async function resolveSignatureDataUrl(src) {
    if (!src) return null;
    if (src.startsWith('data:image')) return src;
    try {
      const response = await fetch(src);
      if (!response.ok) return null;
      const blob = await response.blob();
      return await new Promise((resolve) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = () => resolve(null);
        reader.readAsDataURL(blob);
      });
    } catch (error) {
      console.warn('Failed to fetch signature URL', error);
      return null;
    }
  }

  function updatePreview(dataUrl) {
    currentSignatureDataUrl = dataUrl;
    if (dataUrl) {
      sigImage.src = dataUrl;
      sigImage.style.display = 'block';
      sigEmpty.style.display = 'none';
      sigPreview.classList.add('has-signature');
    } else {
      sigImage.style.display = 'none';
      sigEmpty.style.display = 'block';
      sigPreview.classList.remove('has-signature');
    }
  }

  // Load existing signature
  if (user.default_signature) {
    resolveSignatureDataUrl(user.default_signature).then((dataUrl) => {
      if (dataUrl) {
        updatePreview(dataUrl);
      }
    });
  }

  // Open popup when clicking preview
  sigPreview.addEventListener('click', () => {
    sigPopupOverlay.classList.add('active');
    setTimeout(() => {
      resizeCanvas();
      if (currentSignatureDataUrl) {
        profileSignaturePad.fromDataURL(currentSignatureDataUrl);
      }
    }, 100);
  });

  // Close popup
  function closePopup() {
    sigPopupOverlay.classList.remove('active');
  }
  sigPopupClose.addEventListener('click', closePopup);
  sigPopupOverlay.addEventListener('click', (e) => {
    if (e.target === sigPopupOverlay) closePopup();
  });

  // Done button - save signature to preview
  sigPopupDone.addEventListener('click', () => {
    if (!profileSignaturePad.isEmpty()) {
      const dataUrl = profileSignaturePad.toDataURL('image/png');
      updatePreview(dataUrl);
    }
    closePopup();
  });

  const commentEl = document.getElementById('profileDefaultComment');
  if (commentEl) commentEl.value = user.default_comment || '';

  const clearBtn = document.getElementById('profileClearSignature');
  if (clearBtn) {
    clearBtn.addEventListener('click', () => {
      profileSignaturePad.clear();
      const ctx = canvas.getContext('2d');
      ctx.fillStyle = 'rgb(255, 255, 255)';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
    });
  }

  const saveBtn = document.getElementById('profileSaveSignature');
  if (saveBtn) {
    saveBtn.addEventListener('click', async () => {
      const token = localStorage.getItem('access_token');
      if (!token) {
        alert('Please log in again to save your signature.');
        return;
      }
      const payload = {
        signature_data_url: currentSignatureDataUrl || '',
        default_comment: commentEl ? commentEl.value : ''
      };
      try {
        const response = await fetch('/api/auth/signature-default', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          },
          body: JSON.stringify(payload)
        });
        if (response.status === 401) {
          if (confirm('Session expired. Would you like to log in again?')) {
            window.location.href = '/login';
          }
          return;
        }
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.error || 'Failed to save defaults');
        const userData = localStorage.getItem('user');
        if (userData) {
          const parsed = JSON.parse(userData);
          parsed.default_signature = data.default_signature;
          parsed.default_comment = data.default_comment;
          localStorage.setItem('user', JSON.stringify(parsed));
        }
        saveBtn.textContent = 'Saved!';
        setTimeout(() => { saveBtn.textContent = 'Save'; }, 1500);
      } catch (error) {
        console.error('Save default signature failed', error);
        alert(error.message || 'Failed to save. Please log in again.');
      }
    });
  }

  const removeBtn = document.getElementById('profileRemoveSignature');
  if (removeBtn) {
    removeBtn.addEventListener('click', async () => {
      const token = localStorage.getItem('access_token');
      if (!token) {
        alert('Please log in again.');
        return;
      }
      try {
        const response = await fetch('/api/auth/signature-default', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          },
          body: JSON.stringify({ remove_default: true })
        });
        if (response.status === 401) {
          if (confirm('Session expired. Would you like to log in again?')) {
            window.location.href = '/login';
          }
          return;
        }
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.error || 'Failed to remove defaults');
        if (profileSignaturePad) profileSignaturePad.clear();
        if (commentEl) commentEl.value = '';
        updatePreview(null);
        const userData = localStorage.getItem('user');
        if (userData) {
          const parsed = JSON.parse(userData);
          parsed.default_signature = data.default_signature;
          parsed.default_comment = data.default_comment;
          localStorage.setItem('user', JSON.stringify(parsed));
        }
        removeBtn.textContent = 'Removed!';
        setTimeout(() => { removeBtn.textContent = 'Remove'; }, 1500);
      } catch (error) {
        console.error('Remove default signature failed', error);
        alert(error.message || 'Failed to remove default signature.');
      }
    });
  }
}

// ===========================================
// Change Password Functions
// ===========================================

window.showChangePasswordForm = function() {
  const profileContent = document.getElementById('profileContent');
  const html = `
    <div style="padding: 1rem;">
      <h3 style="margin-bottom: 1.5rem; text-align: center; color: var(--primary);">Change Password</h3>
      <form id="changePasswordForm" onsubmit="event.preventDefault(); submitChangePassword();">
        <div class="mb-3">
          <label for="currentPassword" class="form-label">Current Password</label>
          <input type="password" id="currentPassword" class="form-control" required placeholder="Enter current password" autocomplete="off" data-1p-ignore="true" data-lpignore="true">
        </div>
        <div class="mb-3">
          <label for="newPassword" class="form-label">New Password</label>
          <input type="password" id="newPassword" class="form-control" required minlength="8" placeholder="Enter new password (min 8 chars)" autocomplete="off" data-1p-ignore="true" data-lpignore="true">
          <p class="contact-modal-note" style="margin-top: 0.25rem;">Must be at least 8 characters long.</p>
        </div>
        <div class="mb-3">
          <label for="confirmNewPassword" class="form-label">Confirm New Password</label>
          <input type="password" id="confirmNewPassword" class="form-control" required minlength="8" placeholder="Confirm new password" autocomplete="off" data-1p-ignore="true" data-lpignore="true">
        </div>
        <div id="changePasswordError" class="alert alert-danger" style="display: none; margin-bottom: 1rem; font-size: 0.9rem;"></div>
        <div id="changePasswordSuccess" class="alert alert-success" style="display: none; margin-bottom: 1rem; font-size: 0.9rem;"></div>
        
        <div style="display: flex; gap: 1rem; margin-top: 2rem;">
          <button type="button" class="btn btn-outline-secondary" onclick="loadProfileData()" style="flex: 1; padding: 0.75rem;">Cancel</button>
          <button type="submit" id="submitPasswordBtn" class="btn btn-primary" style="flex: 2; padding: 0.75rem; font-weight: 600;">Update Password</button>
        </div>
      </form>
    </div>
  `;
  profileContent.innerHTML = html;
};

window.submitChangePassword = async function() {
  const currentPassword = document.getElementById('currentPassword').value;
  const newPassword = document.getElementById('newPassword').value;
  const confirmNewPassword = document.getElementById('confirmNewPassword').value;
  const errorDiv = document.getElementById('changePasswordError');
  const successDiv = document.getElementById('changePasswordSuccess');
  const submitBtn = document.getElementById('submitPasswordBtn');
  
  errorDiv.style.display = 'none';
  successDiv.style.display = 'none';
  
  if (newPassword !== confirmNewPassword) {
    errorDiv.textContent = 'New passwords do not match.';
    errorDiv.style.display = 'block';
    return;
  }
  
  const token = localStorage.getItem('access_token');
  if (!token) {
    errorDiv.textContent = 'You are not logged in.';
    errorDiv.style.display = 'block';
    return;
  }
  
  submitBtn.disabled = true;
  submitBtn.innerHTML = 'Updating...';
  
  try {
    const response = await fetch('/api/auth/change-password', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({
        current_password: currentPassword,
        new_password: newPassword
      })
    });
    
    const result = await response.json();
    
    if (!response.ok) {
      throw new Error(result.error || 'Failed to change password');
    }
    
    successDiv.textContent = 'Password updated successfully! Redirecting to login...';
    successDiv.style.display = 'block';
    
    setTimeout(() => {
      localStorage.removeItem('access_token');
      localStorage.removeItem('user_id');
      window.location.href = '/login';
    }, 2000);
    
  } catch (error) {
    console.error('Password change error:', error);
    errorDiv.textContent = error.message;
    errorDiv.style.display = 'block';
    submitBtn.disabled = false;
    submitBtn.innerHTML = 'Update Password';
  }
};

// ===========================================
// Contact Modal Functions
// ===========================================

window.openContactModal = function() {
  const modal = document.getElementById('contactModal');
  if (modal) {
    modal.classList.add('active');
    document.body.style.overflow = 'hidden';
  }
};

window.closeContactModal = function() {
  const modal = document.getElementById('contactModal');
  if (modal) {
    modal.classList.remove('active');
    document.body.style.overflow = '';
  }
};

// ===========================================
// Logout Function
// ===========================================

async function handleLogout() {
  try {
    const token = localStorage.getItem('access_token');
    
    if (!token) {
      localStorage.clear();
      window.location.href = '/login';
      return;
    }
    
    await fetch('/api/auth/logout', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      }
    });
    
    localStorage.clear();
    sessionStorage.clear();
    window.location.href = '/login';
    
  } catch (error) {
    console.error('Logout error:', error);
    localStorage.clear();
    sessionStorage.clear();
    window.location.href = '/login';
  }
}

// ===========================================
// Initialization
// ===========================================

document.addEventListener('DOMContentLoaded', function() {
  // Check if we're on the dashboard page (has modulesGrid or modules section)
  const isDashboardPage = document.getElementById('modulesGrid') || document.getElementById('modules');
  
  // Ensure modules section is visible on load (dashboard only)
  if (isDashboardPage) {
    const modulesSection = document.getElementById('modules');
    if (modulesSection) {
      modulesSection.style.display = 'block';
      modulesSection.style.visibility = 'visible';
      modulesSection.style.opacity = '1';
    }
    
    const modulesGrid = document.getElementById('modulesGrid');
    if (modulesGrid) {
      modulesGrid.style.display = 'grid';
      modulesGrid.style.visibility = 'visible';
    }
    
    loadUserWelcome();
    
    // Check immediately if user data exists
    const userStr = localStorage.getItem('user');
    if (userStr) {
      try {
        const user = JSON.parse(userStr);
        checkAndShowAdminMenu(user);
        updateModuleVisibility(user);
        if (typeof loadPendingCount === 'function') {
          loadPendingCount(user);
        }
      } catch (e) {
        console.error('Error parsing user from localStorage:', e);
      }
    } else {
      const token = localStorage.getItem('access_token');
      if (token) {
        fetch('/api/auth/me', {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        })
        .then(response => response.json())
        .then(data => {
          if (data.user) {
            localStorage.setItem('user', JSON.stringify(data.user));
            checkAndShowAdminMenu(data.user);
            updateModuleVisibility(data.user);
            if (typeof loadPendingCount === 'function') {
              loadPendingCount(data.user);
            }
          }
        })
        .catch(error => {
          console.error('Failed to fetch user data:', error);
        });
      }
    }
  }
  
  // Enhanced scroll effect
  const nav = document.getElementById('nav');
  window.addEventListener('scroll', () => {
    if (window.pageYOffset > 50) {
      nav.classList.add('scrolled');
    } else {
      nav.classList.remove('scrolled');
    }
  });
  
  // Profile link click handler
  const profileLink = document.getElementById('profileLink');
  if (profileLink) {
    profileLink.addEventListener('click', function(e) {
      e.preventDefault();
      openProfileModal();
    });
  }

  // Contact link click handler
  const contactLink = document.getElementById('contactLink');
  if (contactLink) {
    contactLink.addEventListener('click', function(e) {
      e.preventDefault();
      openContactModal();
    });
  }
  const footerContactLink = document.getElementById('footerContactLink');
  if (footerContactLink) {
    footerContactLink.addEventListener('click', function(e) {
      e.preventDefault();
      openContactModal();
    });
  }

  // Close modal when clicking outside
  const contactModal = document.getElementById('contactModal');
  if (contactModal) {
    contactModal.addEventListener('click', function(e) {
      if (e.target === this) {
        closeContactModal();
      }
    });
  }
  
  // Close modal with Escape key
  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
      closeContactModal();
      closeProfileModal();
    }
  });
  
  // Smooth scroll for anchor links
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
      e.preventDefault();
      const href = this.getAttribute('href');
      if (!href || href === '#') return;
      const target = document.querySelector(href);
      if (target) {
        target.scrollIntoView({
          behavior: 'smooth',
          block: 'start'
        });
      }
    });
  });
  
  // Load pending count for badge (only on dashboard)
  if (isDashboardPage) {
    const userDataForNotifications = localStorage.getItem('user');
    if (userDataForNotifications) {
      try {
        const userData = JSON.parse(userDataForNotifications);
        if (typeof loadPendingCount === 'function') {
          loadPendingCount(userData);
        }
      } catch (e) {
        console.error('Error parsing user data for notifications:', e);
      }
    }
  }
  
  // Mobile menu toggle
  const mobileMenuToggle = document.getElementById('mobileMenuToggle');
  const navMenu = document.querySelector('.nav-menu');
  const mobileOverlay = document.getElementById('mobileOverlay');
  
  function closeMobileMenu() {
    if (mobileMenuToggle) mobileMenuToggle.classList.remove('active');
    if (navMenu) navMenu.classList.remove('active');
    if (mobileOverlay) mobileOverlay.classList.remove('active');
    document.body.style.overflow = '';
  }
  
  if (mobileMenuToggle && navMenu) {
    mobileMenuToggle.addEventListener('click', function() {
      const isOpen = navMenu.classList.contains('active');
      if (isOpen) {
        closeMobileMenu();
      } else {
        mobileMenuToggle.classList.add('active');
        navMenu.classList.add('active');
        if (mobileOverlay) mobileOverlay.classList.add('active');
        document.body.style.overflow = 'hidden';
      }
    });
  }
  
  if (mobileOverlay) {
    mobileOverlay.addEventListener('click', closeMobileMenu);
  }
  
  // Close mobile menu when clicking on a link
  if (navMenu) {
    navMenu.querySelectorAll('a').forEach(link => {
      link.addEventListener('click', closeMobileMenu);
    });
  }
  
  // Logout functionality
  const logoutBtn = document.getElementById('logoutBtn');
  if (logoutBtn) {
    logoutBtn.addEventListener('click', handleLogout);
  }
  
  // Initialize notifications
  initNotifications();
});

// ===========================================
// Notification System
// ===========================================

function initNotifications() {
  const notificationBtn = document.getElementById('notificationBtn');
  const notificationDropdown = document.getElementById('notificationDropdown');
  const markAllReadBtn = document.getElementById('markAllRead');
  
  if (!notificationBtn || !notificationDropdown) return;
  
  // Toggle dropdown
  notificationBtn.addEventListener('click', function(e) {
    e.stopPropagation();
    notificationDropdown.classList.toggle('show');
    if (notificationDropdown.classList.contains('show')) {
      loadNotifications();
    }
  });
  
  // Close dropdown when clicking outside
  document.addEventListener('click', function(e) {
    if (!notificationDropdown.contains(e.target) && !notificationBtn.contains(e.target)) {
      notificationDropdown.classList.remove('show');
    }
  });
  
  // Mark all as read
  if (markAllReadBtn) {
    markAllReadBtn.addEventListener('click', async function() {
      try {
        const response = await authenticatedFetch('/hr/api/notifications/mark-all-read', {
          method: 'POST'
        });
        if (response.ok) {
          loadNotifications();
          updateNotificationBadge(0);
        }
      } catch (error) {
        console.error('Error marking all as read:', error);
      }
    });
  }
  
  // Load initial notification count
  loadNotificationCount();
  
  // Poll for new notifications every 30 seconds
  setInterval(loadNotificationCount, 30000);
}

async function loadNotificationCount() {
  const badge = document.getElementById('notificationBadge');
  if (!badge) return;
  
  try {
    const token = localStorage.getItem('access_token');
    if (!token) return;
    
    const response = await authenticatedFetch('/hr/api/notifications/unread-count');
    if (response.ok) {
      const data = await response.json();
      updateNotificationBadge(data.unread_count || 0);
    }
  } catch (error) {
    console.error('Error loading notification count:', error);
  }
}

function updateNotificationBadge(count) {
  const badge = document.getElementById('notificationBadge');
  if (!badge) return;
  
  if (count > 0) {
    badge.textContent = count > 99 ? '99+' : count;
    badge.style.display = 'flex';
  } else {
    badge.style.display = 'none';
  }
}

async function loadNotifications() {
  const notificationList = document.getElementById('notificationList');
  if (!notificationList) return;
  
  try {
    const token = localStorage.getItem('access_token');
    if (!token) return;
    
    const response = await authenticatedFetch('/hr/api/notifications');
    if (!response.ok) throw new Error('Failed to load notifications');
    
    const data = await response.json();
    
    if (data.notifications && data.notifications.length > 0) {
      notificationList.innerHTML = data.notifications.map(n => {
        const iconClass = n.notification_type.includes('approved') ? 'approved' : 
                          n.notification_type.includes('rejected') ? 'rejected' : 'info';
        const iconEmoji = n.notification_type.includes('approved') ? '✓' : 
                          n.notification_type.includes('rejected') ? '✕' : 'ℹ';
        const timeAgo = getTimeAgo(new Date(n.created_at));
        
        return `
          <div class="notification-item ${n.is_read ? '' : 'unread'}" onclick="markNotificationRead(${n.id}, '${(n.submission_id || '').replace(/'/g, "\\'")}', '${(n.notification_type || '').replace(/'/g, "\\'")}')">
            <div class="notification-icon ${iconClass}">${iconEmoji}</div>
            <div class="notification-content">
              <div class="notification-title">${escapeHtml(n.title)}</div>
              <div class="notification-message">${escapeHtml(n.message)}</div>
              <div class="notification-time">${timeAgo}</div>
            </div>
          </div>
        `;
      }).join('');
      
      updateNotificationBadge(data.unread_count || 0);
    } else {
      notificationList.innerHTML = '<div class="notification-empty">No notifications yet</div>';
    }
  } catch (error) {
    console.error('Error loading notifications:', error);
    notificationList.innerHTML = '<div class="notification-empty">Error loading notifications</div>';
  }
}

async function markNotificationRead(id, submissionId, notificationType) {
  try {
    await authenticatedFetch(`/hr/api/notifications/${id}/read`, {
      method: 'POST'
    });
    
    // Refresh notifications
    loadNotifications();
    loadNotificationCount();
    
    // Navigate based on notification type when submission exists
    if (submissionId) {
      const url = (notificationType === 'gm_approval_pending') ? '/hr/gm-approval' : '/hr/';
      window.location.href = url;
    }
  } catch (error) {
    console.error('Error marking notification as read:', error);
  }
}

function getTimeAgo(date) {
  const now = new Date();
  const seconds = Math.floor((now - date) / 1000);
  
  if (seconds < 60) return 'Just now';
  if (seconds < 3600) return `${Math.floor(seconds / 60)} min ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} hr ago`;
  if (seconds < 604800) return `${Math.floor(seconds / 86400)} day${Math.floor(seconds / 86400) > 1 ? 's' : ''} ago`;
  return date.toLocaleDateString();
}
