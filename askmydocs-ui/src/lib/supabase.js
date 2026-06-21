/**
 * Supabase client with in-memory session storage.
 *
 * WHY: The default @supabase/supabase-js client stores the JWT in localStorage
 * (key: sb-<project>-auth-token), making it readable via window.localStorage
 * and vulnerable to XSS. This module replaces that with a plain Map so the
 * token never touches any browser storage API.
 *
 * After every login the token is "promoted" to an httpOnly, Secure,
 * SameSite=Lax cookie by calling /api/auth/session on the FastAPI backend.
 * That cookie is the canonical session credential for API requests.
 *
 * HOW TO VERIFY IN DEVTOOLS:
 *   Application → Local Storage → (your origin) — should be empty / no sb-* key
 *   Application → Cookies → (your origin) — sb-session present, HttpOnly ✓
 */

import { createClient } from '@supabase/supabase-js'

const SUPABASE_URL  = import.meta.env.VITE_SUPABASE_URL
const SUPABASE_ANON = import.meta.env.VITE_SUPABASE_ANON_KEY
const API           = import.meta.env.VITE_API_URL || ''

// ── Memory-only storage adapter ───────────────────────────────────────────────
const _mem = new Map()
const memoryStorage = {
  getItem:    (key) => _mem.get(key) ?? null,
  setItem:    (key, val) => { _mem.set(key, val) },
  removeItem: (key) => { _mem.delete(key) },
}

// ── Supabase client ───────────────────────────────────────────────────────────
export const supabase = (SUPABASE_URL && SUPABASE_ANON)
  ? createClient(SUPABASE_URL, SUPABASE_ANON, {
      auth: {
        storage:          memoryStorage,  // never touches localStorage
        persistSession:   true,
        autoRefreshToken: true,
        detectSessionInUrl: true,
      },
    })
  : null


/**
 * After a successful Supabase login, call this to promote the token to an
 * httpOnly cookie on the FastAPI backend.
 * The frontend itself never reads the cookie (httpOnly blocks JS access).
 */
export async function setServerSession(session) {
  if (!session?.access_token) return
  try {
    await fetch(`${API}/api/auth/session`, {
      method:      'POST',
      credentials: 'include',                    // send/receive cookies
      headers:     { 'Content-Type': 'application/json' },
      body:        JSON.stringify({
        access_token:  session.access_token,
        refresh_token: session.refresh_token ?? '',
      }),
    })
  } catch (e) {
    console.warn('setServerSession failed:', e)
  }
}

/**
 * Clear the httpOnly cookie on the backend and sign out locally.
 */
export async function clearServerSession() {
  try {
    await fetch(`${API}/api/auth/logout`, { method: 'POST', credentials: 'include' })
  } catch {}
  await supabase?.auth.signOut()
}
