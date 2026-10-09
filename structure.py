from statistics import mean


def ema(v,p):
    if len(v)<p:return None
    k=2/(p+1); e=mean(v[:p])
    for x in v[p:]: e=x*k+e*(1-k)
    return e


def atr(c,p=14):
    if len(c)<p+1:return None
    tr=[]
    for i in range(1,len(c)):
        x,y=c[i],c[i-1]
        tr.append(max(x['high']-x['low'],abs(x['high']-y['close']),abs(x['low']-y['close'])))
    return mean(tr[-p:])


def trend(c):
    if len(c)<8:return 'INSUFFICIENT'
    cl=[x['close'] for x in c]; e20=ema(cl,min(20,len(cl))); e50=ema(cl,50) if len(cl)>=50 else None
    if e50 is not None:
        if cl[-1]>e20>e50:return 'BULLISH'
        if cl[-1]<e20<e50:return 'BEARISH'
    h=[x['high'] for x in c[-6:]]; l=[x['low'] for x in c[-6:]]
    if h[-1]>max(h[:-1]) and l[-1]>=min(l[:-1]):return 'BULLISH'
    if l[-1]<min(l[:-1]) and h[-1]<=max(h[:-1]):return 'BEARISH'
    return 'NEUTRAL'


def displacement(c):
    a=atr(c)
    if not a:return 'INSUFFICIENT'
    x=c[-1]; b=abs(x['close']-x['open']); return ('BULLISH' if x['close']>x['open'] else 'BEARISH') if b>=1.25*a else 'NEUTRAL'


def momentum(c):
    a=atr(c)
    if not a or len(c)<8:return 'INSUFFICIENT'
    d=c[-1]['close']-c[-4]['open']
    return 'BULLISH' if d>.8*a else 'BEARISH' if d<-.8*a else 'NEUTRAL'


def sweep(c,n=10):
    if len(c)<n+2:return 'NONE'
    p=c[-n-1:-1]; x=c[-1]; hi=max(z['high'] for z in p); lo=min(z['low'] for z in p)
    if x['high']>hi and x['close']<hi:return 'BUY_SIDE_SWEPT'
    if x['low']<lo and x['close']>lo:return 'SELL_SIDE_SWEPT'
    return 'NONE'


def volatility(c):
    if len(c)<30:return 'INSUFFICIENT'
    r=[x['high']-x['low'] for x in c[-30:]]; q=mean(r[-5:]); b=mean(r[:-5])
    if not b:return 'NORMAL'
    z=q/b
    return 'EXTREME_EXPANSION' if z>=2 else 'EXPANDING' if z>=1.35 else 'COMPRESSED' if z<=.65 else 'NORMAL'


def _pivots(c,left=2,right=2):
    highs=[]; lows=[]
    for i in range(left,len(c)-right):
        h=c[i]['high']; l=c[i]['low']
        if h>max(c[j]['high'] for j in range(i-left,i)) and h>=max(c[j]['high'] for j in range(i+1,i+right+1)): highs.append((i,h))
        if l<min(c[j]['low'] for j in range(i-left,i)) and l<=min(c[j]['low'] for j in range(i+1,i+right+1)): lows.append((i,l))
    return highs,lows


def structure_event(c,lookback=30):
    if len(c)<lookback+5:return {'bos':'NONE','mss':'NONE'}
    p=c[-lookback-1:-1]; x=c[-1]; hi=max(z['high'] for z in p); lo=min(z['low'] for z in p)
    bos='BULLISH' if x['close']>hi else 'BEARISH' if x['close']<lo else 'NONE'
    # MSS is deliberately stricter: sweep/rejection followed by a close through the prior short-term range.
    short=c[-7:-1]; shi=max(z['high'] for z in short); slo=min(z['low'] for z in short)
    mss='BULLISH' if x['close']>shi else 'BEARISH' if x['close']<slo else 'NONE'
    return {'bos':bos,'mss':mss}


def fvg(c):
    if len(c)<3:return 'NONE'
    a,b,x=c[-3],c[-2],c[-1]
    if x['low']>a['high']:return 'BULLISH'
    if x['high']<a['low']:return 'BEARISH'
    return 'NONE'


def equal_levels(c,tol_atr=0.15):
    a=atr(c)
    if not a or len(c)<20:return {'high':False,'low':False}
    highs,lows=_pivots(c[-60:] if len(c)>60 else c)
    hs=[v for _,v in highs[-6:]]; ls=[v for _,v in lows[-6:]]
    eh=any(abs(hs[i]-hs[j])<=tol_atr*a for i in range(len(hs)) for j in range(i) ) if len(hs)>1 else False
    el=any(abs(ls[i]-ls[j])<=tol_atr*a for i in range(len(ls)) for j in range(i) ) if len(ls)>1 else False
    return {'high':eh,'low':el}


def premium_discount(c):
    if len(c)<20:return 'UNKNOWN'
    hi=max(x['high'] for x in c[-50:]); lo=min(x['low'] for x in c[-50:]); mid=(hi+lo)/2; p=c[-1]['close']
    if hi==lo:return 'UNKNOWN'
    return 'PREMIUM' if p>mid+(hi-lo)*0.05 else 'DISCOUNT' if p<mid-(hi-lo)*0.05 else 'EQUILIBRIUM'


def overextension(c):
    a=atr(c)
    if not a or len(c)<20:return 'UNKNOWN'
    e20=ema([x['close'] for x in c],20); d=abs(c[-1]['close']-e20)
    return 'EXTENDED' if d>=2.5*a else 'NORMAL'



def exhaustion(c, direction=None):
    """Estimate whether a directional move is too mature to chase.

    This is a filter, not a reversal predictor. Higher score means worse
    entry location for a fresh continuation entry.
    """
    if len(c) < 25:
        return {'score': 0, 'level': 'UNKNOWN', 'reasons': []}
    a = atr(c, 14)
    e20 = ema([x['close'] for x in c], 20)
    if not a or not e20:
        return {'score': 0, 'level': 'UNKNOWN', 'reasons': []}

    x = c[-1]
    score = 0
    reasons = []
    bullish = direction == 'BULLISH'
    bearish = direction == 'BEARISH'

    # 1) Distance from the short-term mean.
    ema_dist = abs(x['close'] - e20) / a if a else 0
    if ema_dist >= 3.5:
        score += 30; reasons.append(f'EMA20 distance {ema_dist:.1f} ATR (extreme)')
    elif ema_dist >= 2.5:
        score += 22; reasons.append(f'EMA20 distance {ema_dist:.1f} ATR (extended)')
    elif ema_dist >= 2.0:
        score += 12; reasons.append(f'EMA20 distance {ema_dist:.1f} ATR (elevated)')

    # 2) Current range expansion versus the preceding range.
    ranges = [z['high'] - z['low'] for z in c[-25:]]
    base = mean(ranges[:-5]) if len(ranges) > 5 else 0
    recent = mean(ranges[-5:]) if ranges else 0
    expansion = recent / base if base else 0
    if expansion >= 2.0:
        score += 25; reasons.append(f'range expansion {expansion:.1f}x')
    elif expansion >= 1.6:
        score += 16; reasons.append(f'range expansion {expansion:.1f}x')
    elif expansion >= 1.35:
        score += 8; reasons.append(f'range expansion {expansion:.1f}x')

    # 3) Climax candle: unusually large body.
    body = abs(x['close'] - x['open']) / a
    if body >= 2.0:
        score += 20; reasons.append(f'climax body {body:.1f} ATR')
    elif body >= 1.6:
        score += 12; reasons.append(f'large body {body:.1f} ATR')

    # 4) One-sided persistence: repeated candles in the same direction.
    same = 0
    for z in reversed(c[-6:]):
        if bullish and z['close'] > z['open']:
            same += 1
        elif bearish and z['close'] < z['open']:
            same += 1
        else:
            break
    if same >= 5:
        score += 18; reasons.append(f'{same} consecutive directional candles')
    elif same >= 4:
        score += 12; reasons.append(f'{same} consecutive directional candles')
    elif same >= 3:
        score += 6; reasons.append(f'{same} consecutive directional candles')

    # 5) Poor location: chasing into the extreme end of the recent range.
    hi = max(z['high'] for z in c[-30:])
    lo = min(z['low'] for z in c[-30:])
    span = hi - lo
    if span > 0:
        if bullish:
            loc = (x['close'] - lo) / span
            if loc >= .92:
                score += 18; reasons.append('price at upper end of recent range')
            elif loc >= .82:
                score += 10; reasons.append('price near upper end of recent range')
        elif bearish:
            loc = (hi - x['close']) / span
            if loc >= .92:
                score += 18; reasons.append('price at lower end of recent range')
            elif loc >= .82:
                score += 10; reasons.append('price near lower end of recent range')

    # 6) Premium/discount is only a penalty when it agrees with chasing.
    mid=(hi+lo)/2 if span else x['close']
    if bullish and x['close'] > mid + span*.05 and ema_dist >= 2.0:
        score += 8; reasons.append('bullish move stretched in premium')
    elif bearish and x['close'] < mid - span*.05 and ema_dist >= 2.0:
        score += 8; reasons.append('bearish move stretched in discount')

    score=min(100, int(score))
    level='EXTREME' if score>=75 else 'HIGH' if score>=60 else 'ELEVATED' if score>=45 else 'NORMAL'
    return {'score':score,'level':level,'reasons':reasons,'ema_distance_atr':round(ema_dist,3),'range_expansion':round(expansion,3),'body_atr':round(body,3),'same_direction_candles':same}

def summarize(c):
    ev=structure_event(c); eq=equal_levels(c)
    return {
        'count':len(c),'trend':trend(c),'momentum':momentum(c),'displacement':displacement(c),
        'liquidity':sweep(c),'volatility':volatility(c),'close':c[-1]['close'] if c else None,
        'bos':ev['bos'],'mss':ev['mss'],'fvg':fvg(c),'equal_highs':eq['high'],'equal_lows':eq['low'],
        'zone':premium_discount(c),'extension':overextension(c),'exhaustion':exhaustion(c),'atr':atr(c)
    }
