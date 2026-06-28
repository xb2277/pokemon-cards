// ============================================================
// Supabase Client Configuration
// ============================================================
const SUPABASE_URL = 'https://hlmhvuszhugpsvjolgjr.supabase.co';
const SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImhsbWh2dXN6aHVncHN2am9sZ2pyIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODI1NjAxMjUsImV4cCI6MjA5ODEzNjEyNX0.w9j6uYE5ZgK71oYQK9VWXiCX8uLUnR97T2cA5E4N2uY';

// Initialize Supabase client
const supabase = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
    detectSessionInUrl: true
  }
});
