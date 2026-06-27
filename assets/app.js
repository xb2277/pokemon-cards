// Pokemon Cards Manager - Frontend Application Logic (Supabase Edition)
// All data access goes through supabase-config.js

let currentCardId = null;
let editingImageChanged = false;
let currentView = 'table';

// ============ Utility ============

function $(sel) { return document.querySelector(sel); }
function $$(sel) { return document.querySelectorAll(sel); }

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

// ============ Global Auth Nav ============

document.addEventListener('DOMContentLoaded', async () => {
  const nav = document.querySelector('.nav-bar .nav-links');
  if (!nav) return;

  const loggedIn = await isLoggedIn();
  if (loggedIn) {
    const user = await getCurrentUser();
    if (user) {
      const userMenu = document.createElement('span');
      userMenu.style.cssText = 'display:flex;align-items:center;gap:8px;margin-left:12px;font-size:13px;';
      userMenu.innerHTML = `
        <span style="color:var(--text-secondary);">${user.nick_name || user.username || '用户'}</span>
        ${user.role === 'admin' ? '<a href="./admin.html" style="color:var(--gold-500);font-weight:600;">管理</a>' : ''}
        <a href="#" class="logout-link" style="color:var(--text-muted);">退出</a>
      `;
      nav.appendChild(userMenu);

      userMenu.querySelector('.logout-link').addEventListener('click', async function(e) {
        e.preventDefault();
        await authLogout();
        window.location.href = './login.html';
      });
    }
  } else {
    const loginLink = document.createElement('a');
    loginLink.href = './login.html';
    loginLink.textContent = '登录';
    loginLink.style.cssText = 'margin-left:12px;';
    nav.appendChild(loginLink);

    const registerLink = document.createElement('a');
    registerLink.href = './register.html';
    registerLink.textContent = '注册';
    registerLink.style.cssText = 'margin-left:8px;color:var(--gold-500);';
    nav.appendChild(registerLink);
  }
});

// ============ Card Library Page (index.html) ============

let currentPage = 1;
let totalPages = 1;
let totalCards = 0;
const PER_PAGE = 24;
let debounceTimer = null;

document.addEventListener('DOMContentLoaded', async () => {
  if (!$('#cardsGrid')) return;

  // Check auth
  const loggedIn = await isLoggedIn();
  if (!loggedIn) {
    window.location.href = './login.html';
    return;
  }

  loadCards(1);
  loadRarityOptions();

  $('#searchInput').addEventListener('input', () => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => loadCards(1), 300);
  });
  $('#rarityFilter').addEventListener('change', () => loadCards(1));
  $('#sortBySelect').addEventListener('change', () => loadCards(currentPage));

  document.addEventListener('keydown', (e) => {
    if (e.key === 'n' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); openAddModal(); }
    if (e.key === '/' && !['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName)) {
      e.preventDefault(); $('#searchInput').focus();
    }
  });
});

async function loadCards(page = 1) {
  currentPage = page;
  const search = ($('#searchInput').value || '').trim();
  const rarity = $('#rarityFilter').value;
  const sortBy = $('#sortBySelect').value;

  try {
    const { data: cards, total } = await fetchCards({ page, perPage: PER_PAGE, search, rarity, sortBy });
    totalCards = total;
    totalPages = Math.ceil(total / PER_PAGE) || 1;
    renderCards(cards);
    renderPagination();
    updateStatsBar(cards, totalCards);
  } catch(e) { showToast('加载卡牌失败: ' + e.message, 'error'); }
}

function renderCards(cards) {
  const grid = $('#cardsGrid');
  const empty = $('#emptyState');
  const tbody = $('#inventoryTableBody');
  const sectionHeader = $('#inventorySection');
  if (sectionHeader) sectionHeader.style.display = 'block';

  if (!cards || cards.length === 0) {
    grid.innerHTML = '';
    if (tbody) tbody.innerHTML = '';
    empty.style.display = 'block';
    return;
  }

  empty.style.display = 'none';
  grid.innerHTML = cards.map(card => renderCardItem(card)).join('');
  if (tbody) tbody.innerHTML = cards.map(card => renderTableRow(card)).join('');
  applyView(currentView);
}

function renderPagination() {
  const el = $('#pagination');
  if (!el) return;
  if (totalPages <= 1) { el.innerHTML = ''; return; }

  let html = `<span class="page-info">共 ${totalCards} 条 / 第 ${currentPage}/${totalPages} 页</span>`;
  if (currentPage > 1) html += `<button class="btn btn-outline btn-sm" onclick="loadCards(${currentPage - 1})">上一页</button>`;

  const range = new Set([1, totalPages]);
  for (let i = Math.max(1, currentPage - 2); i <= Math.min(totalPages, currentPage + 2); i++) range.add(i);
  let prev = 0;
  [...range].sort((a, b) => a - b).forEach(p => {
    if (prev && p - prev > 1) html += `<span style="color:var(--text-muted)">…</span>`;
    html += `<button class="btn btn-sm ${p === currentPage ? 'btn-primary' : 'btn-outline'}" onclick="loadCards(${p})">${p}</button>`;
    prev = p;
  });

  if (currentPage < totalPages) html += `<button class="btn btn-outline btn-sm" onclick="loadCards(${currentPage + 1})">下一页</button>`;
  el.innerHTML = html;
}

function renderTableRow(c) {
  const thumbHtml = c.image_path
    ? `<img class="table-card-thumb" src="${c.image_path}" alt="" loading="lazy">`
    : '';
  const mp = c.market_price || 0;
  return `<tr onclick="window.location='./card_detail.html?id=${c.id}'">
    <td><div class="table-card-name-cell">${thumbHtml}<span>${c.name}</span></div></td>
    <td>${c.set_name || '--'}</td>
    <td style="font-family:'JetBrains Mono',monospace;font-size:12px;">${c.card_number || '--'}</td>
    <td><span class="rarity-badge badge-${c.rarity}">${c.rarity || '--'}</span></td>
    <td>${conditionLabel(c.condition)}</td>
    <td style="font-weight:700;color:var(--gold-500);">${c.quantity}</td>
    <td style="font-family:'JetBrains Mono',monospace;">${formatMoney(c.cost_price)}</td>
    <td style="font-family:'JetBrains Mono',monospace;color:var(--gold-600);">${formatMoney(mp)}</td>
    <td style="font-weight:700;color:var(--red-500);">${formatMoney(mp * (c.quantity||1))}</td>
    <td><button class="table-action-btn" onclick="event.stopPropagation();window.location='./card_detail.html?id=${c.id}'">详情</button></td>
  </tr>`;
}

function toggleView(view) {
  currentView = view;
  applyView(view);
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
    <div class="card-item" onclick="window.location='./card_detail.html?id=${c.id}'">
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

function updateStatsBar(cards, totalCount) {
  const bar = $('#statsBar');
  if (!bar) return;
  const pageQty = cards.reduce((s, c) => s + (c.quantity||1), 0);
  const pageCost = cards.reduce((s, c) => s + ((c.cost_price||0) * (c.quantity||1)), 0);
  const pageValue = cards.reduce((s, c) => s + ((c.market_price||0) * (c.quantity||1)), 0);
  bar.innerHTML = `
    <div class="stat-card"><div class="stat-label">总卡牌种类</div><div class="stat-value">${totalCount || cards.length}</div></div>
    <div class="stat-card green"><div class="stat-label">本页张数</div><div class="stat-value">${pageQty}</div></div>
    <div class="stat-card orange"><div class="stat-label">本页成本</div><div class="stat-value">${formatMoney(pageCost)}</div></div>
    <div class="stat-card red"><div class="stat-label">本页总价（市场）</div><div class="stat-value" style="color:var(--red-500);">${formatMoney(pageValue)}</div></div>
  `;
}

function loadRarityOptions() {
  const sel = $('#rarityFilter');
  if (!sel) return;
  const rarities = ['C','U','R','RR','SR','SAR','UR','CSR','HR'];
  sel.innerHTML = '<option value="all">全部稀有度</option>' + rarities.map(r => `<option value="${r}">${r} - ${rarityLabel(r)}</option>`).join('');
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
  loadCatalogOptions();
}

function closeModal() {
  $('#cardModal').classList.remove('show');
  currentCardId = null;
}

async function saveCard(event) {
  event.preventDefault();
  const form = $('#cardForm');
  const data = {};
  for (const [key, value] of new FormData(form).entries()) {
    data[key] = value;
  }

  const fileInput = $('#imageInput');
  if (fileInput.files[0]) {
    try {
      data.image_path = await uploadCardImage(fileInput.files[0]);
    } catch(e) { showToast('图片上传失败: ' + e.message, 'error'); return; }
  } else if (form.dataset.catalogImageUrl) {
    data.image_path = form.dataset.catalogImageUrl;
  }

  try {
    let result;
    if (data.catalog_id && !currentCardId) {
      result = await createCardFromCatalog(parseInt(data.catalog_id), {
        quantity: data.quantity,
        cost_price: data.cost_price,
        condition: data.condition,
        notes: data.notes,
      });
    } else {
      result = await createCard(data);
    }
    closeModal();
    showToast(`"${result.name}" 已添加`, 'success');
    loadCards(currentPage);
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
    await deleteCard(deleteTargetId);
    closeDeleteModal();
    showToast('已删除', 'success');
    loadCards(currentPage);
  } catch(e) { showToast(e.message, 'error'); }
}

// ============ Dashboard Page ============

async function loadDashboard() {
  try {
    const d = await fetchDashboardData();
    d.snapshots = await fetchSnapshots(90);
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
      type: 'line', data: values, smooth: true,
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
  if (gl) gl.innerHTML = gainers.map((g,i) => renderRankItem(g, i+1, 'up')).join('') || '<li style="padding:24px;text-align:center;color:var(--text-muted)">暂无数据</li>';
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

// ============ Price Page ============

let priceChartInstance = null;
let currentCatalogId = null;
let priceCatalogItems = [];

async function loadPricePage() {
  try {
    const { data } = await fetchCatalog({ page: 1, perPage: 500 });
    priceCatalogItems = data || [];
    populatePriceCatalogSelect(priceCatalogItems);
    bindPriceSearch();
  } catch(e) {
    console.error('loadPricePage error:', e);
  }
}

function populatePriceCatalogSelect(items) {
  const sel = $('#priceCatalogSelect');
  if (!sel) return;
  sel.innerHTML = '<option value="">-- 从卡牌数据库选择 --</option>';
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
    if (!e.target.closest('.price-search-block')) dropdown.classList.remove('open');
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
  updatePriceHeroUI(item);
  loadCatalogPrices(item.id);
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

function updatePriceHeroUI(item) {
  const title = $('#heroTitle');
  const subtitle = $('#heroSubtitle');
  const img = $('#heroImg');
  const placeholder = $('#heroImgPlaceholder');
  if (title) title.textContent = item.name + (item.name_en ? ' / ' + item.name_en : '');
  if (subtitle) subtitle.textContent = [item.set_name, item.card_number, item.rarity].filter(Boolean).join('  ·  ');
  if (item.image_url) {
    if (img) { img.src = item.image_url; img.style.display = 'block'; }
    if (placeholder) placeholder.style.display = 'none';
  } else {
    if (img) img.style.display = 'none';
    if (placeholder) placeholder.style.display = 'flex';
  }
}

async function loadCatalogPrices(catalogId) {
  try {
    const { latest, history } = await fetchPricesByCatalog(catalogId);
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
    $('#chartArea').innerHTML = '<p style="text-align:center;padding:40px;color:var(--text-muted);">暂无价格记录，请手动录入</p>';
    return;
  }
  if (priceChartInstance) priceChartInstance.dispose();
  priceChartInstance = echarts.init($('#priceChart'));
  const platforms = {};
  history.forEach(h => {
    if (!platforms[h.platform]) platforms[h.platform] = [];
    platforms[h.platform].push([h.recorded_at, h.price]);
  });
  const dates = [...new Set(history.map(h => (h.recorded_at || '').split('T')[0]))].sort();
  const platformColors = {'tcgplayer':'#378add','xianyu':'#d85a30','taobao':'#ff6b35','manual':'#888780','pokemontcg':'#534ab7','闲鱼':'#d85a30','集换社':'#d4a017','手动录入':'#888780'};
  const series = Object.keys(platforms).map(p => ({
    name: p, type: 'line', smooth: true, symbolSize: 4,
    lineStyle: { width: 1.8 },
    itemStyle: { color: platformColors[p] || '#888780' },
    data: platforms[p].map(([t,v]) => [(t||'').split('T')[0], v])
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

async function submitManualPrice(event) {
  event.preventDefault();
  if (!currentCatalogId) return;
  const price = parseFloat($('#manualPrice').value);
  const platform = $('#manualPlatform').value.trim() || '手动录入';
  try {
    await addManualPrice(currentCatalogId, platform, price);
    showToast(`已录入 ¥${price}`, 'success');
    $('#manualPrice').value = '';
    loadCatalogPrices(currentCatalogId);
  } catch(e) { showToast(e.message, 'error'); }
}

function showManualPrice() {
  $('#manualInputArea').style.display = 'block';
}

// ============ Detail Page ============

let detailCard = null;

async function loadDetailPage() {
  const params = new URLSearchParams(window.location.search);
  const cardId = params.get('id');
  if (!cardId) {
    document.querySelector('.detail-grid').innerHTML = '<div class="empty-state"><p>卡牌未找到</p><a href="./index.html" class="btn btn-outline">返回我的卡牌</a></div>';
    return;
  }
  currentCardId = cardId;

  try {
    detailCard = await fetchCardById(cardId);
    let priceData = null;
    try {
      const { latest } = await fetchPricesByCard(cardId);
      if (latest && latest.avg != null) priceData = latest;
    } catch(e) { console.warn('Price fetch failed:', e.message); }
    renderDetail(detailCard, priceData);
  } catch(e) {
    document.querySelector('.detail-grid').innerHTML = '<div class="empty-state"><p>卡牌未找到</p><a href="./index.html" class="btn btn-outline">返回我的卡牌</a></div>';
  }
}

function renderDetail(c, priceData) {
  document.title = `${c.name} - Pokemon Card Manager`;
  const img = $('#detailImage');
  if (c.image_path) { img.src = c.image_path; img.style.display = 'inline'; }
  else { img.style.display = 'none'; $('#imageSection').innerHTML += '<div class="card-img-placeholder" style="width:180px;height:250px;display:inline-flex;">&#9830;</div>'; }

  $('#detailName').textContent = c.name;
  $('#detailNameEn').textContent = c.name_en || '';

  const displayPrice = (priceData && priceData.avg > 0) ? priceData.avg : (c.market_price || 0);
  const costPrice = c.cost_price || 0;
  const quantity = c.quantity || 1;
  const totalValue = displayPrice * quantity;
  const profit = displayPrice - costPrice;
  const profitPct = costPrice > 0 ? ((profit / costPrice) * 100).toFixed(1) : 0;
  const priceLabel = (priceData && priceData.avg > 0) ? '元/张（实时）' : '元/张';

  $('#detailBasicInfo').innerHTML = [
    ['系列', c.set_name || '--'],
    ['编号', c.card_number || '--'],
    ['稀有度', `<span class="rarity-badge badge-${c.rarity}">${c.rarity}</span> ${rarityLabel(c.rarity)}`],
    ['品相', conditionLabel(c.condition)],
  ].map(([k,v]) => `<div class="detail-info-row"><span class="detail-info-label">${k}</span><span class="detail-info-value">${v}</span></div>`).join('');

  $('#detailHoldInfo').innerHTML = [
    ['持有数量', `${quantity} 张`],
    ['收购单价', formatMoney(costPrice)],
    ['入库备注', c.notes || '--'],
  ].map(([k,v]) => `<div class="detail-info-row"><span class="detail-info-label">${k}</span><span class="detail-info-value">${v}</span></div>`).join('');

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

  if (editingImageChanged) {
    const fileInput = $('#editImageInput');
    if (fileInput.files[0]) {
      try {
        data.image_path = await uploadCardImage(fileInput.files[0]);
      } catch(e) { showToast('图片上传失败: ' + e.message, 'error'); return; }
    }
  }

  try {
    const res = await updateCard(currentCardId, data);
    closeEditModal();
    showToast('已更新', 'success');
    detailCard = res;
    renderDetail(res);
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
    await deleteCard(deleteTargetId);
    closeDeleteModal();
    showToast('已删除', 'success');
    setTimeout(() => window.location.href = './index.html', 800);
  } catch(e) { showToast(e.message, 'error'); }
}

// ============ Catalog Select Dropdown (Add Card modal) ============

async function loadCatalogOptions() {
  const sel = $('#catalogSelect');
  if (!sel) return;
  sel.innerHTML = '<option value="">-- 选择卡牌 --</option>';
  try {
    const { data: items } = await fetchCatalog({ page: 1, perPage: 200 });
    if (!items || items.length === 0) {
      sel.innerHTML = '<option value="">(数据库暂无卡种)</option>';
      return;
    }
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
  } catch (e) { console.error('Failed to load catalog options:', e); }
}

function onCatalogSelectChange(value) {
  if (!value) return;
  const sel = $('#catalogSelect');
  const selectedOption = sel.options[sel.selectedIndex];
  let item = null;
  if (selectedOption && selectedOption.dataset.itemJson) {
    try { item = JSON.parse(selectedOption.dataset.itemJson); } catch {}
  }
  if (!item) {
    fetchCatalogById(value).then(it => fillFormFromCatalog(it)).catch(() => {});
    return;
  }
  fillFormFromCatalog(item);
}

function fillFormFromCatalog(item) {
  if (!item) return;
  const form = $('#cardForm');
  if (form.elements['name'])        form.elements['name'].value        = item.name || '';
  if (form.elements['name_en'])     form.elements['name_en'].value     = item.name_en || '';
  if (form.elements['set_name'])    form.elements['set_name'].value    = item.set_name || '';
  if (form.elements['card_number']) form.elements['card_number'].value = item.card_number || '';
  if (form.elements['rarity'])      form.elements['rarity'].value      = item.rarity || 'R';

  const catIdField = $('#catalogIdField');
  if (catIdField) catIdField.value = item.id;

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

  if (item.image_url && !$('#imagePreview').src.startsWith('data:')) {
    $('#imagePreview').src = item.image_url;
    $('#imagePreview').style.display = 'block';
    const wrap = $('.image-preview-wrap');
    if (wrap) wrap.classList.add('has-image');
    $('#uploadHint').style.display = 'none';
    $('#cardForm').dataset.catalogImageUrl = item.image_url;
  }
  setTimeout(() => { const s = $('#catalogSelect'); if (s) s.value = ''; }, 100);
}

// ============ Catalog Quick-Search ============

let catalogSearchDebounce = null;
let catalogDropdownResults = [];
let catalogFocusIndex = -1;

function onCatalogQuickInput(val) {
  clearTimeout(catalogSearchDebounce);
  const dropdown = $('#catalogDropdown');
  if (!val || val.trim().length < 1) { dropdown.classList.remove('open'); return; }
  dropdown.className = 'catalog-dropdown loading';
  dropdown.textContent = '搜索中…';
  catalogSearchDebounce = setTimeout(() => fetchCatalogDropdown(val.trim()), 280);
}

async function fetchCatalogDropdown(query) {
  const dropdown = $('#catalogDropdown');
  try {
    const { data } = await fetchCatalog({ search: query, page: 1, perPage: 12 });
    catalogDropdownResults = data || [];
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
      &nbsp;·&nbsp;<a href="./catalog.html" target="_blank">去数据库添加</a>
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
  if (val && catalogDropdownResults.length) $('#catalogDropdown').classList.add('open');
}

function hideCatalogDropdown() {
  setTimeout(() => { const d = $('#catalogDropdown'); if (d) d.classList.remove('open'); }, 200);
}

function selectCatalogItem(idx) {
  const item = catalogDropdownResults[idx];
  if (!item) return;
  $('#catalogDropdown').classList.remove('open');
  $('#catalogQuickSearch').value = '';
  fillFormFromCatalog(item);
}

function clearCatalogSelection() {
  $('#catalogSelectedCard').style.display = 'none';
  $('#cardForm').dataset.catalogImageUrl = '';
  const f = $('#catalogIdField');
  if (f) f.value = '';
}

document.addEventListener('click', (e) => {
  const wrap = document.querySelector('.catalog-search-wrap');
  if (wrap && !wrap.contains(e.target)) {
    const d = $('#catalogDropdown');
    if (d) d.classList.remove('open');
  }
});
