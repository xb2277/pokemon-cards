const api = require('../../utils/api');
const { showToast } = require('../../utils/util');

Page({
  data: {
    search: '', activeSet: 'all', activeRarity: '',
    sets: [],
    rarityFilter: ['C', 'U', 'R', 'RR', 'SR', 'SAR', 'UR', 'CSR', 'HR'],
    items: [], total: 0, page: 1, perPage: 60, totalPages: 1, loading: true,

    // Sheet
    showSheet: false, editing: null, saving: false,
    form: { name: '', name_en: '', set_name: '', set_code: '', card_number: '', image_url: '', tempImage: '', description: '', rarityIdx: 0 },
    rarityPickList: ['', 'C', 'U', 'R', 'RR', 'SR', 'SAR', 'UR', 'CSR', 'HR'],

    // Bulk
    showBulk: false, bulkItems: [], importing: false
  },

  onLoad() { this.loadSets(); this.loadData(); },
  onPullDownRefresh() { this.loadData().then(() => wx.stopPullDownRefresh()); },

  async loadSets() {
    try {
      const res = await api.catalogSets();
      this.setData({ sets: res.data || [] });
    } catch (e) {}
  },

  async loadData() {
    try {
      let params = `?page=${this.data.page}&per_page=${this.data.perPage}`;
      if (this.data.search) params += `&search=${encodeURIComponent(this.data.search)}`;
      if (this.data.activeSet !== 'all') params += `&set_name=${encodeURIComponent(this.data.activeSet)}`;
      if (this.data.activeRarity) params += `&rarity=${this.data.activeRarity}`;

      const res = await api.catalog(params);
      this.setData({
        items: res.data || [], total: res.total || 0,
        totalPages: Math.ceil((res.total || 0) / this.data.perPage), loading: false
      });
    } catch (e) { showToast('加载失败', 'error'); this.setData({ loading: false }); }
  },

  onSearchInput(e) {
    this.setData({ search: e.detail.value });
    if (this._t) clearTimeout(this._t);
    this._t = setTimeout(() => { this.setData({ page: 1 }); this.loadData(); }, 300);
  },

  setFilter(e) {
    const { type, v } = e.currentTarget.dataset;
    if (type === 'set') this.setData({ activeSet: v, page: 1 });
    else this.setData({ activeRarity: v, page: 1 });
    this.loadData();
  },

  goPage(e) {
    this.setData({ page: parseInt(e.currentTarget.dataset.p) });
    this.loadData();
  },

  // ======== Add/Edit Sheet ========

  showAddSheet() {
    this.setData({
      showSheet: true, editing: null,
      form: { name: '', name_en: '', set_name: '', set_code: '', card_number: '', image_url: '', tempImage: '', description: '', rarityIdx: 0 }
    });
  },

  async editItem(e) {
    const id = e.currentTarget.dataset.id;
    try {
      const res = await api.catalogItem(id);
      const item = res.data;
      const rarityIdx = this.data.rarityPickList.indexOf(item.rarity || '');
      this.setData({
        showSheet: true, editing: item,
        form: {
          name: item.name || '', name_en: item.name_en || '',
          set_name: item.set_name || '', set_code: item.set_code || '',
          card_number: item.card_number || '', image_url: item.image_url || '', tempImage: '',
          description: item.description || '', rarityIdx: rarityIdx >= 0 ? rarityIdx : 0
        }
      });
    } catch (e) { showToast('加载失败', 'error'); }
  },

  hideSheet() { this.setData({ showSheet: false, editing: null }); },
  noop() {},

  onField(e) { this.setData({ [`form.${e.currentTarget.dataset.k}`]: e.detail.value }); },
  onRarityPick(e) { this.setData({ 'form.rarityIdx': parseInt(e.detail.value) }); },

  pickImage() {
    wx.chooseImage({
      count: 1, sizeType: ['compressed'], sourceType: ['camera', 'album'],
      success: (res) => {
        this.setData({
          'form.image_url': res.tempFilePaths[0],
          'form.tempImage': res.tempFilePaths[0]
        });
      }
    });
  },

  async saveItem() {
    const f = this.data.form;
    if (!f.name.trim()) { showToast('请输入名称', 'error'); return; }
    this.setData({ saving: true });

    let image_url = f.image_url.trim();
    // Upload temp image if user took/selected a photo
    if (f.tempImage) {
      try {
        const uploadRes = await api.uploadImage(f.tempImage);
        image_url = uploadRes.image_path;
      } catch (e) { /* keep original image_url if upload fails */ }
    }

    const data = {
      name: f.name.trim(), name_en: f.name_en.trim(),
      set_name: f.set_name.trim(), set_code: f.set_code.trim(),
      card_number: f.card_number.trim(),
      rarity: this.data.rarityPickList[f.rarityIdx] || '',
      image_url, description: f.description.trim()
    };
    try {
      if (this.data.editing) {
        await api.updateCatalogItem(this.data.editing.id, data);
        showToast('已更新');
      } else {
        await api.createCatalogItem(data);
        showToast('已添加');
      }
      this.hideSheet();
      this.loadData();
      this.loadSets();
    } catch (e) { showToast(e.message, 'error'); }
    this.setData({ saving: false });
  },

  deleteCurrent() {
    if (!this.data.editing) return;
    wx.showModal({
      title: '确认删除',
      content: '删除后将无法恢复',
      success: async (res) => {
        if (res.confirm) {
          await api.deleteCatalogItem(this.data.editing.id);
          this.hideSheet();
          showToast('已删除');
          this.loadData();
          this.loadSets();
        }
      }
    });
  },

  // ======== Bulk Import ========

  showBulkSheet() { this.setData({ showBulk: true, bulkItems: [] }); },
  hideBulk() { this.setData({ showBulk: false, bulkItems: [] }); },

  pickJsonFile() {
    wx.chooseMessageFile({
      count: 1, type: 'file', extension: ['json'],
      success: (res) => {
        try {
          const content = wx.getFileSystemManager().readFileSync(res.tempFiles[0].path, 'utf8');
          const parsed = JSON.parse(content);
          if (!Array.isArray(parsed)) throw new Error('JSON 必须是数组');
          const items = parsed.filter(i => i.name);
          if (!items.length) throw new Error('未找到有效数据');
          this.setData({ bulkItems: items });
        } catch (err) { showToast('解析失败: ' + err.message, 'error'); }
      }
    });
  },

  clearBulk() { this.setData({ bulkItems: [] }); },

  async doImport() {
    if (!this.data.bulkItems.length) return;
    this.setData({ importing: true });
    try {
      const res = await api.bulkImportCatalog(this.data.bulkItems);
      this.hideBulk();
      showToast(`新增 ${res.data.inserted}，跳过 ${res.data.skipped}`);
      this.loadData();
      this.loadSets();
    } catch (e) { showToast(e.message, 'error'); }
    this.setData({ importing: false });
  }
});
