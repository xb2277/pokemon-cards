const api = require('../../utils/api');
const { formatMoney, showToast } = require('../../utils/util');

Page({
  data: {
    // Card selection
    cardId: null,
    sel: { name: '', sub: '', image: '' },

    // Catalog picker
    pickerVisible: false,
    catalogSearch: '',
    catalogResults: [],
    catalogLoading: false,

    // Prices
    latest: {},
    noHistory: false,
    chartReady: false, priceEc: {},
    refreshing: false,
    showManual: false, mPrice: '', mPlatform: '手动录入',
    notInCollection: false
  },

  // ======== Catalog Picker ========

  openCatalogPicker() {
    this.setData({
      pickerVisible: true,
      catalogSearch: '',
      catalogResults: []
    });
  },

  closeCatalogPicker() {
    this.setData({ pickerVisible: false });
  },

  onCatalogSearch(e) {
    const v = e.detail.value;
    this.setData({ catalogSearch: v });
    if (!v.trim()) { this.setData({ catalogResults: [] }); return; }
    if (this._t) clearTimeout(this._t);
    this._t = setTimeout(async () => {
      this.setData({ catalogLoading: true });
      try {
        const res = await api.catalog(`?search=${encodeURIComponent(v.trim())}&per_page=30`);
        this.setData({ catalogResults: res.data || [] });
      } catch (e) { /* ignore */ }
      this.setData({ catalogLoading: false });
    }, 280);
  },

  async selectCatalogCard(e) {
    const id = parseInt(e.currentTarget.dataset.id);
    const item = this.data.catalogResults.find(it => it.id === id);
    if (!item) return;

    this.setData({ pickerVisible: false });

    try {
      // Read-only lookup — does NOT auto-create card in collection
      const res = await api.catalogCardLookup(item.id);
      const card = (res.data && res.data.card) ? res.data.card : null;
      const sel = {
        name: item.name + (item.name_en ? ' / ' + item.name_en : ''),
        sub: [item.set_name, item.card_number, item.rarity].filter(Boolean).join(' · '),
        image: item.image_url || ''
      };

      if (!card) {
        // User hasn't added this card to collection — show info but no prices
        this.setData({
          cardId: null, showManual: false, sel,
          chartReady: false, noHistory: true,
          notInCollection: true,
          latest: {}
        });
        return;
      }

      this.setData({
        cardId: card.id, showManual: false, sel,
        notInCollection: false
      });
      this.loadPrices(card.id);
    } catch (e) { showToast('查询卡牌失败', 'error'); }
  },

  // ======== Prices ========

  async loadPrices(cardId) {
    try {
      const res = await api.prices(cardId);
      const latest = res.data.latest || {};
      const history = (res.data.history || []).reverse();

      this.setData({
        latest: {
          avg: latest.avg != null ? formatMoney(latest.avg) : '--',
          max: latest.max != null ? formatMoney(latest.max) : '--',
          min: latest.min != null ? formatMoney(latest.min) : '--',
          count: latest.count || 0
        },
        noHistory: history.length === 0
      });

      if (history.length > 0) this.renderChart(history.reverse());
    } catch (e) {}
  },

  renderChart(history) {
    const platforms = {};
    history.forEach(h => {
      if (!platforms[h.platform]) platforms[h.platform] = [];
      platforms[h.platform].push([h.recorded_at.split(' ')[0], h.price]);
    });
    const dates = [...new Set(history.map(h => h.recorded_at.split(' ')[0]))].sort();
    const colors = { 'tcgplayer': '#378add', 'xianyu': '#d85a30', 'pokemontcg': '#534ab7', 'manual': '#888780', 'pokemontcg-usd': '#534ab7' };
    const series = Object.keys(platforms).map(p => ({
      name: p, type: 'line', smooth: true, symbolSize: 4,
      lineStyle: { width: 1.8 },
      itemStyle: { color: colors[p] || '#888780' },
      data: platforms[p].map(([t, v]) => [t, v])
    }));

    this.setData({
      chartReady: true,
      priceEc: {
        onInit: (canvas, width, height, dpr) => {
          const chart = require('../../utils/echarts').init(canvas, null, { width, height, devicePixelRatio: dpr });
          canvas.setChart(chart);
          chart.setOption({
            tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
            legend: { top: 0, textStyle: { fontSize: 10 } },
            grid: { left: 60, right: 20, top: 36, bottom: 32 },
            xAxis: { type: 'category', data: dates, axisLabel: { fontSize: 9, rotate: 20 }, boundaryGap: false },
            yAxis: { type: 'value', axisLabel: { fontSize: 10, formatter: v => '¥' + v } },
            series
          });
          return chart;
        }
      }
    });
  },

  // Refresh
  async doRefresh() {
    if (!this.data.cardId) { showToast('请先选择卡牌', 'info'); return; }
    this.setData({ refreshing: true });
    try {
      const res = await api.card(this.data.cardId);
      const name = res.data.name_en || res.data.name;
      const tcg = await api.searchTcg(name);
      if (tcg.data && tcg.data.length > 0) {
        const p = tcg.data[0].tcgplayer_prices || {};
        const price = parseFloat((p.normal || {}).market) || parseFloat((p.holofoil || {}).market);
        if (price) {
          const cny = Math.round(price * 7.2 * 100) / 100;
          await api.addManualPrice({ card_id: this.data.cardId, platform: 'pokemontcg', price: cny });
          showToast(`获取价格: $${price} -> ¥${cny}`);
          this.loadPrices(this.data.cardId);
        } else { showToast('TCG 未返回价格', 'info'); }
      } else { showToast('TCG 未找到该卡', 'info'); }
    } catch (e) { showToast('抓取失败', 'error'); }
    this.setData({ refreshing: false });
  },

  toggleManual() { this.setData({ showManual: !this.data.showManual }); },
  onMPrice(e) { this.setData({ mPrice: e.detail.value }); },
  onMPlatform(e) { this.setData({ mPlatform: e.detail.value }); },

  async submitManual() {
    if (!this.data.cardId || !this.data.mPrice) { showToast('请输入价格', 'error'); return; }
    try {
      await api.addManualPrice({
        card_id: this.data.cardId,
        platform: this.data.mPlatform || '手动录入',
        price: parseFloat(this.data.mPrice)
      });
      showToast('已录入');
      this.setData({ mPrice: '', mPlatform: '手动录入' });
      this.loadPrices(this.data.cardId);
    } catch (e) { showToast(e.message, 'error'); }
  }
});
