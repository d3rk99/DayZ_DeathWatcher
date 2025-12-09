const AUTH_STATE = {
  user: null,
};

function isAdminUser(user) {
  if (!user) return false;
  return user.role === 'admin';
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

function ensureAuthControls() {
  const headerInner = document.querySelector('.header-inner');
  if (!headerInner) return null;

  let container = document.querySelector('.auth-controls');
  if (container) return container;

  container = document.createElement('div');
  container.className = 'auth-controls';
  container.innerHTML = `
    <button class="btn btn-ghost" type="button" data-auth-login>Log in with Discord</button>
    <div class="auth-pill" data-auth-user hidden>
      <div class="pill-text">
        <span class="pill-name" data-auth-name></span>
        <span class="pill-role" data-auth-role></span>
      </div>
      <button class="pill-action" type="button" data-auth-logout>&times;</button>
    </div>
  `;

  headerInner.appendChild(container);

  const loginBtn = container.querySelector('[data-auth-login]');
  loginBtn?.addEventListener('click', () => {
    window.location.href = '/auth/discord';
  });

  const logoutBtn = container.querySelector('[data-auth-logout]');
  logoutBtn?.addEventListener('click', async () => {
    try {
      await fetch('/auth/logout', { method: 'POST' });
    } catch (err) {
      console.error('Logout failed', err);
    }
    AUTH_STATE.user = null;
    applyAuthState();
  });

  return container;
}

function applyAdminGate(user) {
  const requiresAdmin = document.body.dataset.requireAdmin === 'true';
  const content = document.querySelector('[data-admin-content]');
  const locked = document.querySelector('[data-admin-locked]');
  const isAdmin = isAdminUser(user);

  if (!requiresAdmin) return;

  if (isAdmin) {
    document.body.classList.add('admin-access');
    content?.classList.remove('is-hidden');
    locked?.classList.add('is-hidden');
  } else {
    document.body.classList.remove('admin-access');
    content?.classList.add('is-hidden');
    locked?.classList.remove('is-hidden');
  }
}

function applyAuthState() {
  const container = ensureAuthControls();
  if (!container) return;
  const loginBtn = container.querySelector('[data-auth-login]');
  const userPill = container.querySelector('[data-auth-user]');
  const nameEl = container.querySelector('[data-auth-name]');
  const roleEl = container.querySelector('[data-auth-role]');
  const user = AUTH_STATE.user;
  const isAdmin = isAdminUser(user);

  if (user) {
    if (nameEl) nameEl.textContent = user.display_name || user.discord_username || 'Logged in';
    if (roleEl) roleEl.textContent = isAdmin ? 'Admin' : 'Player';
    userPill?.removeAttribute('hidden');
    loginBtn?.setAttribute('hidden', 'hidden');
  } else {
    userPill?.setAttribute('hidden', 'hidden');
    loginBtn?.removeAttribute('hidden');
  }

  if (isAdmin) {
    showAdminNav();
  } else {
    hideAdminNav();
  }

  applyAdminGate(user);
}

async function fetchCurrentUser() {
  try {
    const res = await fetch('/auth/me', { credentials: 'same-origin' });
    if (!res.ok) throw new Error('Failed to fetch user');
    const user = await res.json();
    AUTH_STATE.user = user;
  } catch (err) {
    console.warn('Could not load current user', err);
    AUTH_STATE.user = null;
  }
  applyAuthState();
}

document.addEventListener('DOMContentLoaded', () => {
  hideAdminNav();
  ensureAuthControls();
  fetchCurrentUser();
});
