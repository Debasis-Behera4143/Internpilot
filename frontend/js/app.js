/**
 * InternPilot - Professional Student Career & Opportunity Portal
 * Unified Minimalist Application JavaScript Logic
 */

// ==========================================================================
// APPLICATION STATE
// ==========================================================================

const state = {
  activeTab: 'home',
  adminSection: 'overview',
  token: localStorage.getItem('internpilot_token') || null,
  user: JSON.parse(localStorage.getItem('internpilot_user') || 'null') || {
    id: 'default_student',
    email: 'debasis.behera@example.edu',
    name: 'Debasis Behera',
    role: 'STUDENT'
  },
  savedIds: new Set(),
  search: {
    q: '',
    location: '',
    type: 'all',
    workMode: '',
    experience: '',
    skills: '',
    company: '',
    postedWithinDays: '',
    hasSalary: false,
    verifiedOnly: true,
    sortBy: 'newest',
    page: 1,
    limit: 15,
    total: 0,
    totalPages: 1
  },
  currentOpportunities: [],
  currentRecommendations: [],
  activeDetailOpp: null
};

// ==========================================================================
// INITIALIZATION
// ==========================================================================

document.addEventListener('DOMContentLoaded', async () => {
  updateUserInterface();
  await loadSavedIds();
  await loadHomeFeeds();
  await executeSearch();
});

// ==========================================================================
// API CLIENT & AUTHENTICATION
// ==========================================================================

async function fetchWithAuth(url, options = {}) {
  const headers = options.headers || {};
  if (state.token) {
    headers['Authorization'] = `Bearer ${state.token}`;
  }
  options.headers = headers;

  try {
    const res = await fetch(url, options);
    if (res.status === 401) {
      state.token = null;
      localStorage.removeItem('internpilot_token');
      updateUserInterface();
    }
    return res;
  } catch (err) {
    console.error('API Network Error:', err);
    throw err;
  }
}

function updateUserInterface() {
  const userNameEl = document.getElementById('current-user-name');
  const userRoleEl = document.getElementById('current-user-role');
  const authBtn = document.getElementById('btn-auth-action');
  const logoutBtn = document.getElementById('btn-logout-action');
  const adminNav = document.getElementById('admin-nav-container');

  // Admin panel operator details elements
  const admOpName = document.getElementById('admin-operator-name');
  const admOpEmail = document.getElementById('admin-operator-email');
  const admOpRole = document.getElementById('admin-operator-role');
  const admOpAvatar = document.getElementById('admin-operator-avatar');
  const admActName = document.getElementById('adm-active-user-name');
  const admActEmail = document.getElementById('adm-active-user-email');
  const admActRole = document.getElementById('adm-active-user-role');

  if (state.user) {
    const displayName = state.user.name || (state.user.role === 'ADMIN' ? 'Debasis Behera' : 'Debasis Behera');
    const displayEmail = state.user.email || 'admin@careerhub.local';
    const displayRole = state.user.role === 'ADMIN' ? 'SYSTEM ADMINISTRATOR' : 'STUDENT CANDIDATE';
    const initials = displayName.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase() || 'DB';

    if (userNameEl) userNameEl.textContent = displayName;
    if (userRoleEl) {
      userRoleEl.textContent = state.user.role || 'STUDENT';
      userRoleEl.className = `role-tag ${state.user.role === 'ADMIN' ? 'admin' : ''}`;
    }
    if (authBtn) authBtn.style.display = 'none';
    if (logoutBtn) logoutBtn.style.display = 'inline-block';
    if (adminNav) adminNav.style.display = 'block';

    if (admOpName) admOpName.textContent = displayName;
    if (admOpEmail) admOpEmail.textContent = displayEmail;
    if (admOpRole) admOpRole.textContent = state.user.role === 'ADMIN' ? 'SYSTEM ADMIN' : state.user.role;
    if (admOpAvatar) admOpAvatar.textContent = initials;
    if (admActName) admActName.textContent = displayName;
    if (admActEmail) admActEmail.textContent = displayEmail;
    if (admActRole) admActRole.textContent = displayRole;
  } else {
    if (userNameEl) userNameEl.textContent = 'Guest';
    if (userRoleEl) {
      userRoleEl.textContent = 'GUEST';
      userRoleEl.className = 'role-tag';
    }
    if (authBtn) authBtn.style.display = 'inline-block';
    if (logoutBtn) logoutBtn.style.display = 'none';
    if (adminNav) adminNav.style.display = 'block';
  }
}

async function handleLogout() {
  if (state.token) {
    try {
      await fetchWithAuth('/api/auth/logout', { method: 'POST' });
    } catch (e) {
      console.warn('Logout API failed:', e);
    }
  }
  state.token = null;
  state.user = null;
  localStorage.removeItem('internpilot_token');
  localStorage.removeItem('internpilot_user');
  updateUserInterface();
  showToast('Signed out successfully.');
  switchTab('home');
}

// ==========================================================================
// DEMO PERSONA SWITCHING
// ==========================================================================

async function switchDemoPersona(personaId) {
  try {
    const btnA = document.getElementById('btn-demo-a');
    const btnB = document.getElementById('btn-demo-b');
    const btnAdmin = document.getElementById('btn-demo-admin');

    if (personaId === 'admin') {
      if (btnA) btnA.classList.remove('active');
      if (btnB) btnB.classList.remove('active');
      if (btnAdmin) btnAdmin.classList.add('active');

      try {
        const loginRes = await fetch('/api/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email: 'admin@careerhub.local', password: 'CareerHubAdmin2026!' })
        });
        if (loginRes.ok) {
          const authData = await loginRes.json();
          state.token = authData.access_token;
          state.user = {
            id: authData.user?.id || 'admin_user',
            email: 'admin@careerhub.local',
            name: 'Debasis Behera',
            role: 'ADMIN'
          };
          localStorage.setItem('internpilot_token', state.token);
          localStorage.setItem('internpilot_user', JSON.stringify(state.user));
          updateUserInterface();
          showToast('Switched to Admin Mode: Debasis Behera (SYSTEM ADMIN)');
          switchTab('admin');
          switchAdminSection('dashboard');
          return;
        }
      } catch (e) {
        console.warn('Admin auto-login failed:', e);
      }
    } else {
      if (btnAdmin) btnAdmin.classList.remove('active');
      if (personaId === 'student_a') {
        if (btnA) btnA.classList.add('active');
        if (btnB) btnB.classList.remove('active');
      } else {
        if (btnA) btnA.classList.remove('active');
        if (btnB) btnB.classList.add('active');
      }
    }

    const res = await fetch(`/api/student/demo/${personaId}`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to switch persona');
    
    // Auto login
    const email = (personaId === 'student_a') ? 'debasis.behera@example.edu' : 'priya.web@example.edu';
    const name = (personaId === 'student_a') ? 'Debasis Behera' : 'Priya Patel';

    state.user = {
      id: personaId,
      email: email,
      name: name,
      role: 'STUDENT'
    };
    localStorage.setItem('internpilot_user', JSON.stringify(state.user));
    updateUserInterface();
    showToast(`Switched candidate profile to: ${name}`);

    await loadSavedIds();
    if (state.activeTab === 'home') loadHomeFeeds();
    if (state.activeTab === 'jobs') executeSearch();
    if (state.activeTab === 'recommended') loadRecommendations();
    if (state.activeTab === 'profile') loadProfile();
  } catch (e) {
    showToast('Error switching persona: ' + e.message);
  }
}

// ==========================================================================
// NAVIGATION & TABS
// ==========================================================================

function switchTab(tabId) {
  state.activeTab = tabId;

  document.querySelectorAll('.tab-view').forEach(el => el.classList.remove('active'));
  const targetView = document.getElementById(`tab-${tabId}`);
  if (targetView) targetView.classList.add('active');

  document.querySelectorAll('.nav-link').forEach(el => {
    if (el.getAttribute('data-tab') === tabId) {
      el.classList.add('active');
    } else {
      el.classList.remove('active');
    }
  });

  const navMenu = document.getElementById('nav-menu');
  if (navMenu) navMenu.classList.remove('mobile-open');

  if (tabId === 'home') {
    loadHomeFeeds();
  } else if (tabId === 'jobs') {
    executeSearch();
  } else if (tabId === 'recommended') {
    loadRecommendations();
  } else if (tabId === 'saved') {
    loadSavedOpportunities();
  } else if (tabId === 'applications') {
    loadApplications();
  } else if (tabId === 'profile') {
    loadProfile();
  } else if (tabId === 'admin') {
    if (!state.token || state.user?.role !== 'ADMIN') {
      fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: 'admin@careerhub.local', password: 'CareerHubAdmin2026!' })
      }).then(r => r.json()).then(data => {
        if (data.access_token) {
          state.token = data.access_token;
          state.user = {
            id: data.user?.id || 'admin_user',
            email: 'admin@careerhub.local',
            name: 'CareerHub Admin',
            role: 'ADMIN'
          };
          localStorage.setItem('internpilot_token', state.token);
          localStorage.setItem('internpilot_user', JSON.stringify(state.user));
          updateUserInterface();
          switchAdminSection(state.adminSection || 'sources');
        }
      }).catch(err => {
        switchAdminSection(state.adminSection || 'sources');
      });
    } else {
      switchAdminSection(state.adminSection || 'sources');
    }
  }

  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function toggleMobileMenu() {
  const navMenu = document.getElementById('nav-menu');
  if (navMenu) navMenu.classList.toggle('mobile-open');
}

// ==========================================================================
// HOME PAGE SEARCH & FEEDS
// ==========================================================================

function executeHomeSearch() {
  const q = document.getElementById('home-search-query')?.value.trim() || '';
  const loc = document.getElementById('home-search-location')?.value.trim() || '';
  
  const qInput = document.getElementById('search-query-input');
  const locInput = document.getElementById('search-location-input');
  if (qInput) qInput.value = q;
  if (locInput) locInput.value = loc;

  state.search.q = q;
  state.search.location = loc;
  state.search.page = 1;

  switchTab('jobs');
}

function quickFilterHome(filterType) {
  resetAllFilters(false);
  if (filterType === 'internship') state.search.type = 'internship';
  else if (filterType === 'job') state.search.type = 'job';
  else if (filterType === 'remote') state.search.workMode = 'remote';
  else if (filterType === 'fresher') state.search.experience = 'fresher';
  else if (filterType === 'verified') state.search.verifiedOnly = true;

  switchTab('jobs');
}

async function loadHomeFeeds() {
  const recContainer = document.getElementById('home-rec-list');
  const latestContainer = document.getElementById('home-latest-list');

  // Load 3 top recommendations
  if (recContainer) {
    try {
      const res = await fetchWithAuth('/api/matching/recommendations?min_score=30&limit=3');
      if (res.ok) {
        const recs = await res.json();
        const mapped = (Array.isArray(recs) ? recs : []).slice(0, 3).map(r => ({
          id: r.opportunity_id || r.id,
          title: r.title,
          company: r.company,
          location: r.location,
          opportunity_type: r.opportunity_type,
          experience: r.experience,
          stipend: r.stipend,
          salary: r.salary,
          skills: r.matched_skills || [],
          apply_url: r.apply_url,
          verification_status: r.verification_status || 'VERIFIED',
          deadline: r.deadline,
          match_score: r.match_score
        }));
        renderOpportunityCards(recContainer, mapped, true);
      }
    } catch (e) {
      console.warn('Error loading home recs:', e);
    }
  }

  // Load 4 latest verified opportunities
  if (latestContainer) {
    try {
      const res = await fetch('/api/opportunities?limit=4&sort_by=newest');
      if (res.ok) {
        const items = await res.json();
        renderOpportunityCards(latestContainer, Array.isArray(items) ? items : (items.items || []));
      }
    } catch (e) {
      console.warn('Error loading latest verified:', e);
    }
  }
}

// ==========================================================================
// FIND OPPORTUNITIES (SEARCH & FILTER ENGINE)
// ==========================================================================

function handleSearchInput(event) {
  if (event.key === 'Enter') {
    executeSearch();
  }
}

function executeSearch() {
  const queryInput = document.getElementById('search-query-input');
  const locInput = document.getElementById('search-location-input');

  state.search.q = queryInput ? queryInput.value.trim() : '';
  state.search.location = locInput ? locInput.value.trim() : '';
  state.search.page = 1;

  loadOpportunities();
}

function setQuickTypeFilter(typeVal) {
  state.search.type = typeVal;
  state.search.page = 1;

  document.querySelectorAll('.filter-pill[data-filter]').forEach(el => {
    const f = el.getAttribute('data-filter');
    if (['all', 'job', 'internship', 'apprenticeship', 'fulltime', 'parttime'].includes(f)) {
      if (f === typeVal) el.classList.add('active');
      else el.classList.remove('active');
    }
  });

  loadOpportunities();
}

function toggleQuickWorkMode(modeVal) {
  state.search.workMode = (state.search.workMode === modeVal) ? '' : modeVal;
  state.search.page = 1;

  document.querySelectorAll('.filter-pill[data-filter]').forEach(el => {
    const f = el.getAttribute('data-filter');
    if (['remote', 'hybrid', 'onsite'].includes(f)) {
      if (f === state.search.workMode) el.classList.add('active');
      else el.classList.remove('active');
    }
  });

  loadOpportunities();
}

function toggleQuickExperience(expVal) {
  state.search.experience = (state.search.experience === expVal) ? '' : expVal;
  state.search.page = 1;

  document.querySelectorAll('.filter-pill[data-filter]').forEach(el => {
    const f = el.getAttribute('data-filter');
    if (['fresher', 'experienced'].includes(f)) {
      if (f === state.search.experience) el.classList.add('active');
      else el.classList.remove('active');
    }
  });

  loadOpportunities();
}

function applyCompactFilters() {
  const locVal = document.getElementById('filter-location-input')?.value.trim() || '';
  const roleVal = document.getElementById('filter-role-input')?.value.trim() || '';
  const skillsVal = document.getElementById('filter-skills-input')?.value.trim() || '';
  const compVal = document.getElementById('filter-company-input')?.value.trim() || '';
  const salVal = document.getElementById('filter-salary-select')?.value || '';
  const postedVal = document.getElementById('filter-posted-select')?.value || '';
  const verifOnly = document.getElementById('filter-verified-only')?.checked !== false;

  state.search.location = locVal;
  if (roleVal) state.search.q = roleVal;
  state.search.skills = skillsVal;
  state.search.company = compVal;
  state.search.hasSalary = (salVal === 'has_salary' || salVal === 'high');
  state.search.postedWithinDays = postedVal;
  state.search.verifiedOnly = verifOnly;
  state.search.page = 1;

  loadOpportunities();
}

function resetAllFilters() {
  state.search = {
    q: '',
    location: '',
    type: 'all',
    workMode: '',
    experience: '',
    skills: '',
    company: '',
    postedWithinDays: '',
    hasSalary: false,
    verifiedOnly: true,
    sortBy: 'newest',
    page: 1,
    limit: 15,
    total: 0,
    totalPages: 1
  };

  const qInp = document.getElementById('search-query-input');
  const locInp = document.getElementById('search-location-input');
  const fLoc = document.getElementById('filter-location-input');
  const fRole = document.getElementById('filter-role-input');
  const fSkills = document.getElementById('filter-skills-input');
  const fComp = document.getElementById('filter-company-input');
  const fSal = document.getElementById('filter-salary-select');
  const fPost = document.getElementById('filter-posted-select');
  const fVerif = document.getElementById('filter-verified-only');

  if (qInp) qInp.value = '';
  if (locInp) locInp.value = '';
  if (fLoc) fLoc.value = '';
  if (fRole) fRole.value = '';
  if (fSkills) fSkills.value = '';
  if (fComp) fComp.value = '';
  if (fSal) fSal.value = '';
  if (fPost) fPost.value = '';
  if (fVerif) fVerif.checked = true;

  document.querySelectorAll('.filter-pill[data-filter]').forEach(el => {
    if (el.getAttribute('data-filter') === 'all') el.classList.add('active');
    else el.classList.remove('active');
  });

  loadOpportunities();
}

function handleSortChange() {
  const sortSel = document.getElementById('sort-select');
  if (sortSel) {
    state.search.sortBy = sortSel.value;
    state.search.page = 1;
    loadOpportunities();
  }
}

async function loadOpportunities() {
  const container = document.getElementById('jobs-cards-list');
  if (!container) return;

  container.innerHTML = `<div style="padding: 2.5rem; text-align: center; color: var(--text-secondary);">Loading verified opportunities...</div>`;

  const params = new URLSearchParams();
  if (state.search.q) params.append('q', state.search.q);
  if (state.search.location) params.append('location', state.search.location);
  if (state.search.type && state.search.type !== 'all') params.append('type', state.search.type);
  if (state.search.workMode) params.append('work_mode', state.search.workMode);
  if (state.search.experience) params.append('experience', state.search.experience);
  if (state.search.skills) params.append('skill', state.search.skills);
  if (state.search.company) params.append('company', state.search.company);
  if (state.search.postedWithinDays) params.append('posted_within_days', state.search.postedWithinDays);
  if (state.search.hasSalary) params.append('has_salary', 'true');
  if (state.search.sortBy) params.append('sort_by', state.search.sortBy);

  params.append('limit', state.search.limit);
  params.append('page', state.search.page);

  try {
    const res = await fetchWithAuth(`/api/opportunities?${params.toString()}`);
    if (!res.ok) throw new Error('Failed to load opportunities');

    const totalCount = parseInt(res.headers.get('X-Total-Count') || '0', 10);
    const totalPages = parseInt(res.headers.get('X-Total-Pages') || '1', 10);
    const currentPage = parseInt(res.headers.get('X-Page') || '1', 10);

    state.search.total = totalCount;
    state.search.totalPages = totalPages;
    state.search.page = currentPage;

    const items = await res.json();
    state.currentOpportunities = Array.isArray(items) ? items : (items.items || []);

    const countNumEl = document.getElementById('results-count-num');
    if (countNumEl) countNumEl.textContent = totalCount;

    renderOpportunityCards(container, state.currentOpportunities);
    renderPagination();
  } catch (err) {
    console.error('Error loading opportunities:', err);
    container.innerHTML = `<div style="padding: 2rem; text-align: center; color: var(--danger);">Failed to load opportunities: ${escapeHtml(err.message)}</div>`;
  }
}

async function triggerFeedRefresh() {
  const refreshBtns = [
    document.getElementById('btn-home-refresh-jobs'),
    document.getElementById('btn-refresh-feed')
  ].filter(Boolean);

  refreshBtns.forEach(btn => {
    btn.disabled = true;
    btn.innerHTML = '⏳ Checking channels...';
  });

  try {
    showToast('Checking Telegram channels & feeds for new jobs posted today...');
    const res = await fetchWithAuth('/api/opportunities/refresh', { method: 'POST' });
    if (!res.ok) throw new Error('Refresh request failed');
    const data = await res.json();
    const rep = data.report || {};
    const newCount = rep.saved || rep.new_added || rep.verified || 0;
    
    if (newCount > 0) {
      showToast(`Success! Found and published ${newCount} new opportunities.`);
    } else {
      showToast('All sources up to date. Latest jobs are already loaded.');
    }

    // Reload both home feeds and main opportunity list
    await loadHomeFeeds();
    state.search.page = 1;
    await executeSearch();
  } catch (err) {
    console.error('Error refreshing feed:', err);
    showToast(`Refresh notice: ${err.message}`);
  } finally {
    refreshBtns.forEach(btn => {
      btn.disabled = false;
      btn.innerHTML = btn.id === 'btn-home-refresh-jobs' ? '🔄 Fetch Latest Jobs' : '🔄 Check for New Jobs';
    });
  }
}

function renderOpportunityCards(container, items, showMatchScore = false) {
  if (!items || items.length === 0) {
    container.innerHTML = `
      <div style="background: var(--bg-surface); border: 1px solid var(--border-color); border-radius: var(--radius-lg); padding: 3rem 1.5rem; text-align: center;">
        <h3 style="font-size: 1.1rem; font-weight: 600; color: var(--text-primary); margin-bottom: 0.5rem;">No matching opportunities found</h3>
        <p style="font-size: 0.875rem; color: var(--text-secondary); margin-bottom: 1rem;">Try adjusting search terms, clearing location, or resetting filters.</p>
        <button class="btn btn-secondary btn-sm" onclick="resetAllFilters()">Clear All Filters</button>
      </div>
    `;
    return;
  }

  container.innerHTML = items.map(opp => {
    const isSaved = state.savedIds.has(opp.id);
    const stipendOrSalary = opp.stipend || opp.salary || null;
    const isVerified = (opp.verification_status === 'VERIFIED');
    const deadlineStr = opp.deadline ? `Deadline: ${opp.deadline}` : 'No deadline';
    const postedStr = opp.posted_date ? `Posted ${opp.posted_date}` : 'Recently posted';
    const workModeStr = opp.work_mode || (opp.remote ? 'Remote' : 'On-site');
    const targetApplyUrl = opp.application_url || opp.apply_url || '#';

    return `
      <div class="opp-card" onclick="openDetailDrawer('${opp.id}')">
        <div class="opp-card-main">
          <div class="opp-company-row">
            <span class="opp-company-name">${escapeHtml(opp.company || 'Hiring Company')}</span>
            ${isVerified ? `<span class="badge-verified">✓ Verified</span>` : ''}
          </div>

          <h3 class="opp-title">${escapeHtml(opp.title)}</h3>

          <div class="opp-meta-row">
            <span class="meta-item">📍 ${escapeHtml(opp.location || 'Remote')}</span>
            <span class="meta-dot-sep">&bull;</span>
            <span class="meta-item">💼 ${escapeHtml(formatOpportunityType(opp.opportunity_type))}</span>
            <span class="meta-dot-sep">&bull;</span>
            <span class="meta-item">🌐 ${escapeHtml(workModeStr)}</span>
            ${stipendOrSalary ? `
              <span class="meta-dot-sep">&bull;</span>
              <span class="meta-item" style="font-weight: 600; color: #047857;">💰 ${escapeHtml(stipendOrSalary)}</span>
            ` : ''}
          </div>

          <div class="opp-meta-row" style="font-size: 0.8rem; color: var(--text-muted); margin-top: 0.35rem;">
            <span>📅 ${escapeHtml(postedStr)}</span>
            <span class="meta-dot-sep">&bull;</span>
            <span style="color: #b45309; font-weight: 500;">⏳ ${escapeHtml(deadlineStr)}</span>
          </div>
        </div>

        <div class="opp-card-actions">
          <div class="opp-card-actions-row">
            <button class="btn btn-secondary btn-sm" onclick="event.stopPropagation(); toggleBookmark('${opp.id}')">
              ${isSaved ? '★ Saved' : '☆ Save'}
            </button>
            <a href="${escapeHtml(targetApplyUrl)}" target="_blank" rel="noopener noreferrer" class="btn btn-primary btn-sm" onclick="event.stopPropagation();">Apply Now ↗</a>
          </div>
        </div>
      </div>
    `;
  }).join('');
}

function formatOpportunityType(typeStr) {
  if (!typeStr) return 'Internship';
  const clean = typeStr.toLowerCase();
  if (clean.includes('intern')) return 'Internship';
  if (clean.includes('full')) return 'Full-time';
  if (clean.includes('part')) return 'Part-time';
  if (clean.includes('apprentice')) return 'Apprenticeship';
  return typeStr.charAt(0).toUpperCase() + typeStr.slice(1);
}

function renderPagination() {
  const container = document.getElementById('pagination-buttons');
  const infoEl = document.getElementById('pagination-info');
  if (!container) return;

  const { page, totalPages, total, limit } = state.search;
  const startIdx = total === 0 ? 0 : (page - 1) * limit + 1;
  const endIdx = Math.min(total, page * limit);

  if (infoEl) {
    infoEl.textContent = `Showing ${startIdx} - ${endIdx} of ${total} opportunities`;
  }

  if (totalPages <= 1) {
    container.innerHTML = '';
    return;
  }

  let html = `
    <button class="page-btn" ${page <= 1 ? 'disabled' : ''} onclick="changePage(${page - 1})">&larr;</button>
  `;

  for (let i = 1; i <= totalPages; i++) {
    if (i === 1 || i === totalPages || (i >= page - 1 && i <= page + 1)) {
      html += `<button class="page-btn ${i === page ? 'active' : ''}" onclick="changePage(${i})">${i}</button>`;
    } else if (i === page - 2 || i === page + 2) {
      html += `<span style="padding: 0 0.25rem; color: var(--text-muted);">&hellip;</span>`;
    }
  }

  html += `
    <button class="page-btn" ${page >= totalPages ? 'disabled' : ''} onclick="changePage(${page + 1})">&rarr;</button>
  `;

  container.innerHTML = html;
}

function changePage(newPage) {
  if (newPage >= 1 && newPage <= state.search.totalPages) {
    state.search.page = newPage;
    loadOpportunities();
    window.scrollTo({ top: 150, behavior: 'smooth' });
  }
}

function resetAllFilters(reload = true) {
  state.search = {
    q: '',
    location: '',
    type: 'all',
    workMode: '',
    experience: '',
    skills: '',
    company: '',
    postedWithinDays: '',
    hasSalary: false,
    verifiedOnly: true,
    sortBy: 'newest',
    page: 1,
    limit: 15,
    total: 0,
    totalPages: 1
  };

  const qInput = document.getElementById('search-query-input');
  const locInput = document.getElementById('search-location-input');
  const skillInput = document.getElementById('sidebar-skill-input');
  const compInput = document.getElementById('sidebar-company-input');
  const dateSel = document.getElementById('sidebar-date-select');
  const salCheck = document.getElementById('sidebar-has-salary');
  const verifCheck = document.getElementById('sidebar-verified-only');

  if (qInput) qInput.value = '';
  if (locInput) locInput.value = '';
  if (skillInput) skillInput.value = '';
  if (compInput) compInput.value = '';
  if (dateSel) dateSel.value = '';
  if (salCheck) salCheck.checked = false;
  if (verifCheck) verifCheck.checked = true;

  document.querySelectorAll('.sidebar-filter-type, .sidebar-filter-mode, .sidebar-filter-exp').forEach(el => el.checked = false);
  document.querySelectorAll('.filter-pill').forEach(el => {
    el.classList.remove('active');
    if (el.getAttribute('data-filter') === 'all') el.classList.add('active');
  });

  if (reload) loadOpportunities();
}

// ==========================================================================
// RECOMMENDED TAB
// ==========================================================================

async function loadRecommendations() {
  const container = document.getElementById('rec-cards-list');
  const minScoreSel = document.getElementById('rec-min-score');
  const minScore = minScoreSel ? minScoreSel.value : '40';

  if (!container) return;
  container.innerHTML = `<div style="padding: 2.5rem; text-align: center; color: var(--text-secondary);">Calculating personalized match ranking...</div>`;

  try {
    const res = await fetchWithAuth(`/api/matching/recommendations?min_score=${minScore}&limit=30`);
    if (!res.ok) throw new Error('Failed to retrieve recommendations');

    const recs = await res.json();
    state.currentRecommendations = Array.isArray(recs) ? recs : [];

    const mappedItems = state.currentRecommendations.map(r => ({
      id: r.opportunity_id || r.id,
      title: r.title,
      company: r.company,
      location: r.location,
      opportunity_type: r.opportunity_type,
      experience: r.experience,
      stipend: r.stipend,
      salary: r.salary,
      skills: r.matched_skills || [],
      apply_url: r.apply_url,
      verification_status: r.verification_status || 'VERIFIED',
      deadline: r.deadline,
      match_score: r.match_score,
      explanation: r.explanation,
      matched_skills: r.matched_skills,
      missing_skills: r.missing_skills
    }));

    renderOpportunityCards(container, mappedItems, true);
  } catch (err) {
    console.error('Error loading recommendations:', err);
    container.innerHTML = `<div style="padding: 2rem; text-align: center; color: var(--danger);">Failed to load recommendations: ${escapeHtml(err.message)}</div>`;
  }
}

// ==========================================================================
// SAVED OPPORTUNITIES & BOOKMARKING
// ==========================================================================

async function loadSavedIds() {
  try {
    const res = await fetchWithAuth('/api/opportunities/saved/ids');
    if (res.ok) {
      const data = await res.json();
      state.savedIds = new Set(data.saved_ids || []);
      updateSavedBadges();
    }
  } catch (e) {
    console.warn('Error loading saved IDs:', e);
  }
}

function updateSavedBadges() {
  const badge = document.getElementById('badge-saved-count');
  const countNum = document.getElementById('saved-count-num');
  if (badge) badge.textContent = state.savedIds.size;
  if (countNum) countNum.textContent = state.savedIds.size;
}

async function toggleBookmark(oppId) {
  const isSaved = state.savedIds.has(oppId);
  try {
    if (isSaved) {
      const res = await fetchWithAuth(`/api/opportunities/${oppId}/save`, { method: 'DELETE' });
      if (res.ok) {
        state.savedIds.delete(oppId);
        showToast('Removed from Saved.');
      }
    } else {
      const res = await fetchWithAuth(`/api/opportunities/${oppId}/save`, { method: 'POST' });
      if (res.ok) {
        state.savedIds.add(oppId);
        showToast('Saved to bookmarks.');
      }
    }
    updateSavedBadges();

    if (state.activeTab === 'jobs') {
      renderOpportunityCards(document.getElementById('jobs-cards-list'), state.currentOpportunities);
    } else if (state.activeTab === 'saved') {
      await loadSavedOpportunities();
    }
  } catch (err) {
    console.error('Error toggling bookmark:', err);
  }
}

async function loadSavedOpportunities() {
  const container = document.getElementById('saved-cards-list');
  if (!container) return;

  container.innerHTML = `<div style="padding: 2.5rem; text-align: center; color: var(--text-secondary);">Loading saved opportunities...</div>`;

  try {
    const res = await fetchWithAuth('/api/opportunities/saved');
    if (!res.ok) throw new Error('Failed to load saved opportunities');

    const items = await res.json();
    const savedList = Array.isArray(items) ? items : [];

    state.savedIds = new Set(savedList.map(o => o.id));
    updateSavedBadges();

    renderOpportunityCards(container, savedList);
  } catch (err) {
    console.error('Error loading saved opportunities:', err);
    container.innerHTML = `<div style="padding: 2rem; text-align: center; color: var(--danger);">Failed to load saved opportunities: ${escapeHtml(err.message)}</div>`;
  }
}

// ==========================================================================
// JOB DETAILS SLIDE-OVER DRAWER
// ==========================================================================

async function openDetailDrawer(oppId) {
  const overlay = document.getElementById('details-drawer-overlay');
  const drawer = document.getElementById('details-drawer');
  if (!drawer) return;

  let opp = state.currentOpportunities.find(o => o.id === oppId) ||
            state.currentRecommendations.find(o => (o.opportunity_id || o.id) === oppId);

  if (!opp) {
    try {
      const res = await fetchWithAuth(`/api/opportunities/${oppId}`);
      if (res.ok) opp = await res.json();
    } catch (e) {
      console.warn('Error fetching opportunity detail:', e);
    }
  }

  if (!opp) {
    showToast('Opportunity details not available or expired.');
    return;
  }

  state.activeDetailOpp = opp;

  document.getElementById('drawer-opp-title').textContent = opp.title || 'Opportunity Title';
  document.getElementById('drawer-opp-company').textContent = opp.company || 'Hiring Company';

  const bodyEl = document.getElementById('drawer-opp-body');
  const skills = Array.isArray(opp.skills) ? opp.skills : [];
  const stipendOrSal = opp.stipend || opp.salary || 'Not Disclosed';
  const deadline = opp.deadline || 'Open / Ongoing';

  bodyEl.innerHTML = `
    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; background: var(--bg-page); border: 1px solid var(--border-color); border-radius: var(--radius-md); padding: 1rem;">
      <div>
        <span style="font-size: 0.72rem; font-weight: 600; color: var(--text-muted); text-transform: uppercase;">Location & Mode</span>
        <div style="font-size: 0.875rem; font-weight: 600; color: var(--text-primary);">${escapeHtml(opp.location || 'Remote')}</div>
      </div>
      <div>
        <span style="font-size: 0.72rem; font-weight: 600; color: var(--text-muted); text-transform: uppercase;">Role Type</span>
        <div style="font-size: 0.875rem; font-weight: 600; color: var(--text-primary);">${escapeHtml(formatOpportunityType(opp.opportunity_type))}</div>
      </div>
      <div>
        <span style="font-size: 0.72rem; font-weight: 600; color: var(--text-muted); text-transform: uppercase;">Experience</span>
        <div style="font-size: 0.875rem; font-weight: 600; color: var(--text-primary);">${escapeHtml(opp.experience || 'Fresher')}</div>
      </div>
      <div>
        <span style="font-size: 0.72rem; font-weight: 600; color: var(--text-muted); text-transform: uppercase;">Stipend / Salary</span>
        <div style="font-size: 0.875rem; font-weight: 600; color: #047857;">${escapeHtml(stipendOrSal)}</div>
      </div>
      <div>
        <span style="font-size: 0.72rem; font-weight: 600; color: var(--text-muted); text-transform: uppercase;">Deadline</span>
        <div style="font-size: 0.875rem; font-weight: 600; color: var(--text-primary);">${escapeHtml(deadline)}</div>
      </div>
      <div>
        <span style="font-size: 0.72rem; font-weight: 600; color: var(--text-muted); text-transform: uppercase;">Status</span>
        <div style="font-size: 0.875rem; font-weight: 600; color: var(--success-text);">✓ Verified Listing</div>
      </div>
    </div>

    <div>
      <h4 style="font-size: 0.85rem; font-weight: 700; color: var(--text-primary); text-transform: uppercase; margin-bottom: 0.4rem;">Skills</h4>
      <div class="opp-tags-row">
        ${skills.length > 0 ? skills.map(s => `<span class="opp-tag">${escapeHtml(s)}</span>`).join('') : '<span style="font-size: 0.8rem; color: var(--text-muted);">None specified</span>'}
      </div>
    </div>

    <div>
      <h4 style="font-size: 0.85rem; font-weight: 700; color: var(--text-primary); text-transform: uppercase; margin-bottom: 0.4rem;">Eligibility</h4>
      <p style="font-size: 0.875rem; color: var(--text-secondary);">${escapeHtml(opp.eligibility || 'Open to all students and freshers.')}</p>
    </div>

    <div>
      <h4 style="font-size: 0.85rem; font-weight: 700; color: var(--text-primary); text-transform: uppercase; margin-bottom: 0.4rem;">About The Role</h4>
      <p style="font-size: 0.875rem; color: var(--text-secondary); line-height: 1.6; white-space: pre-line;">${escapeHtml(opp.description || 'No additional description provided.')}</p>
    </div>
  `;

  const saveBtn = document.getElementById('drawer-save-btn');
  if (saveBtn) {
    const isSaved = state.savedIds.has(opp.id);
    saveBtn.textContent = isSaved ? '★ Bookmarked' : '☆ Bookmark';
  }

  const applyLink = document.getElementById('drawer-apply-link');
  if (applyLink) {
    applyLink.href = opp.apply_url || '#';
  }

  if (overlay) overlay.classList.add('active');
  drawer.classList.add('active');
  document.body.style.overflow = 'hidden';
}

function closeDetailsDrawer() {
  const overlay = document.getElementById('details-drawer-overlay');
  const drawer = document.getElementById('details-drawer');
  if (overlay) overlay.classList.remove('active');
  if (drawer) drawer.classList.remove('active');
  document.body.style.overflow = '';
}

function toggleSaveCurrentDrawer() {
  if (state.activeDetailOpp) {
    toggleBookmark(state.activeDetailOpp.id);
    const saveBtn = document.getElementById('drawer-save-btn');
    const isSaved = state.savedIds.has(state.activeDetailOpp.id);
    if (saveBtn) saveBtn.textContent = isSaved ? '★ Bookmarked' : '☆ Bookmark';
  }
}

// ==========================================================================
// MOBILE FILTER DRAWER
// ==========================================================================

function openFilterDrawer() {
  const overlay = document.getElementById('filter-drawer-overlay');
  const drawer = document.getElementById('filter-drawer');
  const content = document.getElementById('mobile-filter-drawer-content');
  const sidebar = document.getElementById('opps-sidebar');

  if (content && sidebar) {
    content.innerHTML = sidebar.innerHTML;
  }

  if (overlay) overlay.classList.add('active');
  if (drawer) drawer.classList.add('active');
  document.body.style.overflow = 'hidden';
}

function closeFilterDrawer() {
  const overlay = document.getElementById('filter-drawer-overlay');
  const drawer = document.getElementById('filter-drawer');
  if (overlay) overlay.classList.remove('active');
  if (drawer) drawer.classList.remove('active');
  document.body.style.overflow = '';
}

// ==========================================================================
// MATCH EXPLANATION MODAL (CLEAN & MINIMAL AI INSIGHTS)
// ==========================================================================

async function openMatchExplainModal(oppId = null) {
  const targetId = oppId || state.activeDetailOpp?.id;
  if (!targetId) return;

  const modal = document.getElementById('match-modal');
  const body = document.getElementById('match-modal-content');
  if (!modal || !body) return;

  body.innerHTML = `<div style="padding: 2rem; text-align: center; color: var(--text-secondary);">Calculating profile match reasons...</div>`;
  modal.style.display = 'flex';

  try {
    const res = await fetchWithAuth(`/api/matching/insights/${targetId}`);
    if (!res.ok) throw new Error('Could not calculate insights');
    const data = await res.json();

    const matched = data.matched_skills || [];
    const missing = data.missing_skills || [];
    const score = Math.round(data.match_score || 0);

    body.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; background: var(--bg-subtle); padding: 1.25rem; border-radius: var(--radius-md); border: 1px solid var(--border-color); margin-bottom: 1rem;">
        <div>
          <span style="font-size: 0.75rem; font-weight: 600; color: var(--text-muted); text-transform: uppercase;">Match Score</span>
          <h3 style="font-size: 1.75rem; font-weight: 700; color: var(--primary);">${score}%</h3>
        </div>
        <div style="font-size: 0.85rem; color: var(--text-secondary); text-align: right;">
          <span>✓ Technical Skills Evaluated</span><br>
          <span>✓ Degree &amp; Major Requirements Met</span>
        </div>
      </div>

      <div style="margin-bottom: 1rem;">
        <h4 style="font-size: 0.85rem; font-weight: 700; color: var(--text-primary); text-transform: uppercase; margin-bottom: 0.35rem;">Why this fits you:</h4>
        <p style="font-size: 0.875rem; color: var(--text-secondary); line-height: 1.5;">${escapeHtml(data.explanation || 'Matches your declared skills and career preferences.')}</p>
      </div>

      <div style="margin-bottom: 1rem;">
        <h4 style="font-size: 0.85rem; font-weight: 700; color: var(--success-text); text-transform: uppercase; margin-bottom: 0.35rem;">Matched Skills (${matched.length})</h4>
        <div class="opp-tags-row">
          ${matched.length > 0 ? matched.map(s => `<span class="opp-tag" style="background: var(--success-bg); color: var(--success-text); border-color: var(--success-border);">✓ ${escapeHtml(s)}</span>`).join('') : '<span style="font-size: 0.8rem; color: var(--text-muted);">None matched yet</span>'}
        </div>
      </div>

      <div>
        <h4 style="font-size: 0.85rem; font-weight: 700; color: var(--warning-text); text-transform: uppercase; margin-bottom: 0.35rem;">Skill Gap / Missing (${missing.length})</h4>
        <div class="opp-tags-row">
          ${missing.length > 0 ? missing.map(s => `<span class="opp-tag" style="background: var(--warning-bg); color: var(--warning-text); border-color: var(--warning-border);">+ ${escapeHtml(s)}</span>`).join('') : '<span style="font-size: 0.8rem; color: var(--text-muted);">No major missing skills!</span>'}
        </div>
      </div>
    `;
  } catch (err) {
    body.innerHTML = `<div style="padding: 1.5rem; text-align: center; color: var(--danger);">Failed to load match insights: ${escapeHtml(err.message)}</div>`;
  }
}

function closeMatchModal() {
  const modal = document.getElementById('match-modal');
  if (modal) modal.style.display = 'none';
}

// ==========================================================================
// APPLICATION TRACKER
// ==========================================================================

async function loadApplications() {
  const tbody = document.getElementById('applications-table-body');
  const countBadge = document.getElementById('badge-apps-count');
  if (!tbody) return;

  tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; padding: 2rem; color: var(--text-secondary);">Loading tracked applications...</td></tr>`;

  try {
    const res = await fetchWithAuth('/api/applications');
    if (!res.ok) throw new Error('Failed to load applications');

    const apps = await res.json();
    const appList = Array.isArray(apps) ? apps : [];

    if (countBadge) countBadge.textContent = appList.length;

    if (appList.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="6" style="text-align: center; padding: 3rem; color: var(--text-secondary);">
            No tracked applications yet. Click "+ Log New Application" to record an application.
          </td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = appList.map(app => `
      <tr>
        <td><strong>${escapeHtml(app.company || 'Unknown')}</strong></td>
        <td>${escapeHtml(app.role || 'Role')}</td>
        <td>
          <select class="select-dropdown" style="padding: 0.2rem 0.5rem; font-size: 0.75rem;" onchange="updateAppStatus('${app.id}', this.value)">
            <option value="Applied" ${app.status === 'Applied' ? 'selected' : ''}>Applied</option>
            <option value="Under Review" ${app.status === 'Under Review' ? 'selected' : ''}>Under Review</option>
            <option value="Interview" ${app.status === 'Interview' ? 'selected' : ''}>Interview</option>
            <option value="Offer" ${app.status === 'Offer' ? 'selected' : ''}>Offer</option>
            <option value="Rejected" ${app.status === 'Rejected' ? 'selected' : ''}>Rejected</option>
            <option value="Withdrawn" ${app.status === 'Withdrawn' ? 'selected' : ''}>Withdrawn</option>
          </select>
        </td>
        <td>${escapeHtml(app.applied_date || 'Recent')}</td>
        <td><span style="color: var(--text-secondary);">${escapeHtml(app.notes || '-')}</span></td>
        <td>
          <button class="btn btn-sm btn-secondary" onclick="deleteApplication('${app.id}')" style="color: var(--danger);">Delete</button>
        </td>
      </tr>
    `).join('');
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; padding: 2rem; color: var(--danger);">Failed to load applications: ${escapeHtml(err.message)}</td></tr>`;
  }
}

function openAddAppModal() {
  const modal = document.getElementById('add-app-modal');
  if (modal) modal.style.display = 'flex';
}

function closeAddAppModal() {
  const modal = document.getElementById('add-app-modal');
  if (modal) modal.style.display = 'none';
}

async function handleAddAppSubmit(event) {
  event.preventDefault();
  const company = document.getElementById('app-company').value.trim();
  const role = document.getElementById('app-role').value.trim();
  const statusVal = document.getElementById('app-status').value;
  const notes = document.getElementById('app-notes').value.trim();

  try {
    const res = await fetchWithAuth('/api/applications', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ company, role, status: statusVal, notes })
    });

    if (!res.ok) throw new Error('Failed to create application');

    closeAddAppModal();
    showToast('Application logged successfully.');
    if (state.activeTab === 'applications') loadApplications();
  } catch (err) {
    showToast('Error: ' + err.message);
  }
}

async function updateAppStatus(appId, newStatus) {
  try {
    const res = await fetchWithAuth(`/api/applications/${appId}/status`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: newStatus })
    });
    if (res.ok) showToast(`Status updated to ${newStatus}`);
  } catch (e) {
    console.warn('Error updating status:', e);
  }
}

async function deleteApplication(appId) {
  if (!confirm('Remove this application record?')) return;
  try {
    const res = await fetchWithAuth(`/api/applications/${appId}`, { method: 'DELETE' });
    if (res.ok) {
      showToast('Application record removed.');
      loadApplications();
    }
  } catch (e) {
    console.warn('Error deleting application:', e);
  }
}

// ==========================================================================
// STUDENT PROFILE & RESUME
// ==========================================================================

async function loadProfile() {
  try {
    const res = await fetchWithAuth('/api/student');
    if (!res.ok) return;

    const stud = await res.json();
    document.getElementById('prof-name').value = stud.name || '';
    document.getElementById('prof-email').value = stud.email || state.user?.email || '';
    document.getElementById('prof-phone').value = stud.phone || '';
    document.getElementById('prof-bio').value = stud.bio || '';
    document.getElementById('prof-education').value = stud.education || '';
    document.getElementById('prof-branch').value = stud.branch || '';
    document.getElementById('prof-grad-year').value = stud.graduation_year || 2026;
    document.getElementById('prof-cgpa').value = stud.cgpa || '';
    document.getElementById('prof-skills').value = Array.isArray(stud.skills) ? stud.skills.join(', ') : '';
    document.getElementById('prof-projects').value = Array.isArray(stud.projects) ? stud.projects.join(', ') : '';
    document.getElementById('prof-certs').value = Array.isArray(stud.certifications) ? stud.certifications.join(', ') : '';
    document.getElementById('prof-roles').value = Array.isArray(stud.preferred_roles) ? stud.preferred_roles.join(', ') : '';
    document.getElementById('prof-locations').value = Array.isArray(stud.preferred_locations) ? stud.preferred_locations.join(', ') : '';
    document.getElementById('prof-remote').checked = (stud.remote_preference !== false);

    // Calculate completeness
    let filledCount = 0;
    const fields = [stud.name, stud.email, stud.education, stud.branch, stud.graduation_year, stud.cgpa, stud.skills?.length >= 3, stud.preferred_roles?.length, stud.preferred_locations?.length, stud.projects?.length || stud.experience?.length, stud.bio];
    fields.forEach(f => { if (f) filledCount++; });
    const scorePct = Math.round((filledCount / fields.length) * 100);

    const compText = document.getElementById('prof-completeness-text');
    const compBar = document.getElementById('prof-completeness-bar');
    if (compText) compText.textContent = `${scorePct}%`;
    if (compBar) compBar.style.width = `${scorePct}%`;
  } catch (e) {
    console.warn('Error loading student profile:', e);
  }
}

async function handleProfileSave(event) {
  event.preventDefault();
  const name = document.getElementById('prof-name').value.trim();
  const phone = document.getElementById('prof-phone').value.trim();
  const bio = document.getElementById('prof-bio').value.trim();
  const education = document.getElementById('prof-education').value.trim();
  const branch = document.getElementById('prof-branch').value.trim();
  const gradYear = parseInt(document.getElementById('prof-grad-year').value, 10) || 2026;
  const cgpa = parseFloat(document.getElementById('prof-cgpa').value) || null;
  const skills = document.getElementById('prof-skills').value.split(',').map(s => s.trim()).filter(Boolean);
  const projects = document.getElementById('prof-projects').value.split(',').map(s => s.trim()).filter(Boolean);
  const certs = document.getElementById('prof-certs').value.split(',').map(s => s.trim()).filter(Boolean);
  const roles = document.getElementById('prof-roles').value.split(',').map(s => s.trim()).filter(Boolean);
  const locations = document.getElementById('prof-locations').value.split(',').map(s => s.trim()).filter(Boolean);
  const remote = document.getElementById('prof-remote').checked;

  try {
    const res = await fetchWithAuth('/api/student', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name,
        phone,
        bio,
        education,
        branch,
        graduation_year: gradYear,
        cgpa,
        skills,
        projects,
        certifications: certs,
        preferred_roles: roles,
        preferred_locations: locations,
        remote_preference: remote
      })
    });

    if (!res.ok) throw new Error('Failed to update profile');

    if (state.user) {
      state.user.name = name;
      localStorage.setItem('internpilot_user', JSON.stringify(state.user));
      updateUserInterface();
    }

    showToast('Profile updated successfully.');
    await loadProfile();
  } catch (err) {
    showToast('Error: ' + err.message);
  }
}

async function uploadResume() {
  const fileInput = document.getElementById('resume-file-input');
  const statusEl = document.getElementById('resume-upload-status');
  if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
    showToast('Please select a PDF file.');
    return;
  }

  const file = fileInput.files[0];
  if (!file.name.toLowerCase().endsWith('.pdf')) {
    showToast('Only PDF files are supported.');
    return;
  }

  if (statusEl) statusEl.textContent = 'Uploading & parsing PDF...';

  const formData = new FormData();
  formData.append('file', file);

  try {
    const res = await fetchWithAuth('/api/students/resume?apply_to_profile=true', {
      method: 'POST',
      body: formData
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Resume upload failed');
    }

    const data = await res.json();
    if (statusEl) {
      statusEl.textContent = `✓ Extracted skills: ${data.extracted_data?.skills?.slice(0, 5).join(', ')}`;
    }
    showToast('Resume parsed successfully.');
    await loadProfile();
  } catch (err) {
    if (statusEl) statusEl.textContent = `❌ ${err.message}`;
    showToast('Upload error: ' + err.message);
  }
}

// ==========================================================================
// ADMIN OPERATIONS HUB
// ==========================================================================

// ==========================================================================
// ADMIN OPERATIONS HUB (SIMPLIFIED 6 TABS)
// ==========================================================================

function switchAdminSection(secId) {
  // Normalize legacy tab names if called
  if (secId === 'overview') secId = 'dashboard';
  if (secId === 'opportunities') secId = 'jobs';
  
  state.adminSection = secId;
  document.querySelectorAll('.admin-section').forEach(el => el.style.display = 'none');
  const target = document.getElementById(`admin-sec-${secId}`);
  if (target) target.style.display = 'block';

  document.querySelectorAll('.admin-subnav-btn').forEach(btn => {
    const text = btn.textContent.toLowerCase();
    if (text.includes(secId) ||
        (secId === 'dashboard' && text.includes('dashboard')) ||
        (secId === 'verification' && text.includes('verification')) ||
        (secId === 'health' && text.includes('health'))) {
      btn.classList.add('active');
    } else {
      btn.classList.remove('active');
    }
  });

  if (secId === 'dashboard') loadAdminDashboard();
  else if (secId === 'sources') loadAdminSources();
  else if (secId === 'verification') loadAdminVerificationQueue();
  else if (secId === 'jobs') loadAdminOpportunities();
  else if (secId === 'users') loadAdminUsers();
  else if (secId === 'health') loadAdminHealth();
}

async function loadAdminDashboard() {
  try {
    const res = await fetchWithAuth('/api/admin/dashboard');
    if (res.ok) {
      const data = await res.json();
      const metrics = data.metrics || data;

      // Exactly the 6 requested metrics
      const setMetric = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.textContent = val !== undefined ? val : 0;
      };

      setMetric('adm-metric-sources', metrics.active_sources);
      setMetric('adm-metric-total', metrics.total_jobs);
      setMetric('adm-metric-verified', metrics.verified_jobs);
      setMetric('adm-metric-pending', metrics.pending_review);
      setMetric('adm-metric-rejected', metrics.rejected);
      setMetric('adm-metric-expired', metrics.expired);

      // Populate recent activity table
      const recent = data.recent_opportunities || [];
      const tbody = document.getElementById('admin-recent-opps-body');
      if (tbody) {
        if (recent.length === 0) {
          tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; padding: 2rem; color: var(--text-secondary);">No recent opportunities logged.</td></tr>`;
        } else {
          tbody.innerHTML = recent.map(o => `
            <tr>
              <td><strong>${escapeHtml(o.title)}</strong></td>
              <td>${escapeHtml(o.company)}</td>
              <td>${escapeHtml(o.source)}</td>
              <td><span class="badge-status ${o.status === 'active' ? 'active' : ''}">${escapeHtml(o.status)}</span></td>
              <td><span class="badge-status ${(o.verification_status || '').toLowerCase()}">${escapeHtml(o.verification_status || 'UNVERIFIED')}</span></td>
              <td>${escapeHtml(getHostname(o.application_url || o.apply_url))}</td>
              <td>${escapeHtml((o.created_at || '').substring(0, 10))}</td>
            </tr>
          `).join('');
        }
      }
    }
  } catch (e) {
    console.warn('Error loading admin dashboard:', e);
  }
}

async function loadAdminSources() {
  const tbody = document.getElementById('admin-sources-table-body');
  if (!tbody) return;

  tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; padding: 2rem; color: var(--text-secondary);">Loading registered sources...</td></tr>`;

  try {
    const res = await fetchWithAuth('/api/admin/sources');
    if (!res.ok) throw new Error('Failed to load sources');

    const data = await res.json();
    const sources = data.sources || [];

    if (sources.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; padding: 2rem; color: var(--text-secondary);">No registered sources found. Click "+ Add Source" to add one.</td></tr>`;
      return;
    }

    // Exact Clean 7-Column Table: Source | Type | Status | Jobs | Last Run | Error | Actions
    tbody.innerHTML = sources.map(s => {
      const rawStatus = (s.status || (s.active ? 'ACTIVE' : 'PAUSED')).toUpperCase();
      let statusBadge = '';
      if (rawStatus === 'ACTIVE') {
        statusBadge = `<span class="badge-status active">Active</span>`;
      } else if (rawStatus === 'RUNNING') {
        statusBadge = `<span class="badge-status running" style="background:#e0f2fe;color:#0369a1;border:1px solid #7dd3fc;font-weight:600;">Running...</span>`;
      } else if (rawStatus === 'SUCCESS') {
        statusBadge = `<span class="badge-status active" style="background:#f0fdf4;color:#15803d;border:1px solid #86efac;font-weight:600;">Success</span>`;
      } else if (rawStatus === 'FAILED' || rawStatus === 'ERROR') {
        statusBadge = `<span class="badge-status failed" style="background:#fef2f2;color:#b91c1c;border:1px solid #fca5a5;font-weight:600;">Failed</span>`;
      } else if (rawStatus === 'DISABLED') {
        statusBadge = `<span class="badge-status paused" style="background:#f3f4f6;color:#6b7280;border:1px solid #d1d5db;">Disabled</span>`;
      } else {
        statusBadge = `<span class="badge-status paused">Paused</span>`;
      }

      const isPaused = rawStatus === 'PAUSED' || rawStatus === 'DISABLED';
      const lastRun = s.last_run_at || s.last_ingested_at || s.last_ingestion;
      const lastErr = s.last_error ? escapeHtml(s.last_error) : '';
      const errDisplay = lastErr 
        ? `<span style="color:var(--danger);font-size:0.8rem;font-weight:500;" title="${lastErr}">${escapeHtml(lastErr.length > 25 ? lastErr.substring(0, 22) + '...' : lastErr)}</span>` 
        : `<span style="color:var(--text-secondary);font-size:0.8rem;">None</span>`;
      const targetVal = s.configuration?.url || s.configuration?.channel_username || s.configuration?.channel || '';
      const jobsCount = s.items_verified !== undefined ? s.items_verified : (s.items_accepted !== undefined ? s.items_accepted : (s.items_count || 0));

      return `
        <tr>
          <td><strong>${escapeHtml(s.name)}</strong></td>
          <td><span class="role-tag">${escapeHtml(s.source_type || s.type)}</span></td>
          <td>${statusBadge}</td>
          <td><strong>${jobsCount}</strong></td>
          <td>${escapeHtml((lastRun || '').substring(0, 16).replace('T', ' ') || 'Never')}</td>
          <td>${errDisplay}</td>
          <td>
            <div style="display: flex; gap: 0.35rem; flex-wrap: wrap;">
              <button class="btn btn-sm btn-secondary" onclick="triggerIngestionSource('${s.id}')">Run</button>
              <button class="btn btn-sm ${isPaused ? 'btn-primary' : 'btn-outline'}" onclick="toggleSourceStatus('${s.id}')">${isPaused ? 'Resume' : 'Pause'}</button>
              <button class="btn btn-sm btn-secondary" onclick="openEditSourceModal('${s.id}', '${escapeHtml(s.name)}', '${escapeHtml(rawStatus)}', '${escapeHtml(targetVal)}')">Edit</button>
              <button class="btn btn-sm btn-danger" onclick="deleteSource('${s.id}')">Delete</button>
            </div>
          </td>
        </tr>
      `;
    }).join('');
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; padding: 2rem; color: var(--danger);">Failed: ${escapeHtml(err.message)}</td></tr>`;
  }
}

async function toggleSourceStatus(sourceId) {
  try {
    const res = await fetchWithAuth(`/api/admin/sources/${sourceId}/toggle`, { method: 'POST' });
    if (res.ok) {
      showToast('Source status toggled.');
      loadAdminSources();
    } else {
      const err = await res.json();
      showToast('Error: ' + (err.message || err.detail));
    }
  } catch (e) {
    showToast('Error: ' + e.message);
  }
}

async function deleteSource(sourceId) {
  if (!confirm('Are you sure you want to delete this source?')) return;
  try {
    const res = await fetchWithAuth(`/api/admin/sources/${sourceId}`, { method: 'DELETE' });
    if (res.ok) {
      showToast('Source deleted successfully.');
      loadAdminSources();
    } else {
      const err = await res.json();
      showToast('Error: ' + (err.message || err.detail));
    }
  } catch (e) {
    showToast('Error deleting source: ' + e.message);
  }
}

function openEditSourceModal(id, name, status, target) {
  const modal = document.getElementById('edit-source-modal');
  if (!modal) return;
  document.getElementById('edit-src-id').value = id;
  document.getElementById('edit-src-name').value = name || '';
  document.getElementById('edit-src-status').value = status || 'ACTIVE';
  document.getElementById('edit-src-target').value = target || '';
  modal.style.display = 'flex';
}

function closeEditSourceModal() {
  const modal = document.getElementById('edit-source-modal');
  if (modal) modal.style.display = 'none';
}

async function handleEditSourceSubmit(event) {
  event.preventDefault();
  const id = document.getElementById('edit-src-id').value;
  const name = document.getElementById('edit-src-name').value.trim();
  const status = document.getElementById('edit-src-status').value;
  const target = document.getElementById('edit-src-target').value.trim();

  try {
    const res = await fetchWithAuth(`/api/admin/sources/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name,
        status,
        configuration: target ? { url: target } : {}
      })
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to update source');
    }
    closeEditSourceModal();
    showToast('Source updated successfully.');
    loadAdminSources();
  } catch (e) {
    showToast('Error: ' + e.message);
  }
}

// ==========================================================================
// LINKEDIN SOURCE MANAGEMENT (AUTHORIZED API & IMPORTS)
// ==========================================================================

async function loadAdminLinkedIn() {
  const banner = document.getElementById('linkedin-status-banner');
  const statusEl = document.getElementById('linkedin-metric-status');
  const lastImportEl = document.getElementById('linkedin-metric-last-import');
  const importedEl = document.getElementById('linkedin-metric-imported');
  const acceptedEl = document.getElementById('linkedin-metric-accepted');
  const rejectedEl = document.getElementById('linkedin-metric-rejected');
  const duplicatesEl = document.getElementById('linkedin-metric-duplicates');

  if (!banner) return;

  banner.innerHTML = `<div style="text-align: center; color: var(--text-secondary);">Checking LinkedIn connection status...</div>`;

  try {
    const res = await fetchWithAuth('/api/admin/linkedin/status');
    if (!res.ok) throw new Error('Failed to load LinkedIn source status');
    const data = await res.json();

    const isConnected = data.api_available && data.connection_status === 'CONNECTED';
    if (isConnected) {
      banner.innerHTML = `
        <div style="display: flex; align-items: center; gap: 1rem;">
          <div style="font-size: 2rem;">✅</div>
          <div>
            <div style="font-weight: 700; font-size: 1.05rem; color: var(--success);">LinkedIn Partner API: Connected</div>
            <div style="font-size: 0.85rem; color: var(--text-secondary); margin-top: 0.2rem;">
              Direct authorized API synchronization is available. Client ID: ${escapeHtml(data.client_id || 'Configured')}
            </div>
          </div>
        </div>
      `;
      if (statusEl) {
        statusEl.textContent = 'CONNECTED';
        statusEl.style.color = 'var(--success)';
      }
    } else {
      banner.innerHTML = `
        <div style="display: flex; align-items: center; gap: 1rem;">
          <div style="font-size: 2rem;">ℹ️</div>
          <div>
            <div style="font-weight: 700; font-size: 1.05rem; color: var(--warning);">Authorized import required</div>
            <div style="font-size: 0.85rem; color: var(--text-secondary); margin-top: 0.2rem;">
              LinkedIn API credentials are not configured. To preserve platform compliance and integrity, unauthorized web scraping and browser automation are strictly prohibited. Please import authorized CSV or JSON exports below.
            </div>
          </div>
        </div>
      `;
      if (statusEl) {
        statusEl.textContent = 'Authorized import required';
        statusEl.style.color = 'var(--warning)';
      }
    }

    if (lastImportEl) lastImportEl.textContent = (data.last_import || '').substring(0, 16).replace('T', ' ') || 'Never';
    if (importedEl) importedEl.textContent = data.total_imported || 0;
    if (acceptedEl) acceptedEl.textContent = data.accepted || 0;
    if (rejectedEl) rejectedEl.textContent = data.rejected || 0;
    if (duplicatesEl) duplicatesEl.textContent = data.duplicates || 0;
  } catch (err) {
    banner.innerHTML = `<div style="color: var(--danger);">Failed to load LinkedIn status: ${escapeHtml(err.message)}</div>`;
  }
}

async function handleLinkedInImport() {
  const fileInput = document.getElementById('linkedin-file-input');
  const textInput = document.getElementById('linkedin-text-input');
  const spinner = document.getElementById('linkedin-import-spinner');
  const resultDiv = document.getElementById('linkedin-import-result');
  const btn = document.getElementById('btn-linkedin-import');

  let content = textInput ? textInput.value.trim() : '';
  let filename = '';

  if (fileInput && fileInput.files && fileInput.files.length > 0) {
    const file = fileInput.files[0];
    filename = file.name;
    try {
      content = await file.text();
    } catch (e) {
      showToast('Failed to read file: ' + e.message);
      return;
    }
  }

  if (!content) {
    showToast('Please upload a CSV/JSON file or paste content.');
    return;
  }

  if (spinner) spinner.style.display = 'inline-block';
  if (btn) btn.disabled = true;
  if (resultDiv) resultDiv.style.display = 'none';

  try {
    const payload = {};
    if (filename.endsWith('.json') || content.startsWith('[') || content.startsWith('{')) {
      try {
        payload.json_content = JSON.parse(content);
      } catch (e) {
        payload.csv_content = content;
      }
    } else {
      payload.csv_content = content;
    }

    const res = await fetchWithAuth('/api/admin/linkedin/import', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    const data = await res.json();
    if (!res.ok || data.status === 'error') {
      throw new Error(data.message || 'Import failed');
    }

    if (resultDiv) {
      resultDiv.style.display = 'block';
      resultDiv.innerHTML = `
        <div style="padding: 1rem; border-radius: var(--radius-md); background: var(--bg-page); border: 1px solid var(--border-color);">
          <h4 style="font-weight: 700; color: var(--success); margin-bottom: 0.5rem;">Import Successful</h4>
          <p style="font-size: 0.85rem; margin: 0.25rem 0;">Processed: <strong>${data.total_processed}</strong> records</p>
          <p style="font-size: 0.85rem; margin: 0.25rem 0; color: var(--success);">Accepted: <strong>${data.accepted}</strong> (held in PENDING_REVIEW for safety)</p>
          <p style="font-size: 0.85rem; margin: 0.25rem 0; color: var(--danger);">Rejected: <strong>${data.rejected}</strong></p>
          <p style="font-size: 0.85rem; margin: 0.25rem 0; color: var(--warning);">Duplicates: <strong>${data.duplicates}</strong></p>
          ${(data.sample_rejected || []).length > 0 ? `
            <div style="margin-top: 0.5rem; font-size: 0.8rem; color: var(--danger);">
              <strong>Rejection samples:</strong>
              <ul style="margin: 0.25rem 0 0 1rem; padding: 0;">
                ${data.sample_rejected.slice(0, 5).map(r => `<li>${escapeHtml(r.title || r.company || 'Listing')}: ${escapeHtml(r.reason)}</li>`).join('')}
              </ul>
            </div>
          ` : ''}
        </div>
      `;
    }

    showToast(`Imported ${data.accepted} LinkedIn listings.`);
    loadAdminLinkedIn();
    loadAdminDashboard();
  } catch (err) {
    if (resultDiv) {
      resultDiv.style.display = 'block';
      resultDiv.innerHTML = `<div style="padding: 1rem; color: var(--danger); background: #fff4f4; border-radius: var(--radius-md); border: 1px solid #ffd6d6;">Error: ${escapeHtml(err.message)}</div>`;
    }
    showToast('Import error: ' + err.message);
  } finally {
    if (spinner) spinner.style.display = 'none';
    if (btn) btn.disabled = false;
  }
}

function clearLinkedInImportForm() {
  const fileInput = document.getElementById('linkedin-file-input');
  const textInput = document.getElementById('linkedin-text-input');
  const resultDiv = document.getElementById('linkedin-import-result');
  if (fileInput) fileInput.value = '';
  if (textInput) textInput.value = '';
  if (resultDiv) resultDiv.style.display = 'none';
}

// ==========================================================================
// IMPORT OPPORTUNITIES WORKFLOW (PREVIEW & CONFIRM)
// ==========================================================================

let cachedImportPreview = null;

async function handleImportPreview() {
  const srcName = document.getElementById('import-source-name').value.trim() || 'Authorized Batch Import';
  const srcType = document.getElementById('import-source-type').value;
  const fileInput = document.getElementById('import-file-input');
  const textInput = document.getElementById('import-raw-content');
  const spinner = document.getElementById('import-preview-spinner');
  const container = document.getElementById('import-preview-container');
  const confirmResult = document.getElementById('import-confirm-result');

  if (confirmResult) confirmResult.style.display = 'none';

  let content = textInput ? textInput.value.trim() : '';
  let filename = '';

  if (fileInput && fileInput.files && fileInput.files.length > 0) {
    const file = fileInput.files[0];
    filename = file.name;
    try {
      content = await file.text();
    } catch (e) {
      showToast('Error reading file: ' + e.message);
      return;
    }
  }

  if (!content) {
    showToast('Please upload a file or paste content to preview.');
    return;
  }

  if (spinner) spinner.style.display = 'inline-block';

  try {
    const res = await fetchWithAuth('/api/admin/import/preview', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        content: content,
        source_name: srcName,
        source_type: srcType,
        filename: filename
      })
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Validation preview failed');

    cachedImportPreview = data;

    // Populate metric cards
    document.getElementById('prev-metric-total').textContent = data.total || 0;
    document.getElementById('prev-metric-valid').textContent = data.valid_count || 0;
    document.getElementById('prev-metric-rejected').textContent = data.rejected_count || 0;
    document.getElementById('prev-metric-duplicates').textContent = data.duplicates_count || 0;

    // Populate rejection summary
    const rejSummary = document.getElementById('prev-rejection-summary');
    const rejList = document.getElementById('prev-rejection-list');
    if (rejSummary && rejList) {
      const reasons = data.rejection_reasons || {};
      const entries = Object.entries(reasons);
      if (entries.length > 0) {
        rejList.innerHTML = entries.map(([r, c]) => `<li><strong>${escapeHtml(r)}</strong>: ${c} listings</li>`).join('');
        rejSummary.style.display = 'block';
      } else {
        rejSummary.style.display = 'none';
      }
    }

    // Populate preview table
    const tbody = document.getElementById('import-preview-table-body');
    if (tbody) {
      const items = data.items || [];
      tbody.innerHTML = items.map((item, idx) => `
        <tr>
          <td>${idx + 1}</td>
          <td><strong>${escapeHtml(item.title || '(Untitled)')}</strong></td>
          <td>${escapeHtml(item.company || '(Unknown)')}</td>
          <td>${escapeHtml(item.location || 'Remote')}</td>
          <td>${escapeHtml(item.opportunity_type || 'internship')}</td>
          <td><span style="font-size: 0.75rem;">${escapeHtml(getHostname(item.apply_url))}</span></td>
          <td>
            <span class="badge-status ${item.is_valid ? 'verified' : (item.is_duplicate ? 'paused' : 'rejected')}">
              ${item.is_valid ? 'VALID' : (item.is_duplicate ? 'DUPLICATE' : 'REJECTED')}
            </span>
          </td>
          <td>
            <span style="font-size: 0.8rem; color: ${item.is_valid ? 'var(--success)' : 'var(--danger)'};">
              ${escapeHtml(item.rejection_reason || (item.is_duplicate ? 'Duplicate of existing opportunity' : (item.classification?.job_category || 'Genuine Job')))}
            </span>
          </td>
        </tr>
      `).join('');
    }

    if (container) container.style.display = 'block';
    showToast(`Preview loaded: ${data.valid_count} valid, ${data.rejected_count} rejected.`);
  } catch (err) {
    showToast('Preview error: ' + err.message);
  } finally {
    if (spinner) spinner.style.display = 'none';
  }
}

async function handleImportConfirm() {
  if (!cachedImportPreview || !cachedImportPreview.items) {
    showToast('Please validate and preview content before confirming.');
    return;
  }

  const validItems = cachedImportPreview.items.filter(i => i.is_valid);
  if (validItems.length === 0) {
    showToast('No valid opportunities to ingest.');
    return;
  }

  const srcName = cachedImportPreview.source_name || document.getElementById('import-source-name').value.trim() || 'Authorized Batch Import';
  const srcType = cachedImportPreview.source_type || document.getElementById('import-source-type').value;

  const btn = document.getElementById('btn-import-confirm');
  if (btn) btn.disabled = true;

  try {
    const rawRecords = validItems.map(i => i.raw_data || {
      title: i.title,
      company: i.company,
      location: i.location,
      opportunity_type: i.opportunity_type,
      apply_url: i.apply_url,
      description: i.description
    });

    const res = await fetchWithAuth('/api/admin/import/confirm', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        source_name: srcName,
        source_type: srcType,
        records: rawRecords
      })
    });

    const data = await res.json();
    if (!res.ok || data.status === 'error') {
      throw new Error(data.message || 'Confirmation failed');
    }

    const confirmResult = document.getElementById('import-confirm-result');
    if (confirmResult) {
      confirmResult.style.display = 'block';
      confirmResult.innerHTML = `
        <div style="padding: 1.25rem; background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: var(--radius-md); margin-top: 1rem;">
          <h4 style="color: var(--success); font-weight: 700; margin-bottom: 0.5rem;">Batch Ingestion Complete!</h4>
          <p style="margin: 0.25rem 0; font-size: 0.875rem;">Successfully ingested: <strong>${data.accepted || 0}</strong> opportunities.</p>
          <p style="margin: 0.25rem 0; font-size: 0.875rem; color: var(--text-secondary);">Held in Verification Queue: <strong>${data.held_in_review || data.accepted || 0}</strong> listings (awaiting admin review).</p>
        </div>
      `;
    }

    showToast(`Successfully ingested ${data.accepted} opportunities!`);
    loadAdminSources();
    loadAdminDashboard();
  } catch (err) {
    showToast('Confirmation error: ' + err.message);
  } finally {
    if (btn) btn.disabled = false;
  }
}

function clearImportForm() {
  const fileInput = document.getElementById('import-file-input');
  const textInput = document.getElementById('import-raw-content');
  const container = document.getElementById('import-preview-container');
  const resultDiv = document.getElementById('import-confirm-result');
  if (fileInput) fileInput.value = '';
  if (textInput) textInput.value = '';
  if (container) container.style.display = 'none';
  if (resultDiv) resultDiv.style.display = 'none';
  cachedImportPreview = null;
}

function openAddSourceModal() {
  const modal = document.getElementById('add-source-modal');
  if (modal) modal.style.display = 'flex';
}

function closeAddSourceModal() {
  const modal = document.getElementById('add-source-modal');
  if (modal) modal.style.display = 'none';
}

function toggleSourceTypeFields() {
  const typeVal = document.getElementById('src-type').value;
  const urlGroup = document.getElementById('src-url-group');
  const tgGroup = document.getElementById('src-telegram-group');
  const fileGroup = document.getElementById('src-file-group');

  if (tgGroup) tgGroup.style.display = (typeVal === 'TELEGRAM') ? 'block' : 'none';
  if (fileGroup) fileGroup.style.display = (['CSV', 'JSON', 'LINKEDIN_IMPORT'].includes(typeVal)) ? 'block' : 'none';
  if (urlGroup) urlGroup.style.display = (['ATS', 'COMPANY_CAREERS', 'EMPLOYER', 'COLLEGE'].includes(typeVal)) ? 'block' : 'none';
}

async function handleAddSource(event) {
  event.preventDefault();
  const name = document.getElementById('src-name').value.trim();
  const type = document.getElementById('src-type').value;

  try {
    if (type === 'TELEGRAM') {
      const handle = document.getElementById('src-channel-username').value.trim();
      const res = await fetchWithAuth('/api/admin/sources/telegram/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ channel_name: name, channel_username: handle })
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Validation failed for Telegram channel');
      }
    } else if (['CSV', 'JSON', 'LINKEDIN_IMPORT'].includes(type)) {
      const fileInput = document.getElementById('src-file-input');
      const textInput = document.getElementById('src-raw-content');
      let content = textInput ? textInput.value.trim() : '';

      if (fileInput && fileInput.files && fileInput.files.length > 0) {
        try {
          content = await fileInput.files[0].text();
        } catch (e) {
          throw new Error('Failed to read uploaded file: ' + e.message);
        }
      }

      // Map to backend SourceType
      let mappedType = type === 'LINKEDIN_IMPORT' ? 'LINKEDIN_AUTHORIZED' : type;

      const res = await fetchWithAuth('/api/admin/sources', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name,
          type: mappedType,
          configuration: content ? { raw_data: content } : {}
        })
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Failed to create source');
      }
    } else {
      // ATS, COMPANY_CAREERS, EMPLOYER, COLLEGE
      const url = document.getElementById('src-url').value.trim();
      let mappedType = type;
      if (type === 'ATS') mappedType = 'ATS_PUBLIC_FEED';
      else if (type === 'EMPLOYER') mappedType = 'EMPLOYER_SUBMISSION';
      else if (type === 'COLLEGE') mappedType = 'COLLEGE_SUBMISSION';

      const res = await fetchWithAuth('/api/admin/sources', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name,
          type: mappedType,
          configuration: url ? { url } : {}
        })
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Failed to create source');
      }
    }

    closeAddSourceModal();
    showToast(`Source '${name}' added successfully.`);
    loadAdminSources();
    loadAdminDashboard();
  } catch (err) {
    showToast('Error: ' + err.message);
  }
}

async function loadAdminOpportunities() {
  const tbody = document.getElementById('admin-opportunities-table-body');
  if (!tbody) return;

  tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; padding: 2rem; color: var(--text-secondary);">Loading raw opportunities...</td></tr>`;

  try {
    const res = await fetchWithAuth('/api/admin/opportunities?limit=50');
    if (!res.ok) throw new Error('Failed to load opportunities');

    const data = await res.json();
    const items = data.items || [];

    tbody.innerHTML = items.map(o => `
      <tr>
        <td><strong>${escapeHtml(o.title)}</strong></td>
        <td>${escapeHtml(o.company)}</td>
        <td>${escapeHtml(o.location || 'Remote')}</td>
        <td>${escapeHtml(o.opportunity_type)}</td>
        <td>${escapeHtml(o.source)}</td>
        <td><span class="badge-status ${o.status === 'active' ? 'active' : ''}">${escapeHtml(o.status)}</span></td>
        <td><span class="badge-status ${(o.verification_status || '').toLowerCase()}">${escapeHtml(o.verification_status || 'UNVERIFIED')}</span></td>
        <td>
          <button class="btn btn-sm btn-secondary" onclick="openDetailDrawer('${o.id}')">View</button>
        </td>
      </tr>
    `).join('');
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; padding: 2rem; color: var(--danger);">Failed: ${escapeHtml(err.message)}</td></tr>`;
  }
}

async function loadAdminVerificationQueue() {
  const tbody = document.getElementById('admin-verification-table-body');
  if (!tbody) return;

  const filterEl = document.getElementById('admin-verif-filter');
  const status = filterEl ? filterEl.value : 'PENDING_REVIEW';

  tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; padding: 2rem; color: var(--text-secondary);">Loading verification queue...</td></tr>`;

  try {
    const res = await fetchWithAuth(`/api/admin/verification-queue?status=${status}&page=1&page_size=50`);
    if (!res.ok) throw new Error('Failed to load verification queue');

    const result = await res.json();
    const data = result.data || {};
    const items = data.items || [];

    if (items.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; padding: 2rem; color: var(--text-secondary);">No opportunities found for filter '${escapeHtml(status)}'.</td></tr>`;
      return;
    }

    tbody.innerHTML = items.map(o => {
      const checks = typeof o.verification_checks === 'object' && o.verification_checks ? o.verification_checks : {};
      const checksSummary = Object.entries(checks).map(([k, v]) => `${k}: ${v}`).join(', ') || 'Standard';

      return `
        <tr>
          <td><strong>${escapeHtml(o.title)}</strong></td>
          <td>${escapeHtml(o.company)}</td>
          <td><span class="source-badge">${escapeHtml(o.source || 'External')}</span></td>
          <td><a href="${escapeHtml(o.apply_url || '#')}" target="_blank" rel="noopener" style="font-size: 0.8rem; color: var(--primary); text-decoration: underline;">${escapeHtml(getHostname(o.apply_url) || 'View Link')}</a></td>
          <td><span style="font-size: 0.75rem; color: var(--text-muted);">${escapeHtml(checksSummary)}</span></td>
          <td><span class="badge-status ${(o.verification_status || '').toLowerCase()}">${escapeHtml(o.verification_status || 'UNVERIFIED')}</span></td>
          <td>
            <div style="display: flex; gap: 0.35rem; align-items: center;">
              <button class="btn btn-sm btn-primary" style="padding: 0.2rem 0.6rem; font-size: 0.75rem;" onclick="verifyOpportunityAdmin('${o.id}')">Approve</button>
              <button class="btn btn-sm btn-danger" style="padding: 0.2rem 0.6rem; font-size: 0.75rem;" onclick="rejectOpportunityAdmin('${o.id}')">Reject</button>
            </div>
          </td>
        </tr>
      `;
    }).join('');
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; padding: 2rem; color: var(--danger);">Failed: ${escapeHtml(err.message)}</td></tr>`;
  }
}

async function verifyOpportunityAdmin(oppId) {
  try {
    const res = await fetchWithAuth(`/api/admin/verify/${oppId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ method: 'ADMIN_MANUAL_REVIEW', notes: 'Manually approved by Debasis Behera' })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.message || 'Verification failed');
    showToast('Opportunity verified and published successfully.');
    loadAdminVerificationQueue();
    loadAdminDashboard();
  } catch (e) {
    showToast('Error: ' + e.message);
  }
}

async function rejectOpportunityAdmin(oppId) {
  try {
    const res = await fetchWithAuth(`/api/admin/reject/${oppId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason: 'ADMIN_REJECTED', notes: 'Rejected by admin operator' })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.message || 'Rejection failed');
    showToast('Opportunity marked as REJECTED.');
    loadAdminVerificationQueue();
    loadAdminDashboard();
  } catch (e) {
    showToast('Error: ' + e.message);
  }
}

function openIngestionModal() {
  let modal = document.getElementById('ingestion-stage-modal');
  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'ingestion-stage-modal';
    modal.style.cssText = 'position:fixed;inset:0;background:rgba(15,23,42,0.65);backdrop-filter:blur(4px);z-index:9999;display:flex;align-items:center;justify-content:center;padding:1rem;';
    modal.innerHTML = `
      <div style="background:var(--bg-card,#fff);border-radius:12px;width:100%;max-width:540px;box-shadow:0 25px 50px -12px rgba(0,0,0,0.25);overflow:hidden;border:1px solid var(--border-color,#e2e8f0);">
        <div style="padding:1.25rem 1.5rem;border-bottom:1px solid var(--border-color,#e2e8f0);display:flex;justify-content:space-between;align-items:center;background:var(--bg-card,#fff);">
          <div style="display:flex;align-items:center;gap:0.6rem;">
            <span style="font-size:1.2rem;">⚡</span>
            <h3 style="margin:0;font-size:1.1rem;font-weight:700;color:var(--text-primary,#0f172a);">Pipeline Execution</h3>
          </div>
          <button id="ingest-modal-close-btn" style="background:none;border:none;font-size:1.4rem;cursor:pointer;color:var(--text-secondary,#64748b);line-height:1;display:none;" onclick="closeIngestionModal()">&times;</button>
        </div>
        <div id="ingest-modal-content" style="padding:1.5rem;">
          <!-- Stage indicator & results dynamically rendered -->
        </div>
      </div>
    `;
    document.body.appendChild(modal);
  }
  modal.style.display = 'flex';
  const closeBtn = document.getElementById('ingest-modal-close-btn');
  if (closeBtn) closeBtn.style.display = 'none';
  return modal;
}

function closeIngestionModal() {
  const modal = document.getElementById('ingestion-stage-modal');
  if (modal) modal.style.display = 'none';
}

function renderIngestionStages(activeStep, errorMsg = null, results = null) {
  const container = document.getElementById('ingest-modal-content');
  if (!container) return;

  const steps = ['RUNNING', 'FETCHING', 'PARSING', 'VALIDATING', 'VERIFYING', 'COMPLETE'];
  const activeIdx = steps.indexOf(activeStep);

  let stagesHtml = `
    <div style="display:flex;flex-direction:column;gap:0.6rem;margin-bottom:1.5rem;">
      <div style="display:flex;align-items:center;justify-content:space-between;gap:0.25rem;flex-wrap:wrap;">
  `;

  steps.forEach((step, idx) => {
    let color = '#94a3b8';
    let bg = '#f1f5f9';
    let icon = '○';

    if (errorMsg && idx === activeIdx) {
      color = '#ef4444';
      bg = '#fee2e2';
      icon = '✕';
    } else if (idx < activeIdx || activeStep === 'COMPLETE') {
      color = '#16a34a';
      bg = '#dcfce7';
      icon = '✓';
    } else if (idx === activeIdx) {
      color = '#0284c7';
      bg = '#e0f2fe';
      icon = '▶';
    }

    stagesHtml += `
      <div style="display:flex;align-items:center;gap:0.35rem;font-size:0.75rem;font-weight:700;padding:0.35rem 0.6rem;border-radius:6px;background:${bg};color:${color};">
        <span>${icon}</span>
        <span>${step}</span>
      </div>
    `;
    if (idx < steps.length - 1) {
      stagesHtml += `<span style="color:#cbd5e1;font-weight:700;">→</span>`;
    }
  });

  stagesHtml += `</div></div>`;

  if (errorMsg) {
    stagesHtml += `
      <div style="background:#fef2f2;border:1px solid #fca5a5;border-radius:8px;padding:1rem;color:#b91c1c;">
        <div style="font-weight:700;margin-bottom:0.25rem;">Ingestion Failed</div>
        <div style="font-size:0.875rem;">Reason: <strong>${escapeHtml(errorMsg)}</strong></div>
      </div>
      <div style="margin-top:1.25rem;text-align:right;">
        <button class="btn btn-sm btn-secondary" onclick="closeIngestionModal()">Close</button>
      </div>
    `;
    const closeBtn = document.getElementById('ingest-modal-close-btn');
    if (closeBtn) closeBtn.style.display = 'block';
  } else if (results) {
    stagesHtml += `
      <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:1rem;">
        <div style="font-weight:700;margin-bottom:0.75rem;color:#0f172a;border-bottom:1px solid #e2e8f0;padding-bottom:0.4rem;">
          Ingestion Breakdown
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.5rem 1rem;font-size:0.875rem;">
          <div>Found: <strong>${results.found !== undefined ? results.found : 0}</strong></div>
          <div>Parsed: <strong>${results.parsed !== undefined ? results.parsed : 0}</strong></div>
          <div>Rejected: <strong style="color:#ef4444;">${results.rejected !== undefined ? results.rejected : 0}</strong></div>
          <div>Duplicates: <strong>${results.duplicates !== undefined ? results.duplicates : 0}</strong></div>
          <div>Expired: <strong>${results.expired !== undefined ? results.expired : 0}</strong></div>
          <div>Pending: <strong style="color:#f59e0b;">${results.pending !== undefined ? results.pending : (results.pending_review || 0)}</strong></div>
          <div>Verified: <strong style="color:#16a34a;">${results.verified !== undefined ? results.verified : 0}</strong></div>
        </div>
      </div>
      <div style="margin-top:1.25rem;text-align:right;">
        <button class="btn btn-sm btn-primary" onclick="closeIngestionModal()">Done</button>
      </div>
    `;
    const closeBtn = document.getElementById('ingest-modal-close-btn');
    if (closeBtn) closeBtn.style.display = 'block';
  } else {
    stagesHtml += `
      <div style="display:flex;align-items:center;gap:0.75rem;padding:0.75rem;color:var(--text-secondary,#64748b);font-size:0.875rem;">
        <span style="display:inline-block;width:14px;height:14px;border:2px solid #38bdf8;border-top-color:transparent;border-radius:50%;animation:spin 0.8s linear infinite;"></span>
        <span>Processing stage: <strong>${activeStep}</strong>...</span>
      </div>
    `;
  }

  container.innerHTML = stagesHtml;
}

async function triggerIngestionAll() {
  openIngestionModal();
  renderIngestionStages('RUNNING');

  const t1 = setTimeout(() => renderIngestionStages('FETCHING'), 300);
  const t2 = setTimeout(() => renderIngestionStages('PARSING'), 700);
  const t3 = setTimeout(() => renderIngestionStages('VALIDATING'), 1100);
  const t4 = setTimeout(() => renderIngestionStages('VERIFYING'), 1500);

  try {
    const res = await fetchWithAuth('/api/admin/sources/ingest-all', { method: 'POST' });
    clearTimeout(t1); clearTimeout(t2); clearTimeout(t3); clearTimeout(t4);

    const data = await res.json();
    if (res.ok && data.status === 'success') {
      const rep = data.report || {};
      renderIngestionStages('COMPLETE', null, {
        found: rep.found !== undefined ? rep.found : (rep.collected || 0),
        parsed: rep.parsed !== undefined ? rep.parsed : (rep.total_parsed || 0),
        rejected: rep.rejected !== undefined ? rep.rejected : 0,
        duplicates: rep.duplicates !== undefined ? rep.duplicates : (rep.duplicates_removed || 0),
        expired: rep.expired !== undefined ? rep.expired : 0,
        pending: rep.pending !== undefined ? rep.pending : (rep.pending_review || 0),
        verified: rep.verified !== undefined ? rep.verified : (rep.new_added || 0)
      });
      showToast(`Multi-source ingestion complete!`);
    } else {
      const errMsg = data.message || data.error || 'Ingestion failed';
      renderIngestionStages('VERIFYING', errMsg);
      showToast('Error: ' + errMsg);
    }
  } catch (e) {
    clearTimeout(t1); clearTimeout(t2); clearTimeout(t3); clearTimeout(t4);
    renderIngestionStages('RUNNING', e.message);
    showToast('Error: ' + e.message);
  } finally {
    loadAdminSources();
    loadAdminDashboard();
  }
}

async function triggerIngestionSource(sourceKey) {
  openIngestionModal();
  renderIngestionStages('RUNNING');

  const t1 = setTimeout(() => renderIngestionStages('FETCHING'), 300);
  const t2 = setTimeout(() => renderIngestionStages('PARSING'), 700);
  const t3 = setTimeout(() => renderIngestionStages('VALIDATING'), 1100);
  const t4 = setTimeout(() => renderIngestionStages('VERIFYING'), 1500);

  try {
    const res = await fetchWithAuth(`/api/admin/sources/${sourceKey}/ingest`, { method: 'POST' });
    clearTimeout(t1); clearTimeout(t2); clearTimeout(t3); clearTimeout(t4);

    const data = await res.json();
    if (res.ok && data.status === 'success') {
      const rep = data.report || {};
      renderIngestionStages('COMPLETE', null, {
        found: rep.found !== undefined ? rep.found : (rep.collected || 0),
        parsed: rep.parsed !== undefined ? rep.parsed : (rep.total_parsed || 0),
        rejected: rep.rejected !== undefined ? rep.rejected : 0,
        duplicates: rep.duplicates !== undefined ? rep.duplicates : (rep.duplicates_removed || 0),
        expired: rep.expired !== undefined ? rep.expired : 0,
        pending: rep.pending !== undefined ? rep.pending : (rep.pending_review || 0),
        verified: rep.verified !== undefined ? rep.verified : (rep.new_added || 0)
      });
      showToast(`Ingestion complete! ${rep.verified || rep.new_added || 0} verified.`);
    } else {
      const errMsg = data.message || data.error || (data.report && data.report.error) || 'Ingestion failed';
      renderIngestionStages('VERIFYING', errMsg);
      showToast('Error: ' + errMsg);
    }
  } catch (e) {
    clearTimeout(t1); clearTimeout(t2); clearTimeout(t3); clearTimeout(t4);
    renderIngestionStages('RUNNING', e.message);
    showToast('Error: ' + e.message);
  } finally {
    loadAdminSources();
    loadAdminDashboard();
  }
}

async function loadAdminUsers() {
  const tbody = document.getElementById('admin-users-table-body');
  if (!tbody) return;

  try {
    const res = await fetchWithAuth('/api/admin/users');
    if (!res.ok) throw new Error('Failed to load users');

    const data = await res.json();
    const users = data.users || [];

    tbody.innerHTML = users.map(u => `
      <tr>
        <td><span style="font-family: monospace; font-size: 0.75rem;">${escapeHtml(u.id)}</span></td>
        <td><strong>${escapeHtml(u.email)}</strong></td>
        <td><span class="role-tag ${u.role === 'ADMIN' ? 'admin' : ''}">${escapeHtml(u.role)}</span></td>
        <td><span class="badge-status active">${u.is_active ? 'Active' : 'Disabled'}</span></td>
        <td>
          <select class="select-dropdown" style="padding: 0.2rem 0.5rem; font-size: 0.75rem;" onchange="updateUserRole('${u.id}', this.value)">
            <option value="STUDENT" ${u.role === 'STUDENT' ? 'selected' : ''}>Student</option>
            <option value="ADMIN" ${u.role === 'ADMIN' ? 'selected' : ''}>Admin</option>
          </select>
        </td>
      </tr>
    `).join('');
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--danger);">Error: ${escapeHtml(err.message)}</td></tr>`;
  }
}

async function updateUserRole(userId, newRole) {
  try {
    const res = await fetchWithAuth(`/api/admin/users/${userId}/role`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ role: newRole })
    });
    if (res.ok) {
      showToast(`User role updated to ${newRole}`);
      loadAdminUsers();
    }
  } catch (e) {
    showToast('Error: ' + e.message);
  }
}

async function loadAdminSecurityStatus() {
  const container = document.getElementById('admin-security-status-container');
  if (!container) return;

  try {
    const res = await fetchWithAuth('/api/admin/security-status');
    if (res.ok) {
      const data = await res.json();
      container.innerHTML = `
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1rem;">
          <div style="background: var(--bg-page); padding: 1rem; border-radius: var(--radius-md); border: 1px solid var(--border-color);">
            <div style="font-size: 0.75rem; font-weight: 700; color: var(--text-muted);">SSRF &amp; IP FILTERING</div>
            <div style="font-size: 1rem; font-weight: 700; color: var(--success); margin-top: 0.25rem;">✓ Active &amp; Enforced</div>
            <div style="font-size: 0.75rem; color: var(--text-secondary); margin-top: 0.25rem;">Blocks RFC1918, 127.0.0.1, localhost & metadata</div>
          </div>
          <div style="background: var(--bg-page); padding: 1rem; border-radius: var(--radius-md); border: 1px solid var(--border-color);">
            <div style="font-size: 0.75rem; font-weight: 700; color: var(--text-muted);">PUBLISHING GATE</div>
            <div style="font-size: 1rem; font-weight: 700; color: var(--success); margin-top: 0.25rem;">✓ Verified Only</div>
            <div style="font-size: 0.75rem; color: var(--text-secondary); margin-top: 0.25rem;">Strict publication filter on all student APIs</div>
          </div>
          <div style="background: var(--bg-page); padding: 1rem; border-radius: var(--radius-md); border: 1px solid var(--border-color);">
            <div style="font-size: 0.75rem; font-weight: 700; color: var(--text-muted);">TOKEN BLACKLIST</div>
            <div style="font-size: 1rem; font-weight: 700; color: var(--primary); margin-top: 0.25rem;">SHA-256 Validated</div>
            <div style="font-size: 0.75rem; color: var(--text-secondary); margin-top: 0.25rem;">Instant session revocation on logout</div>
          </div>
        </div>
      `;
    }
  } catch (e) {
    container.innerHTML = `<span style="color: var(--danger);">Error loading security status</span>`;
  }
}

async function loadAdminHealth() {
  const container = document.getElementById('admin-health-container');
  if (!container) return;

  try {
    const res = await fetchWithAuth('/api/admin/system-health');
    if (res.ok) {
      const health = await res.json();
      container.innerHTML = `
        <div style="font-weight: 700; color: ${health.status === 'HEALTHY' ? 'var(--success)' : 'var(--warning)'}; font-size: 1.1rem; margin-bottom: 1rem;">
          SYSTEM STATUS: ${escapeHtml(health.status)}
        </div>
        <div style="display: grid; grid-template-columns: 1fr 2fr; gap: 0.5rem; font-size: 0.875rem;">
          ${Object.entries(health.checks || {}).map(([k, v]) => `
            <div style="font-weight: 600;">${escapeHtml(k)}</div>
            <div>${escapeHtml(String(v))}</div>
          `).join('')}
        </div>
      `;
    }
  } catch (e) {
    container.innerHTML = `<span style="color: var(--danger);">Error checking health</span>`;
  }
}

// ==========================================================================
// AUTH MODAL
// ==========================================================================

let authMode = 'login';

function showAuthModal(mode = 'login') {
  authMode = mode;
  const modal = document.getElementById('auth-modal');
  const title = document.getElementById('auth-modal-title');
  const submitBtn = document.getElementById('auth-submit-btn');
  const prompt = document.getElementById('auth-toggle-prompt');
  const link = document.getElementById('auth-toggle-link');

  if (mode === 'login') {
    if (title) title.textContent = 'Sign In';
    if (submitBtn) submitBtn.textContent = 'Sign In';
    if (prompt) prompt.textContent = "Don't have an account?";
    if (link) link.textContent = 'Register';
  } else {
    if (title) title.textContent = 'Register Account';
    if (submitBtn) submitBtn.textContent = 'Create Account';
    if (prompt) prompt.textContent = 'Already have an account?';
    if (link) link.textContent = 'Sign In';
  }

  if (modal) modal.style.display = 'flex';
}

function closeAuthModal() {
  const modal = document.getElementById('auth-modal');
  if (modal) modal.style.display = 'none';
}

function toggleAuthMode() {
  showAuthModal(authMode === 'login' ? 'register' : 'login');
}

async function handleAuthSubmit(event) {
  event.preventDefault();
  const email = document.getElementById('auth-email').value.trim();
  const password = document.getElementById('auth-password').value;
  const errEl = document.getElementById('auth-error-msg');
  if (errEl) errEl.style.display = 'none';

  try {
    const endpoint = authMode === 'login' ? '/api/auth/login' : '/api/auth/register';
    const bodyPayload = authMode === 'login' 
      ? { email, password }
      : { email, password, name: email.split('@')[0], confirm_password: password };

    const res = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(bodyPayload)
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Authentication failed');
    }

    const data = await res.json();
    state.token = data.access_token;
    state.user = {
      id: data.user.id,
      email: data.user.email,
      name: data.user.email.split('@')[0],
      role: data.user.role
    };
    localStorage.setItem('internpilot_token', state.token);
    localStorage.setItem('internpilot_user', JSON.stringify(state.user));

    closeAuthModal();
    updateUserInterface();
    await loadSavedIds();
    showToast(authMode === 'login' ? 'Signed in successfully.' : 'Account created.');
    executeSearch();
  } catch (err) {
    if (errEl) {
      errEl.textContent = err.message;
      errEl.style.display = 'block';
    }
  }
}

// ==========================================================================
// HELPERS
// ==========================================================================

function getHostname(urlStr) {
  if (!urlStr) return '';
  try {
    const u = new URL(urlStr);
    return u.hostname.replace('www.', '');
  } catch (e) {
    return urlStr.substring(0, 20);
  }
}

function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function showToast(message, duration = 3000) {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = 'toast';
  toast.textContent = message;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transition = 'opacity 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, duration);
}
