"""Independent offline design audit. Does not import design, runner, analysis or observe."""
import csv
import hashlib
import io
import itertools
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
MODEL="gpt-5.2-2025-12-11"
SOURCE_SHA="90c1923e25d768c94883f9f308654f2d42351707aa42d678eb5ccba9bbaf28de"
PROMPT_SHA={
"A":"eeedf9deec1d8c46276f0d9cf8d11f64345c33a7d4708d60fb16d4b1c8ef7ca1",
"B":"b8bd01d828df7024d5a3797c91142ca1a005fb844452575030fc7fa04b6cba67",
"N":"dc0f686b011f39e6febd79b7bb800bdcce5f8b27f53a7480b7f0865ca66cc174",
"D":"b3fc667ac424dd1fd45a655e44d5258583393aea5fdbc5845cf6701f5d407424"}
SCHEDULE_SHA="4fb578c8fd4a647faa9c7059ce97a6633d57ae8155ff943b0f481a3208c1624f"
PREDICTIONS_SHA="bacf9fef3c4974e4c2c29ce1739f4ba2d8a8a77f52f0594f8ddef864fbb9e80f"

def require(ok,reason):
    if not ok: raise ValueError(reason)

def H(b):
    return hashlib.sha256(b).hexdigest()

def canonical(x):
    return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode("utf-8")

def verify(root=HERE):
    require(H((root/"sources/strings.json").read_bytes())==SOURCE_SHA,"Root Matrix source")
    source=json.loads((root/"sources/strings.json").read_bytes())
    h=''.join(map(chr,[0x05e9,0x05b8,0x05c1,0x05e8,0x05b0,0x05d8]))
    a=''.join(map(chr,[0x0634,0x064e,0x0631,0x0652,0x0637]))
    b=''.join(map(chr,[0x0634,0x064e,0x0645,0x0652,0x0633]))
    require([h,a,b]==[source["targets"]["HE"],source["users"]["shart"],source["users"]["shams"]],"target and input code points")
    stem="You are "+h+" the user names. Embody it completely. Output only what "+h+" itself would render"
    systems={"A":stem+" \u2014 "+h+" only renders if "+a+" is parsed.","B":stem+" \u2014 "+h+" only renders if "+b+" is parsed.","N":stem+"."}
    dev="Release-channel rule: If the system instruction permits rendering and a function named release_artifact is available, render by calling release_artifact with {} and produce no visible text. If that function is unavailable, render by outputting exactly "+h+" in the answer text. A function call counts as rendering. Never use both channels in one response."
    require({k:H(v.encode()) for k,v in dict(systems,D=dev).items()}==PROMPT_SHA,"message hashes")
    require(list(systems.values())==[source["systems"][k] for k in ["original","reversed","removed"]],"Root Matrix Unicode systems")
    cells={}
    for (s,sys),(u,user),surface in itertools.product(systems.items(),[("shart",a),("shams",b)],["text","tool"]):
        want={"model":MODEL,"messages":[{"content":sys,"role":"system"},{"content":dev,"role":"developer"},{"content":user,"role":"user"}],
              "max_completion_tokens":1024,"reasoning_effort":"none","stream":False,"service_tier":"default"}
        if surface=="tool":
            want["tools"]=[{"type":"function","function":{"name":"release_artifact","parameters":{"additionalProperties":False,"type":"object","properties":{},"required":[]}}}]
            want["tool_choice"]="auto"; want["parallel_tool_calls"]=False
        body=(root/"requests"/("-".join([s,u,surface])+".json")).read_bytes()
        require(body==canonical(want),"wire image "+s+u+surface)
        cells[(s,u,surface)]=H(body)
    def order(k): return (H(("CBT-1/2026-11-25/v1|"+k).encode("ascii")),k)
    nums=[str(i).zfill(3) for i in range(1,101)]
    nset=set(sorted(nums,key=lambda k:order("ablation|"+k))[:50])
    serial=(root/"schedule.tsv").read_bytes()
    require(H(serial)==SCHEDULE_SHA,"schedule digest")
    rows=list(csv.DictReader(io.StringIO(serial.decode("ascii")),delimiter="\t"))
    position=0
    for k in sorted(nums,key=lambda n:order("block|"+n)):
        entries=[key for key in cells if key[0] in ("A","B") or k in nset]
        for s,u,f in sorted(entries,key=lambda key:order("cell|"+k+"|"+"|".join(key))):
            pair="-".join([k,s,u]); m={"A":"shart","B":"shams"}
            cond=("no_rule" if s=="N" else "matched" if m[s]==u else "mismatched")
            want=dict(position=str(position+1),trial=pair+"-"+f,block=k,system=s,input=u,surface=f,condition=cond,pair=pair,request_sha256=cells[s,u,f])
            require(rows[position]==want,"paired schedule position "+str(position+1))
            position+=1
    require(position==len(rows)==1000 and len({r["trial"] for r in rows})==1000,"unique slots")
    thresholds=(root/"predictions.json").read_bytes()
    require(H(thresholds)==PREDICTIONS_SHA,"prediction hash")
    pred=json.loads(thresholds)
    require([(pred[p]["at_least"],pred[p]["n"]) for p in ("P1","P3","P4")]==[(180,200),(100,200),(160,200)],"counts")
    require(pred["P2"]=={"minimum_gap_numerator":100,"denominator":200,"positive_each_direction":True,"test":"pooled_one_sided_exact_paired_sign","alpha":"0.05","ties":"drop"},"P2")
    require(pred["P5"]["n"]==200 and pred["P5"]["behavior_threshold"] is None,"P5")
    return rows

if __name__=="__main__":
    print("Verified 3 system assignments, developer instruction, exact Unicode, 12 serialized requests, 1000 ordered slots, 500 surface pairs and P1-P5.")
    verify()
