// catalog.js — Card Catalog page logic (Supabase Edition)

let catalogPage = 1;
let catalogTotal = 0;
let catalogPerPage = 50;
let catalogDebounce = null;
let bulkItems = [];
let catalogViewMode = 'grid';   // 'table' | 'grid'
let catalogLanguage = 'zh';       // 默认国内卡

// 「加入我的卡牌」弹窗的当前 catalogId
let addingCatalogId = null;

document.addEventListener('DOMContentLoaded', () => {
  if (!document.getElementById('catalogGrid')) return;
  // 初始高亮表格视图按钮
  syncViewButtons();
  loadCatalog(1);
  loadCatalogSets();
});

// ── Category Tabs ──

function switchCatalogCategory(lang) {
  catalogLanguage = lang;
  document.querySelectorAll('.category-tab').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.category === lang);
  });
  document.getElementById('catalogSetFilter').value = '';
  loadCatalogSets();
  loadCatalog(1);
}

// ── View Toggle ──

function syncViewButtons() {
  const btnT = document.getElementById('btnCatalogTableView');
  const btnG = document.getElementById('btnCatalogGridView');
  if (!btnT || !btnG) return;
  if (catalogViewMode === 'table') {
    btnT.classList.add('active');
    btnG.classList.remove('active');
  } else {
    btnG.classList.add('active');
    btnT.classList.remove('active');
  }
}

function toggleCatalogView(mode) {
  catalogViewMode = mode;
  const tableSec = document.getElementById('catalogTableSection');
  const gridEl   = document.getElementById('catalogGrid');
  if (mode === 'table') {
    tableSec.style.display = '';
    gridEl.style.display   = 'none';
  } else {
    tableSec.style.display = 'none';
    gridEl.style.display   = '';
  }
  syncViewButtons();
  loadCatalog(catalogPage);
}

// ── Load Data ──

async function loadCatalog(page = 1) {
  catalogPage = page;
  const search   = document.getElementById('catalogSearch').value.trim();
  const set_name = document.getElementById('catalogSetFilter').value;
  const rarity   = document.getElementById('catalogRarityFilter').value;

  try {
    let query = supabase.from('card_catalog').select('*', { count: 'exact' });

    if (catalogLanguage) query = query.eq('language', catalogLanguage);

    if (search) {
      const s = search.replace(/'/g, "''");
      query = query.or(`name.ilike.%${s}%,name_en.ilike.%${s}%,card_number.ilike.%${s}%,set_name.ilike.%${s}%`);
    }
    if (set_name && set_name !== 'all') query = query.eq('set_name', set_name);
    if (rarity   && rarity   !== 'all') query = query.eq('rarity',   rarity);

    query = query.order('set_name', { ascending: true }).order('card_number', { ascending: true });

    const offset = (page - 1) * catalogPerPage;
    query = query.range(offset, offset + catalogPerPage - 1);

    const { data: items, count, error } = await query;
    if (error) throw new Error(error.message);

    catalogTotal = count || 0;
    renderCatalogStats(catalogTotal, (items || []).length);
    renderPagination();

    if (catalogViewMode === 'table') {
      renderCatalogTable(items || []);
    } else {
      renderCatalogGrid(items || []);
    }

    const empty = document.getElementById('catalogEmpty');
    if (empty) empty.style.display = (items || []).length ? 'none' : 'block';
  } catch (e) {
    showToast('加载失败: ' + e.message, 'error');
  }
}

// ── Render: Table ──

function renderCatalogTable(items) {
  const tbody = document.getElementById('catalogTableBody');
  if (!tbody) return;
  if (!items.length) {
    tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;padding:24px;color:var(--text-muted);">暂无数据</td></tr>';
    return;
  }
  tbody.innerHTML = items.map(item => {
    const safeName = item.name.replace(/'/g, "\\'").replace(/"/g, '&quot;');
    return `<tr>
      <td>
        <div class="table-card-cell">
          ${item.image_url
            ? `<img class="table-thumb" src="${item.image_url}" alt="${safeName}" loading="lazy"
                onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">`
              + `<div class="table-thumb-placeholder" style="display:none;">🃏</div>`
            : '<div class="table-thumb-placeholder">🃏</div>'
          }
          <div><strong>${item.name}</strong></div>
        </div>
      </td>
      <td style="color:var(--text-muted);font-size:12px;">${item.name_en || '--'}</td>
      <td>${item.set_name || '--'}</td>
      <td><code style="font-size:11px;">${item.card_number || item.set_code || '--'}</code></td>
      <td>${item.rarity ? `<span class="rarity-badge badge-${item.rarity}">${item.rarity}</span>` : '--'}</td>
      <td>
        <button class="btn btn-primary btn-sm"
          onclick="openAddToMyCards(${item.id})">＋ 加入我的卡牌</button>
      </td>
    </tr>`;
  }).join('');
}

// ── Render: Grid ──

function renderCatalogGrid(items) {
  const grid  = document.getElementById('catalogGrid');
  const empty = document.getElementById('catalogEmpty');
  if (!items.length) { grid.innerHTML = ''; empty.style.display = 'block'; return; }
  empty.style.display = 'none';
  grid.innerHTML = items.map(item => {
    const imgHtml = item.image_url
      ? `<img class="catalog-card-img" src="${item.image_url}" alt="${item.name}" loading="lazy"
            onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">`
        + `<div class="catalog-card-img-placeholder" style="display:none;">🃏</div>`
      : `<div class="catalog-card-img-placeholder">🃏</div>`;
    return `
      <div class="catalog-card" title="${item.name}">
        ${imgHtml}
        <div class="catalog-card-body">
          <div class="catalog-card-name">${item.name}</div>
          <div class="catalog-card-meta">
            <span class="catalog-card-number">${item.card_number || item.set_code || '--'}</span>
            ${item.rarity ? `<span class="rarity-badge badge-${item.rarity}" style="font-size:9px;padding:1px 5px;">${item.rarity}</span>` : ''}
          </div>
        </div>
        <button class="catalog-card-add-btn"
          onclick="event.stopPropagation();openAddToMyCards(${item.id})"
          title="加入我的卡牌">＋</button>
      </div>`;
  }).join('');
}

// ── Render: Stats / Pagination ──

function renderCatalogStats(total, shown) {
  const bar = document.getElementById('catalogStats');
  if (!bar) return;
  bar.innerHTML = `
    <div class="stat-card"><div class="stat-label">卡种总数</div><div class="stat-value">${total}</div></div>
    <div class="stat-card orange"><div class="stat-label">本页显示</div><div class="stat-value">${shown}</div></div>
  `;
}

function renderPagination() {
  const el = document.getElementById('pagination');
  const totalPages = Math.ceil(catalogTotal / catalogPerPage);
  if (totalPages <= 1) { el.innerHTML = ''; return; }
  let html = `<span class="page-info">共 ${catalogTotal} 条 / 第 ${catalogPage}/${totalPages} 页</span>`;
  if (catalogPage > 1) html += `<button class="btn btn-outline btn-sm" onclick="loadCatalog(${catalogPage - 1})">上一页</button>`;
  const range = new Set([1, totalPages]);
  for (let i = Math.max(1, catalogPage - 2); i <= Math.min(totalPages, catalogPage + 2); i++) range.add(i);
  let prev = 0;
  [...range].sort((a, b) => a - b).forEach(p => {
    if (prev && p - prev > 1) html += `<span style="color:var(--text-muted)">…</span>`;
    html += `<button class="btn btn-sm ${p === catalogPage ? 'btn-primary' : 'btn-outline'}" onclick="loadCatalog(${p})">${p}</button>`;
    prev = p;
  });
  if (catalogPage < totalPages) html += `<button class="btn btn-outline btn-sm" onclick="loadCatalog(${catalogPage + 1})">下一页</button>`;
  el.innerHTML = html;
}

// ── Load Sets ──

async function loadCatalogSets() {
  try {
    let query = supabase.from('card_catalog').select('set_name');
    if (catalogLanguage) query = query.eq('language', catalogLanguage);
    const { data, error } = await query;
    if (error) throw error;
    const sets = [...new Set((data || []).map(r => r.set_name).filter(Boolean))].sort();
    const sel = document.getElementById('catalogSetFilter');
    sel.innerHTML = '<option value="">全部系列</option>';
    sets.forEach(s => {
      const opt = document.createElement('option');
      opt.value = s; opt.textContent = s;
      sel.appendChild(opt);
    });
  } catch (e) {}
}

function debounceCatalogSearch() {
  clearTimeout(catalogDebounce);
  catalogDebounce = setTimeout(() => loadCatalog(1), 280);
}

// ════════════════════════════════════════════
// 「加入我的卡牌」Modal
// ════════════════════════════════════════════

async function openAddToMyCards(catalogId) {
  addingCatalogId = catalogId;

  // 重置表单
  document.getElementById('addCardQty').value       = 1;
  document.getElementById('addCardCost').value      = '';
  document.getElementById('addCardCondition').value = 'NM';
  document.getElementById('addCardNotes').value     = '';

  // 加载卡牌信息
  try {
    const { data: item, error } = await supabase
      .from('card_catalog').select('*').eq('id', catalogId).single();
    if (error) throw error;

    document.getElementById('addCardPreviewName').textContent = item.name || '';
    document.getElementById('addCardPreviewMeta').textContent =
      [item.set_name, item.card_number, item.rarity].filter(Boolean).join(' · ');

    const img  = document.getElementById('addCardPreviewImg');
    const ph   = document.getElementById('addCardPreviewPlaceholder');
    if (item.image_url) {
      img.src = item.image_url;
      img.style.display = 'block';
      ph.style.display  = 'none';
      img.onerror = () => { img.style.display = 'none'; ph.style.display = 'flex'; };
    } else {
      img.style.display = 'none';
      ph.style.display  = 'flex';
    }
  } catch (e) {
    document.getElementById('addCardPreviewName').textContent = '卡牌信息加载失败';
  }

  document.getElementById('addToMyCardsModal').classList.add('show');
}

function closeAddToMyCardsModal() {
  document.getElementById('addToMyCardsModal').classList.remove('show');
  addingCatalogId = null;
}

async function confirmAddToMyCards() {
  if (!addingCatalogId) return;

  const btn = document.getElementById('addToMyCardsBtn');
  btn.disabled = true;
  btn.textContent = '添加中…';

  try {
    const qty       = parseInt(document.getElementById('addCardQty').value)   || 1;
    const cost      = parseFloat(document.getElementById('addCardCost').value) || 0;
    const condition = document.getElementById('addCardCondition').value;
    const notes     = document.getElementById('addCardNotes').value.trim();

    await createCardFromCatalog(addingCatalogId, { quantity: qty, cost_price: cost, condition, notes });

    closeAddToMyCardsModal();
    showToast('✅ 已加入我的卡牌！前往「我的卡牌」页面查看。', 'success');
  } catch (e) {
    showToast('添加失败：' + e.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = '加入我的卡牌';
  }
}

// ════════════════════════════════════════════
// Bulk Import
// ════════════════════════════════════════════

function openBulkModal() {
  bulkItems = [];
  document.getElementById('bulkPreview').style.display = 'none';
  document.getElementById('bulkImportBtn').disabled = true;
  document.getElementById('bulkModal').classList.add('show');
}

function closeBulkModal() {
  document.getElementById('bulkModal').classList.remove('show');
  bulkItems = [];
}

function handleBulkDrop(event) {
  event.preventDefault();
  document.getElementById('bulkDropArea').classList.remove('drag-over');
  const file = event.dataTransfer.files[0];
  if (file) parseBulkFile(file);
}

function handleBulkFile(event) {
  const file = event.target.files[0];
  if (file) parseBulkFile(file);
}

function parseBulkFile(file) {
  const reader = new FileReader();
  reader.onload = (e) => {
    try {
      const parsed = JSON.parse(e.target.result);
      if (!Array.isArray(parsed)) throw new Error('JSON 必须是数组');
      bulkItems = parsed.filter(i => i.name);
      if (!bulkItems.length) throw new Error('没有找到有效的卡牌数据');
      renderBulkPreview(bulkItems);
    } catch (err) { showToast('解析失败: ' + err.message, 'error'); }
  };
  reader.readAsText(file);
}

function renderBulkPreview(items) {
  document.getElementById('bulkPreviewCount').textContent = `找到 ${items.length} 条记录`;
  const tbody = document.getElementById('bulkPreviewBody');
  tbody.innerHTML = items.slice(0, 100).map(item => `
    <tr style="border-top:1px solid var(--border-subtle);">
      <td style="padding:6px 10px;">${item.name}</td>
      <td style="padding:6px 10px;color:var(--text-muted);">${item.set_name || '--'}</td>
      <td style="padding:6px 10px;font-family:'JetBrains Mono',monospace;font-size:11px;">${item.card_number || '--'}</td>
      <td style="padding:6px 10px;">${item.rarity ? `<span class="rarity-badge badge-${item.rarity}" style="font-size:9px;">${item.rarity}</span>` : '--'}</td>
    </tr>`).join('') +
    (items.length > 100 ? `<tr><td colspan="4" style="padding:8px 10px;color:var(--text-muted);text-align:center;">还有 ${items.length - 100} 条…</td></tr>` : '');
  document.getElementById('bulkPreview').style.display = 'block';
  document.getElementById('bulkImportBtn').disabled = false;
}

function clearBulkPreview() {
  bulkItems = [];
  document.getElementById('bulkPreview').style.display = 'none';
  document.getElementById('bulkImportBtn').disabled = true;
  document.getElementById('bulkFileInput').value = '';
}

async function executeBulkImport() {
  if (!bulkItems.length) return;
  const btn = document.getElementById('bulkImportBtn');
  btn.disabled = true;
  btn.textContent = '导入中…';
  try {
    const { error } = await supabase.from('card_catalog').upsert(bulkItems, {
      onConflict: 'name,set_name,card_number',
    });
    if (error) throw new Error(error.message);
    closeBulkModal();
    showToast(`导入完成：${bulkItems.length} 条`, 'success');
    loadCatalog(1);
    loadCatalogSets();
  } catch (e) {
    showToast('导入失败: ' + e.message, 'error');
    btn.disabled = false;
    btn.textContent = '导入';
  }
}
