// LLM Trading Dashboard — app.js
// Fetches signal and plan data from the GitHub repo and renders the dashboard.

const GITHUB_REPO   = 'anileppakayala88/llm-trading-project'  // update if repo changes
const GITHUB_API    = `https://api.github.com/repos/${GITHUB_REPO}/contents`
const SIGNALS_PATH  = 'signals'
const REFRESH_MS    = 60_000   // refresh every 60 seconds

const MODULE_MAP = {
  orb_mmxm:     { id: 'm1', label: 'M1' },
  pm_sweep_smt: { id: 'm2', label: 'M2' },
  scam_range:   { id: 'm3', label: 'M3' },
}

// ── Session Timeline ──────────────────────────────────────────────────────────

const TIMELINE = [
  { id: 'tl-pm1',     start: 7*60,      end: 8*60+30 },
  { id: 'tl-pm2',     start: 8*60+30,   end: 9*60+30 },
  { id: 'tl-orb',     start: 9*60+30,   end: 10*60 },
  { id: 'tl-primary', start: 10*60,     end: 11*60+30 },
  { id: 'tl-cutoff',  start: 11*60+30,  end: 12*60 },
]

const TRADE_START = 7 * 60   // 07:00 ET
const TRADE_END   = 12 * 60  // 12:00 ET (display end)

function getETMinutes() {
  const now = new Date()
  const et  = new Date(now.toLocaleString('en-US', { timeZone: 'America/New_York' }))
  return et.getHours() * 60 + et.getMinutes()
}

function getETTime() {
  return new Date().toLocaleTimeString('en-US', {
    timeZone: 'America/New_York',
    hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false
  })
}

function getETDate() {
  return new Date().toLocaleDateString('en-US', {
    timeZone: 'America/New_York',
    weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'
  })
}

function getETDateKey() {
  return new Date().toLocaleDateString('en-CA', { timeZone: 'America/New_York' })
}

function updateTimeline() {
  const mins = getETMinutes()
  const pct  = Math.min(100, Math.max(0, (mins - TRADE_START) / (TRADE_END - TRADE_START) * 100))

  document.getElementById('tl-now').style.left = pct + '%'
  document.getElementById('session-timer').textContent = getETTime() + ' ET'
  document.getElementById('session-date').textContent  = getETDate()

  TIMELINE.forEach(({ id, start, end }) => {
    const el = document.getElementById(id)
    if (!el) return
    el.classList.toggle('active', mins >= start && mins < end)
  })

  // Kill switch: after 11:30
  const ks = document.getElementById('kill-switch')
  if (mins >= 11 * 60 + 30) {
    ks.textContent = 'Kill Switch: AFTER CUTOFF'
    ks.className   = 'badge badge-block'
  } else {
    ks.textContent = 'Kill Switch: CLEAR'
    ks.className   = 'badge badge-green'
  }
}

// ── GitHub Fetching ───────────────────────────────────────────────────────────

async function fetchJSON(url) {
  const r = await fetch(url, { headers: { Accept: 'application/vnd.github+json' } })
  if (!r.ok) return null
  return r.json()
}

async function fetchTodayPlans() {
  const today   = getETDateKey()
  const plans   = {}

  for (const module of Object.keys(MODULE_MAP)) {
    const dir = await fetchJSON(`${GITHUB_API}/${SIGNALS_PATH}/${module}/plans`)
    if (!Array.isArray(dir)) continue

    // Find today's plan files, take the most recent
    const todayFiles = dir
      .filter(f => f.name.startsWith(today) && f.name.endsWith('.json'))
      .sort((a, b) => b.name.localeCompare(a.name))

    if (todayFiles.length === 0) continue

    // Fetch the latest plan file
    const fileData = await fetchJSON(todayFiles[0].download_url)
    if (fileData) plans[module] = fileData
  }

  return plans
}

// ── Panel Rendering ───────────────────────────────────────────────────────────

const CONF_CLASS = {
  high:      'signal-high',
  medium:    'signal-medium',
  low:       'signal-low',
  no_signal: '',
}

const CONF_BADGE = {
  high:      ['HIGH',      'badge-green'],
  medium:    ['MEDIUM',    'badge-yellow'],
  low:       ['LOW',       'badge-red'],
  no_signal: ['NO SIGNAL', 'badge-gray'],
}

function renderLevels(plan, moduleId) {
  const el = document.getElementById(`levels-${moduleId}`)
  if (!el) return

  const items = []
  if (plan.entry_price)  items.push({ cls: 'entry',  lbl: 'Entry',  val: plan.entry_price })
  if (plan.stop_price)   items.push({ cls: 'stop',   lbl: 'Stop',   val: plan.stop_price })
  if (plan.target_price) items.push({ cls: 'target', lbl: 'Target', val: plan.target_price })
  if (plan.risk_reward)  items.push({ cls: 'rr',     lbl: 'R/R',    val: plan.risk_reward + ':1' })

  el.innerHTML = items.map(({ cls, lbl, val }) =>
    `<div class="level-item ${cls}"><span class="lbl">${lbl}</span>${val}</div>`
  ).join('')
}

function renderPanel(module, planRecord) {
  const meta  = MODULE_MAP[module]
  if (!meta) return

  const { id }     = meta
  const plan       = planRecord.plan || {}
  const conf       = plan.confidence || 'no_signal'
  const narrative  = plan.narrative  || ''
  const timestamp  = planRecord.timestamp || ''
  const signalType = plan.signal_type || plan.mmxm_phase || plan.break_direction || ''
  const modelUsed  = planRecord.model_used || ''

  // Panel border
  const panel = document.getElementById(`panel-${id}`)
  if (panel) {
    panel.className = `panel ${CONF_CLASS[conf] || ''}`
  }

  // Confidence badge
  const confEl = document.getElementById(`conf-${id}`)
  if (confEl) {
    const [label, cls] = CONF_BADGE[conf] || ['—', 'badge-gray']
    confEl.textContent = label
    confEl.className   = `confidence-badge badge ${cls}`
  }

  // Meta
  const metaEl = document.getElementById(`meta-${id}`)
  if (metaEl) {
    const parts = []
    if (timestamp) parts.push(timestamp.slice(11, 16) + ' ET')
    if (signalType) parts.push(signalType.replace(/_/g, ' '))
    if (modelUsed) parts.push(modelUsed)
    metaEl.textContent = parts.join(' · ') || 'Signal received'
  }

  // Levels
  renderLevels(plan, id)

  // Narrative
  const narEl = document.getElementById(`narrative-${id}`)
  if (narEl) narEl.textContent = narrative || 'No narrative provided.'

  // Analogs (placeholder — populated when similarity engine has data)
  const analogEl = document.getElementById(`analogs-${id}`)
  if (analogEl) analogEl.innerHTML = ''
}

// ── Signal Log ────────────────────────────────────────────────────────────────

function renderLogRow(module, planRecord) {
  const plan   = planRecord.plan || {}
  const conf   = plan.confidence || '—'
  const ccls   = `conf-${conf === 'no_signal' ? 'none' : conf}`
  const time   = (planRecord.timestamp || '').slice(11, 16)
  const label  = MODULE_MAP[module]?.label || module
  const signal = plan.signal_type || plan.mmxm_phase || plan.orb_break_side || '—'
  const rr     = plan.risk_reward ? plan.risk_reward + ':1' : '—'

  return `<tr>
    <td>${time}</td>
    <td>${label}</td>
    <td>${signal.replace(/_/g, ' ')}</td>
    <td class="${ccls}">${conf.toUpperCase()}</td>
    <td>${plan.entry_price  || '—'}</td>
    <td>${plan.stop_price   || '—'}</td>
    <td>${plan.target_price || '—'}</td>
    <td>${rr}</td>
  </tr>`
}

function renderLog(plans) {
  const tbody = document.getElementById('log-body')
  if (!tbody) return

  const entries = Object.entries(plans)
  if (entries.length === 0) {
    tbody.innerHTML = '<tr><td colspan="8" class="empty-row">No signals today.</td></tr>'
    return
  }

  tbody.innerHTML = entries
    .map(([module, record]) => renderLogRow(module, record))
    .join('')
}

// ── Main Refresh Loop ─────────────────────────────────────────────────────────

async function refresh() {
  document.getElementById('last-refresh').textContent =
    'Refreshing... ' + new Date().toLocaleTimeString()

  try {
    const plans = await fetchTodayPlans()

    // Update panels
    Object.entries(plans).forEach(([module, record]) => renderPanel(module, record))

    // Update log
    renderLog(plans)

    document.getElementById('last-refresh').textContent =
      'Updated ' + new Date().toLocaleTimeString()

  } catch (err) {
    console.error('Refresh error:', err)
    document.getElementById('last-refresh').textContent = 'Refresh failed — ' + err.message
  }
}

// ── Init ──────────────────────────────────────────────────────────────────────

updateTimeline()
setInterval(updateTimeline, 1000)

refresh()
setInterval(refresh, REFRESH_MS)
