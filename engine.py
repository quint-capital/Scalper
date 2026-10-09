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
        sl = max(m1_stop, m5_stop)
        min_risk = max(0.75 * a1, 0.20 * a5)
        # v3.5 adaptive risk gate: strong structural setups may legitimately
        # require a little more room on V75. The old hard cap was a major
        # opportunity bottleneck because valid continuation/transition setups
        # were discarded solely for stop width. Weak setups still keep the
        # tighter cap.
        strength = max(float(r.get('structure_score', 0)), float(r.get('trigger_score', 0)),
                       float(r.get('continuation_score', 0)), float(r.get('transition_score', 0)))
        strong = strength >= 80
        max_risk = min((1.50 if strong else 1.25) * a5,
                       (1.00 if strong else 0.80) * a15) if a15 else (1.50 if strong else 1.25) * a5
        if entry - sl < min_risk:
            sl = entry - min_risk
        risk = entry - sl
        if risk <= 0 or risk > max_risk:
            return {'quality':'RISK TOO WIDE — SKIP','entry':entry,'sl':sl,'risk':risk,'reason':f'structural stop exceeds adaptive V75 risk cap ({max_risk:.5f})'}
    else:
        m1_levels = [v for _, v in h1 if v > entry]
        m5_levels = [v for _, v in h5 if v > entry]
        m1_stop = (min(m1_levels) + 0.20 * a1) if m1_levels else (max(z['high'] for z in m1[-8:]) + 0.20 * a1)
        m5_stop = (min(m5_levels) + 0.15 * a5) if m5_levels else (max(z['high'] for z in m5[-6:]) + 0.15 * a5)
        sl = min(m1_stop, m5_stop)
        min_risk = max(0.75 * a1, 0.20 * a5)
        # Same adaptive risk gate for SELL setups.
        strength = max(float(r.get('structure_score', 0)), float(r.get('trigger_score', 0)),
                       float(r.get('continuation_score', 0)), float(r.get('transition_score', 0)))
        strong = strength >= 80
        max_risk = min((1.50 if strong else 1.25) * a5,
                       (1.00 if strong else 0.80) * a15) if a15 else (1.50 if strong else 1.25) * a5
        if sl - entry < min_risk:
            sl = entry + min_risk
        risk = sl - entry
        if risk <= 0 or risk > max_risk:
            return {'quality':'RISK TOO WIDE — SKIP','entry':entry,'sl':sl,'risk':risk,'reason':f'structural stop exceeds adaptive V75 risk cap ({max_risk:.5f})'}

    # Scalping target geometry: the official simulated exit is TP1.
    # Use a modest first target (0.75R) to test quick V75 moves, but do not
    # place TP1 beyond the nearest confirmed opposing M5 pivot.
    # If nearby structure leaves less than 0.75R room, skip rather than
    # pretending the target is realistically reachable.
    opposing = _nearest_pivot(m5[-30:], direction, entry)
    min_rr = float(os.getenv("SCALP_TP1_RR", "0.75"))
    max_tp1_rr = float(os.getenv("SCALP_TP1_MAX_RR", "1.00"))
    if direction == 'BULLISH':
        structural_dist = (opposing - entry) if opposing is not None else 0
    else:
        structural_dist = (entry - opposing) if opposing is not None else 0

    if structural_dist >= min_rr * risk:
        tp1_dist = min(structural_dist, max_tp1_rr * risk)
        tp1_basis = 'M5 opposing structure'
    else:
        return {'quality':'SCALP TARGET TOO CLOSE — SKIP','entry':entry,'sl':sl,'risk':risk,
                'reason':f'nearest M5 opposing structure offers less than {min_rr:.2f}R'}

    tp2_dist = 1.25 * risk
    tp3_dist = 1.75 * risk
    if direction == 'BULLISH':
        targets = [entry + tp1_dist, entry + tp2_dist, entry + tp3_dist]
    else:
        targets = [entry - tp1_dist, entry - tp2_dist, entry - tp3_dist]

    return {
        'quality':'STRUCTURAL-LOCAL',
        'entry':entry,'sl':sl,'tp1':targets[0],'tp2':targets[1],'tp3':targets[2],
        'risk':risk,'tp1_rr':round(tp1_dist/risk,2),'tp1_basis':tp1_basis,
        'sl_basis':'M1/M5 local invalidation','risk_cap':round(max_risk,5),'risk_mode':'ADAPTIVE_STRONG' if strong else 'STANDARD',
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
    transition_direction = 'BEARISH' if r['M30']['trend']=='BEARISH' or r['M15']['trend']=='BEARISH' or r['M5']['mss']=='BEARISH' or r['M1']['mss']=='BEARISH' else 'BULLISH'
    transition=_structural_transition_context(frames,transition_direction)
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

    setup=_setup(frames,direction,r) if state in ('BUY SETUP','SELL SETUP') else None
    if setup and setup.get('quality') in ('RISK TOO WIDE — SKIP', 'SCALP TARGET TOO CLOSE — SKIP') and state in ('BUY SETUP','SELL SETUP'):
        state='NO TRADE — SCALP GEOMETRY SKIP'
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
    return {'readings':r,'direction':direction,'score':structure_score,'structure_score':structure_score,
            'trigger_score':trigger_score,'confidence':confidence,'state':state,
            'confirmations':trigger_reasons[-12:],'conflicts':all_conflicts,'setup':setup,'ready':ready,
            'confirmation_count':confirmation_count,'entry_quality':entry_quality,
            'setup_type':setup_type,'continuation_score':continuation.get('score',0),
            'continuation_reasons':continuation.get('reasons',[]),
            'transition_score':transition.get('score',0),
            'transition_reasons':transition.get('reasons',[]),
            'exhaustion_score':exhaustion_score,'exhaustion_level':exhaustion_level,
            'exhaustion_reasons':exhaustion_reasons[-20:],
            'trigger_reasons':trigger_reasons[-12:],'trigger_conflicts':trigger_conflicts[-10:]}


def report(x):
    lines=['QUINT CAPITAL V75 LIVE INTELLIGENCE v3.4','ANALYSIS ONLY — NO TRADE EXECUTION','='*68,
           f"STATE: {x['state']}",f"MARKET BIAS: {x['direction']}",
           f"STRUCTURE SCORE: {x['structure_score']}/100 (NOT A PROBABILITY)",
           f"TRIGGER SCORE: {x['trigger_score']}/100 (NOT A PROBABILITY)",
           f"CONFIDENCE: {x['confidence']}",f"ENTRY CONFIRMATIONS: {x['confirmation_count']}",
           f"ENTRY QUALITY: {x['entry_quality']}",f"SETUP TYPE: {x.get('setup_type','NONE')}",
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
            tp1_dist=abs(s['tp1']-s['entry']); tp2_dist=abs(s['tp2']-s['entry']); tp3_dist=abs(s['tp3']-s['entry'])
            lines.append(f"- TP1: {s['tp1']:.5f} | DISTANCE={tp1_dist:.5f} points | RR={s.get('tp1_rr', tp1_dist/s['risk'] if s.get('risk') else 0):.2f}R | BASIS={s.get('tp1_basis','1.25R fallback')}")
            lines.append(f"- TP2: {s['tp2']:.5f} | DISTANCE={tp2_dist:.5f} points | RR=2.00R")
            lines.append(f"- TP3: {s['tp3']:.5f} | DISTANCE={tp3_dist:.5f} points | RR=3.00R")
        else:
            lines.append(f"- QUALITY: {s.get('quality','STRUCTURAL')}")
    if x['confirmations']: lines += ['ENTRY CONFIRMATIONS:']+['- '+z for z in x['confirmations']]
    if x['conflicts']: lines += ['CONFLICTS / WARNINGS:']+['- '+z for z in x['conflicts']]
    return '\n'.join(lines)
