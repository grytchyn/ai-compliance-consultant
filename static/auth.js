/**
 * Auth module for AI Verify.
 * Handles Google Sign-In, JWT management, and user state.
 */

// ── Configuration ──────────────────────────────────────
const AUTH = {
  CLIENT_ID: '945886082965-qoe3vq3tgk6f9o0tu4versmrdmh7posn.apps.googleusercontent.com',
  TOKEN_KEY: 'aiverify_jwt',
  USER_KEY: 'aiverify_user',
};

// ── State ──────────────────────────────────────────────
let authCallback = null;
let currentUser = null;

// ── Token Management ───────────────────────────────────
function saveToken(token, user) {
  localStorage.setItem(AUTH.TOKEN_KEY, token);
  localStorage.setItem(AUTH.USER_KEY, JSON.stringify(user));
  currentUser = user;
}

function clearToken() {
  localStorage.removeItem(AUTH.TOKEN_KEY);
  localStorage.removeItem(AUTH.USER_KEY);
  currentUser = null;
}

function getToken() {
  return localStorage.getItem(AUTH.TOKEN_KEY);
}

function getUser() {
  if (currentUser) return currentUser;
  const stored = localStorage.getItem(AUTH.USER_KEY);
  if (stored) {
    try {
      currentUser = JSON.parse(stored);
      return currentUser;
    } catch { return null; }
  }
  return null;
}

function isLoggedIn() {
  return !!getToken();
}

// ── Google Sign-In ─────────────────────────────────────
function initGoogleSignIn(buttonElement, onLogin, onError) {
  /**
   * Initialize Google Identity Services on a button element.
   * Uses the new Google Identity Services (GIS) library.
   */
  authCallback = onLogin;

  // Load Google's GIS library if not already loaded
  if (typeof google === 'undefined' || typeof google.accounts === 'undefined') {
    // Google One Tap is already loaded from the <script> tag in the HTML
    console.warn('Google Identity Services not loaded yet');
    return;
  }

  // Render the Google Sign-In button
  google.accounts.id.initialize({
    client_id: AUTH.CLIENT_ID,
    callback: handleGoogleCredential,
    cancel_on_tap_outside: false,
  });

  if (buttonElement) {
    google.accounts.id.renderButton(buttonElement, {
      type: 'standard',
      shape: 'pill',
      theme: 'outline',
      text: 'signin_with',
      size: 'medium',
      logo_alignment: 'left',
    });
  }
}

function handleGoogleCredential(response) {
  // Called by Google when user completes sign-in
  if (!response || !response.credential) {
    console.error('No credential from Google');
    return;
  }

  // Send credential to our backend
  exchangeGoogleToken(response.credential);
}

async function exchangeGoogleToken(credential) {
  try {
    const resp = await fetch('/auth/google', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ credential }),
    });

    if (!resp.ok) {
      const err = await resp.json();
      console.error('Auth failed:', err);
      return;
    }

    const data = await resp.json();
    saveToken(data.token, data.user);
    
    // Call success callback
    if (authCallback) authCallback(data.user);
    updateUIBasedOnAuth();
    
  } catch (err) {
    console.error('Auth error:', err);
  }
}

// ── API Helpers ────────────────────────────────────────
async function authFetch(url, options = {}) {
  const token = getToken();
  if (!token) {
    return fetch(url, options);
  }
  return fetch(url, {
    ...options,
    headers: {
      ...options.headers,
      'Authorization': `Bearer ${token}`,
    },
  });
}

async function saveResultToProfile(subId) {
  if (!isLoggedIn()) return false;
  try {
    const resp = await authFetch(`/auth/save/${subId}`, { method: 'POST' });
    return resp.ok;
  } catch {
    return false;
  }
}

async function getUserResults() {
  if (!isLoggedIn()) return [];
  try {
    const resp = await authFetch('/auth/results');
    if (!resp.ok) return [];
    const data = await resp.json();
    return data.results || [];
  } catch {
    return [];
  }
}

// ── UI Update ──────────────────────────────────────────
function updateUIBasedOnAuth() {
  const user = getUser();
  const loginBtns = document.querySelectorAll('.auth-login-btn');
  const userMenus = document.querySelectorAll('.auth-user-menu');
  const savePrompts = document.querySelectorAll('.auth-save-prompt');

  if (user) {
    loginBtns.forEach(el => el.style.display = 'none');
    userMenus.forEach(el => {
      el.style.display = 'flex';
      const avatar = el.querySelector('.auth-avatar');
      const name = el.querySelector('.auth-name');
      if (avatar) {
        avatar.innerHTML = '';
        if (user.avatar_url) {
          const img = document.createElement('img');
          img.src = user.avatar_url;
          img.alt = '';
          img.style.cssText = 'width:28px;height:28px;border-radius:50%;';
          avatar.appendChild(img);
        } else {
          avatar.textContent = (user.name || user.email)[0].toUpperCase();
        }
      }
      // Hide username text — keep only avatar circle
      if (name) name.style.display = 'none';
    });
    savePrompts.forEach(el => el.style.display = 'none');
  } else {
    loginBtns.forEach(el => el.style.display = 'flex');
    userMenus.forEach(el => el.style.display = 'none');
    savePrompts.forEach(el => el.style.display = ''); // show prompts
  }
}

function logout() {
  clearToken();
  updateUIBasedOnAuth();
  if (typeof google !== 'undefined' && google.accounts) {
    google.accounts.id.disableAutoSelect();
  }
}

// ── Save Prompt Logic ──────────────────────────────────
function setupSavePrompt(subId) {
  const saveBtns = document.querySelectorAll('.auth-save-btn');
  saveBtns.forEach(btn => {
    btn.addEventListener('click', async () => {
      if (!isLoggedIn()) {
        // Trigger Google Sign-In
        if (typeof google !== 'undefined' && google.accounts) {
          google.accounts.id.prompt();
        }
        return;
      }
      btn.textContent = 'Saving...';
      btn.disabled = true;
      const ok = await saveResultToProfile(subId);
      if (ok) {
        btn.textContent = '✅ Saved!';
        btn.classList.add('saved');
        // Hide save prompts
        document.querySelectorAll('.auth-save-prompt').forEach(el => el.style.display = 'none');
      } else {
        btn.textContent = '❌ Failed — try again';
        btn.disabled = false;
      }
    });
  });
}

// ── Init on page load ──────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  updateUIBasedOnAuth();
});
