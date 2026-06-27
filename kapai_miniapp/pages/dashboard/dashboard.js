const api = require('../../utils/api');
const { formatMoney } = require('../../utils/util');

Page({
  data: {
    loading: true,
    data: {},
    gainers: [],
    losers: [],
    trendReady: false,
    trendEmpty: false,
    distReady: false,
    trendEc: {},
    distEc: {}
  },

  onLoad() {
    this.loadDashboard();
  },

  onPullDownRefresh() {
    this.loadDashboard().then(() => wx.stopPullDownRefresh());
  },

  async loadDashboard() {
    try {
      const res = await api.dashboard();
      const d = res.data;

      this.setData({
        loading: false,
        data: {
          total_cards: d.total_cards,
          total_cost: formatMoney(d.total_cost),
          total_value: formatMoney(d.total_value),
          profit: d.profit,
          profit_pct: d.profit_pct,
          profit_display: (d.profit >= 0 ? '+' : '') + formatMoney(d.profit)
        },
        gainers: (d.top_gainers || []).map(g => ({
          ...g,
          current_display: formatMoney(g.current)
        })),
        losers: (d.top_losers || []).map(l => ({
          ...l,
          current_display: formatMoney(l.current)
        }))
      });

      // Render charts
      if (d.snapshots && d.snapshots.length > 0) {
        this.renderTrendChart(d.snapshots);
      } else {
        this.setData({ trendEmpty: true });
      }

      if (d.rarity_distribution && d.rarity_distribution.length > 0) {
        this.renderDistChart(d.rarity_distribution);
      }

    } catch (e) {
      this.setData({ loading: false });
      wx.showToast({ title: '加载失败', icon: 'none' });
    }
  },

  renderTrendChart(snapshots) {
    const dates = snapshots.map(s => s.snapshot_date);
    const values = snapshots.map(s => s.total_value);

    this.setData({
      trendReady: true,
      trendEc: {
        onInit: (canvas, width, height, dpr) => {
          const chart = require('../../utils/echarts').init(canvas, null, { width, height, devicePixelRatio: dpr });
          canvas.setChart(chart);
          chart.setOption(this.getTrendOption(dates, values));
          return chart;
        }
      }
    });
  },

  getTrendOption(dates, values) {
    return {
      tooltip: { trigger: 'axis' },
      grid: { left: 60, right: 20, top: 20, bottom: 30 },
      xAxis: { type: 'category', data: dates, axisLabel: { fontSize: 10 }, boundaryGap: false },
      yAxis: { type: 'value', axisLabel: { fontSize: 10, formatter: v => '¥' + (v / 10000).toFixed(1) + 'w' } },
      series: [{
        type: 'line', data: values, smooth: true,
        areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(55,138,221,0.15)' }, { offset: 1, color: 'rgba(55,138,221,0.01)' }] } },
        lineStyle: { color: '#378add', width: 2 },
        itemStyle: { color: '#378add' },
        symbolSize: 4
      }]
    };
  },

  renderDistChart(dist) {
    const colors = ['#B4B2A9', '#9FE1CB', '#FAC775', '#CECBF6', '#F5C4B3', '#F0997B', '#D4537E', '#993C1D', '#3B6D11'];
    const data = dist.map((d, i) => ({ name: d.name, value: d.value, itemStyle: { color: colors[i % colors.length] } }));

    this.setData({
      distReady: true,
      distEc: {
        onInit: (canvas, width, height, dpr) => {
          const chart = require('../../utils/echarts').init(canvas, null, { width, height, devicePixelRatio: dpr });
          canvas.setChart(chart);
          chart.setOption({
            tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
            series: [{
              type: 'pie', radius: ['40%', '70%'], center: ['50%', '50%'],
              label: { show: false },
              emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,.15)' } },
              data
            }]
          });
          return chart;
        }
      }
    });
  },

  goToDetail(e) {
    const id = e.currentTarget.dataset.id;
    wx.navigateTo({ url: `/pages/detail/detail?id=${id}` });
  }
});
