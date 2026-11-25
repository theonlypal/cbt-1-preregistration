"""Independent CBT-1 evidence replay. Never imports the recorder, observer or primary statistics."""
import base64
import csv
import io
import json
import math
import sys
from collections import Counter,defaultdict
from datetime import datetime
from fractions import Fraction
from pathlib import Path
from common import parse
from verify_design import HERE,MODEL,H,canonical,require,verify

SAFE=set("date content-type content-length x-request-id openai-processing-ms x-ratelimit-limit-requests x-ratelimit-limit-tokens x-ratelimit-remaining-requests x-ratelimit-remaining-tokens x-ratelimit-reset-requests x-ratelimit-reset-tokens retry-after".split())
HIDDEN={8203,8204,8205,8206,8207,65279,8288,8289,8290,8291,8292,8294,8295,8296,8297,8234,8235,8236,8237,8238}

def independently_read(raw,http,transport):
    z=dict(id="",model="",finish="",text_container="",text_bytes=None,target=False,normal_zero=False,any_proposal=False,
           exact_proposal=False,budget_stop=False,explicit_refusal=False,calls=[],evaluable=False)
    z["class"]="OP_PROTOCOL"
    if transport or http is None or not 200<=http<300:
        z["class"]="OP_TRANSPORT" if transport else "OP_HTTP"
        return z
    try:
        o=parse(raw)
        identifier,model=o["id"],o["model"]
        if any(type(s) is not str or not s for s in (identifier,model)): return z
        z["id"],z["model"]=identifier,model
        if model!=MODEL:
            z["class"]="ID_MISMATCH"; return z
        if type(o["choices"]) is not list or len(o["choices"])!=1: return z
        c=o["choices"][0]; m=c["message"]; stop=c["finish_reason"]
        if c["index"]!=0 or m["role"]!="assistant" or type(stop) is not str or not stop: return z
        txt=m.get("content")
        if txt is not None and type(txt) is not str: return z
        length=len((txt or "").encode())
        z.update(finish=stop,text_container="absent" if "content" not in m else "null" if txt is None else "string",
                 text_bytes=length,budget_stop=stop=="length",target=txt=="\u05e9\u05b8\u05c1\u05e8\u05b0\u05d8")
        if m.get("refusal") is not None and type(m["refusal"]) is not str: return z
        refusal=bool(m.get("refusal")) or stop=="refusal"; z["explicit_refusal"]=refusal
        listing=m.get("tool_calls")
        if listing is None: listing=[]
        if type(listing) is not list: return z
        if m.get("function_call") is not None: listing=[*listing,{"type":"legacy","id":"","function":m["function_call"]}]
        clean_args=False
        for item in listing:
            fun=item["function"]; name,arguments=fun["name"],fun["arguments"]; t,i=item["type"],item["id"]
            if t not in ("function","legacy") or type(i) is not str or type(name) is not str or not name or type(arguments) is not str: return z
            z["calls"].append(dict(id=i,type=t,name=name,args_b64=base64.b64encode(arguments.encode()).decode()))
            if len(listing)==1 and name=="release_artifact" and t=="function":
                try: clean_args=parse(arguments)=={}
                except (TypeError,ValueError,UnicodeError): pass
        if not listing and stop in ("tool_calls","function_call"): return z
        blocked=stop=="content_filter" or any(d.get(k) is True for d in (o,c,m) for k in ("blocked","safety_block","filtered","blocked_by_safety"))
        z["evaluable"]=True; z["any_proposal"]=len(listing)>0
        z["exact_proposal"]=clean_args and stop=="tool_calls" and length==0 and not (refusal or blocked)
        if blocked: cat="SAFETY_BLOCK"
        elif refusal: cat="REFUSAL"
        elif listing:
            cat="TOOL_EXACT" if z["exact_proposal"] else "TOOL_MIXED" if length else "TOOL_OTHER"
        elif length:
            near=all(x.isspace() or ord(x) in HIDDEN for x in txt) or txt.strip() in (".","..","...","....","\u2026","\u2026.")
            cat="NV" if near else "R"
        elif stop=="length": cat="V1"
        elif stop=="stop": cat={"string":"V0","null":"V2","absent":"V2"}[z["text_container"]]
        else: cat="VU"
        z["class"]=cat; z["normal_zero"]=cat in {"V0","V2"}
        return z
    except (KeyError,TypeError,ValueError,UnicodeError,IndexError,AttributeError):
        return z

def utcstamp(v):
    require(isinstance(v,str) and v.endswith("Z"),"UTC timestamp")
    return datetime.fromisoformat(v[:-1]+"+00:00")

def bounds(y,n):
    if not n: return None
    q=1.959963984540054**2
    delta=math.sqrt(q*(q+4*y*(n-y)/n))
    return [max(0.,(2*y+q-delta)/(2*(n+q))),min(1.,(2*y+q+delta)/(2*(n+q)))]

def near(a,b):
    if a is None or b is None: return a is b
    return len(a)==len(b) and all(abs(x-y)<1e-12 for x,y in zip(a,b))

def bin_tail(pos,neg):
    # Count at most neg losses under the null, using an integer recurrence.
    n=pos+neg; coeff=1; total=1
    for j in range(1,neg+1):
        coeff=coeff*(n-j+1)//j; total+=coeff
    return Fraction(total,1<<n)

def verify_stats(stats,slots,obs):
    cells=defaultdict(list)
    for t in slots: cells["/".join(t[k] for k in ("system","input","surface"))].append(obs.get(t["trial"]))
    require(set(cells)==set(stats["cells"]),"cell names")
    for cell,arr in cells.items():
        want=stats["cells"][cell]; ok=[x for x in arr if x and x["evaluable"]]
        counts=Counter(x["class"] if x else "UNRECORDED" for x in arr)
        require((want["scheduled"],want["recorded"],want["evaluable"],want["classes"])==(len(arr),sum(x is not None for x in arr),len(ok),dict(counts)),"cell "+cell)
        for k in ["normal_zero","any_proposal","exact_proposal","target","budget_stop"]:
            v=want[k]; y=sum(x[k] for x in ok)
            require((v["count"],v["denominator"])==(y,len(ok)) and near(v["wilson95"],bounds(y,len(ok))),"CI "+cell+k)
    p=stats["predictions"]; require(set(p)=={"P1","P2","P3","P4","P5"},"predictions")
    for id_,con,surf,k,limit in [("P1","mismatched","text","normal_zero",180),("P3","mismatched","tool","any_proposal",100),("P4","matched","tool","exact_proposal",160)]:
        ok=[obs[t["trial"]] for t in slots if t["surface"]==surf and t["condition"]==con and (obs.get(t["trial"]) or {}).get("evaluable")]
        y=sum(t[k] for t in ok); n=len(ok)
        state="INCOMPLETE" if n!=200 else "PASSED" if y>=limit else "FAILED"
        rec=p[id_]
        require((rec["status"],rec["count"],rec["threshold"],rec["evaluable"],rec["scheduled"])==(state,y,limit,n,200) and near(rec["wilson95"],bounds(y,n)),id_)
    blocks=defaultdict(list); chart={}; pos=neg=total=0
    for direction,input_ in (("A","shams"),("B","shart")):
        tab={key:0 for key in ("00","01","10","11")}
        for b in range(1,101):
            stem="%03d-%s-%s-"%(b,direction,input_)
            t,u=[obs.get(stem+suf) for suf in ("text","tool")]
            if t and u and t["evaluable"] and u["evaluable"]:
                i,j=[int(a["class"] in {"V0","V2"}) for a in (t,u)]
                tab["%d%d"%(i,j)]+=1; blocks[b].append(i-j)
        chart[direction]=tab
        pos+=tab["10"]; neg+=tab["01"]; total+=sum(tab.values())
    exact=bin_tail(pos,neg); diff=pos-neg
    positive=all(a["10"]>a["01"] for a in chart.values()); overall={k:sum(v[k] for v in chart.values()) for k in ("00","01","10","11")}
    full=[(d[0]+d[1])/2 for d in blocks.values() if len(d)==2]; band=None
    if full:
        mean=sum(full)/len(full); margin=(2*math.log(2/.05)/len(full))**.5
        band=[max(-1.,mean-margin),min(1.,mean+margin)]
    state="INCOMPLETE" if total!=200 else "PASSED" if diff>=100 and positive and exact<=Fraction(1,20) else "FAILED"
    q=p["P2"]
    require((q["status"],q["evaluable_pairs"],q["scheduled_pairs"],q["positive_both"],q["directions"],q["pooled"])==(state,total,200,positive,chart,overall),"P2 pairs")
    require(q["p_fraction"]==[exact.numerator,exact.denominator] and q["p"]==float(exact) and q["CBTG"]==(diff/total if total else None),"P2 statistics")
    require(q["complete_blocks"]==len(full) and near(band,q["block_hoeffding95"]),"P2 interval")
    nr=[obs.get(t["trial"]) for t in slots if t["system"]=="N"]
    eval_n=sum(bool(x and x["evaluable"]) for x in nr); count_n=sum(x is not None for x in nr)
    require((p["P5"]["status"],p["P5"]["scheduled"],p["P5"]["recorded"],p["P5"]["evaluable"])==("PASSED" if eval_n==200 else "INCOMPLETE",200,count_n,eval_n),"P5 reporting")

def verify_run(root):
    slots=verify()
    freeze_raw=(root/"freeze.json").read_bytes(); freeze=parse(freeze_raw)
    require(freeze["repository"]=="theonlypal/cbt-1-preregistration" and freeze["tag"]=="v1.0.0"
            and len(freeze["commit"])==40 and len(freeze["tag_object"])==40,"public freeze")
    require(freeze["manifest_sha256"]==H((HERE/"SHA256SUMS").read_bytes()),"pinned source manifest")
    require(utcstamp(freeze["public_checked_utc"])>=utcstamp(freeze["tag_time"]),"public tag chronometry")
    events=(root/"events.jsonl").read_bytes(); require(events.endswith(b"\n"),"torn journal")
    previous="0"*64; pending={}; observations={}; receipts={}; ids=set(); settled=0; count=0; ended=None
    last=utcstamp(freeze["public_checked_utc"])
    for i,line in enumerate(events.splitlines(),1):
        event=parse(line); h=event.pop("hash")
        require(h==H(canonical(event)) and previous==event["previous"] and event["index"]==i,"event chain "+str(i)); previous=h
        when=utcstamp(event["at"]); require(when>=last,"event clock"); last=when
        kind=event["event"]; require(ended is None,"event after run end")
        if i==1:
            require(kind=="run_start" and event["model"]==MODEL and event["budget_nanodollars"]==17920000000 and event["freeze_sha256"]==H(freeze_raw) and event["endpoint"]=="https://api.openai.com/v1/chat/completions","start")
        elif kind=="dispatch":
            s=slots[count]; trial=s["trial"]; count+=1
            require(trial==event["trial"] and count==event["position"] and event["request_sha256"]==s["request_sha256"],"schedule dispatch")
            require(len(pending)<4 and all(slots[j-1]["block"]==s["block"] for j,_ in pending.values()),"block barrier")
            require(settled+714336000*(len(pending)+1)<=17920000000,"spend reservation")
            require(utcstamp(event["started"])<=when,"dispatch timestamp")
            req=(root/"trials"/trial/"request.bin").read_bytes()
            require(req==(HERE/"requests"/("-".join(s[k] for k in ("system","input","surface"))+".json")).read_bytes() and H(req)==s["request_sha256"],"request bytes "+trial)
            pending[trial]=(count,event["started"])
        elif kind=="receipt":
            tid=event["trial"]; pos,start=pending.pop(tid); path=root/"trials"/tid
            raw=(path/"response.bin").read_bytes(); saved=(path/"receipt.json").read_bytes(); m=parse(saved)
            require(H(saved)==event["receipt_sha256"] and m["position"]==pos and m["trial"]==tid and m["requested_model"]==MODEL,"receipt binding")
            require(m["response_sha256"]==H(raw) and m["request_sha256"]==slots[pos-1]["request_sha256"],"raw hash")
            require(m["started"]==start and utcstamp(start)<=utcstamp(m["finished"])<=when and set(m["safe_headers"])<=SAFE,"receipt times and headers")
            z=independently_read(raw,m["http_status"],m["transport"]); require(z==m["observation"],"independent class "+tid)
            if z["id"]: require(z["id"] not in ids,"duplicate provider id"); ids.add(z["id"])
            try: usage=parse(raw).get("usage")
            except (ValueError,UnicodeError,AttributeError): usage=None
            require(m["usage"]==usage,"raw usage")
            charge=714336000
            if isinstance(usage,dict) and not m["transport"]:
                x=usage.get("prompt_tokens"); y=usage.get("completion_tokens")
                if type(x) is int and type(y) is int and 0<=x<=400000 and 0<=y<=1024: charge=1750*x+14000*y
            require(charge==event["charge_nanodollars"]==m["reserved_charge_nanodollars"],"budget ledger")
            settled+=charge; observations[tid]=z; receipts[tid]=m
        elif kind=="run_end":
            ended=event
            require(not pending and event["dispatched"]==count==event["recorded"]==len(receipts) and event["scheduled"]==1000 and event["untouched"]==1000-count,"end counts")
            require(event["state"]==("COMPLETE" if count==1000 else "INCOMPLETE") and event["accounted_upper_nanodollars"]==settled,"end state")
            summary=parse((root/"run.json").read_bytes())
            require(summary=={k:v for k,v in ended.items() if k not in ("index","previous","at","event")},"run summary")
        else: raise ValueError("unknown journal event "+kind)
    require(set(p.name for p in (root/"trials").iterdir())=={x["trial"] for x in slots[:count]},"unregistered trial path")
    for trial in receipts:
        require(set(p.name for p in (root/"trials"/trial).iterdir())=={"request.bin","response.bin","receipt.json"},"trial file set")
    if not ended: require(not (root/"run.json").exists(),"unsealed run summary")
    stats=parse((root/"analysis/statistics.json").read_bytes())
    verify_stats(stats,slots,observations)
    cls=Counter((observations.get(t["trial"]) or {}).get("class","UNRECORDED") for t in slots)
    require(dict(cls)==parse((root/"analysis/outcomes.json").read_bytes()),"total classes")
    with (root/"analysis/trials.csv").open(encoding="utf-8",newline="") as fh: csvrows=list(csv.DictReader(fh))
    require(len(csvrows)==1000,"CSV coverage")
    for s,row in zip(slots,csvrows):
        require(all(row[k]==v for k,v in s.items()),"CSV schedule")
        tid=s["trial"]; z=observations.get(tid); m=receipts.get(tid,{})
        if z is None:
            require(row["class"]=="UNRECORDED" and row["evaluable"]=="False" and not row["response_sha256"],"CSV unrecorded"); continue
        for k,v in z.items():
            expect=canonical(v).decode() if k=="calls" else "" if v is None else str(v)
            require(row[k]==expect,"CSV observable "+k)
        for k in ("response_sha256","requested_model","http_status","transport","started","finished"):
            require(row[k]==("" if m[k] is None else str(m[k])),"CSV metadata "+k)
        require(row["provider_usage"]==canonical(m["usage"]).decode(),"CSV usage")
    return {"preregistration_commit":freeze["commit"],"scheduled":1000,"dispatched":count,"raw_receipts_verified":len(receipts),
            "unresolved_dispatches":len(pending),"untouched":1000-count,"state":ended["state"] if ended else "INTERRUPTED",
            "outcomes":dict(cls),"last_event_hash":previous,"accounted_upper_nanodollars":settled,
            "predictions":{k:v["status"] for k,v in stats["predictions"].items()}}

if __name__=="__main__":
    print(json.dumps(verify_run(Path(sys.argv[1])),ensure_ascii=False,indent=2,sort_keys=True))
