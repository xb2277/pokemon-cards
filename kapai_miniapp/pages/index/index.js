const api = require('../../utils/api');
const { formatMoney, showToast } = require('../../utils/util');

Page({
  data: {
    userInfo: null,
    loginSheetVisible: false,
    loginForm: { avatar: '', nickName: '', phone: '' },
    loginLoading: false,
    stats: { total: 0, qty: 0, cost: '¥0', value: '¥0' }
  },

  onLoad() {
    const app = getApp();
    if (app.globalData.userInfo) {
      this.setData({ userInfo: app.globalData.userInfo });
    }
    this.loadStats();
  },

  onShow() {
    const app = getApp();
    const ui = app.globalData.userInfo;
    if (ui !== this.data.userInfo) {
      this.setData({ userInfo: ui || null });
    }
    // Refresh stats when coming back to this page
    if (app.globalData.token) {
      this.loadStats();
    }
  },

  onPullDownRefresh() {
    this.loadStats().then(() => wx.stopPullDownRefresh());
  },

  async loadStats() {
    try {
      const res = await api.dashboard();
      const d = res.data;
      this.setData({
        stats: {
          total: d.total_cards || 0,
          qty: d.total_quantity || 0,
          cost: formatMoney(d.total_cost),
          value: formatMoney(d.total_value)
        }
      });
    } catch (e) { /* offline or not logged in, ignore */ }
  },

  // ======== Navigation ========

  goCollection() {
    wx.switchTab({ url: '/pages/collection/collection' });
  },

  goCatalog() {
    wx.navigateTo({ url: '/pages/catalog/catalog' });
  },

  goDashboard() {
    wx.navigateTo({ url: '/pages/dashboard/dashboard' });
  },

  goPrice() {
    wx.switchTab({ url: '/pages/price/price' });
  },

  // ======== Login ========

  showLoginSheet() {
    const ui = this.data.userInfo;
    this.setData({
      loginSheetVisible: true,
      loginForm: {
        avatar: ui ? ui.avatar : '',
        nickName: ui ? ui.nickName : '',
        phone: ui ? ui.phone : ''
      }
    });
  },

  hideLoginSheet() { this.setData({ loginSheetVisible: false }); },

  onChooseAvatar(e) {
    const { avatarUrl } = e.detail;
    if (avatarUrl) this.setData({ 'loginForm.avatar': avatarUrl });
  },

  onNicknameInput(e) {
    this.setData({ 'loginForm.nickName': e.detail.value });
  },

  onNicknameBlur(e) {
    if (e.detail.value) this.setData({ 'loginForm.nickName': e.detail.value });
  },

  onGetPhoneNumber(e) {
    const { code, errMsg } = e.detail;
    if (errMsg === 'getPhoneNumber:ok' && code) {
      this.setData({ 'loginForm.phone': code });
      showToast('手机号已授权');
    } else if (errMsg === 'getPhoneNumber:fail user deny') {
      showToast('已取消手机授权', 'error');
    }
  },

  doLogin() {
    const { avatar, nickName, phone } = this.data.loginForm;
    if (!nickName.trim()) { showToast('请输入昵称', 'error'); return; }

    this.setData({ loginLoading: true });

    // 1. wx.login to get code
    wx.login({
      success: (loginRes) => {
        if (!loginRes.code) {
          this.setData({ loginLoading: false });
          showToast('微信登录失败，请重试', 'error');
          return;
        }

        // 2. Exchange code + profile for token
        wx.request({
          url: getApp().globalData.apiBase + '/api/auth/wechat-login',
          method: 'POST',
          header: { 'Content-Type': 'application/json' },
          data: {
            code: loginRes.code,
            nickName: nickName.trim(),
            avatar: avatar || '',
            phone: phone || ''
          },
          success: (resp) => {
            this.setData({ loginLoading: false });
            const json = resp.data;
            if (json.success && json.data.token) {
              const app = getApp();
              app.globalData.token = json.data.token;
              wx.setStorageSync('token', json.data.token);

              const userInfo = {
                avatar: avatar || '',
                nickName: nickName.trim(),
                phone: phone || ''
              };
              app.saveUserInfo(userInfo);
              this.setData({ userInfo, loginSheetVisible: false });
              showToast('登录成功');
              this.loadStats();
            } else {
              showToast(json.message || '登录失败', 'error');
            }
          },
          fail: () => {
            this.setData({ loginLoading: false });
            showToast('网络错误，请重试', 'error');
          }
        });
      },
      fail: () => {
        this.setData({ loginLoading: false });
        showToast('微信登录失败，请重试', 'error');
      }
    });
  },

  doLogout() {
    wx.showModal({
      title: '退出登录',
      content: '确定要退出登录吗？',
      success: (res) => {
        if (res.confirm) {
          const app = getApp();
          app.clearUserInfo();
          this.setData({
            userInfo: null,
            loginSheetVisible: false,
            stats: { total: 0, qty: 0, cost: '¥0', value: '¥0' },
            loginForm: { avatar: '', nickName: '', phone: '' }
          });
          showToast('已退出');
        }
      }
    });
  }
});
