const api = require('../../utils/api');
const { formatMoney, conditionLabel, showToast } = require('../../utils/util');

Page({
  data: {
    cardId: null, card: null, loading: true,
    condLabel: '', costPrice: '--', marketPrice: '--', totalValue: '--',
    estPrice: '', estTotal: '',

    // Edit sheet
    showEdit: false, saving: false,
    edit: {}, editTemp: '',
    rList: ['C', 'U', 'R', 'RR', 'SR', 'SAR', 'UR', 'CSR', 'HR'],
    cList: ['NM 近全新', 'LP 轻微痕迹', 'MP 中度磨损', 'HP 重度磨损', 'Damaged 损坏'],
    cValues: ['NM', 'LP', 'MP', 'HP', 'Damaged']
  },

  onLoad(options) {
    if (options.id) {
      this.setData({ cardId: parseInt(options.id) });
      this.loadCard();
    }
  },

  async loadCard() {
    try {
      const res = await api.card(this.data.cardId);
      const c = res.data;
      this.setData({
        card: c, loading: false,
        condLabel: conditionLabel(c.condition),
        costPrice: formatMoney(c.cost_price),
        marketPrice: formatMoney(c.market_price),
        totalValue: formatMoney((c.market_price || 0) * (c.quantity || 1))
      });
      // Price
      try {
        const pr = await api.prices(c.id);
        const latest = pr.data.latest;
        if (latest.avg != null) {
          this.setData({
            estPrice: formatMoney(latest.avg),
            estTotal: formatMoney(latest.avg * (c.quantity || 1))
          });
        }
      } catch (e) {}
    } catch (e) {
      this.setData({ loading: false });
      showToast('卡牌未找到', 'error');
    }
  },

  goBack() { wx.navigateBack({ fail: () => wx.switchTab({ url: '/pages/index/index' }) }); },
  goPrice() { wx.switchTab({ url: '/pages/price/price' }); },

  // ======== Edit ========

  showEditSheet() {
    const c = this.data.card;
    this.setData({
      showEdit: true, editTemp: '',
      edit: {
        image: c.image_path || '',
        name: c.name || '', name_en: c.name_en || '',
        set_name: c.set_name || '', card_number: c.card_number || '',
        rarityIdx: this.data.rList.indexOf(c.rarity || 'R'),
        condIdx: this.data.cValues.indexOf(c.condition || 'NM'),
        quantity: String(c.quantity || 1),
        cost_price: String(c.cost_price || ''), market_price: String(c.market_price || ''),
        notes: c.notes || ''
      }
    });
    const ri = this.data.edit.rarityIdx;
    const ci = this.data.edit.condIdx;
    this.setData({ 'edit.rarityIdx': ri >= 0 ? ri : 2, 'edit.condIdx': ci >= 0 ? ci : 0 });
  },

  hideEditSheet() { this.setData({ showEdit: false }); },
  noop() {},

  pickEditImage() {
    wx.chooseImage({
      count: 1, sizeType: ['compressed'], sourceType: ['album', 'camera'],
      success: (res) => {
        this.setData({ editTemp: res.tempFilePaths[0], 'edit.image': res.tempFilePaths[0] });
      }
    });
  },

  onEditField(e) { this.setData({ [`edit.${e.currentTarget.dataset.k}`]: e.detail.value }); },
  onEditRarity(e) { this.setData({ 'edit.rarityIdx': parseInt(e.detail.value) }); },
  onEditCond(e) { this.setData({ 'edit.condIdx': parseInt(e.detail.value) }); },

  async saveEdit() {
    const e = this.data.edit;
    this.setData({ saving: true });
    const data = {
      name: e.name.trim(), name_en: e.name_en.trim(),
      set_name: e.set_name.trim(), card_number: e.card_number.trim(),
      rarity: this.data.rList[e.rarityIdx],
      condition: this.data.cValues[e.condIdx],
      quantity: parseInt(e.quantity) || 1,
      cost_price: parseFloat(e.cost_price) || 0,
      market_price: parseFloat(e.market_price) || 0,
      notes: e.notes.trim()
    };

    try {
      if (this.data.editTemp) {
        const up = await api.uploadImage(this.data.editTemp);
        data.image_path = up.image_path;
      }
      const res = await api.updateCard(this.data.cardId, data);
      this.hideEditSheet();
      showToast('已更新');
      const c = res.data;
      this.setData({
        card: c,
        condLabel: conditionLabel(c.condition),
        costPrice: formatMoney(c.cost_price),
        marketPrice: formatMoney(c.market_price),
        totalValue: formatMoney((c.market_price || 0) * (c.quantity || 1))
      });
    } catch (err) { showToast(err.message, 'error'); }
    this.setData({ saving: false });
  },

  // ======== Delete ========

  doDelete() {
    wx.showModal({
      title: '确认删除',
      content: `确定要删除「${this.data.card.name}」吗？`,
      success: async (res) => {
        if (res.confirm) {
          await api.deleteCard(this.data.cardId);
          showToast('已删除');
          setTimeout(() => {
            wx.navigateBack({ fail: () => wx.switchTab({ url: '/pages/index/index' }) });
          }, 800);
        }
      }
    });
  }
});
