// API helper — wraps wx.request with Promise
const app = getApp();

function getBaseUrl() {
  return app ? app.globalData.apiBase : 'https://your-server.com';
}

function getToken() {
  return app ? app.globalData.token : '';
}

function request(method, path, data) {
  return new Promise((resolve, reject) => {
    const url = getBaseUrl() + path;
    const header = {};

    // Attach auth token
    const token = getToken();
    if (token) {
      header['Authorization'] = 'Bearer ' + token;
    }

    // Set JSON content type for all requests (upload uses wx.uploadFile separately)
    header['Content-Type'] = 'application/json';

    wx.request({
      url,
      method,
      header,
      data: data ? JSON.stringify(data) : undefined,
      success(res) {
        const contentType = res.header['content-type'] || '';
        if (contentType.includes('application/json')) {
          const json = res.data;
          if (res.statusCode === 401) {
            // Token expired or invalid — clear it
            if (app) {
              app.globalData.token = '';
              wx.removeStorageSync('token');
            }
            reject(new Error('请先登录'));
            return;
          }
          if (json.success) {
            resolve(json);
          } else {
            reject(new Error(json.message || 'Request failed'));
          }
        } else {
          reject(new Error(`Server error (${res.statusCode})`));
        }
      },
      fail(err) {
        reject(new Error(err.errMsg || 'Network error'));
      }
    });
  });
}

const api = {
  get(path) { return request('GET', path); },
  post(path, data) { return request('POST', path, data); },
  put(path, data) { return request('PUT', path, data); },
  delete(path) { return request('DELETE', path); },

  // Cards
  cards(params = '') { return this.get('/api/cards' + params); },
  card(id) { return this.get(`/api/cards/${id}`); },
  createCard(data) { return this.post('/api/cards', data); },
  updateCard(id, data) { return this.put(`/api/cards/${id}`, data); },
  deleteCard(id) { return this.delete(`/api/cards/${id}`); },

  // Dashboard
  dashboard() { return this.get('/api/dashboard'); },

  // Prices
  prices(cardId) { return this.get(`/api/prices?card_id=${cardId}`); },
  addManualPrice(data) { return this.post('/api/prices/manual', data); },

  // TCG Search
  searchTcg(q) { return this.get(`/api/search-tcg?q=${encodeURIComponent(q)}`); },

  // Catalog
  catalog(params = '') { return this.get('/api/catalog' + params); },
  catalogItem(id) { return this.get(`/api/catalog/${id}`); },
  createCatalogItem(data) { return this.post('/api/catalog', data); },
  updateCatalogItem(id, data) { return this.put(`/api/catalog/${id}`, data); },
  deleteCatalogItem(id) { return this.delete(`/api/catalog/${id}`); },
  bulkImportCatalog(items) { return this.post('/api/catalog/bulk', { items }); },
  catalogSets() { return this.get('/api/catalog/sets'); },

  // Ensure card from catalog (creates card — use for collection, NOT for price lookup)
  cardFromCatalog(catalogId) { return this.post('/api/cards/from-catalog', { catalog_id: catalogId }); },

  // Read-only catalog-to-card lookup (no side effects — safe for price page)
  catalogCardLookup(catalogId) { return this.get(`/api/catalog/${catalogId}/card`); },

  // Sets info
  setsInfo() { return this.get('/api/sets-info'); },

  // Upload
  uploadImage(filePath) {
    return new Promise((resolve, reject) => {
      const header = {};
      const token = getToken();
      if (token) header['Authorization'] = 'Bearer ' + token;
      wx.uploadFile({
        url: getBaseUrl() + '/api/upload',
        filePath,
        name: 'file',
        header,
        success(res) {
          try {
            const json = JSON.parse(res.data);
            if (json.success) resolve(json);
            else reject(new Error(json.message));
          } catch (e) {
            reject(new Error('Upload failed'));
          }
        },
        fail(err) {
          reject(new Error(err.errMsg));
        }
      });
    });
  }
};

module.exports = api;
