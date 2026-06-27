App({
  globalData: {
    // API base URL — change this to your deployed Flask server
    apiBase: 'http://192.168.0.106:5001',
    currentCardId: null,
    userInfo: null,
    token: ''
  },

  onLaunch() {
    // System info for ec-canvas pixel ratio
    this.globalData.systemInfo = wx.getSystemInfoSync();

    // Check for saved API base
    const saved = wx.getStorageSync('apiBase');
    if (saved) {
      this.globalData.apiBase = saved;
    }

    // Restore token and user info from storage
    const token = wx.getStorageSync('token');
    if (token) {
      this.globalData.token = token;
      // Verify token is still valid
      this.verifyToken();
    }

    const userInfo = wx.getStorageSync('userInfo');
    if (userInfo) {
      this.globalData.userInfo = userInfo;
    }

    // If no token, do silent login
    if (!token) {
      this.silentLogin();
    }
  },

  silentLogin() {
    wx.login({
      success: (res) => {
        if (res.code) {
          wx.request({
            url: this.globalData.apiBase + '/api/auth/wechat-login',
            method: 'POST',
            header: { 'Content-Type': 'application/json' },
            data: { code: res.code },
            success: (resp) => {
              const json = resp.data;
              if (json.success && json.data.token) {
                this.globalData.token = json.data.token;
                wx.setStorageSync('token', json.data.token);
              }
            }
          });
        }
      }
    });
  },

  verifyToken() {
    wx.request({
      url: this.globalData.apiBase + '/api/auth/me',
      method: 'GET',
      header: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + this.globalData.token
      },
      success: (resp) => {
        if (resp.statusCode === 200 || (resp.data && resp.data.success)) {
          const u = resp.data.data;
          if (u) {
            const info = {
              avatar: u.avatar || '',
              nickName: u.nick_name || '',
              phone: u.phone || ''
            };
            this.saveUserInfo(info);
          }
        } else {
          // Token invalid — try silent login
          this.globalData.token = '';
          wx.removeStorageSync('token');
          this.silentLogin();
        }
      },
      fail: () => {}
    });
  },

  saveUserInfo(info) {
    this.globalData.userInfo = info;
    wx.setStorageSync('userInfo', info);
  },

  clearUserInfo() {
    this.globalData.userInfo = null;
    this.globalData.token = '';
    wx.removeStorageSync('userInfo');
    wx.removeStorageSync('token');
  }
});
