// pipeline/webhook/api/webhook.js
// Vercel Serverless Webhook Receiver — LLM Trading Project
//
// Full pipeline: TradingView alert → validate → Claude API → store to GitHub

import Anthropic from '@anthropic-ai/sdk'
import crypto from 'crypto'
import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'
import { dirname } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname  = dirname(__filename)
const ROOT       = path.join(__dirname, '../../..')

const WEBHOOK_SECRET  = process.env.WEBHOOK_SECRET
const GITHUB_TOKEN    = process.env.GITHUB_TOKEN
const GITHUB_REPO     = process.env.GITHUB_REPO
const PIPELINE_MODE   = process.env.PIPELINE_MODE || 'advisory'
const VALID_MODULES   = ['orb_mmxm', 'pm_sweep_smt', 'scam_range']

const MODEL = PIPELINE_MODE === 'conditional_auto' || PIPELINE_MODE === 'semi_auto'
  ? (process.env.CLAUDE_MODEL_LIVE || 'claude-sonnet-4-6')
  : (process.env.CLAUDE_MODEL_DEV  || 'claude-haiku-4-5-20251001')

const anthropic = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY })

// ── Prompt Loading ────────────────────────────────────────────────────────────

const PROMPT_PATHS = {
  orb_mmxm:    'modules/module1_orb_mmxm/prompts/system_prompt.md',
  pm_sweep_smt:'modules/module2_pm_sweep/prompts/system_prompt.md',
  scam_range:  'modules/module3_scam_range/prompts/system_prompt.md',
}

function loadSystemPrompt(module) {
  const claudeMdPath = path.join(ROOT, 'CLAUDE.md')
  const claudeMd     = fs.existsSync(claudeMdPath) ? fs.readFileSync(claudeMdPath, 'utf-8') : ''

  const promptPath   = path.join(ROOT, PROMPT_PATHS[module] || '')
  const modulePrompt = fs.existsSync(promptPath) ? fs.readFileSync(promptPath, 'utf-8') : ''

  return `${claudeMd}\n\n---\n\n## Module-Specific Instructions\n\n${modulePrompt}`
}

function buildUserMessage(module, payload, killSwitch = {}) {
  const blocked = killSwitch.blocked || false
  const reasons = killSwitch.reasons || []
  const now     = new Date().toLocaleString('en-US', { timeZone: 'America/New_York' })

  return `## Today's Live Session Context

Module: ${module}
Date: ${now}
Instrument: ${payload.ticker || 'MNQ1!'}

### Kill Switch Status
Blocked: ${blocked}
Reasons: ${reasons.length ? reasons.join(', ') : 'None — all clear'}

### Live Data
${JSON.stringify(payload, null, 2)}

### Top Analog Days (Historical Similarity)
No analog days available yet — similarity engine requires historical data.

---

Based on the above context, generate a trade plan for this session.
Respond ONLY with a valid JSON object matching the output schema defined in CLAUDE.md.
Include a 'narrative' field with a plain English summary of the plan.
If kill switch is blocked, set confidence to 'no_signal' and explain why in narrative.`
}

// ── Kill Switch (lightweight JS version) ─────────────────────────────────────

function evaluateKillSwitch(payload) {
  const nowET = new Date(new Date().toLocaleString('en-US', { timeZone: 'America/New_York' }))
  const reasons  = []

  const cutoff = new Date(nowET)
  cutoff.setHours(11, 30, 0, 0)
  if (nowET >= cutoff) {
    reasons.push('time_after_1130_ET: ' + nowET.toTimeString().slice(0, 5) + ' ET')
  }

  return { blocked: reasons.length > 0, reasons }
}

// ── Claude API Call ───────────────────────────────────────────────────────────

async function callClaude(module, payload, killSwitch) {
  const systemPrompt = loadSystemPrompt(module)
  const userMessage  = buildUserMessage(module, payload, killSwitch)

  const response = await anthropic.messages.create({
    model:      MODEL,
    max_tokens: 1000,
    system:     systemPrompt,
    messages:   [{ role: 'user', content: userMessage }],
  })

  const rawText = response.content[0].text

  let plan
  try {
    plan = JSON.parse(rawText)
  } catch {
    plan = { narrative: rawText, confidence: 'low', parse_error: true }
  }

  return {
    plan,
    narrative:     plan.narrative || rawText,
    confidence:    plan.confidence || 'low',
    model_used:    MODEL,
    input_tokens:  response.usage.input_tokens,
    output_tokens: response.usage.output_tokens,
  }
}

// ── GitHub Storage ────────────────────────────────────────────────────────────

async function storeToGitHub(module, type, data) {
  if (!GITHUB_TOKEN || !GITHUB_REPO) {
    console.warn('GitHub credentials not set — skipping storage')
    return
  }

  const date     = new Date().toISOString().split('T')[0]
  const ts       = Date.now()
  const filename = `signals/${module}/${type}/${date}_${ts}.json`
  const content  = Buffer.from(JSON.stringify(data, null, 2)).toString('base64')

  try {
    const res = await fetch(`https://api.github.com/repos/${GITHUB_REPO}/contents/${filename}`, {
      method:  'PUT',
      headers: {
        'Authorization': `token ${GITHUB_TOKEN}`,
        'Content-Type':  'application/json',
      },
      body: JSON.stringify({
        message: `${type}: ${module} — ${data.event || 'signal'}`,
        content,
      }),
    })
    if (!res.ok) console.error('GitHub store failed:', res.status, await res.text())
  } catch (err) {
    console.error('GitHub store error:', err.message)
  }
}

// ── Field Validation ──────────────────────────────────────────────────────────

const REQUIRED_FIELDS = {
  orb_mmxm:    ['orb_high', 'orb_low', 'orb_range', 'mmxm_model', 'mmxm_phase', 'smt_signal'],
  pm_sweep_smt:['pm1_high', 'pm1_low', 'pm2_high', 'pm2_low', 'signal_type'],
  scam_range:  ['zone_top', 'zone_bottom', 'zone_midpoint', 'break_direction'],
}

function validatePayload(module, payload) {
  const required = REQUIRED_FIELDS[module] || []
  const missing  = required.filter(f => payload[f] === undefined)
  if (missing.length) throw new Error(`Missing fields for ${module}: ${missing.join(', ')}`)
}

// ── Main Handler ──────────────────────────────────────────────────────────────

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' })
  }

  // Auth
  const sig = req.headers['x-webhook-secret']
  if (!sig || sig !== WEBHOOK_SECRET) {
    console.error('Invalid webhook secret')
    return res.status(401).json({ error: 'Unauthorized' })
  }

  // Parse
  let payload
  try {
    payload = typeof req.body === 'string' ? JSON.parse(req.body) : req.body
  } catch {
    return res.status(400).json({ error: 'Invalid JSON payload' })
  }

  const { module, event, timestamp, ticker, price } = payload

  // Validate module
  if (!module || !VALID_MODULES.includes(module)) {
    return res.status(400).json({ error: `Invalid module. Must be one of: ${VALID_MODULES.join(', ')}` })
  }
  if (!event || !timestamp || !ticker || price === undefined) {
    return res.status(400).json({ error: 'Missing required fields: event, timestamp, ticker, price' })
  }

  // Validate module-specific fields
  try {
    validatePayload(module, payload)
  } catch (err) {
    return res.status(400).json({ error: err.message })
  }

  console.log(`[${new Date().toISOString()}] Signal — ${module} | ${event} | ${ticker} @ ${price}`)

  try {
    // Kill switch
    const killSwitch = evaluateKillSwitch(payload)

    // Store raw signal
    await storeToGitHub(module, 'raw', { ...payload, kill_switch: killSwitch })

    // Call Claude
    const llmResult = await callClaude(module, payload, killSwitch)

    // Store plan
    const planRecord = {
      module,
      event,
      timestamp,
      ticker,
      price,
      kill_switch:   killSwitch,
      plan:          llmResult.plan,
      confidence:    llmResult.confidence,
      narrative:     llmResult.narrative,
      model_used:    llmResult.model_used,
      input_tokens:  llmResult.input_tokens,
      output_tokens: llmResult.output_tokens,
      pipeline_mode: PIPELINE_MODE,
    }
    await storeToGitHub(module, 'plans', planRecord)

    console.log(`[${module}] Confidence: ${llmResult.confidence} | Tokens: ${llmResult.input_tokens}in/${llmResult.output_tokens}out`)

    return res.status(200).json({
      success:    true,
      module,
      event,
      confidence: llmResult.confidence,
      narrative:  llmResult.narrative,
      plan:       llmResult.plan,
      model_used: llmResult.model_used,
      kill_switch: killSwitch,
    })

  } catch (err) {
    console.error('Pipeline error:', err)
    return res.status(500).json({ error: 'Pipeline error', details: err.message })
  }
}
