"""Master Bias Engine: scores -100 (strongly bearish) to +100 (strongly bullish)."""
from typing import Optional


def _clamp(val: float, lo: float = -100, hi: float = 100) -> float:
    return max(lo, min(hi, val))


class BiasEngine:
    def calculate(self, market_data: dict) -> dict:
        """
        market_data keys expected:
          qqq_price, qqq_change_pct, vwap, wave (dict), leadership (list),
          call_wall, put_wall, net_gex, unusual_count (int), news_sentiment (str)
        """
        components = {}

        # 1. VWAP position (-20 to +20)
        price = market_data.get("qqq_price")
        vwap = market_data.get("vwap")
        if price and vwap and vwap > 0:
            pct_from_vwap = (price - vwap) / vwap * 100
            components["vwap"] = _clamp(pct_from_vwap * 8, -20, 20)
        else:
            components["vwap"] = 0

        # 2. Net WAVE (-20 to +20)
        wave = market_data.get("wave") or {}
        net_wave = wave.get("net_wave") or 0
        total_prem = wave.get("total_premium") or 1
        wave_ratio = net_wave / total_prem if total_prem > 0 else 0
        components["wave"] = _clamp(wave_ratio * 40, -20, 20)

        # 3. Leadership breadth (-15 to +15)
        leadership = market_data.get("leadership") or []
        if leadership:
            weighted_score = 0.0
            total_weight = 0.0
            for stock in leadership:
                chg = stock.get("change_pct") or 0
                wt = stock.get("nasdaq_weight", 0.01)
                weighted_score += chg * wt
                total_weight += wt
            avg_weighted_chg = weighted_score / total_weight if total_weight else 0
            components["leadership"] = _clamp(avg_weighted_chg * 6, -15, 15)
        else:
            components["leadership"] = 0

        # 4. Price momentum (-20 to +20)
        chg_pct = market_data.get("qqq_change_pct") or 0
        components["momentum"] = _clamp(chg_pct * 4, -20, 20)

        # 5. Near call/put wall (-5 to +5)
        call_wall = market_data.get("call_wall")
        put_wall = market_data.get("put_wall")
        if price and call_wall and put_wall:
            dist_call = (call_wall - price) / price * 100
            dist_put = (price - put_wall) / price * 100
            if dist_call < 0.3:
                components["gamma_walls"] = -5  # approaching resistance
            elif dist_put < 0.3:
                components["gamma_walls"] = 5   # near support
            else:
                components["gamma_walls"] = 0
        else:
            components["gamma_walls"] = 0

        raw_score = sum(components.values())
        score = int(_clamp(raw_score))

        # Confidence: based on alignment of components
        vals = list(components.values())
        same_sign = sum(1 for v in vals if v * score > 0)
        confidence = int(60 + (same_sign / len(vals)) * 40) if vals else 60
        confidence = min(100, confidence)

        label = self._score_to_label(score)
        confidence_label = "High" if confidence >= 75 else ("Medium" if confidence >= 50 else "Low")

        bullish_reasons, bearish_reasons = self._build_reasons(components, market_data)
        checklist = self._build_checklist(components, market_data)
        trade_plan = self._build_trade_plan(score, market_data, bullish_reasons)
        regime = self._detect_regime(score, confidence, wave, market_data)
        no_trade = abs(score) < 20 or (confidence < 45 and abs(score) < 35)
        no_trade_reason = self._no_trade_reason(score, confidence, components) if no_trade else None

        return {
            "score": score,
            "label": label,
            "confidence": confidence,
            "confidence_label": confidence_label,
            "components": components,
            "reasons_bullish": bullish_reasons,
            "reasons_bearish": bearish_reasons,
            "checklist": checklist,
            "trade_plan": trade_plan,
            "regime": regime,
            "no_trade_warning": no_trade,
            "no_trade_reason": no_trade_reason,
        }

    def _score_to_label(self, score: int) -> str:
        if score >= 60:
            return "Strongly Bullish"
        if score >= 25:
            return "Bullish Lean"
        if score <= -60:
            return "Strongly Bearish"
        if score <= -25:
            return "Bearish Lean"
        if abs(score) < 20:
            return "Chop / No Trade"
        return "Neutral"

    def _build_reasons(self, components: dict, data: dict):
        bull, bear = [], []
        if components.get("vwap", 0) > 5:
            bull.append("QQQ is above VWAP")
        elif components.get("vwap", 0) < -5:
            bear.append("QQQ is below VWAP")
        if components.get("wave", 0) > 5:
            bull.append("Net options WAVE is positive (call premium dominant)")
        elif components.get("wave", 0) < -5:
            bear.append("Net options WAVE is negative (put premium dominant)")
        leadership = data.get("leadership") or []
        green_count = sum(1 for s in leadership if s.get("bullish"))
        total = len(leadership)
        if total > 0:
            if green_count >= total * 0.7:
                bull.append(f"Leadership basket strong: {green_count}/{total} green")
            elif green_count <= total * 0.3:
                bear.append(f"Leadership basket weak: {green_count}/{total} green")
        if components.get("momentum", 0) > 5:
            bull.append(f"QQQ price momentum positive ({data.get('qqq_change_pct', 0):+.2f}%)")
        elif components.get("momentum", 0) < -5:
            bear.append(f"QQQ price momentum negative ({data.get('qqq_change_pct', 0):+.2f}%)")
        if components.get("gamma_walls", 0) < 0:
            bear.append("QQQ approaching call wall — upside may slow")
        elif components.get("gamma_walls", 0) > 0:
            bull.append("QQQ near put wall support")
        return bull, bear

    def _build_checklist(self, components: dict, data: dict) -> list:
        vwap = data.get("vwap")
        price = data.get("qqq_price")
        wave = data.get("wave") or {}
        leadership = data.get("leadership") or []
        green_count = sum(1 for s in leadership if s.get("bullish"))

        return [
            {"label": "QQQ above VWAP", "value": bool(price and vwap and price > vwap)},
            {"label": "Net WAVE positive", "value": (wave.get("net_wave") or 0) > 0},
            {"label": "Call premium dominant", "value": (wave.get("call_dominance_pct") or 50) > 55},
            {"label": "Leadership majority green", "value": green_count > len(leadership) // 2 if leadership else False},
            {"label": "Price momentum positive", "value": (data.get("qqq_change_pct") or 0) > 0},
            {"label": "Below call wall", "value": bool(data.get("call_wall") and price and price < data["call_wall"])},
            {"label": "Above put wall", "value": bool(data.get("put_wall") and price and price > data["put_wall"])},
        ]

    def _build_trade_plan(self, score: int, data: dict, bull_reasons: list) -> dict:
        price = data.get("qqq_price", 450)
        vwap = data.get("vwap", price)
        call_wall = data.get("call_wall")
        put_wall = data.get("put_wall")

        if score >= 25:
            return {
                "primary": "Long Pullback / Reclaim",
                "long_setup": f"Wait for MNQ to pull back to VWAP (~{vwap:.2f}) or prior structure and hold. Enter on confirmation.",
                "short_setup": "Short only on clear VWAP failure + put WAVE expansion. Otherwise avoid.",
                "invalidation": f"Bullish thesis fails if QQQ loses VWAP ({vwap:.2f}) and put WAVE expands.",
                "avoid": f"Avoid chasing directly into the call wall{f' (~{call_wall:.0f})' if call_wall else ''}.",
                "key_levels": [f"VWAP: {vwap:.2f}"] + ([f"Call wall: {call_wall:.0f}"] if call_wall else []) + ([f"Put wall: {put_wall:.0f}"] if put_wall else []),
            }
        elif score <= -25:
            return {
                "primary": "Short Failed Reclaims",
                "long_setup": "Long only on QQQ VWAP reclaim with volume + call WAVE turning positive.",
                "short_setup": f"Enter short when QQQ fails VWAP retests ({vwap:.2f}). Target put wall or prior structure.",
                "invalidation": f"Bearish thesis fails if QQQ reclaims VWAP ({vwap:.2f}) and call WAVE expands.",
                "avoid": "Avoid shorting directly into the put wall support.",
                "key_levels": [f"VWAP: {vwap:.2f}"] + ([f"Put wall: {put_wall:.0f}"] if put_wall else []) + ([f"Call wall: {call_wall:.0f}"] if call_wall else []),
            }
        else:
            return {
                "primary": "Wait for Clarity",
                "long_setup": "Long only if QQQ reclaims VWAP with call WAVE and leadership confirming.",
                "short_setup": "Short only if QQQ loses VWAP with put WAVE expanding and leadership red.",
                "invalidation": "N/A — no directional bias established yet.",
                "avoid": "Avoid forcing trades in choppy, low-conviction conditions.",
                "key_levels": [f"VWAP: {vwap:.2f}"] + ([f"Call wall: {call_wall:.0f}"] if call_wall else []) + ([f"Put wall: {put_wall:.0f}"] if put_wall else []),
            }

    def _detect_regime(self, score: int, confidence: int, wave: dict, data: dict) -> str:
        if abs(score) >= 60 and confidence >= 70:
            return "Trend Up" if score > 0 else "Trend Down"
        if abs(score) < 20:
            return "Chop"
        if abs(score) >= 35 and confidence >= 60:
            return "Breakout Watch" if score > 0 else "Reversal Watch"
        return "Range"

    def _no_trade_reason(self, score: int, confidence: int, components: dict) -> Optional[str]:
        if abs(score) < 20:
            return "Mixed signals — WAVE, VWAP, and leadership are not aligned. Wait for clearer setup."
        if confidence < 45:
            return "Low confidence — conflicting signals present. Reduce size or wait."
        return "Conditions not ideal for high-quality trade entry."
