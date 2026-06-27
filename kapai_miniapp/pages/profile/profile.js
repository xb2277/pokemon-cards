const api = require('../../utils/api');
const { formatMoney } = require('../../utils/util');

Page({
  data: {
    stats: { cards: 0, qty: 0, cost: '¥0', profit: '¥0' },
    apiBase: '',
    apiUrlInput: '',
    showConfig: false
  },

  onShow() {
    const app = getApp();
    this.setData({ apiBase: app.globalData.apiBase });
    this.loadStats();
  },

  async loadStats() {
    try {
      const res = await api.dashboard();
      const d = res.data;
      this.setData({
        stats: {
          cards: d.total_cards || 0,
          qty: d.total_quantity || 0,
          cost: formatMoney(d.total_cost),
          profit: (d.profit >= 0 ? '+' : '') + formatMoney(d.profit),
        }
      });
    } catch (e) { /* offline, ignore */ }
  },

  goDashboard() { wx.navigateTo({ url: '/pages/dashboard/dashboard' }); },
  goPrice() { wx.switchTab({ url: '/pages/price/price' }); },
  goCatalog() { wx.navigateTo({ url: '/pages/catalog/catalog' }); },

  showApiConfig() {
    const app = getApp();
    this.setData({ showConfig: true, apiUrlInput: app.globalData.apiBase });
  },

  hideConfig() { this.setData({ showConfig: false }); },
  noop() {},

  onApiInput(e) { this.setData({ apiUrlInput: e.detail.value }); },

  saveApiConfig() {
    const url = this.data.apiUrlInput.trim().replace(/\/$/, '');
    const app = getApp();
    app.globalData.apiBase = url;
    wx.setStorageSync('apiBase', url);
    this.setData({ apiBase: url, showConfig: false });
    wx.showToast({ title: '已保存', icon: 'success' });
  }
});
