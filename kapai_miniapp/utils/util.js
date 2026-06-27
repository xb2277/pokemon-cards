// Utility functions

function formatMoney(n) {
  if (n == null || isNaN(n)) return '--';
  return '¥' + Math.round(Number(n)).toLocaleString('zh-CN');
}

function rarityLabel(r) {
  const map = {
    'C': 'Common', 'U': 'Uncommon', 'R': 'Rare', 'RR': 'Double Rare',
    'SR': 'Special Rare', 'SAR': 'Special Art Rare', 'UR': 'Ultra Rare',
    'CSR': 'Character Super Rare', 'HR': 'Hyper Rare'
  };
  return map[r] || r;
}

function conditionLabel(c) {
  const map = {
    'NM': '近全新', 'LP': '轻微使用', 'MP': '中度磨损',
    'HP': '重度磨损', 'Damaged': '损坏'
  };
  return map[c] || c;
}

function showToast(msg, type = 'success') {
  wx.showToast({
    title: msg,
    icon: type === 'error' ? 'none' : type,
    duration: 2000
  });
}

function confirm(msg) {
  return new Promise((resolve) => {
    wx.showModal({
      title: '确认',
      content: msg,
      success(res) {
        resolve(res.confirm);
      }
    });
  });
}

module.exports = {
  formatMoney,
  rarityLabel,
  conditionLabel,
  showToast,
  confirm
};
