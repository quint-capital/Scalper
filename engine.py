import os
from structure import summarize, atr, _pivots

WEIGHTS={'H4':28,'H1':23,'M30':17,'M15':15,'M5':10,'M1':7}
MIN={'H4':20,'H1':30,'M30':40,'M15':50,'M5':100,'M1':200}


def _directional_evidence(r, direction):
    score=0.0; reasons=[]; conflicts=[]
    for tf,w in WEIGHTS.items():
        tr=r[tf]['trend']
        if tr==direction: score += w
        elif tr not in ('NEUTRAL','INSUFFICIENT') and tr!=direction:
            conflicts.append(tf+' trend conflict')
    for tf in ('H1','M30','M15','M5','M1'):
        x=r[tf]
        if x['momentum']==direction: score += 2; reasons.append(tf+' momentum')
        if x['displacement']==direction: score += 4; reasons.append(tf+' displacement')
        if x['mss']==direction: score += 7; reasons.append(tf+' MSS')
        if x['bos']==direction: score += 4; reasons.append(tf+' BOS')
        wanted='SELL_SIDE_SWEPT' if direction=='BULLISH' else 'BUY_SIDE_SWEPT'
        opposite='BUY_SIDE_SWEPT' if direction=='BULLISH' else 'SELL_SIDE_SWEPT'
        if x['liquidity']==wanted: score += 6; reasons.append(tf+' favorable liquidity sweep')
        elif x['liquidity']==opposite: score -= 8; conflicts.append(tf+' adverse liquidity sweep')
        if x['fvg']==direction: score += 2; reasons.append(tf+' FVG')
    aligned=sum(1 for tf in WEIGHTS if r[tf]['trend']==direction)
    if aligned>=5: score += 4
    if aligned==6: score += 2
    return score,reasons,conflicts


def _nearest_pivot(c, direction, entry):
    """Return the nearest confirmed pivot on the opposing side of entry."""
    if len(c) < 8:
        return None
    highs, lows = _pivots(c, 2, 2)
    if direction == 'BULLISH':
        vals = [v for _, v in highs if v > entry]
        return min(vals) if vals else None
    vals = [v for _, v in lows if v < entry]
    return max(vals) if vals else None


def _setup(frames, direction, r):
    """Build a V75 entry using local invalidation + realistic target geometry.

    v3.2 deliberately removes the old 29-candle M15 stop. The trigger is
    generated from M15/M5/M1 structure, so the invalidation is now anchored to
    the recent M1/M5 structure instead of a multi-hour extreme.
    """
    m1 = frames.get('M1', [])
    m5 = frames.get('M5', [])
    if len(m1) < 30 or len(m5) < 12 or direction not in ('BULLISH', 'BEARISH'):
        return None

    a1 = atr(m1, 14)
    a5 = atr(m5, 14)
    a15 = atr(frames.get('M15', []), 14) if len(frames.get('M15', [])) >= 15 else None
    if not a1 or not a5:
        return None

    entry = float(m1[-1]['close'])

    # Local invalidation candidates. M1 gives precise trigger invalidation;
    # M5 protects against an unrealistically tight M1 stop.
    h1, l1 = _pivots(m1[-30:], 2, 2)
    h5, l5 = _pivots(m5[-12:], 2, 2)

    if direction == 'BULLISH':
        m1_levels = [v for _, v in l1 if v < entry]
        m5_levels = [v for _, v in l5 if v < entry]
        m1_stop = (max(m1_levels) - 0.20 * a1) if m1_levels else (min(z['low'] for z in m1[-8:]) - 0.20 * a1)
        m5_stop = (max(m5_levels) - 0.15 * a5) if m5_levels else (min(z['low'] for z in m5[-6:]) - 0.15 * a5)
        sl = min(m1_stop, m5_stop)  # conservative: stop below both structural invalidation candidates
        min_risk = max(0.75 * a1, 0.20 * a5)
        # Risk-width rejection is disabled: preserve the structural stop even
        # when it is wider than the former adaptive cap. The cap is retained
        # below only as a diagnostic/reference value, not as a rejection rule.
        strength = max(float(r.get('structure_score', 0)), float(r.get('trigger_score', 0)),
                       float(r.get('continuation_score', 0)), float(r.get('transition_score', 0)))
        strong = strength >= 80
        max_risk = min((1.50 if strong else 1.25) * a5,
                       (1.00 if strong else 0.80) * a15) if a15 else (1.50 if strong else 1.25) * a5
        if entry - sl < min_risk:
            sl = entry - min_risk
        risk = entry - sl
        if risk <= 0:
            return {'quality':'INVALID STOP GEOMETRY — SKIP','entry':entry,'sl':sl,'risk':risk,'reason':'stop-loss must be below entry for BUY setups'}
    else:
        m1_levels = [v for _, v in h1 if v > entry]
        m5_levels = [v for _, v in h5 if v > entry]
        m1_stop = (min(m1_levels) + 0.20 * a1) if m1_levels else (max(z['high'] for z in m1[-8:]) + 0.20 * a1)
        m5_stop = (min(m5_levels) + 0.15 * a5) if m5_levels else (max(z['high'] for z in m5[-6:]) + 0.15 * a5)
        sl = max(m1_stop, m5_stop)  # conservative: stop above both structural invalidation candidates
        min_risk = max(0.75 * a1, 0.20 * a5)
        # Risk-width rejection is disabled for SELL setups as well.
        strength = max(float(r.get('structure_score', 0)), float(r.get('trigger_score', 0)),
                       float(r.get('continuation_score', 0)), float(r.get('transition_score', 0)))
        strong = strength >= 80
        max_risk = min((1.50 if strong else 1.25) * a5,
                       (1.00 if strong else 0.80) * a15) if a15 else (1.50 if strong else 1.25) * a5
        if sl - entry < min_risk:
            sl = entry + min_risk
        risk = sl - entry
        if risk <= 0:
            return {'quality':'INVALID STOP GEOMETRY — SKIP','entry':entry,'sl':sl,'risk':risk,'reason':'stop-loss must be above entry for SELL setups'}

    # Structure-led TP1: target the nearest meaningful opposing objective,
    # front-run it by a small ATR buffer, and reject geometrically poor setups.
    # This changes exits only; direction/trigger selection above is untouched.
    m15 = frames.get('M15', [])
    opposing_candidates = []
    pivot_sources = []
    for candles, label, lookback in ((m5, 'M5', 60), (m15, 'M15', 30)):
        if len(candles) >= 8:
            highs, lows = _pivots(candles[-lookback:], 2, 2)
            levels = highs if direction == 'BULLISH' else lows
            eligible = [float(v) for _, v in levels
                        if (v > entry if direction == 'BULLISH' else v < entry)]
            if eligible:
                nearest = min(eligible) if direction == 'BULLISH' else max(eligible)
                opposing_candidates.append((abs(nearest-entry), nearest, label))
                pivot_sources.append((label, eligible))

    # A repeated pivot zone can represent clustered liquidity. The closest
    # confirmed opposing level remains the destination; the buffer avoids
    # requiring an exact touch of the pivot price.
    if opposing_candidates:
        _, opposing, source_tf = min(opposing_candidates, key=lambda z: z[0])
        target_buffer = max(0.08 * a5, 0.05 * a1)
        structural_dist = abs(opposing-entry) - target_buffer
        if structural_dist <= 0:
            structural_dist = abs(opposing-entry) * 0.5
        tp1_dist = structural_dist
        tp1_basis = f'{source_tf} opposing swing/liquidity objective, front-run by ATR buffer'
    else:
        # Only when no confirmed opposing swing exists do we use a volatility
        # fallback. It is explicit in the journal so results can be segmented.
        tp1_dist = max(0.80 * risk, 1.00 * a5)
        tp1_basis = 'ATR fallback — no confirmed opposing M5/M15 swing'

    # Momentum affects confidence in reachability, not the signal direction.
    # If both trigger timeframes are opposed, require a closer target rather
    # than stretching toward a distant swing.
    m1_read = r.get('M1', {})
    m5_read = r.get('M5', {})
    aligned = sum(1 for x in (m1_read, m5_read)
                  if x.get('momentum') == direction or x.get('displacement') == direction)
    if aligned == 0:
        tp1_dist = min(tp1_dist, max(0.65 * risk, 0.75 * a5))
        tp1_basis += ' | reduced for weak M1/M5 momentum'

    # The target is still dictated by structure; RR is a viability check, not
    # a formula used to invent a farther TP. Skip only when the objective gives
    # too little room relative to the structural stop.
    min_tp1_rr = float(os.getenv('REV2_SCALP_TP1_MIN_RR', '0.65'))
    planned_rr = tp1_dist / risk if risk > 0 else 0
    if planned_rr < min_tp1_rr:
        return {
            'quality':'SCALP TARGET TOO CLOSE — SKIP', 'entry':entry, 'sl':sl,
            'risk':risk, 'structural_dist':round(tp1_dist, 5),
            'required_dist':round(min_tp1_rr * risk, 5),
            'opposing_pivot':opposing if opposing_candidates else None,
            'reason':f'nearest realistic objective offers only {planned_rr:.2f}R; minimum is {min_tp1_rr:.2f}R',
            'sl_basis':'M1/M5 swing invalidation + ATR buffer', 'tp1_basis':tp1_basis,
        }

    # V3.8: cap far structural targets. The supplied 21-trade sample averaged
    # only 1.17R MFE while the planned targets were commonly 1.6R–3.0R.
    # Keep nearer structural objectives, but do not demand more than 1.25R.
    max_target_r = float(os.getenv('REV3_MAX_TP1_RR', '1.25'))
    if risk > 0 and tp1_dist > max_target_r * risk:
        tp1_dist = max_target_r * risk
        tp1_basis += f' | capped at {max_target_r:.2f}R reachability limit'

    source_tp1 = entry + tp1_dist if direction == 'BULLISH' else entry - tp1_dist

    return {
        'quality':'STRUCTURAL-LOCAL',
        'entry':entry,'sl':sl,'tp1':source_tp1,
        'risk':risk,'tp1_basis':tp1_basis, 'planned_rr':round(tp1_dist / risk, 4),
        'sl_basis':'M1/M5 swing invalidation + ATR buffer','risk_cap':round(max_risk,5),'risk_mode':'ADAPTIVE_STRONG' if strong else 'STANDARD',
    }



def _continuation_context(frames, direction):
    """Identify trend-continuation opportunities without requiring a liquidity sweep.

    This is deliberately conservative: the higher timeframes establish direction,
    while M15/M5/M1 provide the continuation trigger. It does not replace the
    existing reversal setup; it adds a second path for clean directional moves.
    """
    if direction not in ('BULLISH','BEARISH'):
        return {'valid':False,'kind':'NONE','reasons':[],'score':0}
    h4=frames.get('H4',[]); h1=frames.get('H1',[]); m30=frames.get('M30',[])
    m15=frames.get('M15',[]); m5=frames.get('M5',[]); m1=frames.get('M1',[])
    if min(map(len,(h1,m30,m15,m5,m1))) < 8:
        return {'valid':False,'kind':'NONE','reasons':[],'score':0}

    r={tf:summarize(frames.get(tf,[])) for tf in ('H4','H1','M30','M15','M5','M1')}
    reasons=[]; score=0

    # H1 is the primary directional filter. H4 is context only.
    if r['H1']['trend']==direction:
        score += 25; reasons.append('H1 trend aligned')
    else:
        return {'valid':False,'kind':'NONE','reasons':['H1 trend not aligned'],'score':score}
    if r['M30']['trend']==direction:
        score += 20; reasons.append('M30 trend aligned')
    elif r['M30']['trend'] not in ('NEUTRAL','INSUFFICIENT'):
        return {'valid':False,'kind':'NONE','reasons':['M30 trend conflict'],'score':score}
    else:
        score += 8; reasons.append('M30 neutral — acceptable continuation context')

    if r['H4']['trend']==direction:
        score += 10; reasons.append('H4 aligned')
    elif r['H4']['trend'] in ('NEUTRAL','INSUFFICIENT'):
        score += 4; reasons.append('H4 neutral')

    # M15 should participate or be transitioning toward the HTF direction.
    m15_participating = r['M15']['trend']==direction or r['M15']['mss']==direction or r['M15']['bos']==direction
    if m15_participating:
        score += 15; reasons.append('M15 participation/transition')
    elif r['M15']['trend'] not in ('NEUTRAL','INSUFFICIENT'):
        return {'valid':False,'kind':'NONE','reasons':['M15 trend conflict'],'score':score}

    # M5 must not be structurally opposed. M1 supplies the actual trigger.
    if r['M5']['trend']==direction:
        score += 10; reasons.append('M5 aligned')
    elif r['M5']['trend'] in ('NEUTRAL','INSUFFICIENT'):
        score += 4; reasons.append('M5 neutral')
    else:
        return {'valid':False,'kind':'NONE','reasons':['M5 trend conflict'],'score':score}

    trigger = (r['M1']['mss']==direction or r['M1']['bos']==direction or
               r['M1']['displacement']==direction)
    if trigger:
        score += 15; reasons.append('M1 continuation trigger')
    else:
        return {'valid':False,'kind':'NONE','reasons':['no M1 continuation trigger'],'score':score}

    # A pullback is present when the most recent few M1 candles contain
    # counter-direction pressure before the current directional trigger.
    last=m1[-6:]
    opposite=0
    for z in last[:-1]:
        if direction=='BULLISH' and z['close']<z['open']: opposite += 1
        elif direction=='BEARISH' and z['close']>z['open']: opposite += 1
    pullback = opposite >= 2

    # Avoid chasing a deeply extended trigger candle.
    if r['M1']['extension']=='EXTENDED':
        return {'valid':False,'kind':'NONE','reasons':reasons+['M1 extended — do not chase'],'score':score}
    if r['M1']['exhaustion']['score']>=60:
        return {'valid':False,'kind':'NONE','reasons':reasons+['M1 exhaustion too high'],'score':score}

    if pullback:
        score += 5; reasons.append('M1 pullback before continuation')
        kind='PULLBACK CONTINUATION'
    else:
        kind='MOMENTUM CONTINUATION'

    return {'valid':score>=65,'kind':kind,'reasons':reasons,'score':min(100,score)}



def _entry_confirmation(frames, direction):
    """Direction-aware M1 pullback/resumption gate; does not alter risk geometry."""
    c=frames.get('M1', [])
    if len(c) < 8 or direction not in ('BULLISH','BEARISH'):
        return {'valid':False, 'reason':'insufficient M1 candles', 'pullback_candles':0, 'resumption':False}
    # Use only the five completed candles before the latest completed candle.
    prior=c[-6:-1]
    last=c[-1]
    if direction=='BULLISH':
        opposite=sum(1 for z in prior if z['close'] < z['open'])
        resumption=last['close'] > max(z['high'] for z in prior[-3:])
    else:
        opposite=sum(1 for z in prior if z['close'] > z['open'])
        resumption=last['close'] < min(z['low'] for z in prior[-3:])
    # v3.6 experiment: allow one counter-direction candle, but still require
    # the confirming close beyond the recent three-candle range.
    valid=opposite>=1 and resumption
    reason='one-candle pullback + directional close confirmed' if valid else ('need at least 1 counter-direction candle' if opposite<1 else 'no close through recent 3-candle range')
    return {'valid':valid, 'reason':reason, 'pullback_candles':opposite, 'resumption':resumption}

def _continuation_fast_confirmation(frames, direction, readings):
    """Alternative confirmation for clean continuation displacement only."""
    c=frames.get('M1', [])
    if len(c) < 8 or direction not in ('BULLISH','BEARISH'):
        return {'valid':False,'reason':'insufficient M1 candles for continuation'}
    last=c[-1]
    directional_close = last['close'] > last['open'] if direction=='BULLISH' else last['close'] < last['open']
    x=readings.get('M1', {})
    structural_break = x.get('bos')==direction or x.get('mss')==direction
    displacement = x.get('displacement')==direction
    extended = x.get('extension')=='EXTENDED'
    exhausted = x.get('exhaustion',{}).get('score',0) >= 60
    valid = directional_close and (structural_break or displacement) and not extended and not exhausted
    reason = 'continuation displacement confirmed without mandatory pullback' if valid else 'continuation fast path conditions incomplete'
    return {'valid':valid,'reason':reason,'pullback_candles':0,'resumption':directional_close,'continuation_fast_path':True}


def _structural_transition_context(frames, direction):
    """Detect an early structural transition against still-unflipped H4/H1 context.

    This is intentionally stricter than simply allowing a lower-timeframe trend
    conflict. It requires M30/M15 transition evidence plus M5/M1 structural
    confirmation, displacement, acceptable exhaustion, and no micro-timeframe
    conflict. H4/H1 remain context rather than absolute vetoes.
    """
    if direction not in ('BULLISH','BEARISH'):
        return {'valid':False,'score':0,'kind':'NONE','reasons':[]}
    r={tf:summarize(frames.get(tf,[])) for tf in ('H4','H1','M30','M15','M5','M1')}
    if min(r[t]['count'] for t in r) <= 0:
        return {'valid':False,'score':0,'kind':'NONE','reasons':[]}
    reasons=[]; score=0
    opp='BEARISH' if direction=='BULLISH' else 'BULLISH'
    # Higher timeframes are allowed to lag. A direct opposite H4 trend is still
    # a strong warning, while H1 may remain unchanged during an early transition.
    if r['H4']['trend']==direction:
        score += 5; reasons.append('H4 context aligned')
    elif r['H4']['trend'] in ('NEUTRAL','INSUFFICIENT'):
        score += 7; reasons.append('H4 neutral context')
    else:
        score -= 10; reasons.append('H4 opposing context')

    if r['H1']['trend']==direction:
        score += 4; reasons.append('H1 already aligned')
    elif r['H1']['trend'] in ('NEUTRAL','INSUFFICIENT'):
        score += 8; reasons.append('H1 neutral transition context')
    else:
        score -= 4; reasons.append('H1 opposing trend')

    # M30/M15 are the transition bridge. At least one must show an actual
    # structural event; trend alone is not enough.
    bridge=0
    for tf,pts in (('M30',15),('M15',18)):
        x=r[tf]
        if x['trend']==direction: score += pts*0.45; reasons.append(tf+' trend transitioned')
        if x['mss']==direction: score += pts*0.45; bridge += 1; reasons.append(tf+' MSS')
        if x['bos']==direction: score += pts*0.35; bridge += 1; reasons.append(tf+' BOS')
        if x['displacement']==direction: score += 5; reasons.append(tf+' displacement')
        if x['momentum']==direction: score += 3; reasons.append(tf+' momentum')

    # M5/M1 must confirm the transition, preferably with MSS/BOS on both.
    micro_events=0
    for tf,pts in (('M5',20),('M1',20)):
        x=r[tf]
        if x['trend']==direction: score += 5; reasons.append(tf+' trend aligned')
        if x['mss']==direction: score += pts*0.55; micro_events += 1; reasons.append(tf+' MSS')
        if x['bos']==direction: score += pts*0.35; micro_events += 1; reasons.append(tf+' BOS')
        if x['displacement']==direction: score += 7; reasons.append(tf+' displacement')
        if x['fvg']==direction: score += 3; reasons.append(tf+' FVG')
        if x['momentum']==direction: score += 3; reasons.append(tf+' momentum')

    # A transition is stronger when the old direction is being invalidated on
    # M30/M15 rather than merely oscillating on M1.
    if bridge >= 1: score += 8; reasons.append('M30/M15 structural bridge confirmed')
    if micro_events >= 2: score += 10; reasons.append('M5/M1 structural confirmation')

    exhaustion=max(r[t]['exhaustion']['score'] for t in ('M15','M5','M1'))
    if exhaustion >= 60:
        score -= 20; reasons.append('exhaustion too high')
    elif exhaustion >= 45:
        score -= 8; reasons.append('elevated exhaustion')

    # Do not accept a transition while both trigger timeframes are still
    # structurally/momentum opposed to the intended direction.
    adverse=sum(1 for t in ('M5','M1') if
                r[t]['trend'] not in (direction,'NEUTRAL','INSUFFICIENT') or
                r[t]['momentum'] not in (direction,'NEUTRAL','INSUFFICIENT'))
    if adverse >= 2:
        score -= 15; reasons.append('micro conflict')

    score=round(max(0,min(100,score)),1)
    valid=(bridge >= 1 and micro_events >= 2 and exhaustion < 60 and adverse < 2 and score >= 68)
    return {'valid':valid,'score':score,'kind':'STRUCTURAL TRANSITION' if valid else 'NONE','reasons':reasons[-16:]}


def _market_regime(readings):
    """Classify broad regime from completed timeframe readings, not a prediction."""
    tfs = ("H4", "H1", "M30", "M15")
    bull = sum(readings.get(tf, {}).get("trend") == "BULLISH" for tf in tfs)
    bear = sum(readings.get(tf, {}).get("trend") == "BEARISH" for tf in tfs)
    neutral = sum(readings.get(tf, {}).get("trend") in ("NEUTRAL", "INSUFFICIENT", None) for tf in tfs)
    if bull >= 3:
        return {"label":"BULLISH TREND", "bias":"BULLISH", "alignment":bull, "range_risk":False}
    if bear >= 3:
        return {"label":"BEARISH TREND", "bias":"BEARISH", "alignment":bear, "range_risk":False}
    if readings.get("H4", {}).get("trend") == readings.get("H1", {}).get("trend") and readings.get("H4", {}).get("trend") in ("BULLISH", "BEARISH"):
        return {"label":"TREND WITH COUNTERTREND PULLBACK", "bias":readings["H4"]["trend"], "alignment":2, "range_risk":False}
    if neutral >= 2 or (bull < 3 and bear < 3):
        return {"label":"RANGE / TRANSITION / MIXED", "bias":"MIXED", "alignment":max(bull,bear), "range_risk":True}
    return {"label":"TRANSITION", "bias":"MIXED", "alignment":max(bull,bear), "range_risk":True}


def _improved_entry_confirmation(frames, readings, direction):
    """Balanced confirmation: retain a directional close and require 2 of 3 independent cues.

    This is intentionally less restrictive than V3.8's all-of-three gate, while
    still preventing a candle-only signal from qualifying as a trade.
    """
    candles = frames.get("M1", [])
    if len(candles) < 8:
        return {"valid":False,"reason":"insufficient M1 candles","score":0}
    last = candles[-1]
    close_directional = (last["close"] > last["open"]) if direction == "BULLISH" else (last["close"] < last["open"])
    m1 = readings.get("M1", {})
    m5 = readings.get("M5", {})
    structural = any(m1.get(k) == direction for k in ("mss", "bos", "displacement"))
    m5_support = any(m5.get(k) == direction for k in ("momentum", "mss", "bos", "displacement"))
    cues = int(structural) + int(m5_support) + int(m1.get("momentum") == direction)
    valid = close_directional and cues >= 2
    reasons = []
    if not close_directional: reasons.append("last completed M1 candle did not close in trade direction")
    if structural: reasons.append("M1 structure/displacement aligned")
    if m5_support: reasons.append("M5 directional support")
    if m1.get("momentum") == direction: reasons.append("M1 momentum aligned")
    if cues < 2: reasons.append(f"only {cues}/3 confirmation cues aligned; need 2")
    return {"valid":valid,"score":cues,"reason":"balanced confirmation passed" if valid else "; ".join(reasons)}


def _entry_timing_filter(frames, readings, direction, setup_type):
    """Experimental entry-timing gate; does not change signal direction or SL/TP logic.

    Blocks entries when M15/M5 still show persistent pressure against the proposed
    trade, and avoids continuation entries when the M5 move is already extended.
    It uses only the candles/readings available at decision time.
    """
    if direction not in ('BULLISH', 'BEARISH'):
        return {'valid': False, 'reason': 'no clear direction', 'checks': []}

    opposite = 'BEARISH' if direction == 'BULLISH' else 'BULLISH'
    m15 = readings.get('M15', {})
    m5 = readings.get('M5', {})
    m1 = readings.get('M1', {})
    checks = []

    # Strong counter-direction pressure on both M15 and M5 suggests that a
    # pullback may still be active rather than completed.
    m15_counter = (m15.get('momentum') == opposite)
    m5_counter = (m5.get('momentum') == opposite)
    m15m5_trend_counter = (m15.get('trend') == opposite and m5.get('trend') == opposite)
    m5m1_counter = (m5.get('momentum') == opposite and m1.get('momentum') == opposite)

    if m15_counter and m5_counter:
        checks.append('M15 and M5 momentum still oppose proposed direction')
        return {'valid': False, 'reason': '; '.join(checks), 'checks': checks}
    if m15m5_trend_counter and m5m1_counter:
        checks.append('M15/M5 trends and M5/M1 momentum still oppose proposed direction')
        return {'valid': False, 'reason': '; '.join(checks), 'checks': checks}

    # For continuation entries, avoid chasing a stretched M5 move even when M1
    # produces a trigger. This is an additional guard to the existing M1 checks.
    if setup_type not in ('REVERSAL', 'STRUCTURAL TRANSITION') and m5.get('extension') == 'EXTENDED':
        checks.append('M5 extended — wait for a fresh pullback')
        return {'valid': False, 'reason': '; '.join(checks), 'checks': checks}

    # In compressed/choppy M5 conditions, require actual directional structure or
    # displacement on M1; neutral momentum alone is not enough to accept a setup.
    if m5.get('volatility') == 'COMPRESSED':
        micro_trigger = any(m1.get(k) == direction for k in ('mss', 'bos', 'displacement'))
        if not micro_trigger:
            checks.append('M5 compressed and no directional M1 structure/displacement')
            return {'valid': False, 'reason': '; '.join(checks), 'checks': checks}

    checks.append('pullback pressure not persistently opposed')
    checks.append('no M5 extension/chop veto')
    return {'valid': True, 'reason': 'entry timing checks passed', 'checks': checks}


def _invert_setup_geometry(setup, direction, state, setup_type):
    """Reverse a completed signal and swap source SL/TP1 into inverse geometry."""
    original_direction = direction
    if setup and state in ("BUY SETUP", "SELL SETUP") and "tp1" in setup and "sl" in setup:
        original_sl = float(setup["sl"])
        original_tp1 = float(setup["tp1"])
        entry = float(setup["entry"])
        inverse_direction = "BEARISH" if direction == "BULLISH" else "BULLISH"
        inverse_state = "SELL SETUP" if state == "BUY SETUP" else "BUY SETUP"
        setup["original_sl"] = original_sl
        setup["original_tp1"] = original_tp1
        setup["sl"] = original_tp1
        setup["tp1"] = original_sl
        setup["risk"] = abs(entry - setup["sl"])
        setup.pop("tp2", None)
        setup.pop("tp3", None)
        setup.pop("tp1_rr", None)
        setup.pop("tp2_rr", None)
        setup.pop("tp3_rr", None)
        setup["tp1_basis"] = "Original structural SL (swapped to inverse TP1)"
        setup["sl_basis"] = "Original TP1 (swapped to inverse SL)"
        setup["inverse"] = True
        setup["original_direction"] = "BUY" if original_direction == "BULLISH" else "SELL"
        direction = inverse_direction
        state = inverse_state
        setup_type = f"INVERSE OF {setup_type}"
    return direction, state, setup_type, original_direction

def analyze(frames):
    r={tf:summarize(frames.get(tf,[])) for tf in WEIGHTS}
    ready=all(len(frames.get(t,[]))>=MIN[t] for t in MIN)
    bull,b_reasons,bconf=_directional_evidence(r,'BULLISH')
    bear,s_reasons,rconf=_directional_evidence(r,'BEARISH')

    if bull>=58 and bull>bear+12: direction='BULLISH'
    elif bear>=58 and bear>bull+12: direction='BEARISH'
    else: direction='MIXED'

    # v2.4: STRUCTURE SCORE is deliberately independent of momentum/FVG-heavy
    # evidence.  Trend alignment establishes the environment; actual BOS/MSS,
    # displacement and liquidity events earn the higher-quality structural points.
    selected=r if direction!='MIXED' else None
    if direction=='MIXED':
        structure_score=0.0
        conflicts=[]
    else:
        # 50 points: multi-timeframe trend alignment.
        trend_points=sum(WEIGHTS[t] for t in WEIGHTS if r[t]['trend']==direction) / 2.0
        # 25 points: actual structural events, with HTF weighted more heavily.
        event_points=0.0
        for tf,pts in (('H4',5),('H1',7),('M30',6),('M15',4),('M5',2),('M1',1)):
            if r[tf]['bos']==direction: event_points += pts
            if r[tf]['mss']==direction: event_points += pts
        event_points=min(25.0,event_points)
        # 15 points: displacement + momentum, supporting structure rather than
        # acting as entry confirmation.
        support_points=0.0
        for tf,pts in (('H1',3),('M30',3),('M15',3),('M5',3),('M1',3)):
            if r[tf]['displacement']==direction: support_points += pts*0.7
            if r[tf]['momentum']==direction: support_points += pts*0.3
        support_points=min(15.0,support_points)
        # 10 points: favorable liquidity/FVG context.
        context_points=0.0
        for tf in ('H1','M30','M15','M5','M1'):
            if r[tf]['liquidity']==('SELL_SIDE_SWEPT' if direction=='BULLISH' else 'BUY_SIDE_SWEPT'):
                context_points += 3.0
            if r[tf]['fvg']==direction:
                context_points += 1.0
        context_points=min(10.0,context_points)
        structure_score=trend_points+event_points+support_points+context_points
        conflicts=bconf if direction=='BULLISH' else rconf
        # Explicit penalties for evidence that argues against the structural thesis.
        for tf in ('H1','M30'):
            if r[tf]['liquidity']==('BUY_SIDE_SWEPT' if direction=='BULLISH' else 'SELL_SIDE_SWEPT'):
                structure_score-=5
        for tf in ('M15','M5','M1'):
            if r[tf]['trend'] not in (direction,'NEUTRAL','INSUFFICIENT'):
                structure_score-=7
            if r[tf]['momentum'] not in (direction,'NEUTRAL','INSUFFICIENT'):
                structure_score-=3
        # Premium/discount is context, not a direction signal. Penalize only
        # when it creates a poor location for the chosen direction.
        if direction=='BULLISH' and r['M15']['zone']=='PREMIUM': structure_score-=3
        if direction=='BEARISH' and r['M15']['zone']=='DISCOUNT': structure_score-=3
        structure_score=round(max(0.0,min(100.0,structure_score)),1)

    wanted='SELL_SIDE_SWEPT' if direction=='BULLISH' else 'BUY_SIDE_SWEPT'
    adverse='BUY_SIDE_SWEPT' if direction=='BULLISH' else 'SELL_SIDE_SWEPT'
    trigger_points=0.0; trigger_reasons=[]; trigger_conflicts=[]
    # Entry confirmations are ONLY actual trigger evidence. Momentum/FVG alone
    # never creates a confirmation.
    if direction!='MIXED':
        for tf,pts in (('M15',15),('M5',20),('M1',20)):
            if r[tf]['mss']==direction: trigger_points+=pts; trigger_reasons.append(tf+' MSS')
            if r[tf]['bos']==direction: trigger_points+=min(10,pts//2); trigger_reasons.append(tf+' BOS')
            if r[tf]['displacement']==direction: trigger_points+=10; trigger_reasons.append(tf+' displacement')
        for tf in ('M15','M5','M1'):
            if r[tf]['liquidity']==wanted: trigger_points+=12; trigger_reasons.append(tf+' favorable liquidity sweep')
            elif r[tf]['liquidity']==adverse: trigger_points-=10; trigger_conflicts.append(tf+' adverse liquidity sweep')
        # FVG is context unless paired with a trigger; it can support the score
        # but cannot count as an entry confirmation by itself.
        if r['M1']['fvg']==direction: trigger_points+=8; trigger_reasons.append('M1 FVG context')
        elif r['M5']['fvg']==direction: trigger_points+=5; trigger_reasons.append('M5 FVG context')
        if r['M1']['trend'] not in (direction,'NEUTRAL','INSUFFICIENT'):
            trigger_points-=15; trigger_conflicts.append('M1 trend conflict')
        if r['M5']['trend'] not in (direction,'NEUTRAL','INSUFFICIENT'):
            trigger_points-=10; trigger_conflicts.append('M5 trend conflict')
    trigger_score=round(max(0,min(100,trigger_points)),1)
    continuation=_continuation_context(frames,direction)
    # Evaluate both transition directions instead of allowing any bearish clue
    # to force the transition candidate to BEARISH.
    transition_bull=_structural_transition_context(frames,'BULLISH')
    transition_bear=_structural_transition_context(frames,'BEARISH')
    if transition_bull['score'] >= transition_bear['score']:
        transition_direction, transition = 'BULLISH', transition_bull
    else:
        transition_direction, transition = 'BEARISH', transition_bear
    continuation_score=continuation['score'] if continuation['valid'] else 0
    continuation_ok=continuation['valid'] and not conflicts and not trigger_conflicts

    # Count only genuine trigger events: MSS/BOS/displacement/favorable liquidity.
    confirmation_count=sum(1 for z in trigger_reasons if not z.endswith('FVG context'))
    m15,m5,m1=r['M15'],r['M5'],r['M1']
    exhaustion_score=max(r[t]['exhaustion']['score'] for t in ('M15','M5','M1')) if direction!='MIXED' else 0
    exhaustion_level=max((r[t]['exhaustion']['level'] for t in ('M15','M5','M1')), key=lambda z: {'NORMAL':0,'ELEVATED':1,'HIGH':2,'EXTREME':3,'UNKNOWN':0}.get(z,0)) if direction!='MIXED' else 'NORMAL'
    exhaustion_reasons=[]
    for t in ('M15','M5','M1'):
        for reason in r[t]['exhaustion'].get('reasons',[]):
            exhaustion_reasons.append(f'{t} {reason}')
    favorable_liq=any(r[t]['liquidity']==wanted for t in ('M15','M5','M1')) if direction!='MIXED' else False
    displacement_ok=any(r[t]['displacement']==direction for t in ('M15','M5','M1')) if direction!='MIXED' else False
    mss_ok=any(r[t]['mss']==direction for t in ('M15','M5','M1')) if direction!='MIXED' else False
    adverse_micro=any(r[t]['trend'] not in (direction,'NEUTRAL','INSUFFICIENT') or
                      r[t]['momentum'] not in (direction,'NEUTRAL','INSUFFICIENT')
                      for t in ('M5','M1')) if direction!='MIXED' else False
    late_entry=((direction=='BULLISH' and m15['zone']=='PREMIUM' and m1['extension']=='EXTENDED') or
                (direction=='BEARISH' and m15['zone']=='DISCOUNT' and m1['extension']=='EXTENDED'))
    exhaustion_block=direction!='MIXED' and exhaustion_score>=60
    exhaustion_wait=direction!='MIXED' and exhaustion_score>=45

    # A valid setup needs a real trigger sequence, not just alignment.
    # High/EXTREME exhaustion is a hard entry block: do not chase the move.
    reversal_ok=(direction!='MIXED' and ready and structure_score>=55 and trigger_score>=55 and
                confirmation_count>=2 and mss_ok and displacement_ok and
                (favorable_liq or m1['fvg']==direction or m5['fvg']==direction) and
                not adverse_micro and not late_entry and not exhaustion_block)

    # New v3.2/v1.1 continuation path: do not require a sweep/FVG when the
    # higher-timeframe trend is established and the lower timeframe resumes it.
    continuation_entry_ok=(direction!='MIXED' and ready and continuation_ok and
                           structure_score>=45 and not adverse_micro and
                           not late_entry and not exhaustion_block)
    transition_entry_ok=(ready and transition['valid'] and not late_entry and not exhaustion_block)
    trigger_ok=reversal_ok or continuation_entry_ok or transition_entry_ok
    entry_gate=_entry_confirmation(frames, transition_direction if transition_entry_ok else direction)
    # v3.7: continuation setups get a separate, less restrictive route. They
    # still need directional M1 close + BOS/MSS or displacement and remain
    # blocked by extension, exhaustion, adverse microstructure and geometry.
    if trigger_ok and not entry_gate['valid'] and continuation_entry_ok:
        fast_gate=_continuation_fast_confirmation(frames, direction, r)
        if fast_gate['valid']:
            entry_gate=fast_gate
    if trigger_ok and not entry_gate['valid']:
        trigger_ok=False
        reversal_ok=False
        continuation_entry_ok=False
        transition_entry_ok=False
    if transition_entry_ok:
        direction=transition_direction
        setup_type='STRUCTURAL TRANSITION'
        structure_score=max(structure_score, transition['score'])
        trigger_score=max(trigger_score, transition['score'])
        confirmation_count=max(confirmation_count, 2)
        trigger_reasons=transition['reasons']
        trigger_conflicts=[]
    else:
        setup_type=('REVERSAL' if reversal_ok else continuation['kind'] if continuation_entry_ok else 'NONE')

    if transition_entry_ok:
        state='BUY SETUP' if direction=='BULLISH' else 'SELL SETUP'
    elif direction!='MIXED' and ready and trigger_ok:
        state='BUY SETUP' if direction=='BULLISH' else 'SELL SETUP'
    elif direction!='MIXED' and ready and (structure_score>=45 or continuation['score']>=60):
        state='WAIT — MOVE EXHAUSTED' if exhaustion_block else ('ARMED — WAIT FOR PULLBACK' if (late_entry or exhaustion_wait) else 'ARMED — WAIT FOR CONFIRMATION')
    else:
        state='NO TRADE'
    if m1['volatility']=='EXTREME_EXPANSION': state='WAIT — EXTREME VOLATILITY'

    # V2 RESPONSIVE INVERSE EXPERIMENT:
    # The source signal's own timing gate was designed for the source direction.
    # Applying it as a hard veto before inversion, then demanding a second
    # opposite-direction timing gate, caused two competing gates to suppress
    # almost every inverse setup. Keep timing diagnostics, but use the already
    # validated source trigger + regime + inverse geometry as the admission path.
    timing_filter = {'valid': True, 'reason': 'diagnostic only in V2; source timing is not a hard veto for inverse setups', 'checks': []}
    original_direction = direction
    if state in ('BUY SETUP', 'SELL SETUP'):
        source_timing = _entry_timing_filter(frames, r, direction, setup_type)
        timing_filter = {'valid': source_timing.get('valid', False),
                         'reason': source_timing.get('reason', 'source timing diagnostic'),
                         'checks': source_timing.get('checks', []),
                         'mode': 'DIAGNOSTIC_ONLY'}
        # Reverse BUY/SELL signals only. The source setup has already passed
        # the original engine's trigger and entry-confirmation checks above.
        direction = 'BEARISH' if direction == 'BULLISH' else 'BULLISH'
        state = 'SELL SETUP' if state == 'BUY SETUP' else 'BUY SETUP'
        timing_filter['emitted_direction'] = 'SELL' if direction == 'BEARISH' else 'BUY'
        timing_filter['source_direction'] = 'BUY' if original_direction == 'BULLISH' else 'SELL'

    regime = _market_regime(r)
    regime_gate = {"valid": True, "reason": "not evaluated — no candidate setup"}
    confirmation_gate = {"valid": True, "reason": "not evaluated — no candidate setup"}
    setup=_setup(frames,direction,r) if state in ('BUY SETUP','SELL SETUP') else None
    if setup and state in ('BUY SETUP','SELL SETUP'):
        setup['source_direction'] = 'BUY' if original_direction == 'BULLISH' else 'SELL' if original_direction == 'BEARISH' else 'UNKNOWN'
        setup['emitted_direction'] = 'BUY' if direction == 'BULLISH' else 'SELL'

    if setup and setup.get('quality') in ('INVALID STOP GEOMETRY — SKIP', 'SCALP TARGET TOO CLOSE — SKIP'):
        state = 'NO TRADE — SCALP GEOMETRY SKIP — ' + setup.get('reason', 'invalid source geometry')
        setup = None

    if setup and state in ('BUY SETUP','SELL SETUP'):
        # V3.9 balanced admission: allow more qualified opportunities without
        # dropping directional confirmation. Require a directional M1 close and
        # 2/3 independent cues. In mixed regimes, permit a trade only when the
        # transition is valid OR M15/M5/M1 provide multi-timeframe support and
        # the major H4/H1 context is not unanimously opposed.
        emitted_confirmation = _improved_entry_confirmation(frames, r, direction)
        emitted_transition = _structural_transition_context(frames, direction)
        transition_matches = bool(emitted_transition.get('valid'))
        regime_matches = regime.get('bias') == direction and not regime.get('range_risk')
        m15 = r.get('M15', {}); m5 = r.get('M5', {}); m1 = r.get('M1', {})
        lower_support = sum([
            m15.get('trend') == direction or m15.get('mss') == direction or m15.get('bos') == direction,
            m5.get('trend') == direction or m5.get('momentum') == direction or m5.get('mss') == direction or m5.get('bos') == direction,
            m1.get('momentum') == direction or m1.get('mss') == direction or m1.get('bos') == direction or m1.get('displacement') == direction,
        ])
        major_context = [r.get(tf, {}).get('trend') for tf in ('H4', 'H1')]
        major_opposed = all(t not in (direction, 'NEUTRAL', 'INSUFFICIENT') for t in major_context)
        balanced_regime_ok = lower_support >= 2 and not major_opposed
        if not emitted_confirmation.get('valid'):
            confirmation_gate = {
                'valid': False,
                'reason': 'reversed-direction confirmation failed: ' + emitted_confirmation.get('reason', 'no confirmation'),
                'mode': 'BALANCED_2_OF_3_CONFIRMATION'
            }
            state = 'WAIT — REVERSED DIRECTION NOT CONFIRMED — ' + confirmation_gate['reason']
            setup = None
        elif not (regime_matches or transition_matches or balanced_regime_ok):
            regime_gate = {
                'valid': False,
                'reason': f"emitted direction {direction} lacks regime, transition, or balanced multi-timeframe support ({lower_support}/3)"
            }
            state = 'WAIT — REGIME/REVERSAL CONFLICT — ' + regime_gate['reason']
            setup = None
        else:
            regime_gate = {
                'valid': True,
                'reason': 'emitted direction aligns with regime' if regime_matches else ('structural transition confirmed' if transition_matches else f'balanced lower-timeframe support {lower_support}/3; major context not unanimously opposed')
            }
            confirmation_gate = {
                'valid': True,
                'reason': emitted_confirmation.get('reason'),
                'mode': 'BALANCED_2_OF_3_CONFIRMATION'
            }

    if setup and state in ('BUY SETUP','SELL SETUP'):
        # Final geometry audit: directionally valid SL/TP, bounded stop relative
        # to M5 ATR, and a structural target that clears minimum RR.
        entry = float(setup['entry']); sl = float(setup['sl']); tp1 = float(setup['tp1'])
        risk = abs(entry - sl); reward = abs(tp1 - entry)
        a5 = atr(frames.get('M5', []), 14) or 0.0
        valid_geometry = (risk > 0 and ((direction == 'BULLISH' and sl < entry < tp1) or
                                        (direction == 'BEARISH' and tp1 < entry < sl)))
        max_stop = float(os.getenv('REV2_MAX_STOP_ATR_M5', '2.50'))
        min_rr = float(os.getenv('REV2_SCALP_TP1_MIN_RR', '0.75'))
        rr = reward / risk if risk else 0.0
        if not valid_geometry:
            setup['quality'] = 'INVALID STOP/TARGET GEOMETRY — SKIP'
            setup['reason'] = 'SL/TP must be on the correct side of entry for the emitted reversed direction'
        elif a5 and risk > max_stop * a5:
            setup['quality'] = 'STOP TOO WIDE — SKIP'
            setup['reason'] = f'structural stop is {risk/a5:.2f} M5 ATR; maximum allowed is {max_stop:.2f}'
        elif rr < min_rr:
            setup['quality'] = 'TARGET RR TOO LOW — SKIP'
            setup['reason'] = f'structural target offers {rr:.2f}R; minimum is {min_rr:.2f}R'
        if setup.get('quality') in ('INVALID STOP/TARGET GEOMETRY — SKIP','STOP TOO WIDE — SKIP','TARGET RR TOO LOW — SKIP'):
            state = 'NO TRADE — GEOMETRY FILTER — ' + setup.get('reason','invalid geometry')
            setup = None

    if setup and setup.get('quality') in ('INVALID STOP GEOMETRY — SKIP', 'SCALP TARGET TOO CLOSE — SKIP') and state in ('BUY SETUP','SELL SETUP'):
        # Stop-width cap is disabled. Still reject mathematically invalid stop
        # geometry and targets that cannot fit the strategy's target rules.
        detail=(f"{setup.get('quality')}: {setup.get('reason','no reason supplied')} | "
                f"entry={setup.get('entry')} SL={setup.get('sl')} risk={setup.get('risk')}")
        if 'structural_dist' in setup:
            detail += (f" target_room={setup.get('structural_dist')} "
                       f"required_room={setup.get('required_dist')} "
                       f"nearest_M5_pivot={setup.get('opposing_pivot')}")
        state=f'NO TRADE — SCALP GEOMETRY SKIP — {detail}'
        setup=None
    elif setup:
        setup['quality']='TRIGGERED' if state in ('BUY SETUP','SELL SETUP') else 'WAITING'

    if not ready: confidence='LIMITED'
    elif state in ('BUY SETUP','SELL SETUP'):
        confidence='HIGH' if structure_score>=75 and trigger_score>=70 and not conflicts and not trigger_conflicts else 'MODERATE-HIGH'
    elif direction!='MIXED': confidence='MODERATE-HIGH' if structure_score>=70 else 'MODERATE'
    else: confidence='LOW'

    entry_quality=('TRIGGERED' if trigger_ok else 'WAIT FOR PULLBACK' if late_entry else 'WAIT FOR CONFIRMATION')
    all_conflicts=(conflicts+trigger_conflicts)[-12:]
    return {'readings':r,'direction':direction,'original_direction':original_direction,'signal_mode':'IMPROVED_REVERSED_V3_9_BALANCED','score':structure_score,'structure_score':structure_score,
            'trigger_score':trigger_score,'confidence':confidence,'state':state,
            'confirmations':trigger_reasons[-12:],'conflicts':all_conflicts,'setup':setup,'ready':ready,
            'confirmation_count':confirmation_count,'entry_quality':entry_quality,
            'setup_type':setup_type,'continuation_score':continuation.get('score',0),
            'continuation_reasons':continuation.get('reasons',[]),
            'transition_score':transition.get('score',0),
            'transition_reasons':transition.get('reasons',[]),
            'entry_gate':entry_gate,'entry_timing_filter':timing_filter,'market_regime':regime,'regime_gate':regime_gate,'improved_confirmation_gate':confirmation_gate,
            'exhaustion_score':exhaustion_score,'exhaustion_level':exhaustion_level,
            'exhaustion_reasons':exhaustion_reasons[-20:],
            'trigger_reasons':trigger_reasons[-12:],'trigger_conflicts':trigger_conflicts[-10:]}


def report(x):
    lines=['QUINT CAPITAL QUTE V75 IMPROVED REVERSED-SIGNAL V2 RESPONSIVE — PAPER TEST','REVERSED BUY/SELL SIGNALS + REGIME/CONFIRMATION/GEOMETRY GUARDS | ANALYSIS ONLY — NO EXECUTION','='*68,
           f"STATE: {x['state']}",f"DIRECTION FIELD: {x['direction']} (accepted setups reverse the source BUY/SELL signal)",
           f"STRUCTURE SCORE: {x['structure_score']}/100 (NOT A PROBABILITY)",
           f"TRIGGER SCORE: {x['trigger_score']}/100 (NOT A PROBABILITY)",
           f"CONFIDENCE: {x['confidence']}",f"ENTRY CONFIRMATIONS: {x['confirmation_count']}",
           f"ENTRY QUALITY: {x['entry_quality']}",f"SETUP TYPE: {x.get('setup_type','NONE')}", f"MARKET REGIME: {x.get('market_regime',{}).get('label','UNKNOWN')}", f"REGIME GATE: {x.get('regime_gate',{}).get('reason','N/A')}", f"IMPROVED CONFIRMATION: {x.get('improved_confirmation_gate',{}).get('reason','N/A')}",
           f"CONTINUATION SCORE: {x.get('continuation_score',0)}/100",
           f"TRANSITION SCORE: {x.get('transition_score',0)}/100",
           f"EXHAUSTION: {x['exhaustion_level']} ({x['exhaustion_score']}/100)"]
    for t in ('H4','H1','M30','M15','M5','M1'):
        r=x['readings'][t]
        lines.append(f"{t}: {r['trend']} | MOM={r['momentum']} | BOS={r['bos']} | MSS={r['mss']} | DISP={r['displacement']} | FVG={r['fvg']} | LIQ={r['liquidity']} | ZONE={r['zone']} | EXT={r['extension']} | VOL={r['volatility']} | N={r['count']}")
    if x.get('exhaustion_reasons') and x.get('exhaustion_level') in ('HIGH','EXTREME'):
        lines += ['EXHAUSTION WARNINGS:'] + ['- '+z for z in x['exhaustion_reasons'][-8:]]
    if x['setup']:
        s=x['setup']
        lines.append('TRADE FOUND — TRADE PARAMETERS:')
        lines.append(f"- DIRECTION: {'BUY' if x['direction']=='BULLISH' else 'SELL'}")
        lines.append(f"- ENTRY: {s['entry']:.5f}")
        lines.append(f"- SL: {s['sl']:.5f}")
        lines.append(f"- RISK: {s['risk']:.5f} points")
        if s.get('sl_basis'): lines.append(f"- SL BASIS: {s['sl_basis']}")
        if 'tp1' in s:
            tp1_dist=abs(s['tp1']-s['entry'])
            lines.append(f"- TP1 (ONLY TAKE-PROFIT): {s['tp1']:.5f} | DISTANCE={tp1_dist:.5f} points")
            lines.append('- DIRECTION: original QUTE direction logic preserved')
        else:
            lines.append(f"- QUALITY: {s.get('quality','STRUCTURAL')}")
    if x['confirmations']: lines += ['ENTRY CONFIRMATIONS:']+['- '+z for z in x['confirmations']]
    if x['conflicts']: lines += ['CONFLICTS / WARNINGS:']+['- '+z for z in x['conflicts']]
    tf=x.get('entry_timing_filter', {})
    if tf:
        lines.append(f"ENTRY TIMING FILTER: {'PASS' if tf.get('valid') else 'WAIT/BLOCK'} — {tf.get('reason','N/A')}")
    return '\n'.join(lines)
