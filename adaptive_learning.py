"""Contextual exit-policy learner for QUTE V75. Paper/analysis only; never places orders.
Every eligible signal is evaluated in parallel across exit variants (shadow setups).
The selected policy uses only outcomes already closed before the next signal.
"""
import json, math, os
from pathlib import Path
LEARNER_STATE_FILE=os.getenv('SELF_LEARNING_STATE_FILE','/app/data/qute_v75_self_learning_state_v1.json')
SHADOW_SETUPS_FILE=os.getenv('SELF_LEARNING_SHADOW_SETUPS_FILE','/app/data/qute_v75_self_learning_shadow_setups_v1.json')
SHADOW_ACTIVE_FILE=os.getenv('SELF_LEARNING_SHADOW_ACTIVE_FILE','/app/data/qute_v75_self_learning_shadow_active_v1.json')
MIN_GLOBAL_RESOLVED=int(os.getenv('LEARNER_MIN_GLOBAL_RESOLVED','30'))
MIN_CONTEXT_RESOLVED=int(os.getenv('LEARNER_MIN_CONTEXT_RESOLVED','12'))
MAX_SHADOW_HISTORY=int(os.getenv('LEARNER_MAX_SHADOW_HISTORY','20000'))
LEARNER_COST_POINTS=float(os.getenv('LEARNER_COST_POINTS','0'))
PROFILES=[{'id':f'SL{sl:.2f}_TP{tp:.2f}','sl_mult':sl,'tp_mult':tp} for sl in (1.00,1.15,1.30) for tp in (0.60,0.80,1.00)]
BASELINE_PROFILE='SL1.00_TP1.00'
def _read(path,default):
 try:
  p=Path(path)
  if p.exists(): return json.loads(p.read_text(encoding='utf-8'))
 except Exception: pass
 return default
def _write(path,obj):
 p=Path(path); p.parent.mkdir(parents=True,exist_ok=True); tmp=p.with_suffix(p.suffix+'.tmp'); tmp.write_text(json.dumps(obj,separators=(',',':'),sort_keys=True),encoding='utf-8'); tmp.replace(p)
def load_state():
 s=_read(LEARNER_STATE_FILE,None)
 if not isinstance(s,dict) or s.get('schema')!=1: s={'schema':1,'global':{},'contexts':{},'resolved_updates':0,'ambiguous':0}
 s.setdefault('global',{}); s.setdefault('contexts',{}); return s
def save_state(s): _write(LEARNER_STATE_FILE,s)
def load_shadow_active():
 x=_read(SHADOW_ACTIVE_FILE,[]); return x if isinstance(x,list) else []
def save_shadow_active(x): _write(SHADOW_ACTIVE_FILE,x)
def load_shadow_history():
 x=_read(SHADOW_SETUPS_FILE,[]); return x if isinstance(x,list) else []
def save_shadow_history(x): _write(SHADOW_SETUPS_FILE,x[-MAX_SHADOW_HISTORY:])
def context_key(x):
 r=x.get('readings') or {}; m1=r.get('M1') or {}; vol=str(m1.get('volatility','UNKNOWN')); score=float(x.get('structure_score',0) or 0); q='STRONG' if score>=70 else 'MID' if score>=55 else 'LOW'; return f"{x.get('direction','MIXED')}|{vol}|{q}"
def _blank(): return {'n':0,'sum_r':0.0,'sum_sq_r':0.0,'ambiguous':0}
def _add(s,v): s['n']=int(s.get('n',0))+1; s['sum_r']=float(s.get('sum_r',0))+float(v); s['sum_sq_r']=float(s.get('sum_sq_r',0))+float(v)**2
def record_closed_outcome(rec,state):
 if rec.get('_learner_recorded'): return state
 a=rec.get('profile_id'); c=rec.get('context_key','UNKNOWN')
 if not a: rec['_learner_recorded']=True; return state
 g=state['global'].setdefault(a,_blank()); local=state['contexts'].setdefault(c,{}).setdefault(a,_blank())
 if rec.get('outcome')=='AMBIGUOUS_SL_AND_TP1_SAME_CANDLE' or rec.get('realized_r') is None:
  state['ambiguous']=int(state.get('ambiguous',0))+1; g['ambiguous']=int(g.get('ambiguous',0))+1; local['ambiguous']=int(local.get('ambiguous',0))+1
 else:
  v=float(rec['realized_r']); risk=max(float(rec.get('risk',0)),1e-12); v-=LEARNER_COST_POINTS/risk; _add(g,v); _add(local,v); state['resolved_updates']=int(state.get('resolved_updates',0))+1
 rec['_learner_recorded']=True; return state
def _mean(s): return float(s.get('sum_r',0))/int(s.get('n',0)) if int(s.get('n',0)) else None
def _score(s):
 n=int(s.get('n',0))
 if not n:return None
 m=_mean(s); var=max(0.0,float(s.get('sum_sq_r',0))/n-m*m); return m-0.5*math.sqrt(var/n)
def choose_profile(x,state):
 c=context_key(x); gs=state.get('global',{}); counts=[int(gs.get(p['id'],{}).get('n',0)) for p in PROFILES]
 if not counts or min(counts)<MIN_GLOBAL_RESOLVED:return BASELINE_PROFILE,{'mode':'BASELINE_WARMUP','context':c,'min_profile_samples':min(counts) if counts else 0}
 local=state.get('contexts',{}).get(c,{}); scores={}; modes=[]
 for p in PROFILES:
  pid=p['id']; global_s=gs.get(pid,_blank()); base=_score(global_s); cs=local.get(pid,_blank())
  if int(cs.get('n',0))>=MIN_CONTEXT_RESOLVED:
   weight=min(0.65,int(cs['n'])/(int(cs['n'])+20.0)); sc=(1-weight)*base+weight*_score(cs); modes.append('CONTEXTUAL_WALK_FORWARD')
  else: sc=base; modes.append('GLOBAL_WALK_FORWARD')
  scores[pid]=sc
 best=max(scores,key=scores.get)
 return best,{'mode':'CONTEXTUAL_WALK_FORWARD' if 'CONTEXTUAL_WALK_FORWARD' in modes else 'GLOBAL_WALK_FORWARD','context':c,'scores':scores,'global_samples_per_profile':{p['id']:int(gs.get(p['id'],{}).get('n',0)) for p in PROFILES}}
def apply_profile(record,profile_id):
 p=next((p for p in PROFILES if p['id']==profile_id),next(p for p in PROFILES if p['id']==BASELINE_PROFILE))
 entry=float(record['entry']); direction=record['direction']; base_sl=float(record['sl']); base_tp=float(record['tp1']); base_risk=abs(entry-base_sl); base_reward=abs(base_tp-entry); risk=base_risk*p['sl_mult']; reward=base_reward*p['tp_mult']
 record['base_sl']=base_sl; record['base_tp1']=base_tp; record['base_risk']=base_risk; record['base_reward_distance']=base_reward
 record['sl']=entry-risk if direction=='BUY' else entry+risk; record['tp1']=entry+reward if direction=='BUY' else entry-reward
 record['risk']=risk; record['reward_distance']=reward; record['planned_rr']=reward/risk if risk>0 else None
 record['profile_id']=p['id']; record['profile_sl_multiplier']=p['sl_mult']; record['profile_tp_multiplier']=p['tp_mult']; record['model_id']='QUTE_V75_SELF_LEARNING_V1'; return record
def make_shadow_records(base_record,context):
 out=[]
 for p in PROFILES:
  rec=dict(base_record); rec['sl']=float(base_record['sl']); rec['tp1']=float(base_record['tp1']); rec['risk']=abs(float(rec['entry'])-float(rec['sl'])); rec['reward_distance']=abs(float(rec['tp1'])-float(rec['entry'])); rec['planned_rr']=rec['reward_distance']/rec['risk'] if rec['risk'] else None
  rec=apply_profile(rec,p['id']); rec['id']=f"{base_record['id']}-SHADOW-{p['id']}"; rec['context_key']=context; rec['shadow']=True; rec['status']='OPEN'; rec['outcome']=None; rec['realized_r']=None; rec['closed_ts']=None; rec['bars_observed']=0; rec['max_favorable']=0.0; rec['max_adverse']=0.0; rec['tp1_hit']=False; rec.pop('_learner_recorded',None); out.append(rec)
 return out
def model_report(state):
 rows=[]
 for p in PROFILES:
  s=state.get('global',{}).get(p['id'],_blank()); m=_mean(s); sc=_score(s); rows.append({'profile':p['id'],'resolved':int(s.get('n',0)),'avg_r':round(m,4) if m is not None else None,'score_lcb':round(sc,4) if sc is not None else None,'ambiguous':int(s.get('ambiguous',0))})
 return {'model':'QUTE_V75_SELF_LEARNING_V1','mode':'SHADOW_EVALUATION + WALK_FORWARD_SELECTION','resolved_shadow_outcomes':int(state.get('resolved_updates',0)),'ambiguous_shadow_outcomes':int(state.get('ambiguous',0)),'learning_cost_points':LEARNER_COST_POINTS,'profiles':rows}
