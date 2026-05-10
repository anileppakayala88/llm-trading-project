// pipeline/webhook/api/webhook.js
// Vercel Serverless Webhook Receiver — LLM Trading Project
//
// Receives alerts from TradingView Pine Script indicators
// Routes to correct module handler
// Triggers Python pipeline (or calls Claude API directly)

import crypto from 'crypto';

const WEBHOOK_SECRET = process.env.WEBHOOK_SECRET;
const VALID_MODULES = ['orb_mmxm', 'pm_sweep_smt', 'scam_range'];

export default async function handler(req, res) {
  // Only accept POST
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  // Verify webhook secret
  const signature = req.headers['x-webhook-secret'];
  if (!signature || signature !== WEBHOOK_SECRET) {
    console.error('Invalid webhook secret');
    return res.status(401).json({ error: 'Unauthorized' });
  }

  let payload;
  try {
    payload = typeof req.body === 'string' ? JSON.parse(req.body) : req.body;
  } catch (err) {
    return res.status(400).json({ error: 'Invalid JSON payload' });
  }

  // Validate required fields
  const { module, event, timestamp, ticker, price } = payload;

  if (!module || !VALID_MODULES.includes(module)) {
    return res.status(400).json({ 
      error: `Invalid module. Must be one of: ${VALID_MODULES.join(', ')}` 
    });
  }

  if (!event || !timestamp || !ticker || price === undefined) {
    return res.status(400).json({ 
      error: 'Missing required fields: event, timestamp, ticker, price' 
    });
  }

  console.log(`[${new Date().toISOString()}] Signal received — Module: ${module}, Event: ${event}, Ticker: ${ticker}, Price: ${price}`);

  // Route to module handler
  try {
    let result;

    switch (module) {
      case 'orb_mmxm':
        result = await handleOrbMmxm(payload);
        break;
      case 'pm_sweep_smt':
        result = await handlePmSweep(payload);
        break;
      case 'scam_range':
        result = await handleScamRange(payload);
        break;
    }

    return res.status(200).json({ 
      success: true, 
      module, 
      event,
      result 
    });

  } catch (err) {
    console.error('Pipeline error:', err);
    return res.status(500).json({ error: 'Pipeline error', details: err.message });
  }
}

// ── Module Handlers ──────────────────────────────────────────────────────────

async function handleOrbMmxm(payload) {
  // Validate module-specific fields
  const required = ['orb_high', 'orb_low', 'orb_range', 'mmxm_model', 'mmxm_phase', 'smt_signal'];
  validateFields(payload, required);

  // Log signal
  await logSignal('orb_mmxm', payload);

  // TODO: Trigger Python pipeline or call Claude API
  // For now: store to GitHub and return
  return { status: 'logged', module: 'orb_mmxm' };
}

async function handlePmSweep(payload) {
  // Validate module-specific fields
  const required = ['pm1_high', 'pm1_low', 'pm2_high', 'pm2_low', 'signal_type'];
  validateFields(payload, required);

  await logSignal('pm_sweep_smt', payload);

  return { status: 'logged', module: 'pm_sweep_smt' };
}

async function handleScamRange(payload) {
  // Validate module-specific fields
  const required = ['zone_top', 'zone_bottom', 'zone_midpoint', 'break_direction'];
  validateFields(payload, required);

  await logSignal('scam_range', payload);

  return { status: 'logged', module: 'scam_range' };
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function validateFields(payload, required) {
  const missing = required.filter(field => payload[field] === undefined);
  if (missing.length > 0) {
    throw new Error(`Missing required fields for ${payload.module}: ${missing.join(', ')}`);
  }
}

async function logSignal(module, payload) {
  // Log to GitHub (same pattern as existing trade log pipeline)
  const GITHUB_TOKEN = process.env.GITHUB_TOKEN;
  const GITHUB_REPO = process.env.GITHUB_REPO;

  if (!GITHUB_TOKEN || !GITHUB_REPO) {
    console.warn('GitHub credentials not set — signal not persisted');
    return;
  }

  const date = new Date().toISOString().split('T')[0];
  const filename = `signals/${module}/${date}_${Date.now()}.json`;
  const content = Buffer.from(JSON.stringify(payload, null, 2)).toString('base64');

  try {
    await fetch(`https://api.github.com/repos/${GITHUB_REPO}/contents/${filename}`, {
      method: 'PUT',
      headers: {
        'Authorization': `token ${GITHUB_TOKEN}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        message: `Signal: ${module} — ${payload.event}`,
        content,
      }),
    });
    console.log(`Signal logged to GitHub: ${filename}`);
  } catch (err) {
    console.error('GitHub log error:', err.message);
  }
}
