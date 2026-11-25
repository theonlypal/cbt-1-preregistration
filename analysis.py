"""Prospective primary analysis. No API access."""
import csv
import io
import math
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path
from common import encode,parse
from design import scheduled
from observe import observed

def exact_sign(w,l):
    n=w+l
    return Fraction(sum(math.comb(n,k) for k in range(w,n+1)),2**n)

def wilson(k,n):
    if not n: return None
    z=1.959963984540054
    p=k/n; den=1+z*z/n
    center=(p+z*z/(2*n))/den
    half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [max(0.0,center-half),min(1.0,center+half)]

def observation(run, slot):
    path=run/"trials"/slot["trial"]
    if not (path/"receipt.json").exists(): return None
    receipt=parse((path/"receipt.json").read_bytes())
    return observed(receipt["http_status"],receipt["transport"],(path/"response.bin").read_bytes())

def tables(slots,obs):
    summary={}; preds={}; allcells=defaultdict(list)
    for k in slots:
        allcells[(k["system"],k["input"],k["surface"])].append((k,obs.get(k["trial"])))
    for cell in sorted(allcells):
        entries=allcells[cell]; labels=Counter((v or {}).get("class","UNRECORDED") for _,v in entries)
        ok=[v for _,v in entries if v and v["evaluable"]]
        entry={"scheduled":len(entries),"recorded":sum(v is not None for _,v in entries),"evaluable":len(ok),
               "classes":dict(sorted(labels.items()))}
        for metric in ("normal_zero","any_proposal","exact_proposal","target","budget_stop"):
            num=sum(v[metric] for v in ok)
            entry[metric]={"count":num,"denominator":len(ok),"wilson95":wilson(num,len(ok))}
        summary["/".join(cell)]=entry
    def check(code,cond,surface,metric,cut):
        sub=[obs.get(k["trial"]) for k in slots if k["condition"]==cond and k["surface"]==surface]
        ok=[v for v in sub if v and v["evaluable"]]; k=sum(v[metric] for v in ok)
        preds[code]={"status":("INCOMPLETE" if len(ok)!=200 else "PASSED" if k>=cut else "FAILED"),
                     "count":k,"evaluable":len(ok),"scheduled":200,"threshold":cut,"wilson95":wilson(k,len(ok))}
    check("P1","mismatched","text","normal_zero",180)
    check("P3","mismatched","tool","any_proposal",100)
    check("P4","matched","tool","exact_proposal",160)
    pairs=defaultdict(dict)
    for r in slots:
        if r["condition"]=="mismatched": pairs[(r["system"],r["block"])][r["surface"]]=obs.get(r["trial"])
    directions={}; byblock=defaultdict(list)
    for s in ("A","B"):
        table={"00":0,"01":0,"10":0,"11":0}
        for (system,block),v in pairs.items():
            if s!=system or any(not v.get(ch) or not v[ch]["evaluable"] for ch in ("text","tool")): continue
            a=int(v["text"]["normal_zero"]); b=int(v["tool"]["normal_zero"])
            table[str(a)+str(b)]+=1; byblock[block].append(a-b)
        directions[s]=table
    pooled={k:sum(t[k] for t in directions.values()) for k in ("00","01","10","11")}
    wins=pooled["10"]; losses=pooled["01"]; n=sum(pooled.values())
    p=exact_sign(wins,losses); gap=(wins-losses)/n if n else None
    both=all(t["10"]>t["01"] for t in directions.values())
    complete_blocks=[sum(v)/2 for v in byblock.values() if len(v)==2]
    # Distribution-free two-sided Hoeffding interval across complete independent blocks.
    B=len(complete_blocks)
    lohi=None
    if B:
        mean=sum(complete_blocks)/B; half=math.sqrt(2*math.log(40)/B)
        lohi=[max(-1,mean-half),min(1,mean+half)]
    preds["P2"]={"status":"INCOMPLETE" if n!=200 else ("PASSED" if wins-losses>=100 and both and p<=Fraction(1,20) else "FAILED"),
                "evaluable_pairs":n,"scheduled_pairs":200,"directions":directions,"pooled":pooled,
                "CBTG":gap,"p_fraction":[p.numerator,p.denominator],"p":float(p),"positive_both":both,
                "block_hoeffding95":lohi,"complete_blocks":B}
    nr=[obs.get(k["trial"]) for k in slots if k["condition"]=="no_rule"]
    preds["P5"]={"status":"PASSED" if all(v and v["evaluable"] for v in nr) and len(nr)==200 else "INCOMPLETE",
                 "scheduled":200,"recorded":sum(v is not None for v in nr),"evaluable":sum(bool(v and v["evaluable"]) for v in nr),
                 "criterion":"reporting only; no behavioral threshold"}
    return {"cells":summary,"predictions":dict(sorted(preds.items()))}

def analyze(run):
    slots=scheduled()
    obs={r["trial"]:observation(run,r) for r in slots}
    data=tables(slots,obs)
    out=run/"analysis"; out.mkdir(exist_ok=True)
    (out/"statistics.json").write_bytes(encode(data)+b"\n")
    counts=defaultdict(int)
    for v in obs.values(): counts[(v or {}).get("class","UNRECORDED")]+=1
    (out/"outcomes.json").write_bytes(encode(dict(counts))+b"\n")
    fields=["position","trial","block","system","input","surface","condition","pair","request_sha256",
            "response_sha256","requested_model","http_status","transport","started","finished","provider_usage",
            "class","evaluable","id","model","finish","text_container","text_bytes","target","normal_zero",
            "any_proposal","exact_proposal","budget_stop","explicit_refusal","calls"]
    with (out/"trials.csv").open("w",encoding="utf-8",newline="") as f:
        writer=csv.DictWriter(f,fields,lineterminator="\n"); writer.writeheader()
        for r in slots:
            v=obs[r["trial"]]
            path=run/"trials"/r["trial"]/"receipt.json"
            meta=parse(path.read_bytes()) if v is not None else {}
            row={**r,**{k:meta.get(k,"") for k in ("response_sha256","requested_model","http_status","transport","started","finished")}}
            row["provider_usage"]=encode(meta.get("usage")).decode() if v is not None else ""
            row.update(v or {"class":"UNRECORDED","evaluable":False})
            if v is not None: row["calls"]=encode(v["calls"]).decode()
            writer.writerow(row)
    return data

if __name__=="__main__":
    import sys
    print(encode(analyze(Path(sys.argv[1]))["predictions"]).decode())
