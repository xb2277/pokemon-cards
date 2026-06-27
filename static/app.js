// Pokemon Cards Manager - Frontend Application Logic

const API = {
  cards: '/api/cards',
  dashboard: '/api/dashboard',
  prices: (id) => `/api/prices?card_id=${id}`,
  priceManual: '/api/prices/manual',
  upload: '/api/upload',
  searchTcg: (q) => `/api/search-tcg?q=${encodeURIComponent(q)}`,
};

let currentCardId = null; // for detail page
let editingImageChanged = false;

// ============ Auth ============

function getToken() {
  return localStorage.getItem('token') || '';
}

function isLoggedIn() {
  return !!getToken();
}

// ============ Utility ============

function $(sel) { return document.querySelector(sel); }
function $$(sel) { return document.querySelectorAll(sel); }

async function api(method, url, data) {
  const opts = { method };
  const headers = {};

  // Attach auth token
  const token = getToken();
  if (token) {
    headers['Authorization'] = 'Bearer ' + token;
  }

  if (!(data instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
    if (data) opts.body = JSON.stringify(data);
  } else {
    opts.body = data;
  }
  opts.headers = headers;

  const res = await fetch(url, opts);

  // Handle 401 — redirect to login
  if (res.status === 401) {
    localStorage.removeItem('token');
    if (window.location.pathname !== '/login') {
      window.location.href = '/login';
    }
    throw new Error('请先登录');
  }

  // Handle non-JSON responses
  let json;
  const contentType = res.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    json = await res.json();
  } else {
    const text = await res.text();
    throw new Error(`服务器错误 (${res.status}): ${text.slice(0, 200)}`);
  }

  if (!json.success) throw new Error(json.message || `Request failed (${res.status})`);
  return json;
}

// ============ Global Auth Nav ============

document.addEventListener('DOMContentLoaded', () => {
  const nav = document.querySelector('.nav-bar .nav-links');
  if (!nav) return;

  const token = getToken();
  if (token) {
    // Fetch user info and add to nav
    fetch('/api/auth/me', {
      headers: { 'Authorization': 'Bearer ' + token }
    })
    .then(r => r.json())
    .then(json => {
      if (json.success) {
        const u = json.data;
        const userMenu = document.createElement('span');
        userMenu.style.cssText = 'display:flex;align-items:center;gap:8px;margin-left:12px;font-size:13px;';
        userMenu.innerHTML = `
          <span style="color:var(--text-secondary);">${u.nick_name || '用户'}</span>
          ${u.role === 'admin' ? '<a href="/admin" style="color:var(--gold-500);font-weight:600;">管理</a>' : ''}
          <a href="#" class="logout-link" style="color:var(--text-muted);">退出</a>
        `;
        nav.appendChild(userMenu);

        // Bind logout click event
        userMenu.querySelector('.logout-link').addEventListener('click', function(e) {
          e.preventDefault();
          localStorage.clear();
          window.location.href = '/login';
        });
      }
    })
    .catch(() => {});
  } else {
    const loginLink = document.createElement('a');
    loginLink.href = '/login';
    loginLink.textContent = '登录';
    loginLink.style.cssText = 'margin-left:12px;';
    nav.appendChild(loginLink);

    const registerLink = document.createElement('a');
    registerLink.href = '/register';
    registerLink.textContent = '注册';
    registerLink.style.cssText = 'margin-left:8px;color:var(--gold-500);';
    nav.appendChild(registerLink);
  }
});

function showToast(msg, type = 'info') {
  const container = $('#toastContainer') || createToastContainer();
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.textContent = msg;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 3000);
}

function createToastContainer() {
  const c = document.createElement('div');
  c.id = 'toastContainer';
  c.className = 'toast-container';
  document.body.appendChild(c);
  return c;
}

function formatMoney(n) {
  if (n == null || isNaN(n)) return '--';
  return '\u00a5' + Math.round(Number(n)).toLocaleString('zh-CN');
}

function rarityLabel(r) {
  const map = {
    'C': 'Common', 'U': 'Uncommon', 'R': 'Rare', 'RR': 'Double Rare',
    'SR': 'Special Rare', 'SAR': 'Special Art Rare', 'UR': 'Ultra Rare',
    'CSR': 'Character Super Rare', 'HR': 'Hyper Rare'
  };
  return map[r] || r;
}

function conditionLabel(c) {
  const map = { 'NM': '近全新', 'LP': '轻微使用', 'MP': '中度磨损', 'HP': '重度磨损', 'Damaged': '损坏' };
  return map[c] || c;
}

// ============ Card Library Page (index.html) ============

let allCards = [];
let debounceTimer = null;
let currentView = 'table'; // default: table view on homepage

document.addEventListener('DOMContentLoaded', () => {
  // Only run on index page
  if (!$('#cardsGrid')) return;
  loadCards();
  loadRarityOptions();

  $('#searchInput').addEventListener('input', () => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(renderCards, 300);
  });
  $('#rarityFilter').addEventListener('change', renderCards);
  $('#sortBySelect').addEventListener('change', renderCards);

  // Keyboard shortcuts
  document.addEventListener('keydown', (e) => {
    if (e.key === 'n' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); openAddModal(); }
    if (e.key === '/' && !['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName)) {
      e.preventDefault(); $('#searchInput').focus(); }
  });
});

async function loadCards() {
  try {
    const res = await api('GET', API.cards + '?sort_by=updated_at&limit=500');
    allCards = res.data || [];
    renderCards();
  } catch(e) { showToast('加载卡牌失败: ' + e.message, 'error'); }
}

function renderCards() {
  const search = ($('#searchInput').value || '').trim().toLowerCase();
  const rarity = $('#rarityFilter').value;
  const sortBy = $('#sortBySelect').value;
  let filtered = [...allCards];

  if (search) {
    filtered = filtered.filter(c =>
      c.name.toLowerCase().includes(search) ||
      (c.name_en||'').toLowerCase().includes(search) ||
      (c.card_number||'').toLowerCase().includes(search) ||
      (c.set_name||'').toLowerCase().includes(search)
    );
  }

  if (rarity && rarity !== 'all') {
    filtered = filtered.filter(c => c.rarity === rarity);
  }

  // Sort
  if (sortBy === 'name') {
    filtered.sort((a,b) => a.name.localeCompare(b.name));
  } else if (sortBy === 'set_name') {
    filtered.sort((a,b) => (a.set_name||'').localeCompare(b.set_name||''));
  } else if (sortBy === 'rarity') {
    const order = ['C','U','R','RR','SR','SAR','UR','CSR','HR'];
    filtered.sort((a,b) => order.indexOf(a.rarity) - order.indexOf(b.rarity));
  } else if (sortBy === 'quantity') {
    filtered.sort((a,b) => b.quantity - a.quantity);
  } else if (sortBy === 'cost_price') {
    filtered.sort((a,b) => (b.cost_price||0) - (a.cost_price||0));
  }
  // else: updated_at (default, already sorted from API)

  const grid = $('#cardsGrid');
  const empty = $('#emptyState');
  const tbody = $('#inventoryTableBody');

  // Always keep the section header visible (toggle buttons)
  const sectionHeader = $('#inventorySection');
  if (sectionHeader) sectionHeader.style.display = 'block';

  if (filtered.length === 0) {
    grid.innerHTML = '';
    if (tbody) tbody.innerHTML = '';
    empty.style.display = 'block';
    updateStatsBar(allCards);
    return;
  }

  empty.style.display = 'none';

  // Always render both views
  grid.innerHTML = filtered.map(card => renderCardItem(card)).join('');

  if (tbody) {
    tbody.innerHTML = filtered.map(card => renderTableRow(card)).join('');
  }

  // Show/hide based on current view
  applyView(currentView);

  updateStatsBar(filtered);
}

function renderTableRow(c) {
  const thumbHtml = c.image_path
    ? `<img class="table-card-thumb" src="${c.image_path}" alt="" loading="lazy">`
    : '';
  const mp = c.market_price || 0;
  return `<tr onclick="window.location='/card/${c.id}'">
    <td><div class="table-card-name-cell">${thumbHtml}<span>${c.name}</span></div></td>
    <td>${c.set_name || '--'}</td>
    <td style="font-family:'JetBrains Mono',monospace;font-size:12px;">${c.card_number || '--'}</td>
    <td><span class="rarity-badge badge-${c.rarity}">${c.rarity || '--'}</span></td>
    <td>${conditionLabel(c.condition)}</td>
    <td style="font-weight:700;color:var(--gold-500);">${c.quantity}</td>
    <td style="font-family:'JetBrains Mono',monospace;">${formatMoney(c.cost_price)}</td>
    <td style="font-family:'JetBrains Mono',monospace;color:var(--gold-600);">${formatMoney(mp)}</td>
    <td style="font-weight:700;color:var(--red-500);">${formatMoney(mp * (c.quantity||1))}</td>
    <td><button class="table-action-btn" onclick="event.stopPropagation();window.location='/card/${c.id}'">详情</button></td>
  </tr>`;
}

function toggleView(view) {
  currentView = view;
  applyView(view);

  // Update button states
  const btnT = $('#btnTableView');
  const btnG = $('#btnGridView');
  if (btnT) btnT.classList.toggle('active', view === 'table');
  if (btnG) btnG.classList.toggle('active', view === 'grid');
}

function applyView(view) {
  const grid = $('#cardsGrid');
  const tableWrapper = $('#inventoryTableWrapper');
  if (!grid) return;

  if (view === 'table') {
    grid.style.display = 'none';
    if (tableWrapper) tableWrapper.style.display = 'block';
  } else {
    grid.style.display = 'grid';
    if (tableWrapper) tableWrapper.style.display = 'none';
  }
}

function renderCardItem(c) {
  const imgHtml = c.image_path
    ? `<img src="${c.image_path}" alt="${c.name}" loading="lazy">`
    : `<div class="card-img-placeholder">&#9830;</div>`;
  const mp = c.market_price || 0;
  return `
    <div class="card-item" onclick="window.location='/card/${c.id}'">
      <div class="card-img-wrap">${imgHtml}</div>
      <div class="card-info">
        <div class="card-name" title="${c.name}">${c.name}</div>
        <div class="card-meta">
          <span class="card-number">${c.card_number || c.set_name || '--'}</span>
          <span class="card-qty">x${c.quantity}</span>
        </div>
        <div class="card-price-row">
          <span class="card-cost">收购 ${formatMoney(c.cost_price)}</span>
          <span class="card-market" style="color:var(--gold-600);">市场 ${formatMoney(mp)}</span>
        </div>
      </div>
    </div>`;
}

function updateStatsBar(cards) {
  const bar = $('#statsBar');
  if (!bar) return;
  const totalQty = cards.reduce((s, c) => s + (c.quantity||1), 0);
  const totalCost = cards.reduce((s, c) => s + ((c.cost_price||0) * (c.quantity||1)), 0);
  const totalValue = cards.reduce((s, c) => s + ((c.market_price||0) * (c.quantity||1)), 0);
  bar.innerHTML = `
    <div class="stat-card"><div class="stat-label">总卡牌种类</div><div class="stat-value">${cards.length}</div></div>
    <div class="stat-card green"><div class="stat-label">总持有张数</div><div class="stat-value">${totalQty}</div></div>
    <div class="stat-card orange"><div class="stat-label">总成本</div><div class="stat-value">${formatMoney(totalCost)}</div></div>
    <div class="stat-card red"><div class="stat-label">持有总价（市场）</div><div class="stat-value" style="color:var(--red-500);">${formatMoney(totalValue)}</div></div>
  `;
}

async function loadRarityOptions() {
  try {
    const res = await api('GET', '/api/sets-info');
    const sel = $('#rarityFilter');
    if (res.data && res.data.rarities) {
      // Already has default "all" option
    }
  } catch {}
}

// ============ Add/Edit Modal ============

function openAddModal() {
  currentCardId = null;
  $('#modalTitle').textContent = '新增卡牌';
  $('#cardForm').reset();
  $('#imagePreview').style.display = 'none';
  const previewWrap = $('.image-preview-wrap');
  if (previewWrap) previewWrap.classList.remove('has-image');
  $('#uploadHint').style.display = 'block';
  $('#cardModal').classList.add('show');
  // Reset catalog search state
  const catalogQuickSearch = $('#catalogQuickSearch');
  if (catalogQuickSearch) {
    catalogQuickSearch.value = '';
    const dropdown = $('#catalogDropdown');
    if (dropdown) dropdown.classList.remove('open');
    const selectedCard = $('#catalogSelectedCard');
    if (selectedCard) selectedCard.style.display = 'none';
    delete $('#cardForm').dataset.catalogImageUrl;
  }
  const catalogSelect = $('#catalogSelect');
  if (catalogSelect) catalogSelect.value = '';
  // Populate catalog dropdown
  loadCatalogOptions();
}

function closeModal() {
  $('#cardModal').classList.remove('show');
  currentCardId = null;
}

async function saveCard(event) {
  event.preventDefault();
  const form = $('#cardForm');
  const fd = new FormData(form);

  // Build plain object from form fields
  const data = {};
  for (const [key, value] of fd.entries()) {
    data[key] = value;
  }

  // Handle image
  const fileInput = $('#imageInput');
  if (fileInput.files[0]) {
    // If there's a file, we need to upload it separately first
    // For now, skip file upload in this flow - use catalog image or empty
  } else if (form.dataset.catalogImageUrl) {
    data.image_path = form.dataset.catalogImageUrl;
  }

  try {
    let res;
    if (data.catalog_id && !currentCardId) {
      // 新增模式 + 已选数据库卡牌 → 走 from-catalog 接口
      const payload = {
        catalog_id: parseInt(data.catalog_id),
        quantity:   parseInt(data.quantity)  || 1,
        cost_price: parseFloat(data.cost_price) || 0,
        condition:  data.condition  || 'NM',
        notes:      data.notes      || '',
      };
      res = await api('POST', '/api/cards/from-catalog', payload);
    } else {
      // 编辑模式 或 未选数据库卡牌（个人卡）→ 走普通接口
      res = await api(currentCardId ? 'PUT' : 'POST',
                 currentCardId ? `${API.cards}/${currentCardId}` : API.cards,
                 data);
    }
    closeModal();
    showToast(`"${res.data.name}" ${currentCardId ? '已更新' : '已添加'}`, 'success');
    loadCards();
  } catch(e) { showToast(e.message, 'error'); }
}

function previewImage(event) {
  const file = event.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = (e) => {
    const preview = $('#imagePreview');
    preview.src = e.target.result;
    preview.style.display = 'block';
    const wrap = $('.image-preview-wrap');
    if (wrap) wrap.classList.add('has-image');
    $('#uploadHint').style.display = 'none';
  };
  reader.readAsDataURL(file);
}

// ============ Delete Modal ============

let deleteTargetId = null;
function openDeleteModal(id, name) {
  deleteTargetId = id;
  $('#deleteCardName').textContent = name || '';
  $('#deleteModal').classList.add('show');
}
function closeDeleteModal() { $('#deleteModal').classList.remove('show'); deleteTargetId = null; }

async function confirmDelete() {
  if (!deleteTargetId) return;
  try {
    await api('DELETE', `${API.cards}/${deleteTargetId}`);
    closeDeleteModal();
    showToast('已删除', 'success');
    loadCards();
  } catch(e) { showToast(e.message, 'error'); }
}


// ============ Dashboard Page (dashboard.html) ============

async function loadDashboard() {
  try {
    const res = await api('GET', API.dashboard);
    const d = res.data;
    renderDashStats(d);
    renderDashTrend(d.snapshots || []);
    renderDashDist(d.rarity_distribution || []);
    renderRankings(d.top_gainers || [], d.top_losers || []);
  } catch(e) { showToast('加载看板数据失败: ' + e.message, 'error'); }
}

function renderDashStats(d) {
  const el = $('#dashStats');
  if (!el) return;
  const profitClass = d.profit >= 0 ? 'positive' : 'negative';
  el.innerHTML = `
    <div class="stat-card"><div class="stat-label">卡牌种类</div><div class="stat-value">${d.total_cards}</div><div class="stat-sub">共 ${d.total_quantity} 张</div></div>
    <div class="stat-card orange"><div class="stat-label">总成本</div><div class="stat-value">${formatMoney(d.total_cost)}</div></div>
    <div class="stat-card green"><div class="stat-label">当前估值</div><div class="stat-value">${formatMoney(d.total_value)}<br><span style="font-size:12px;color:var(--text-muted);font-weight:400;">${d.valued_cards} 张有价格</span></div></div>
    <div class="stat-card ${d.profit >= 0 ? 'green' : 'red'}"><div class="stat-label">预估盈亏</div><div class="stat-value ${profitClass}">${d.profit >= 0 ? '+' : ''}${formatMoney(d.profit)}<br><span style="font-size:12px;font-weight:400;">${d.profit_pct >= 0 ? '+' : ''}${d.profit_pct}%</span></div></div>
  `;
}

function renderDashTrend(snapshots) {
  const chart = echarts.init($('#dashboardTrendChart'));
  const dates = snapshots.map(s => s.snapshot_date);
  const values = snapshots.map(s => s.total_value);
  chart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 50, right: 20, top: 20, bottom: 30 },
    xAxis: { type: 'category', data: dates, axisLabel: { fontSize: 11 }, boundaryGap: false },
    yAxis: { type: 'value', axisLabel: { formatter: v => formatMoney(v), fontSize: 11 } },
    series: [{
      type: 'line', data: values,
      smooth: true,
      areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{offset:0,color:'rgba(55,138,221,0.15)'},{offset:1,color:'rgba(55,138,221,0.01)'}] }},
      lineStyle: { color: '#378add', width: 2 },
      itemStyle: { color: '#378add' },
      symbolSize: 4,
    }]
  });
  window.addEventListener('resize', () => chart.resize());
}

function renderDashDist(dist) {
  const chart = echarts.init($('#dashboardDistChart'));
  const colors = ['#B4B2A9','#9FE1CB','#FAC775','#CECBF6','#F5C4B3','#F0997B','#D4537E','#993C1D','#3B6D11'];
  chart.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { orient: 'right', right: 0, top: 'center', textStyle:{fontSize:11} },
    series: [{
      type: 'pie', radius: ['40%', '70%'], center: ['35%', '50%'],
      label: { show: false },
      emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,.15)' } },
      data: dist.map((d,i) => ({ name: d.name || d.value, value: d.value, itemStyle: {color: colors[i%colors.length]} }))
    }]
  });
  window.addEventListener('resize', () => chart.resize());
}

function renderRankings(gainers, losers) {
  const gl = $('#gainersList');
  const ll = $('#losersList');
  if (gl) gl.innerHTML = gainers.map((g,i) => renderRankItem(g, i+1, 'up')).join('') || '<li style="padding:24px;text-align:center;color:var(--text-muted)">暂无数据（需要先录入价格）</li>';
  if (ll) ll.innerHTML = losers.map((l,i) => renderRankItem(l, i+1, 'down')).join('') || '<li style="padding:24px;text-align:center;color:var(--text-muted)">暂无数据</li>';
}

function renderRankItem(item, rank, direction) {
  const numClass = rank <= 3 ? `top${rank}` : '';
  return `<li class="rank-item">
    <span class="rank-num ${numClass}">${rank}</span>
    <span class="rank-name" title="${item.name}">${item.name}</span>
    <span class="rank-change ${direction === 'up' ? 'up' : 'down'}">${item.change_pct >= 0 ? '+' : ''}${item.change_pct}%</span>
    <span class="rank-price">${formatMoney(item.current)}</span>
  </li>`;
}


// ============ Price Page (price.html) ============

let priceChartInstance = null;
let currentCatalogId = null;
let priceCatalogItems = [];


async function loadPricePage(shouldSeed) {
  // Load catalog items
  try {
    const res = await api('GET', '/api/catalog?per_page=500');
    priceCatalogItems = res.data || [];

    populatePriceCatalogSelect(priceCatalogItems);
    bindPriceSearch();

    // Seed: ensure Gengar exists, then auto-select
    if (shouldSeed) {
      await seedGengarIfNeeded();
    }
  } catch(e) {
    console.error('loadPricePage error:', e);
  }
}


function populatePriceCatalogSelect(items) {
  const sel = $('#priceCatalogSelect');
  if (!sel) return;
  sel.innerHTML = '<option value="">-- 从卡牌数据库选择 --</option>';

  // Group by set_name
  const groups = {};
  items.forEach(it => {
    const key = it.set_name || '其他';
    if (!groups[key]) groups[key] = [];
    groups[key].push(it);
  });

  Object.keys(groups).sort().forEach(setName => {
    const optgroup = document.createElement('optgroup');
    optgroup.label = setName;
    groups[setName].forEach(it => {
      const opt = document.createElement('option');
      opt.value = it.id;
      opt.textContent = `${it.name}${it.name_en ? ' / ' + it.name_en : ''}  ${it.card_number ? '#'+it.card_number : ''}  ${it.rarity ? '['+it.rarity+']' : ''}`;
      opt.dataset.itemJson = JSON.stringify(it);
      optgroup.appendChild(opt);
    });
    sel.appendChild(optgroup);
  });

  sel.addEventListener('change', onPriceCatalogSelectChange);
}


function bindPriceSearch() {
  const input = $('#priceCatalogSearch');
  const dropdown = $('#priceSearchDropdown');
  if (!input || !dropdown) return;

  let debounceTimer;
  input.addEventListener('input', () => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      const q = input.value.trim();
      if (q.length < 1) { dropdown.classList.remove('open'); return; }
      const matches = priceCatalogItems.filter(it =>
        it.name.includes(q) || (it.name_en || '').toLowerCase().includes(q.toLowerCase())
      ).slice(0, 20);
      renderPriceSearchDropdown(matches);
    }, 200);
  });

  input.addEventListener('focus', () => {
    const q = input.value.trim();
    if (q.length >= 1) {
      const matches = priceCatalogItems.filter(it =>
        it.name.includes(q) || (it.name_en || '').toLowerCase().includes(q.toLowerCase())
      ).slice(0, 20);
      renderPriceSearchDropdown(matches);
    }
  });

  document.addEventListener('click', (e) => {
    if (!e.target.closest('.price-search-block')) {
      dropdown.classList.remove('open');
    }
  });
}


function renderPriceSearchDropdown(items) {
  const dropdown = $('#priceSearchDropdown');
  if (!dropdown) return;
  if (!items.length) {
    dropdown.innerHTML = '<div class="catalog-dropdown-empty">未找到匹配的卡牌</div>';
    dropdown.classList.add('open');
    return;
  }
  dropdown.innerHTML = items.map(it => {
    const img = it.image_url
      ? `<img class="price-search-thumb" src="${it.image_url}" alt="">`
      : `<div class="price-search-thumb-placeholder">?</div>`;
    return `<div class="price-search-item" data-id="${it.id}">
      ${img}
      <div class="price-search-item-info">
        <div class="price-search-item-name">${it.name}${it.name_en ? ' / <span class="en">'+it.name_en+'</span>' : ''}</div>
        <div class="price-search-item-meta">${it.set_name || ''}  ${it.card_number || ''}</div>
      </div>
    </div>`;
  }).join('');
  dropdown.classList.add('open');

  dropdown.querySelectorAll('.price-search-item').forEach(el => {
    el.addEventListener('click', () => {
      const id = parseInt(el.dataset.id);
      const item = priceCatalogItems.find(it => it.id === id);
      if (item) selectPriceCatalogItem(item);
      dropdown.classList.remove('open');
      $('#priceCatalogSearch').value = '';
    });
  });
}


async function selectPriceCatalogItem(item) {
  currentCatalogId = item.id;
  updatePriceHeroUI(item, null);

  // Always show price panel — prices are tied to catalog, not user collection
  loadCatalogPrices(item.id);

  // Sync select
  const sel = $('#priceCatalogSelect');
  if (sel) sel.value = item.id;
}


function onPriceCatalogSelectChange() {
  const sel = $('#priceCatalogSelect');
  const id = parseInt(sel.value);
  if (!id) return;
  const item = priceCatalogItems.find(it => it.id === id);
  if (item) selectPriceCatalogItem(item);
}


function updatePriceHeroUI(item, card) {
  const title = $('#heroTitle');
  const subtitle = $('#heroSubtitle');
  const img = $('#heroImg');
  const placeholder = $('#heroImgPlaceholder');

  if (title) title.textContent = item.name + (item.name_en ? ' / ' + item.name_en : '');
  if (subtitle) subtitle.textContent = [item.set_name, item.card_number, item.rarity].filter(Boolean).join('  ·  ');

  if (item.image_url) {
    if (img) {
      img.src = item.image_url;
      img.style.display = 'block';
    }
    if (placeholder) placeholder.style.display = 'none';
  } else {
    if (img) img.style.display = 'none';
    if (placeholder) placeholder.style.display = 'flex';
  }
}


async function seedGengarIfNeeded() {
  // Check if any catalog item matches 耿鬼 or Gengar
  let gengar = priceCatalogItems.find(it =>
    it.name === '耿鬼' || (it.name_en || '').toLowerCase() === 'gengar'
  );

  if (!gengar) {
    // Create Gengar in catalog
    try {
      const res = await api('POST', '/api/catalog', {
        name: '耿鬼',
        name_en: 'Gengar',
        set_name: '闪色珍贵卡盒',
        card_number: '119/086',
        rarity: 'SAR',
        image_url: 'https://images.pokemontcg.io/swsh12pt5/119_hires.png',
        description: '闪色珍贵卡盒 耿鬼 SAR',
      });
      gengar = res.data;
      priceCatalogItems.push(gengar);
      populatePriceCatalogSelect(priceCatalogItems);
    } catch(e) {
      console.error('Failed to seed Gengar:', e);
      return;
    }
  }

  // Ensure price history exists for this card
  await ensureGengarPriceData(gengar.id);

  // Auto-select Gengar
  selectPriceCatalogItem(gengar);
}


async function ensureGengarPriceData(catalogId) {
  // Price data is tied to catalog_id, so we can seed directly
  try {
    // Check existing price records
    const priceRes = await api('GET', `/api/prices?catalog_id=${catalogId}`);
    if (priceRes.data.history && priceRes.data.history.length > 0) return; // already has data

    // Insert sample price history
    const today = new Date();
    const samples = [];
    let base = 1200;
    for (let i = 60; i >= 0; i -= 3) {
      const d = new Date(today);
      d.setDate(d.getDate() - i);
      const dateStr = d.toISOString().split('T')[0];
      const price = Math.round(base + (Math.random() - 0.5) * 300);
      samples.push({ catalog_id: catalogId, platform: '闲鱼', price, date: dateStr });
      base += (Math.random() - 0.45) * 20;
      if (base < 600) base = 600;
      if (base > 2500) base = 2500;
    }
    for (const s of samples) {
      try {
        await api('POST', '/api/prices/manual', {
          catalog_id: s.catalog_id,
          platform: s.platform,
          price: Math.round(s.price),
        });
      } catch(e) {}
    }
  } catch(e) {
    console.error('ensureGengarPriceData error:', e);
  }
}


async function loadCatalogPrices(catalogId) {
  try {
    const res = await api('GET', `/api/prices?catalog_id=${catalogId}`);
    const data = res.data;
    const latest = data.latest;
    const history = data.history || [];

    $('#priceCurrentPanel').style.display = 'grid';
    $('#chartArea').style.display = 'block';
    $('#manualInputArea').style.display = 'block';
    $('#priceEmptyState').style.display = 'none';

    $('#statAvgPrice').textContent = latest.avg != null ? formatMoney(latest.avg) : '--';
    $('#statMaxPrice').textContent = latest.max != null ? formatMoney(latest.max) : '--';
    $('#statMinPrice').textContent = latest.min != null ? formatMoney(latest.min) : '--';
    $('#statRecordCount').textContent = latest.count || 0;

    renderPriceChart(history.reverse());
  } catch(e) { showToast('加载价格失败: ' + e.message, 'error'); }
}


function renderPriceChart(history) {
  if (!history.length) {
    $('#chartArea').innerHTML = '<p style="text-align:center;padding:40px;color:var(--text-muted);">暂无价格记录，请手动录入或刷新抓取</p>';
    return;
  }

  if (priceChartInstance) priceChartInstance.dispose();
  priceChartInstance = echarts.init($('#priceChart'));

  const platforms = {};
  history.forEach(h => {
    if (!platforms[h.platform]) platforms[h.platform] = [];
    platforms[h.platform].push([h.recorded_at, h.price]);
  });

  const dates = [...new Set(history.map(h => h.recorded_at.split(' ')[0]))].sort();
  const platformColors = {'tcgplayer':'#378add','xianyu':'#d85a30','taobao':'#ff6b35','manual':'#888780','pokemontcg':'#534ab7','闲鱼':'#d85a30'};
  const series = Object.keys(platforms).map(p => ({
    name: p, type: 'line', smooth: true, symbolSize: 4,
    lineStyle: { width: 1.8 },
    itemStyle: { color: platformColors[p] || '#888780' },
    data: platforms[p].map(([t,v]) => [t.split(' ')[0], v])
  }));

  priceChartInstance.setOption({
    tooltip: { trigger: 'axis', axisPointer: {type: 'cross'} },
    legend: { top: 0, textStyle: {fontSize:11} },
    grid: { left: 60, right: 20, top: 36, bottom: 32 },
    xAxis: { type: 'category', data: dates, axisLabel: { fontSize: 10, rotate: 20 }, boundaryGap: false },
    yAxis: { type: 'value', axisLabel: { formatter: v => formatMoney(v), fontSize: 11 } },
    series
  });
  window.addEventListener('resize', () => priceChartInstance && priceChartInstance.resize());
}


async function refreshCardPrice() {
  if (!currentCatalogId) { showToast('请先选择一张卡', 'info'); return; }
  const btn = $('#refreshBtn');
  btn.disabled = true; btn.textContent = '抓取中...';

  try {
    const result = await api('POST', '/api/prices/fetch', { catalog_id: currentCatalogId });
    if (result.success) {
      const prices = result.prices || [];
      const priceStr = prices.map(p => `${p.platform}: ¥${p.price}`).join(', ');
      showToast(`抓取成功！${priceStr}`, 'success');
      loadCatalogPrices(currentCatalogId);
    } else {
      showToast(`抓取失败: ${result.message}`, 'info');
    }
  } catch(e) {
    showToast('抓取失败: ' + e.message, 'error');
  }
  btn.disabled = false; btn.textContent = '刷新价格';
}


async function submitManualPrice(event) {
  event.preventDefault();
  if (!currentCatalogId) return;
  const price = parseFloat($('#manualPrice').value);
  const platform = $('#manualPlatform').value.trim() || '手动录入';
  try {
    await api('POST', '/api/prices/manual', { catalog_id: currentCatalogId, platform, price });
    showToast(`已录入 ¥${price}`, 'success');
    $('#manualPrice').value = '';
    loadCatalogPrices(currentCatalogId);
  } catch(e) { showToast(e.message, 'error'); }
}

// ============ Detail Page (card_detail.html) ============

let detailCard = null;

async function loadDetailPage() {
  const pathParts = window.location.pathname.split('/');
  const cardId = pathParts[pathParts.length - 1];
  currentCardId = cardId;

  try {
    const res = await api('GET', `${API.cards}/${cardId}`);
    detailCard = res.data;

    // Fetch latest price from price_records (best-effort)
    let priceData = null;
    try {
      const priceRes = await api('GET', API.prices(cardId));
      if (priceRes && priceRes.data && priceRes.data.latest && priceRes.data.latest.avg != null) {
        priceData = priceRes.data.latest;
      }
    } catch(e) {
      console.warn('Price fetch failed:', e.message);
    }

    renderDetail(detailCard, priceData);
  } catch(e) {
    document.querySelector('.detail-grid').innerHTML = '<div class="empty-state"><p>卡牌未找到</p><a href="/" class="btn btn-outline">返回我的卡牌</a></div>';
  }
}

function renderDetail(c, priceData) {
  document.title = `${c.name} - Pokemon Card Manager`;

  // Image
  const img = $('#detailImage');
  if (c.image_path) { img.src = c.image_path; img.style.display = 'inline'; }
  else { img.style.display = 'none'; $('#imageSection').innerHTML += '<div class="card-img-placeholder" style="width:180px;height:250px;display:inline-flex;">&#9830;</div>'; }

  $('#detailName').textContent = c.name;
  $('#detailNameEn').textContent = c.name_en || '';

  // Use priceData.avg if available (more up-to-date than c.market_price)
  const displayPrice = (priceData && priceData.avg > 0) ? priceData.avg : (c.market_price || 0);
  const costPrice = c.cost_price || 0;
  const quantity = c.quantity || 1;
  const totalValue = displayPrice * quantity;
  const profit = displayPrice - costPrice;
  const profitPct = costPrice > 0 ? ((profit / costPrice) * 100).toFixed(1) : 0;
  const priceLabel = (priceData && priceData.avg > 0) ? '元/张（实时）' : '元/张';

  // ---- 基本信息卡 ----
  $('#detailBasicInfo').innerHTML = [
    ['系列', c.set_name || '--'],
    ['编号', c.card_number || '--'],
    ['稀有度', `<span class="rarity-badge badge-${c.rarity}">${c.rarity}</span> ${rarityLabel(c.rarity)}`],
    ['品相', conditionLabel(c.condition)],
  ].map(([k,v]) => `<div class="detail-info-row"><span class="detail-info-label">${k}</span><span class="detail-info-value">${v}</span></div>`).join('');

  // ---- 持有信息卡 ----
  $('#detailHoldInfo').innerHTML = [
    ['持有数量', `${quantity} 张`],
    ['收购单价', formatMoney(costPrice)],
    ['入库备注', c.notes || '--'],
  ].map(([k,v]) => `<div class="detail-info-row"><span class="detail-info-label">${k}</span><span class="detail-info-value">${v}</span></div>`).join('');

  // ---- 价格信息卡 ----
  $('#detailPriceInfo').innerHTML = `
    <div class="detail-price-hero">
      <div class="detail-price-main">
        <span class="detail-price-number">${displayPrice > 0 ? formatMoney(displayPrice) : '暂无'}</span>
        <span class="detail-price-unit">${priceLabel}</span>
      </div>
    </div>
    <div class="detail-price-rows">
      <div class="detail-info-row">
        <span class="detail-info-label">持有总价</span>
        <span class="detail-info-value" style="color:var(--red-500);font-weight:700;">${formatMoney(totalValue)}</span>
      </div>
      <div class="detail-info-row">
        <span class="detail-info-label">收购成本</span>
        <span class="detail-info-value">${formatMoney(costPrice * quantity)}</span>
      </div>
      ${costPrice > 0 && displayPrice > 0 ? `
      <div class="detail-info-row" id="detailProfitRow">
        <span class="detail-info-label">盈亏</span>
        <span class="detail-info-value" style="color:${profit >= 0 ? 'var(--green-500)' : 'var(--red-500)'};font-weight:700;">
          ${profit >= 0 ? '+' : ''}${formatMoney(profit)} (${profit >= 0 ? '+' : ''}${profitPct}%)
        </span>
      </div>` : ''}
    </div>
  `;
}

function openEditModal() {
  if (!detailCard) return;
  const form = $('#editForm');
  form.reset();

  // Fill fields
  form.elements['name'].value = detailCard.name || '';
  form.elements['name_en'].value = detailCard.name_en || '';
  form.elements['set_name'].value = detailCard.set_name || '';
  form.elements['card_number'].value = detailCard.card_number || '';
  form.elements['rarity'].value = detailCard.rarity || 'R';
  form.elements['condition'].value = detailCard.condition || 'NM';
  form.elements['quantity'].value = detailCard.quantity || 1;
  form.elements['cost_price'].value = detailCard.cost_price || '';
  form.elements['market_price'].value = detailCard.market_price || '';
  form.elements['notes'].value = detailCard.notes || '';
  $('#editCardId').value = detailCard.id;

  // Image preview
  if (detailCard.image_path) {
    $('#editImagePreview').src = detailCard.image_path;
    $('#editImagePreview').style.display = 'block';
    $('#editUploadHint').style.display = 'none';
  } else {
    $('#editImagePreview').style.display = 'none';
    $('#editUploadHint').style.display = 'block';
  }
  editingImageChanged = false;

  $('#editModal').classList.add('show');
}

function closeEditModal() { $('#editModal').classList.remove('show'); editingImageChanged = false; }

function previewEditImage(event) {
  const file = event.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = (e) => {
    $('#editImagePreview').src = e.target.result;
    $('#editImagePreview').style.display = 'block';
    $('#editUploadHint').style.display = 'none';
    editingImageChanged = true;
  };
  reader.readAsDataURL(file);
}

async function saveEditCard(event) {
  event.preventDefault();
  if (!currentCardId) return;

  const formData = new FormData($('#editForm'));
  if (editingImageChanged) {
    const fileInput = $('#editImageInput');
    if (fileInput.files[0]) formData.append('file', fileInput.files[0]);
  }

  // Build JSON payload
  const data = {
    name: formData.get('name'),
    name_en: formData.get('name_en'),
    set_name: formData.get('set_name'),
    card_number: formData.get('card_number'),
    rarity: formData.get('rarity'),
    condition: formData.get('condition'),
    quantity: parseInt(formData.get('quantity')) || 1,
    cost_price: parseFloat(formData.get('cost_price')) || 0,
    market_price: parseFloat(formData.get('market_price')) || 0,
    notes: formData.get('notes'),
  };

  try {
    const res = await api('PUT', `${API.cards}/${currentCardId}`, data);
    closeEditModal();
    showToast('已更新', 'success');
    detailCard = res.data;
    renderDetail(res.data);
  } catch(e) { showToast(e.message, 'error'); }
}

function openDeleteModal() {
  if (!detailCard) return;
  deleteTargetId = currentCardId;
  $('#deleteCardName').textContent = detailCard.name;
  $('#deleteModal').classList.add('show');
}

async function confirmDeleteDetail() {
  if (!deleteTargetId) return;
  try {
    await api('DELETE', `${API.cards}/${deleteTargetId}`);
    closeDeleteModal();
    showToast('已删除', 'success');
    setTimeout(() => window.location.href = '/', 800);
  } catch(e) { showToast(e.message, 'error'); }
}


// ============ Catalog Select Dropdown (inside Add Card modal) ============

async function loadCatalogOptions() {
  const sel = $('#catalogSelect');
  if (!sel) return;
  // Reset
  sel.innerHTML = '<option value="">-- 选择卡牌 --</option>';
  try {
    const res = await api('GET', '/api/catalog?per_page=200');
    const items = res.data || [];
    if (items.length === 0) {
      sel.innerHTML = '<option value="">(数据库暂无卡种)</option>';
      return;
    }
    // Group by set_name for readability
    const groups = {};
    items.forEach(item => {
      const setName = item.set_name || '未分类';
      if (!groups[setName]) groups[setName] = [];
      groups[setName].push(item);
    });
    for (const [setName, groupItems] of Object.entries(groups)) {
      const optGroup = document.createElement('optgroup');
      optGroup.label = setName;
      groupItems.forEach(item => {
        const opt = document.createElement('option');
        opt.value = item.id;
        const metaParts = [item.card_number, item.rarity].filter(Boolean);
        opt.textContent = `${item.name}${metaParts.length ? ' (' + metaParts.join(' · ') + ')' : ''}`;
        opt.dataset.itemJson = JSON.stringify(item);
        optGroup.appendChild(opt);
      });
      sel.appendChild(optGroup);
    }
  } catch (e) {
    console.error('Failed to load catalog options:', e);
  }
}

function onCatalogSelectChange(value) {
  if (!value) return; // -- 选择卡牌 --
  const sel = $('#catalogSelect');
  const selectedOption = sel.options[sel.selectedIndex];
  let item = null;
  if (selectedOption && selectedOption.dataset.itemJson) {
    try { item = JSON.parse(selectedOption.dataset.itemJson); } catch {}
  }
  // Fallback: fetch by ID
  if (!item) {
    api('GET', `/api/catalog/${value}`).then(res => { item = res.data; fillFormFromCatalog(item); }).catch(() => {});
    return;
  }
  fillFormFromCatalog(item);
}

function fillFormFromCatalog(item) {
  if (!item) return;

  // Fill form fields
  const form = $('#cardForm');
  if (form.elements['name'])        form.elements['name'].value        = item.name || '';
  if (form.elements['name_en'])     form.elements['name_en'].value     = item.name_en || '';
  if (form.elements['set_name'])    form.elements['set_name'].value    = item.set_name || '';
  if (form.elements['card_number']) form.elements['card_number'].value = item.card_number || '';
  if (form.elements['rarity'])      form.elements['rarity'].value      = item.rarity || 'R';

  // 写入 catalog_id（提交时走 from-catalog 接口）
  const catIdField = $('#catalogIdField');
  if (catIdField) catIdField.value = item.id;

  // Show selected card chip
  const chip = $('#catalogSelectedCard');
  const meta = [item.set_name, item.card_number, item.rarity].filter(Boolean).join(' · ');
  chip.style.display = 'flex';
  chip.innerHTML =
    (item.image_url
      ? `<img class="catalog-selected-img" src="${item.image_url}" alt="">`
      : '<div style="width:32px;height:44px;background:var(--bg-elevated);border-radius:4px;display:flex;align-items:center;justify-content:center;font-size:14px;flex-shrink:0;">🃏</div>'
    ) +
    `<div class="catalog-selected-info">
       <div class="catalog-selected-name">${item.name}</div>
       ${meta ? `<div class="catalog-selected-meta">${meta}</div>` : ''}
     </div>
     <button type="button" class="catalog-selected-clear" onclick="clearCatalogSelection()" title="清除选择">✕</button>`;

  // Image preview from catalog
  if (item.image_url && !$('#imagePreview').src.startsWith('data:')) {
    $('#imagePreview').src = item.image_url;
    $('#imagePreview').style.display = 'block';
    const wrap = $('.image-preview-wrap');
    if (wrap) wrap.classList.add('has-image');
    $('#uploadHint').style.display = 'none';
    $('#cardForm').dataset.catalogImageUrl = item.image_url;
  }

  // Reset select so user can pick again if needed
  setTimeout(() => { const s = $('#catalogSelect'); if (s) s.value = ''; }, 100);
}


// ============ Catalog Quick-Search (inside Add Card modal) ============

let catalogSearchDebounce = null;
let catalogDropdownResults = [];
let catalogFocusIndex = -1;

function onCatalogQuickInput(val) {
  clearTimeout(catalogSearchDebounce);
  const dropdown = $('#catalogDropdown');
  if (!val || val.trim().length < 1) {
    dropdown.classList.remove('open');
    return;
  }
  dropdown.className = 'catalog-dropdown loading';
  dropdown.textContent = '搜索中…';
  catalogSearchDebounce = setTimeout(() => fetchCatalogDropdown(val.trim()), 280);
}

async function fetchCatalogDropdown(query) {
  const dropdown = $('#catalogDropdown');
  try {
    const res = await fetch(`/api/catalog?search=${encodeURIComponent(query)}&per_page=12`);
    const json = await res.json();
    catalogDropdownResults = json.data || [];
    catalogFocusIndex = -1;
    renderCatalogDropdown(catalogDropdownResults, query);
  } catch {
    dropdown.className = 'catalog-dropdown';
    dropdown.classList.remove('loading');
    dropdown.classList.add('open');
    dropdown.innerHTML = '<div class="catalog-dropdown-empty">搜索出错，请重试</div>';
  }
}

function renderCatalogDropdown(items, query) {
  const dropdown = $('#catalogDropdown');
  dropdown.className = 'catalog-dropdown open';
  if (!items.length) {
    dropdown.innerHTML = `<div class="catalog-dropdown-empty">
      没有找到"${query}"
      &nbsp;·&nbsp;<a href="/catalog" target="_blank">去数据库添加</a>
    </div>`;
    return;
  }
  dropdown.innerHTML = items.map((item, i) => {
    const thumb = item.image_url
      ? `<img class="catalog-dropdown-thumb" src="${item.image_url}" alt="" loading="lazy"
             onerror="this.style.display='none'">`
      : `<div class="catalog-dropdown-thumb-placeholder">🃏</div>`;
    const meta = [item.set_name, item.card_number, item.rarity].filter(Boolean).join(' · ');
    return `<div class="catalog-dropdown-item" data-idx="${i}" onmousedown="selectCatalogItem(${i})">
      ${thumb}
      <div class="catalog-dropdown-info">
        <div class="catalog-dropdown-name">${item.name}</div>
        ${meta ? `<div class="catalog-dropdown-meta">${meta}</div>` : ''}
      </div>
      ${item.rarity ? `<span class="rarity-badge badge-${item.rarity}" style="font-size:9px;flex-shrink:0;">${item.rarity}</span>` : ''}
    </div>`;
  }).join('');
}

function showCatalogDropdown() {
  const val = $('#catalogQuickSearch').value.trim();
  if (val && catalogDropdownResults.length) {
    $('#catalogDropdown').classList.add('open');
  }
}

function hideCatalogDropdown() {
  setTimeout(() => {
    const d = $('#catalogDropdown');
    if (d) d.classList.remove('open');
  }, 200);
}

function selectCatalogItem(idx) {
  const item = catalogDropdownResults[idx];
  if (!item) return;

  // Hide dropdown & clear search input
  $('#catalogDropdown').classList.remove('open');
  $('#catalogQuickSearch').value = '';
  fillFormFromCatalog(item);
}

function clearCatalogSelection() {
  $('#catalogSelectedCard').style.display = 'none';
  $('#cardForm').dataset.catalogImageUrl = '';
  // 清除 catalog_id，后续提交走普通新增接口
  const f = $('#catalogIdField');
  if (f) f.value = '';
  // Optionally clear form fields - subtle: just clear the chip, let user keep fields
}

// Close dropdown when clicking outside
document.addEventListener('click', (e) => {
  const wrap = document.querySelector('.catalog-search-wrap');
  if (wrap && !wrap.contains(e.target)) {
    const d = $('#catalogDropdown');
    if (d) d.classList.remove('open');
  }
});
