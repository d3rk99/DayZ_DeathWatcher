const AUTH_STATE = {
  user: null,
};

const API_BASE =
  window.__AUTH_API_BASE__ ||
  (window.location.protocol === 'file:' || window.location.origin === 'null'
    ? 'http://localhost:3001'
    : '');

function buildUrl(path) {
  try {
    if (API_BASE) return new URL(path, API_BASE).toString();
  } catch (err) {
    console.warn('Could not build auth URL', err);
  }
  return path;
}

function buildAuthContainer() {
  const headerInner = document.querySelector('.header-inner');
  if (!headerInner) return null;

  let container = document.querySelector('[data-auth-container]');
  if (container) return container;

  container = document.createElement('div');
  container.className = 'auth-controls';
  container.setAttribute('data-auth-container', '');
  container.innerHTML = `
    <a class="btn btn-ghost" href="${buildUrl('/auth/discord')}" data-auth-login>Login with Discord</a>
    <div class="auth-pill" data-auth-user hidden>
      <div class="pill-avatar" data-auth-avatar hidden></div>
      <div class="pill-text">
        <span class="pill-name" data-auth-name></span>
        <span class="pill-role" data-auth-role></span>
      </div>
      <a class="pill-action" href="${buildUrl('/auth/logout')}" data-auth-logout aria-label="Logout">&times;</a>
    </div>
  `;

  headerInner.appendChild(container);
  return container;
}

function hideAdminNav() {
  document.querySelectorAll('.main-nav a[href^="admin.html"]').forEach((link) => {
    const navItem = link.closest('.nav-item') || link;
    navItem.classList.add('admin-hidden');
  });
}

function showAdminNav() {
  document.querySelectorAll('.main-nav a[href^="admin.html"]').forEach((link) => {
    const navItem = link.closest('.nav-item') || link;
    navItem.classList.remove('admin-hidden');
  });
}

function applyAdminGate(user) {
  const requiresAdmin = document.body.dataset.requireAdmin === 'true';
  if (!requiresAdmin) return;

  const content = document.querySelector('[data-admin-content]');
  const locked = document.querySelector('[data-admin-locked]');
  const lockedMessage = document.querySelector('[data-admin-message]');
  const isAdmin = Boolean(user?.isAdmin);

  if (isAdmin) {
    document.body.classList.add('admin-access');
    content?.classList.remove('is-hidden');
    locked?.classList.add('is-hidden');
  } else {
    document.body.classList.remove('admin-access');
    content?.classList.add('is-hidden');
    if (locked) locked.classList.remove('is-hidden');
    if (lockedMessage) {
      lockedMessage.textContent = user
        ? 'You are not authorized to view the admin console.'
        : 'Log in with Discord to verify you can access the admin console.';
    }
  }
}

function applyLoginRequirement(user) {
  const requiresAuth = document.body.dataset.requireAuth === 'true';
  if (!requiresAuth) return;

  const gatedSections = document.querySelectorAll('[data-requires-login]');
  const prompts = document.querySelectorAll('[data-login-prompt]');
  const isAuthed = Boolean(user);

  prompts.forEach((prompt) => {
    prompt.querySelectorAll('[data-auth-login-cta]').forEach((cta) => {
      cta.setAttribute('href', buildUrl('/auth/discord'));
    });
  });

  gatedSections.forEach((section) => {
    section.classList.toggle('is-hidden', !isAuthed);
  });

  prompts.forEach((prompt) => {
    prompt.classList.toggle('is-hidden', isAuthed);
  });
}

function applyAuthState() {
  const container = buildAuthContainer();
  if (!container) return;

  const loginLink = container.querySelector('[data-auth-login]');
  const userPill = container.querySelector('[data-auth-user]');
  const nameEl = container.querySelector('[data-auth-name]');
  const roleEl = container.querySelector('[data-auth-role]');
  const avatarEl = container.querySelector('[data-auth-avatar]');

  const user = AUTH_STATE.user;
  const isAdmin = Boolean(user?.isAdmin);

  if (user) {
    if (nameEl) nameEl.textContent = user.username || 'Logged in';
    if (roleEl) roleEl.textContent = isAdmin ? 'Admin' : 'Player';
    if (avatarEl) {
      if (user.avatar) {
        avatarEl.removeAttribute('hidden');
        avatarEl.style.backgroundImage = `url(${user.avatar})`;
      } else {
        avatarEl.setAttribute('hidden', 'hidden');
        avatarEl.style.backgroundImage = '';
      }
    }
    userPill?.removeAttribute('hidden');
    loginLink?.setAttribute('hidden', 'hidden');
  } else {
    userPill?.setAttribute('hidden', 'hidden');
    loginLink?.removeAttribute('hidden');
  }

  if (isAdmin) {
    showAdminNav();
  } else {
    hideAdminNav();
  }

  applyLoginRequirement(user);
  applyAdminGate(user);
}

async function fetchCurrentUser() {
  try {
    const res = await fetch(buildUrl('/auth/me'), { credentials: 'same-origin' });
    if (!res.ok) throw new Error('Failed to fetch user');
    const payload = await res.json();
    AUTH_STATE.user = payload?.user || null;
  } catch (err) {
    console.warn('Could not load current user', err);
    AUTH_STATE.user = null;
  }
  applyAuthState();
}

window.addEventListener('DOMContentLoaded', () => {
  hideAdminNav();
  buildAuthContainer();
  fetchCurrentUser();
});
