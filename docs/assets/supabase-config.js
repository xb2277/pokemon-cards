// ============================================================
// Supabase Client Configuration
// ============================================================
// Replace these with your actual Supabase project credentials
// Find them at: Supabase Dashboard → Settings → API
const SUPABASE_URL = 'https://hlmhvuszhugpsvjolgjr.supabase.co';
const SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImhsbWh2dXN6aHVncHN2am9sZ2pyIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODI1NjAxMjUsImV4cCI6MjA5ODEzNjEyNX0.w9j6uYE5ZgK71oYQK9VWXiCX8uLUnR97T2cA5E4N2uY';

// Initialize Supabase client
const supabase = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
  }
});

// ============================================================
// Auth helpers (replace old JWT token system)
// ============================================================

async function getCurrentUser() {
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return null;

  // Fetch profile (role, nick_name, etc.)
  const { data: profile } = await supabase
    .from('profiles')
    .select('*')
    .eq('id', user.id)
    .single();

  return { ...user, ...profile };
}

async function isLoggedIn() {
  const { data: { session } } = await supabase.auth.getSession();
  return !!session;
}

async function requireAuth() {
  const loggedIn = await isLoggedIn();
  if (!loggedIn) {
    window.location.href = './login.html';
    return false;
  }
  return true;
}

async function isAdmin() {
  const user = await getCurrentUser();
  return user?.role === 'admin';
}

// ============================================================
// Data access layer (replaces fetch('/api/...'))
// ============================================================

const PER_PAGE = 24;

// ---- Cards CRUD ----

async function fetchCards({ page = 1, perPage = PER_PAGE, search = '', rarity = '', sortBy = 'updated_at' } = {}) {
  let query = supabase.from('cards').select('*', { count: 'exact' });

  if (search) {
    // Supabase doesn't support OR across multiple columns in a single .or() easily
    // Use .or() with ilike
    const s = search.replace(/'/g, "''");
    query = query.or(`name.ilike.%${s}%,name_en.ilike.%${s}%,card_number.ilike.%${s}%,set_name.ilike.%${s}%`);
  }

  if (rarity && rarity !== 'all') {
    query = query.eq('rarity', rarity);
  }

  // Sort
  const sortMap = {
    'updated_at': 'updated_at',
    'name': 'name',
    'set_name': 'set_name',
    'quantity': 'quantity',
    'cost_price': 'cost_price',
  };
  const sortCol = sortMap[sortBy] || 'updated_at';
  query = query.order(sortCol, { ascending: false });

  // Pagination
  const offset = (page - 1) * perPage;
  query = query.range(offset, offset + perPage - 1);

  const { data, error, count } = await query;
  if (error) throw new Error(error.message);
  return { data: data || [], total: count || 0 };
}

async function fetchCardById(id) {
  const { data, error } = await supabase
    .from('cards')
    .select('*')
    .eq('id', id)
    .single();
  if (error) throw new Error(error.message);
  return data;
}

async function createCard(cardData) {
  const { data: { user } } = await supabase.auth.getUser();
  const payload = {
    ...cardData,
    user_id: user?.id,
    quantity: parseInt(cardData.quantity) || 1,
    cost_price: parseFloat(cardData.cost_price) || 0,
    market_price: parseFloat(cardData.market_price) || 0,
  };
  const { data, error } = await supabase.from('cards').insert(payload).select().single();
  if (error) throw new Error(error.message);
  return data;
}

async function createCardFromCatalog(catalogId, { quantity, cost_price, condition, notes }) {
  // Fetch catalog item
  const { data: catalog, error: catErr } = await supabase
    .from('card_catalog')
    .select('*')
    .eq('id', catalogId)
    .single();
  if (catErr) throw new Error(catErr.message);

  const { data: { user } } = await supabase.auth.getUser();

  // Check if card already exists for this user
  const { data: existing } = await supabase
    .from('cards')
    .select('*')
    .eq('catalog_id', catalogId)
    .eq('user_id', user?.id)
    .maybeSingle();

  if (existing) {
    // Update quantity
    const { data, error } = await supabase
      .from('cards')
      .update({
        quantity: existing.quantity + (parseInt(quantity) || 1),
        cost_price: parseFloat(cost_price) || existing.cost_price,
        condition: condition || existing.condition,
        notes: notes || existing.notes,
      })
      .eq('id', existing.id)
      .select()
      .single();
    if (error) throw new Error(error.message);
    return data;
  }

  // Create new card
  const payload = {
    user_id: user?.id,
    catalog_id: catalogId,
    name: catalog.name,
    name_en: catalog.name_en || '',
    set_name: catalog.set_name || '',
    card_number: catalog.card_number || '',
    rarity: catalog.rarity || 'C',
    condition: condition || 'NM',
    quantity: parseInt(quantity) || 1,
    cost_price: parseFloat(cost_price) || 0,
    market_price: catalog.market_price || 0,
    image_path: catalog.image_url || '',
    notes: notes || '',
  };
  const { data, error } = await supabase.from('cards').insert(payload).select().single();
  if (error) throw new Error(error.message);
  return data;
}

async function updateCard(id, cardData) {
  const payload = {
    name: cardData.name,
    name_en: cardData.name_en,
    set_name: cardData.set_name,
    card_number: cardData.card_number,
    rarity: cardData.rarity,
    condition: cardData.condition,
    quantity: parseInt(cardData.quantity) || 1,
    cost_price: parseFloat(cardData.cost_price) || 0,
    market_price: parseFloat(cardData.market_price) || 0,
    notes: cardData.notes,
  };
  const { data, error } = await supabase.from('cards').update(payload).eq('id', id).select().single();
  if (error) throw new Error(error.message);
  return data;
}

async function deleteCard(id) {
  const { error } = await supabase.from('cards').delete().eq('id', id);
  if (error) throw new Error(error.message);
}

// ---- Dashboard ----

async function fetchDashboardData() {
  const { data: cards, error } = await supabase.from('cards').select('*');
  if (error) throw new Error(error.message);

  const total_quantity = cards.reduce((s, c) => s + (c.quantity || 1), 0);
  const total_cost = cards.reduce((s, c) => s + ((c.cost_price || 0) * (c.quantity || 1)), 0);

  // Get latest prices for each card's catalog_id
  let total_value = 0;
  let valued_cards = 0;

  for (const card of cards) {
    let price = card.market_price || 0;

    // Try to get latest price from price_records
    if (card.catalog_id) {
      const { data: prices } = await supabase
        .from('price_records')
        .select('price')
        .eq('catalog_id', card.catalog_id)
        .order('recorded_at', { ascending: false })
        .limit(30);
      if (prices && prices.length > 0) {
        price = prices.reduce((s, p) => s + p.price, 0) / prices.length;
      }
    }

    if (price > 0) {
      total_value += price * (card.quantity || 1);
      valued_cards++;
    }
  }

  const profit = total_value - total_cost;
  const profit_pct = total_cost > 0 ? (profit / total_cost * 100) : 0;

  // Rarity distribution
  const rarityMap = {};
  cards.forEach(c => {
    const r = c.rarity || 'unknown';
    if (!rarityMap[r]) rarityMap[r] = { name: r, value: 0, types: 0 };
    rarityMap[r].value += c.quantity || 1;
    rarityMap[r].types++;
  });
  const rarity_distribution = Object.values(rarityMap).sort((a, b) => b.value - a.value);

  // Set distribution
  const setMap = {};
  cards.forEach(c => {
    const s = c.set_name || '其他';
    if (!setMap[s]) setMap[s] = { name: s, value: 0 };
    setMap[s].value += c.quantity || 1;
  });
  const set_distribution = Object.values(setMap).sort((a, b) => b.value - a.value);

  // Rankings
  const rankings = [];
  for (const card of cards) {
    let currentPrice = card.market_price || 0;
    if (card.catalog_id) {
      const { data: prices } = await supabase
        .from('price_records')
        .select('price')
        .eq('catalog_id', card.catalog_id)
        .order('recorded_at', { ascending: false })
        .limit(30);
      if (prices && prices.length > 0) {
        currentPrice = prices.reduce((s, p) => s + p.price, 0) / prices.length;
      }
    }
    if (currentPrice > 0 && card.cost_price > 0) {
      rankings.push({
        id: card.id,
        name: card.name,
        cost: card.cost_price,
        current: currentPrice,
        change_pct: Math.round(((currentPrice - card.cost_price) / card.cost_price * 100) * 10) / 10,
        quantity: card.quantity,
        image_path: card.image_path,
      });
    }
  }
  rankings.sort((a, b) => b.change_pct - a.change_pct);

  return {
    total_cards: cards.length,
    total_quantity,
    total_cost: Math.round(total_cost * 100) / 100,
    total_value: Math.round(total_value * 100) / 100,
    profit: Math.round(profit * 100) / 100,
    profit_pct: Math.round(profit_pct * 10) / 10,
    valued_cards,
    rarity_distribution,
    set_distribution,
    snapshots: [], // will be fetched separately
    top_gainers: rankings.slice(0, 10),
    top_losers: rankings.slice(-10).reverse(),
  };
}

async function fetchSnapshots(days = 90) {
  const { data, error } = await supabase
    .from('snapshots')
    .select('*')
    .order('snapshot_date', { ascending: true })
    .limit(days);
  if (error) return [];
  return data || [];
}

// ---- Price Records ----

async function fetchPricesByCatalog(catalogId) {
  const { data: history, error } = await supabase
    .from('price_records')
    .select('*')
    .eq('catalog_id', catalogId)
    .order('recorded_at', { ascending: false })
    .limit(60);
  if (error) throw new Error(error.message);

  // Compute stats
  let latest = { avg: null, max: null, min: null, count: 0 };
  if (history && history.length > 0) {
    const prices = history.map(h => h.price);
    latest = {
      avg: Math.round(prices.reduce((s, p) => s + p, 0) / prices.length * 100) / 100,
      max: Math.max(...prices),
      min: Math.min(...prices),
      count: prices.length,
    };
  }

  return { history: history || [], latest };
}

async function fetchPricesByCard(cardId) {
  // First get the card to find catalog_id
  const { data: card } = await supabase
    .from('cards')
    .select('id, catalog_id')
    .eq('id', cardId)
    .single();

  if (card?.catalog_id) {
    return fetchPricesByCatalog(card.catalog_id);
  }

  // Fallback: query by card_id
  const { data: history, error } = await supabase
    .from('price_records')
    .select('*')
    .eq('card_id', cardId)
    .order('recorded_at', { ascending: false })
    .limit(60);
  if (error) return { history: [], latest: { avg: null, max: null, min: null, count: 0 } };

  let latest = { avg: null, max: null, min: null, count: 0 };
  if (history && history.length > 0) {
    const prices = history.map(h => h.price);
    latest = {
      avg: Math.round(prices.reduce((s, p) => s + p, 0) / prices.length * 100) / 100,
      max: Math.max(...prices),
      min: Math.min(...prices),
      count: prices.length,
    };
  }
  return { history: history || [], latest };
}

async function addManualPrice(catalogId, platform, price) {
  const { data, error } = await supabase
    .from('price_records')
    .insert({
      catalog_id: catalogId,
      platform: platform || '手动录入',
      price: parseFloat(price),
      currency: 'CNY',
    })
    .select()
    .single();
  if (error) throw new Error(error.message);
  return data;
}

// ---- Card Catalog ----

async function fetchCatalog({ search = '', page = 1, perPage = 60 } = {}) {
  let query = supabase.from('card_catalog').select('*', { count: 'exact' });

  if (search) {
    const s = search.replace(/'/g, "''");
    query = query.or(`name.ilike.%${s}%,name_en.ilike.%${s}%,card_number.ilike.%${s}%,set_name.ilike.%${s}%`);
  }

  query = query.order('set_name', { ascending: true }).order('card_number', { ascending: true });

  const offset = (page - 1) * perPage;
  query = query.range(offset, offset + perPage - 1);

  const { data, error, count } = await query;
  if (error) throw new Error(error.message);
  return { data: data || [], total: count || 0 };
}

async function fetchCatalogById(id) {
  const { data, error } = await supabase
    .from('card_catalog')
    .select('*')
    .eq('id', id)
    .single();
  if (error) throw new Error(error.message);
  return data;
}

async function fetchCatalogSets() {
  const { data, error } = await supabase
    .from('card_catalog')
    .select('set_name')
    .neq('set_name', '');
  if (error) return [];
  const sets = [...new Set(data.map(r => r.set_name))].sort();
  return sets;
}

// ---- Auth ----

async function authLogin(email, password) {
  const { data, error } = await supabase.auth.signInWithPassword({ email, password });
  if (error) throw new Error(error.message);

  // Fetch profile to get role
  const { data: profile } = await supabase
    .from('profiles')
    .select('role')
    .eq('id', data.user.id)
    .single();

  return { ...data, role: profile?.role || 'user' };
}

async function authRegister(email, password, username) {
  const { data, error } = await supabase.auth.signUp({
    email,
    password,
    options: {
      data: { username, nick_name: username }
    }
  });
  if (error) throw new Error(error.message);
  return data;
}

async function authLogout() {
  await supabase.auth.signOut();
}

// ---- Image upload (Supabase Storage) ----

async function uploadCardImage(file) {
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) throw new Error('未登录');

  const ext = file.name.split('.').pop();
  const fileName = `${user.id}/${Date.now()}.${ext}`;

  const { error } = await supabase.storage
    .from('card-images')
    .upload(fileName, file);

  if (error) throw new Error(error.message);

  const { data: urlData } = supabase.storage
    .from('card-images')
    .getPublicUrl(fileName);

  return urlData.publicUrl;
}
