// catalog.js — Card Catalog page logic (Supabase Edition)

let catalogPage = 1;
let catalogTotal = 0;
let catalogPerPage = 60;
let catalogDebounce = null;
let editingCatalogId = null;
let deleteCatalogId = null;
let bulkItems = [];
let catalogViewMode = 'table';

document.addEventListener('DOMContentLoaded', () => {
  if (!document.getElementById('catalogGrid')) return;
  loadCatalog(1);
  loadCatalogSets();
});

function toggleCatalogView(mode) {
  catalogViewMode = mode;
  const tableSec = document.getElementById('catalogTableSection');
  const gridEl = document.getElementById('catalogGrid');
  const btnT = document.getElementById('btnCatalogTableView');
  const btnG = document.getElementById('btnCatalogGridView');
  if (mode === 'table') {
    tableSec.style.display = '';
    gridEl.style.display = 'none';
    if (btnT) btnT.classList.add('active');
    if (btnG) btnG.classList.remove('active');
  } else {
    tableSec.style.display = 'none';
    gridEl.style.display = '';
    if (btnG) btnG.classList.add('active');
    if (btnT) btnT.classList.remove('active');
  }
  loadCatalog(catalogPage);
}

async function loadCatalog(page = 1) {
  catalogPage = page;
  const search = document.getElementById('catalogSearch').value.trim();
  const set_name = document.getElementById('catalogSetFilter').value;
  const rarity = document.getElementById('catalogRarityFilter').value;

  try {
    let query = supabase.from('card_catalog').select('*', { count: 'exact' });

    if (search) {
      const s = search.replace(/'/g, "''");
      query = query.or(`name.ilike.%${s}%,name_en.ilike.%${s}%,card_number.ilike.%${s}%,set_name.ilike.%${s}%`);
    }
    if (set_name && set_name !== 'all') query = query.eq('set_name', set_name);
    if (rarity && rarity !== 'all') query = query.eq('rarity', rarity);

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

function renderCatalogTable(items) {
  const tbody = document.getElementById('catalogTableBody');
  if (!tbody) return;
  if (!items.length) {
    tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;padding:24px;color:var(--text-muted);">暂无数据</td></tr>';
    return;
  }
  tbody.innerHTML = items.map(item =>
    `<tr>
      <td>
        <div class="table-card-cell">
          ${item.image_url
            ? `<img class="table-thumb" src="${item.image_url}" alt="${item.name}" loading="lazy"
                onerror="this.outerHTML='<span style=\\'color:var(--text-muted);font-size:20px\\'>🃏</span>'">`
            : '<span style="color:var(--text-muted);font-size:18px;">🃏</span>'
          }
          <div><strong>${item.name}</strong></div>
        </div>
      </td>
      <td style="color:var(--text-muted);font-size:12px;">${item.name_en || '--'}</td>
      <td>${item.set_name || '--'}</td>
      <td><code style="font-size:11px;">${item.card_number || item.set_code || '--'}</code></td>
      <td>${item.rarity ? `<span class="rarity-badge badge-${item.rarity}">${item.rarity}</span>` : '--'}</td>
      <td>
        <button class="btn btn-outline btn-sm" onclick="openCatalogEditModal(${item.id})">编辑</button>
        <button class="btn btn-danger btn-sm" style="margin-left:4px;" onclick="promptCatalogDelete(${item.id},'${item.name}')">删除</button>
      </td>
    </tr>`
  ).join('');
}

function renderCatalogGrid(items) {
  const grid = document.getElementById('catalogGrid');
  const empty = document.getElementById('catalogEmpty');
  if (!items.length) { grid.innerHTML = ''; empty.style.display = 'block'; return; }
  empty.style.display = 'none';
  grid.innerHTML = items.map(item => {
    const imgHtml = item.image_url
      ? `<img class="catalog-card-img" src="${item.image_url}" alt="${item.name}" loading="lazy" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">`
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
        <button class="catalog-card-edit-btn" onclick="event.stopPropagation();openCatalogEditModal(${item.id})" title="编辑">✏️</button>
      </div>`;
  }).join('');
}

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

async function loadCatalogSets() {
  try {
    const sets = await fetchCatalogSets();
    const sel = document.getElementById('catalogSetFilter');
    sets.forEach(s => {
      const opt = document.createElement('option');
      opt.value = s;
      opt.textContent = s;
      sel.appendChild(opt);
    });
  } catch (e) {}
}

function debounceCatalogSearch() {
  clearTimeout(catalogDebounce);
  catalogDebounce = setTimeout(() => loadCatalog(1), 280);
}

// ── Add / Edit Modal ──

function openCatalogAddModal() {
  editingCatalogId = null;
  document.getElementById('catalogModalTitle').textContent = '新增卡种';
  document.getElementById('catalogForm').reset();
  document.getElementById('catalogImgPreview').style.display = 'none';
  document.getElementById('catalogSubmitBtn').textContent = '保存';
  document.getElementById('catalogModal').classList.add('show');
}

async function openCatalogEditModal(id) {
  try {
    const item = await fetchCatalogById(id);
    editingCatalogId = id;
    document.getElementById('catalogModalTitle').textContent = '编辑卡种';
    document.getElementById('catalogSubmitBtn').textContent = '更新';
    const form = document.getElementById('catalogForm');
    form.reset();
    form.elements['name'].value = item.name || '';
    form.elements['name_en'].value = item.name_en || '';
    form.elements['set_name'].value = item.set_name || '';
    form.elements['set_code'].value = item.set_code || '';
    form.elements['card_number'].value = item.card_number || '';
    form.elements['rarity'].value = item.rarity || '';
    form.elements['image_url'].value = item.image_url || '';
    form.elements['description'].value = item.description || '';
    previewCatalogImg(item.image_url);
    document.getElementById('catalogModal').classList.add('show');

    const footer = document.querySelector('#catalogModal .modal-footer');
    const existingDel = footer.querySelector('.btn-danger');
    if (!existingDel) {
      const delBtn = document.createElement('button');
      delBtn.type = 'button';
      delBtn.className = 'btn btn-danger';
      delBtn.style.marginRight = 'auto';
      delBtn.textContent = '删除';
      delBtn.onclick = () => { closeCatalogModal(); promptCatalogDelete(id, item.name); };
      footer.insertBefore(delBtn, footer.firstChild);
    } else {
      existingDel.onclick = () => { closeCatalogModal(); promptCatalogDelete(id, item.name); };
    }
  } catch (e) { showToast('加载失败: ' + e.message, 'error'); }
}

function closeCatalogModal() {
  document.getElementById('catalogModal').classList.remove('show');
  editingCatalogId = null;
  const delBtn = document.querySelector('#catalogModal .btn-danger');
  if (delBtn) delBtn.remove();
}

function previewCatalogImg(url) {
  const img = document.getElementById('catalogImgPreview');
  if (url && url.startsWith('http')) {
    img.src = url; img.style.display = 'block';
    img.onerror = () => { img.style.display = 'none'; };
  } else { img.style.display = 'none'; }
}

async function saveCatalogItem(event) {
  event.preventDefault();
  const form = document.getElementById('catalogForm');
  const data = {
    name: form.elements['name'].value.trim(),
    name_en: form.elements['name_en'].value.trim(),
    set_name: form.elements['set_name'].value.trim(),
    set_code: form.elements['set_code'].value.trim(),
    card_number: form.elements['card_number'].value.trim(),
    rarity: form.elements['rarity'].value,
    image_url: form.elements['image_url'].value.trim(),
    description: form.elements['description'].value.trim(),
  };

  try {
    if (editingCatalogId) {
      const { error } = await supabase.from('card_catalog').update(data).eq('id', editingCatalogId);
      if (error) throw new Error(error.message);
    } else {
      const { error } = await supabase.from('card_catalog').insert(data);
      if (error) throw new Error(error.message);
    }
    closeCatalogModal();
    showToast(editingCatalogId ? '已更新' : `"${data.name}" 已添加`, 'success');
    loadCatalog(catalogPage);
    loadCatalogSets();
  } catch (e) { showToast(e.message, 'error'); }
}

// ── Delete ──

function promptCatalogDelete(id, name) {
  deleteCatalogId = id;
  document.getElementById('deleteCatalogName').textContent = name;
  document.getElementById('catalogDeleteModal').classList.add('show');
}

function closeCatalogDeleteModal() {
  document.getElementById('catalogDeleteModal').classList.remove('show');
  deleteCatalogId = null;
}

async function confirmCatalogDelete() {
  if (!deleteCatalogId) return;
  try {
    const { error } = await supabase.from('card_catalog').delete().eq('id', deleteCatalogId);
    if (error) throw new Error(error.message);
    closeCatalogDeleteModal();
    showToast('已删除', 'success');
    loadCatalog(catalogPage);
  } catch (e) { showToast(e.message, 'error'); }
}

// ── Bulk Import ──

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
    </tr>`).join('') + (items.length > 100 ? `<tr><td colspan="4" style="padding:8px 10px;color:var(--text-muted);text-align:center;">还有 ${items.length - 100} 条…</td></tr>` : '');
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
    const { data, error } = await supabase.from('card_catalog').upsert(bulkItems, {
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
