// ECharts wrapper for WeChat Mini Program
//
// 使用方法：
// 1. 从 https://github.com/ecomfe/echarts-for-weixin 下载 ec-canvas 目录
//    或从 https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js 下载 echarts
// 2. 将 echarts.min.js 放到 utils/ 目录
// 3. 取消下面 require 的注释

// const echarts = require('./echarts.min');
// module.exports = echarts;

// 临时 polyfill：在正式使用前，需要下载真实的 echarts 库
// 下面的 init 只是占位，不渲染实际图表

const noopChart = {
  setOption() { return this; },
  dispose() {},
  on() {},
  off() {},
  getWidth() { return 300; },
  getHeight() { return 200; },
  resize() {}
};

module.exports = {
  init(canvas, theme, opts) {
    // TODO: 替换为真实 echarts 库
    // 下载 echarts.min.js 放到 utils/ 目录，然后取消下面的注释：
    // return echarts.init(canvas, theme, opts);

    console.warn('[echarts] Using noop stub. Download echarts.min.js from https://echarts.apache.org/');
    return noopChart;
  }
};
