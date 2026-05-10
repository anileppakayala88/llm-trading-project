"""
Telegram Bot — Stage 2 Semi-Automated Execution
LLM Trading Project

Receives trade plans from the LLM layer, formats and sends them via Telegram,
and handles Approve/Reject responses to trigger Tradovate execution.

Setup:
    1. Create a bot via @BotFather on Telegram
    2. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env
    3. Run: python bot.py

Usage (from pipeline):
    from pipeline.telegram.bot import send_trade_plan
    await send_trade_plan(plan_dict)
"""

import asyncio
import json
import logging
import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import (
        Application, CallbackQueryHandler, CommandHandler, ContextTypes
    )
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    print("python-telegram-bot not installed. Run: pip install python-telegram-bot")

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# ── Message Formatting ────────────────────────────────────────────────────────

CONFIDENCE_EMOJI = {
    "high":      "🟢",
    "medium":    "🟡",
    "low":       "🔴",
    "no_signal": "⛔",
}

MODULE_LABELS = {
    "orb_mmxm":    "M1 — ORB+MMXM",
    "pm_sweep_smt":"M2 — PM Sweep+SMT",
    "scam_range":  "M3 — SCAM Range",
}


def format_plan_message(plan: dict, module: str, kill_switch: dict) -> str:
    conf    = plan.get("confidence", "no_signal")
    emoji   = CONFIDENCE_EMOJI.get(conf, "⚪")
    label   = MODULE_LABELS.get(module, module)
    blocked = kill_switch.get("blocked", False)

    if blocked:
        reasons = "\n".join(f"  ✗ {r}" for r in kill_switch.get("reasons", []))
        return (
            f"⛔ *{label}*\n"
            f"Kill switch active:\n{reasons}\n\n"
            f"_{plan.get('narrative', 'No trade.')}_"
        )

    entry  = plan.get("entry_price")
    stop   = plan.get("stop_price")
    target = plan.get("target_price")
    rr     = plan.get("risk_reward")

    levels = ""
    if entry and stop and target:
        levels = (
            f"\n\n📍 *Entry:* `{entry}`"
            f"\n🛑 *Stop:*  `{stop}`"
            f"\n🎯 *Target:* `{target}`"
        )
        if rr:
            levels += f"\n📊 *R/R:* {rr}:1"

    window = plan.get("entry_window", "")
    win_str = f"\n⏱ *Window:* {window}" if window else ""

    return (
        f"{emoji} *{label}*\n"
        f"Confidence: *{conf.upper()}*{win_str}"
        f"{levels}\n\n"
        f"_{plan.get('narrative', '')}_"
    )


# ── Plan Delivery ─────────────────────────────────────────────────────────────

async def send_trade_plan(
    plan:        dict,
    module:      str,
    kill_switch: Optional[dict] = None,
    raw_payload: Optional[dict] = None,
) -> Optional[int]:
    """
    Send a formatted trade plan to Telegram with Approve/Reject buttons.

    Returns the message_id for later reference, or None if no token configured.
    """
    if not TELEGRAM_AVAILABLE or not BOT_TOKEN or not CHAT_ID:
        log.warning("Telegram not configured — plan not sent")
        _print_plan_fallback(plan, module, kill_switch or {})
        return None

    from telegram import Bot
    bot  = Bot(token=BOT_TOKEN)
    text = format_plan_message(plan, module, kill_switch or {})

    conf    = plan.get("confidence", "no_signal")
    blocked = (kill_switch or {}).get("blocked", False)

    # Only show Approve button for medium+ confidence, not blocked
    if conf in ("high", "medium") and not blocked:
        payload_json = json.dumps({
            "module":  module,
            "plan":    plan,
            "payload": raw_payload or {},
        })
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Approve",  callback_data=f"approve|{module}"),
            InlineKeyboardButton("❌ Reject",   callback_data=f"reject|{module}"),
        ]])
    else:
        keyboard = None

    msg = await bot.send_message(
        chat_id=CHAT_ID,
        text=text,
        parse_mode="Markdown",
        reply_markup=keyboard,
    )
    log.info(f"Plan sent: {module} | {conf} | msg_id={msg.message_id}")
    return msg.message_id


def _print_plan_fallback(plan: dict, module: str, kill_switch: dict):
    """Console fallback when Telegram is not configured."""
    print(f"\n{'='*60}")
    print(f"TRADE PLAN — {MODULE_LABELS.get(module, module)}")
    print(f"Confidence: {plan.get('confidence', 'unknown').upper()}")
    print(f"Kill Switch: {'BLOCKED' if kill_switch.get('blocked') else 'CLEAR'}")
    if plan.get("entry_price"):
        print(f"Entry:  {plan['entry_price']} | Stop: {plan.get('stop_price')} | Target: {plan.get('target_price')}")
    print(f"Narrative: {plan.get('narrative', '')}")
    print('='*60)


# ── Callback Handlers ─────────────────────────────────────────────────────────

async def on_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User tapped Approve — route to Tradovate for execution."""
    query  = update.callback_query
    await query.answer()

    parts  = query.data.split("|")
    module = parts[1] if len(parts) > 1 else "unknown"

    await query.edit_message_text(
        text=query.message.text + "\n\n⏳ *Sending order to Tradovate...*",
        parse_mode="Markdown",
    )

    try:
        from pipeline.execution.tradovate_client import TradovateClient, OrderSide
        # Extract plan from context (stored in bot_data by send_trade_plan)
        plan = context.bot_data.get(f"pending_plan_{module}", {})

        client = TradovateClient()
        client.authenticate()

        side = OrderSide.BUY if plan.get("orb_break_side") == "bull" else OrderSide.SELL
        result = client.place_bracket_order(
            symbol=  "MNQM5",   # current front month — update each quarter
            side=    side,
            qty=     1,
            entry=   plan.get("entry_price"),
            stop=    plan.get("stop_price"),
            target=  plan.get("target_price"),
        )
        await query.edit_message_text(
            text=query.message.text.replace("⏳ *Sending order...*", "") +
                 f"\n\n✅ *Order placed* — ID: {result.get('orderId', 'unknown')}",
            parse_mode="Markdown",
        )
        log.info(f"Order placed: {result}")

    except Exception as e:
        log.error(f"Order error: {e}")
        await query.edit_message_text(
            text=query.message.text + f"\n\n❌ *Order failed:* {e}",
            parse_mode="Markdown",
        )


async def on_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User tapped Reject — log and dismiss."""
    query  = update.callback_query
    await query.answer("Signal rejected.")
    parts  = query.data.split("|")
    module = parts[1] if len(parts) > 1 else "unknown"

    await query.edit_message_text(
        text=query.message.text + "\n\n❌ *Rejected by trader.*",
        parse_mode="Markdown",
    )
    log.info(f"Signal rejected: {module}")


async def on_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Respond to /status command with pipeline state."""
    await update.message.reply_text(
        f"🤖 *LLM Trading Bot*\n"
        f"Mode: `{os.getenv('PIPELINE_MODE', 'advisory')}`\n"
        f"Model: `{os.getenv('CLAUDE_MODEL_DEV', 'claude-haiku-4-5')}`\n"
        f"Status: Running",
        parse_mode="Markdown",
    )


# ── Bot Runner ────────────────────────────────────────────────────────────────

def run_bot():
    """Start the bot in polling mode (for development/advisory stage)."""
    if not TELEGRAM_AVAILABLE:
        print("Install python-telegram-bot: pip install python-telegram-bot")
        return
    if not BOT_TOKEN:
        print("Set TELEGRAM_BOT_TOKEN in .env")
        return

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("status", on_status))
    app.add_handler(CallbackQueryHandler(on_approve, pattern="^approve\\|"))
    app.add_handler(CallbackQueryHandler(on_reject,  pattern="^reject\\|"))

    log.info("Telegram bot started — polling for updates")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    run_bot()
