// ec-canvas — ECharts component for WeChat Mini Program
// Based on echarts-for-weixin (https://github.com/ecomfe/echarts-for-weixin)

const app = getApp();

Component({
  properties: {
    canvasId: {
      type: String,
      value: 'ec-canvas'
    },
    ec: {
      type: Object,
      observer: 'onEcReady'
    },
    bindtouchstart: {
      type: String,
      value: ''
    },
    bindtouchmove: {
      type: String,
      value: ''
    },
    bindtouchend: {
      type: String,
      value: ''
    }
  },

  data: {
    chartId: '',
    width: '100%',
    height: '300px',
    chart: null
  },

  lifetimes: {
    attached() {
      // Generate a unique chart ID
      const chartId = 'ec-' + Math.random().toString(36).substr(2, 9);
      this.setData({ chartId });
    },
    detached() {
      if (this.data.chart) {
        this.data.chart.dispose();
      }
    }
  },

  methods: {
    onEcReady(ec) {
      if (!ec || !this.data.chartId) return;

      const query = this.createSelectorQuery();
      query.select('#' + this.data.chartId)
        .fields({ node: true, size: true })
        .exec((res) => {
          if (!res || !res[0]) {
            // Retry after a delay
            setTimeout(() => this.onEcReady(ec), 100);
            return;
          }

          const canvasNode = res[0].node;
          const width = res[0].width;
          const height = res[0].height;

          if (!canvasNode || width <= 0 || height <= 0) {
            setTimeout(() => this.onEcReady(ec), 100);
            return;
          }

          this.setData({ width: width + 'px', height: height + 'px' });

          if (typeof ec.onInit === 'function') {
            const chart = ec.onInit(canvasNode, width, height, app.globalData.systemInfo.pixelRatio);
            this.setData({ chart });
          }
        });
    }
  }
});
