"""
Tradovate API Client — Stage 2/3 Execution Layer
LLM Trading Project

Handles authentication and order placement via Tradovate REST API.
Uses demo environment by default — set TRADOVATE_ENV=live for production.

Docs: https://api.tradovate.com/
"""

import os
import json
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

DEMO_URL = "https://demo.tradovateapi.com/v1"
LIVE_URL = "https://live.tradovateapi.com/v1"

ENV          = os.getenv("TRADOVATE_ENV", "demo")
USERNAME     = os.getenv("TRADOVATE_USERNAME", "")
PASSWORD     = os.getenv("TRADOVATE_PASSWORD", "")
APP_ID       = os.getenv("TRADOVATE_APP_ID", "")
APP_VERSION  = os.getenv("TRADOVATE_APP_VERSION", "1.0")
ACCOUNT_ID   = os.getenv("TRADOVATE_ACCOUNT_ID", "")

MNQ_TICK_SIZE   = 0.25    # MNQ minimum price increment
MNQ_TICK_VALUE  = 0.50    # $0.50 per tick ($2/point)


class OrderSide(str, Enum):
    BUY  = "Buy"
    SELL = "Sell"


class OrderStatus(str, Enum):
    PENDING   = "Pending"
    WORKING   = "Working"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"
    REJECTED  = "Rejected"


@dataclass
class OrderResult:
    order_id:   Optional[int]
    status:     str
    fill_price: Optional[float]
    message:    str
    raw:        dict


# ── Client ────────────────────────────────────────────────────────────────────

class TradovateClient:
    def __init__(self, env: str = ENV):
        self.base_url   = LIVE_URL if env == "live" else DEMO_URL
        self.env        = env
        self.token      = None
        self.token_exp  = 0
        self.account_id = int(ACCOUNT_ID) if ACCOUNT_ID else None
        self._session   = requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})

    # ── Auth ──────────────────────────────────────────────────────────────────

    def authenticate(self) -> str:
        """Authenticate and cache the access token."""
        if self.token and time.time() < self.token_exp - 60:
            return self.token

        payload = {
            "name":       USERNAME,
            "password":   PASSWORD,
            "appId":      APP_ID,
            "appVersion": APP_VERSION,
            "deviceId":   "llm-trading-bot",
            "cid":        0,
            "sec":        "",
        }

        r = self._session.post(f"{self.base_url}/auth/accesstokenrequest", json=payload)
        r.raise_for_status()

        data = r.json()
        if "errorText" in data:
            raise RuntimeError(f"Tradovate auth error: {data['errorText']}")

        self.token     = data["accessToken"]
        self.token_exp = time.time() + data.get("expirationTime", 3600)
        self._session.headers.update({"Authorization": f"Bearer {self.token}"})
        log.info(f"Authenticated to Tradovate ({self.env})")
        return self.token

    # ── Account ───────────────────────────────────────────────────────────────

    def get_accounts(self) -> list[dict]:
        r = self._get("/account/list")
        return r

    def get_account_summary(self) -> dict:
        """Return cash balance and today's realized P&L."""
        r = self._get(f"/cashBalance/getcashbalancesnapshot?accountId={self.account_id}")
        return r

    def get_daily_pnl(self) -> float:
        """Return today's realized P&L in USD."""
        try:
            summary = self.get_account_summary()
            return float(summary.get("realizedPnL", 0))
        except Exception as e:
            log.warning(f"Could not fetch daily P&L: {e}")
            return 0.0

    # ── Positions ─────────────────────────────────────────────────────────────

    def get_positions(self) -> list[dict]:
        """Return all open positions for the account."""
        r = self._get(f"/position/list?accountId={self.account_id}")
        return [p for p in r if p.get("netPos", 0) != 0]

    def get_open_position_count(self) -> int:
        return len(self.get_positions())

    # ── Orders ────────────────────────────────────────────────────────────────

    def place_bracket_order(
        self,
        symbol: str,
        side:   OrderSide,
        qty:    int,
        entry:  float,
        stop:   float,
        target: float,
    ) -> OrderResult:
        """
        Place a bracket order (entry + stop-loss + take-profit).

        Args:
            symbol: Contract symbol e.g. "MNQM5" (quarterly front month)
            side:   OrderSide.BUY or OrderSide.SELL
            qty:    Number of contracts (typically 1)
            entry:  Limit entry price
            stop:   Stop-loss price
            target: Take-profit price

        Returns:
            OrderResult with order_id and status
        """
        self.authenticate()

        # Round prices to MNQ tick size
        entry  = self._round_tick(entry)
        stop   = self._round_tick(stop)
        target = self._round_tick(target)

        # Bracket = parent limit + 2 OCA children (stop + target)
        payload = {
            "accountSpec":    USERNAME,
            "accountId":      self.account_id,
            "action":         side.value,
            "symbol":         symbol,
            "orderQty":       qty,
            "orderType":      "Limit",
            "price":          entry,
            "isAutomated":    True,
            "bracket1":       {
                "action":    "Sell" if side == OrderSide.BUY else "Buy",
                "orderType": "Stop",
                "stopPrice": stop,
            },
            "bracket2":       {
                "action":    "Sell" if side == OrderSide.BUY else "Buy",
                "orderType": "Limit",
                "price":     target,
            },
        }

        log.info(f"Placing bracket: {side.value} {qty}x {symbol} @ {entry} | SL:{stop} TP:{target}")

        try:
            r    = self._post("/order/placebracket", payload)
            oid  = r.get("orderId")
            log.info(f"Bracket order placed — ID: {oid}")
            return OrderResult(
                order_id=oid, status=OrderStatus.WORKING,
                fill_price=None, message="Bracket order placed", raw=r
            )
        except Exception as e:
            log.error(f"Order failed: {e}")
            return OrderResult(
                order_id=None, status=OrderStatus.REJECTED,
                fill_price=None, message=str(e), raw={}
            )

    def cancel_order(self, order_id: int) -> dict:
        """Cancel a working order by ID."""
        self.authenticate()
        return self._post("/order/cancelorder", {"orderId": order_id})

    def get_order_status(self, order_id: int) -> dict:
        return self._get(f"/order/item?id={order_id}")

    # ── Kill Switch Integration ───────────────────────────────────────────────

    def check_execution_allowed(self) -> dict:
        """
        Pull live account state and evaluate kill switch conditions.
        Returns dict compatible with kill_switch.KillSwitchResult.
        """
        reasons = []
        try:
            pnl       = self.get_daily_pnl()
            positions = self.get_open_position_count()

            daily_limit = float(os.getenv("MAX_DAILY_LOSS_USD", "-200"))
            max_pos     = int(os.getenv("MAX_OPEN_POSITIONS", "1"))

            if pnl <= daily_limit:
                reasons.append(f"daily_loss_exceeded: ${pnl:.0f} ≤ ${daily_limit:.0f}")
            if positions >= max_pos:
                reasons.append(f"open_position_exists: {positions} open")

        except Exception as e:
            reasons.append(f"account_check_failed: {e}")

        return {"blocked": len(reasons) > 0, "reasons": reasons}

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _round_tick(self, price: float) -> float:
        return round(round(price / MNQ_TICK_SIZE) * MNQ_TICK_SIZE, 2)

    def _get(self, endpoint: str) -> dict | list:
        r = self._session.get(f"{self.base_url}{endpoint}")
        r.raise_for_status()
        return r.json()

    def _post(self, endpoint: str, body: dict) -> dict:
        r = self._session.post(f"{self.base_url}{endpoint}", json=body)
        r.raise_for_status()
        return r.json()


# ── CLI Test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    if not USERNAME or not PASSWORD:
        print("Set TRADOVATE_USERNAME and TRADOVATE_PASSWORD in .env")
    else:
        client = TradovateClient(env="demo")
        client.authenticate()
        print("Auth OK")

        accounts = client.get_accounts()
        print(f"Accounts: {[a.get('name') for a in accounts]}")

        pnl = client.get_daily_pnl()
        print(f"Daily P&L: ${pnl:.2f}")

        positions = client.get_positions()
        print(f"Open positions: {len(positions)}")

        kill = client.check_execution_allowed()
        print(f"Kill switch: {'BLOCKED' if kill['blocked'] else 'CLEAR'}")
        for r in kill["reasons"]:
            print(f"  ✗ {r}")
