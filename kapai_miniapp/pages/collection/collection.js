const api = require('../../utils/api');
const { formatMoney, showToast } = require('../../utils/util');

Page({
  data: {
    allCards: [],
    cards: [],
    search: '',
    activeRarity: 'all',
    sortKey: 'updated_at',
    loading: true,
    stats: { total: 0, qty: 0, cost: '¥0', value: '¥0' },

    rarities: ['C', 'U', 'R', 'RR', 'SR', 'SAR', 'UR', 'CSR', 'HR'],
    sorts: [
      { key: 'updated_at', label: '最近' },
      { key: 'name', label: '名称' },
      { key: 'rarity', label: '稀有度' },
      { key: 'quantity', label: '数量' },
      { key: 'cost_price', label: '收购价' }
    ],

    sheetVisible: false,
    saving: false,
    editingId: null,
    catalogSearch: '',
    catalogResults: [],
    form: {
      image: '', tempImage: '',
      name: '', name_en: '', set_name: '', card_number: '',
      rarityIdx: 2, condIdx: 0,
      quantity: '1', cost_price: '', market_price: ''
    },
    rarityPickList: ['C', 'U', 'R', 'RR', 'SR', 'SAR', 'UR', 'CSR', 'HR'],
    condList: ['NM 近全新', 'LP 轻微痕迹', 'MP 中度磨损', 'HP 重度磨损', 'Damaged 损坏'],
    condValues: ['NM', 'LP', 'MP', 'HP', 'Damaged']
  },

  onLoad() { this.loadCards(); },
  onShow() { if (this.data.allCards.length) this.loadCards(); },
  onPullDownRefresh() { this.loadCards().then(() => wx.stopPullDownRefresh()); },

  async loadCards() {
    try {
      const res = await api.cards('?sort_by=updated_at&limit=500');
      this.setData({ allCards: res.data || [], loading: false });
      this.applyFilters();
    } catch (e) {
      showToast('加载失败', 'error');
      this.setData({ loading: false });
    }
  },

  applyFilters() {
    let cards = [...this.data.allCards];
    const s = this.data.search.toLowerCase();
    const r = this.data.activeRarity;
    const sk = this.data.sortKey;

    if (s) {
      cards = cards.filter(c =>
        (c.name || '').toLowerCase().includes(s) ||
        (c.name_en || '').toLowerCase().includes(s) ||
        (c.card_number || '').toLowerCase().includes(s) ||
        (c.set_name || '').toLowerCase().includes(s)
      );
    }
    if (r !== 'all') cards = cards.filter(c => c.rarity === r);

    const rarityOrder = ['C', 'U', 'R', 'RR', 'SR', 'SAR', 'UR', 'CSR', 'HR'];
    if (sk === 'name') cards.sort((a, b) => (a.name || '').localeCompare(b.name || ''));
    else if (sk === 'rarity') cards.sort((a, b) => rarityOrder.indexOf(a.rarity) - rarityOrder.indexOf(b.rarity));
    else if (sk === 'quantity') cards.sort((a, b) => b.quantity - a.quantity);
    else if (sk === 'cost_price') cards.sort((a, b) => (b.cost_price || 0) - (a.cost_price || 0));

    const qty = cards.reduce((s, c) => s + (c.quantity || 1), 0);
    const cost = cards.reduce((s, c) => s + ((c.cost_price || 0) * (c.quantity || 1)), 0);
    const value = cards.reduce((s, c) => s + ((c.market_price || 0) * (c.quantity || 1)), 0);

    this.setData({
      cards,
      stats: { total: cards.length, qty, cost: formatMoney(cost), value: formatMoney(value) }
    });
  },

  onSearch(e) { this.setData({ search: e.detail.value }); this.applyFilters(); },
  setRarity(e) { this.setData({ activeRarity: e.currentTarget.dataset.r }); this.applyFilters(); },
  setSort(e) { this.setData({ sortKey: e.currentTarget.dataset.k }); this.applyFilters(); },

  goDetail(e) {
    wx.navigateTo({ url: `/pages/detail/detail?id=${e.currentTarget.dataset.id}` });
  },

  onLongPress(e) {
    const { id, name } = e.currentTarget.dataset;
    wx.showActionSheet({
      itemList: ['编辑', '删除'],
      success: (res) => {
        if (res.tapIndex === 0) this.editCard(id);
        else this.confirmDelete(id, name);
      }
    });
  },

  async editCard(id) {
    try {
      const res = await api.card(id);
      const c = res.data;
      const rarityIdx = this.data.rarityPickList.indexOf(c.rarity || 'R');
      const condIdx = this.data.condValues.indexOf(c.condition || 'NM');
      this.setData({
        sheetVisible: true,
        editingId: id,
        form: {
          image: c.image_path || '', tempImage: '',
          name: c.name || '', name_en: c.name_en || '',
          set_name: c.set_name || '', card_number: c.card_number || '',
          rarityIdx: rarityIdx >= 0 ? rarityIdx : 2,
          condIdx: condIdx >= 0 ? condIdx : 0,
          quantity: String(c.quantity || 1),
          cost_price: String(c.cost_price || ''),
          market_price: String(c.market_price || '')
        }
      });
    } catch (e) { showToast('加载失败', 'error'); }
  },

  showActionSheet() {
    this.setData({
      sheetVisible: true, editingId: null,
      catalogSearch: '', catalogResults: [],
      form: {
        image: '', tempImage: '',
        name: '', name_en: '', set_name: '', card_number: '',
        rarityIdx: 2, condIdx: 0,
        quantity: '1', cost_price: '', market_price: ''
      }
    });
  },

  hideSheet() { this.setData({ sheetVisible: false, editingId: null }); },
  noop() {},

  onField(e) {
    this.setData({ [`form.${e.currentTarget.dataset.k}`]: e.detail.value });
  },

  onRarityPick(e) { this.setData({ 'form.rarityIdx': parseInt(e.detail.value) }); },
  onCondPick(e) { this.setData({ 'form.condIdx': parseInt(e.detail.value) }); },

  pickImage() {
    wx.chooseImage({
      count: 1, sizeType: ['compressed'], sourceType: ['album', 'camera'],
      success: (res) => {
        this.setData({ 'form.image': res.tempFilePaths[0], 'form.tempImage': res.tempFilePaths[0] });
      }
    });
  },

  onCatalogSearch(e) {
    const v = e.detail.value;
    this.setData({ catalogSearch: v });
    if (!v.trim()) { this.setData({ catalogResults: [] }); return; }
    if (this._timer) clearTimeout(this._timer);
    this._timer = setTimeout(async () => {
      try {
        const res = await api.catalog(`?search=${encodeURIComponent(v.trim())}&per_page=10`);
        this.setData({ catalogResults: res.data || [] });
      } catch (e) { /* ignore */ }
    }, 280);
  },

  pickCatalog(e) {
    const id = parseInt(e.currentTarget.dataset.id);
    const item = this.data.catalogResults.find(it => it.id === id);
    if (!item) return;
    const rarityIdx = this.data.rarityPickList.indexOf(item.rarity || 'R');
    this.setData({
      catalogSearch: '', catalogResults: [],
      'form.name': item.name || '',
      'form.name_en': item.name_en || '',
      'form.set_name': item.set_name || '',
      'form.card_number': item.card_number || '',
      'form.rarityIdx': rarityIdx >= 0 ? rarityIdx : 2,
      'form.image': item.image_url || this.data.form.image,
      'form.tempImage': ''
    });
  },

  async saveCard() {
    const f = this.data.form;
    if (!f.name.trim()) { showToast('请输入卡牌名称', 'error'); return; }

    this.setData({ saving: true });
    const data = {
      name: f.name.trim(), name_en: f.name_en.trim(),
      set_name: f.set_name.trim(), card_number: f.card_number.trim(),
      rarity: this.data.rarityPickList[f.rarityIdx],
      condition: this.data.condValues[f.condIdx],
      quantity: parseInt(f.quantity) || 1,
      cost_price: parseFloat(f.cost_price) || 0,
      market_price: parseFloat(f.market_price) || 0
    };

    try {
      if (f.tempImage) {
        const uploadRes = await api.uploadImage(f.tempImage);
        data.image_path = uploadRes.image_path;
      } else if (f.image && f.image.startsWith('http')) {
        data.image_path = f.image;
      }

      const eid = this.data.editingId;
      if (eid) {
        await api.updateCard(eid, data);
        showToast('已更新');
      } else {
        await api.createCard(data);
        showToast('已收藏');
      }
      this.hideSheet();
      this.loadCards();
    } catch (e) { showToast(e.message, 'error'); }
    this.setData({ saving: false });
  },

  confirmDelete(id, name) {
    wx.showModal({
      title: '确认删除',
      content: `确定要删除「${name}」吗？此操作不可恢复。`,
      success: async (res) => {
        if (res.confirm) {
          try {
            await api.deleteCard(id);
            showToast('已删除');
            this.loadCards();
          } catch (e) { showToast(e.message, 'error'); }
        }
      }
    });
  }
});
