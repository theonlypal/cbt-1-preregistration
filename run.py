"""One-shot CBT-1 executor. No retries, SDK, redirects, tool implementation or follow-up."""
import argparse
import concurrent.futures
import http.client
import itertools
import json
import os
import socket
import ssl
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from common import digest,encode,manifest,parse,utc,write_new
from design import BUDGET,MODEL,RESERVE,ROOT,URL
from observe import bounded_charge,observed
from verify_design import verify

SLUG="theonlypal/cbt-1-preregistration"
TAG="v1.0.0"
SAFE_HEADERS={"date","content-type","content-length","x-request-id","openai-processing-ms",
              "x-ratelimit-limit-requests","x-ratelimit-limit-tokens","x-ratelimit-remaining-requests",
              "x-ratelimit-remaining-tokens","x-ratelimit-reset-requests","x-ratelimit-reset-tokens","retry-after"}

def public_freeze():
    def get(url):
        req=urllib.request.Request(url,headers={"User-Agent":"CBT-1-public-freeze-verifier"})
        with urllib.request.urlopen(req,timeout=30) as r: return r.read()
    api="https://api.github.com/repos/"+SLUG
    if parse(get(api))["private"]: raise ValueError("preregistration must be public")
    ref=parse(get(api+"/git/ref/tags/"+TAG))["object"]
    if ref["type"]!="tag": raise ValueError("annotated tag required")
    tag=parse(get(api+"/git/tags/"+ref["sha"]))
    head=subprocess.check_output(["git","-C",str(ROOT),"rev-parse","HEAD"],text=True).strip()
    if tag["object"]!={"sha":head,"type":"commit","url":api+"/git/commits/"+head}:
        raise ValueError("public tag and checkout disagree")
    source=(ROOT/"SHA256SUMS").read_bytes()
    if source!=manifest(ROOT) or source!=get("https://raw.githubusercontent.com/"+SLUG+"/"+head+"/SHA256SUMS"):
        raise ValueError("source manifest differs from public freeze")
    return {"repository":SLUG,"tag":TAG,"commit":head,"tag_object":ref["sha"],"tag_time":tag["tagger"]["date"],
            "public_checked_utc":utc(),"manifest_sha256":digest(source)}

class Journal:
    def __init__(self,path):
        self.fp=path.open("xb")
        self.previous="0"*64
        self.index=0
    def append(self,kind,**data):
        self.index+=1
        item={"index":self.index,"at":utc(),"previous":self.previous,"event":kind,**data}
        self.previous=digest(encode(item))
        self.fp.write(encode({**item,"hash":self.previous})+b"\n")
        self.fp.flush(); os.fsync(self.fp.fileno())

def capture(key,wire):
    status=None; headers={}; raw=b""; transport=""
    conn=http.client.HTTPSConnection("api.openai.com",timeout=120,context=ssl.create_default_context())
    try:
        conn.request("POST","/v1/chat/completions",body=wire,headers={
            "Authorization":"Bearer "+key,"Content-Type":"application/json","Accept":"application/json",
            "Accept-Encoding":"identity","User-Agent":"CBT-1/1.0.0"})
        res=conn.getresponse()
        status=res.status
        headers={k.lower():v for k,v in res.getheaders() if k.lower() in SAFE_HEADERS}
        try: raw=res.read()
        except http.client.IncompleteRead as e: raw=e.partial; transport="IncompleteRead"
    except (OSError,http.client.HTTPException,ssl.SSLError) as e:
        transport=type(e).__name__
    finally:
        conn.close()
    return status,headers,raw,transport,utc()

def usage_object(raw):
    try:
        obj=parse(raw)
        return obj.get("usage") if type(obj) is dict else None
    except (ValueError,UnicodeError):
        return None

def admission(settled,pending,budget):
    return settled+(pending+1)*RESERVE<=budget

def execute(root,key,ref,rows):
    # mkdir is the process lock. An existing output, even if incomplete, is never resumed.
    root.mkdir(mode=0o700,parents=False,exist_ok=False)
    trialroot=root/"trials"; trialroot.mkdir()
    write_new(root/"freeze.json",encode(ref)+b"\n")
    log=Journal(root/"events.jsonl")
    log.append("run_start",model=MODEL,endpoint=URL,freeze_sha256=digest((root/"freeze.json").read_bytes()),budget_nanodollars=BUDGET)
    settled=0; done_count=0; sent=0; stop=None; op_streak=0
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for block,group in itertools.groupby(rows,key=lambda r:r["block"]):
            if stop: break
            cells=list(group); index=0; active={}
            while active or (not stop and index<len(cells)):
                while not stop and index<len(cells) and len(active)<4 and admission(settled,len(active),BUDGET):
                    row=cells[index]; index+=1; trial=row["trial"]; folder=trialroot/trial; folder.mkdir()
                    wire=(ROOT/"requests"/("-".join([row["system"],row["input"],row["surface"]])+".json")).read_bytes()
                    if digest(wire)!=row["request_sha256"]: raise RuntimeError("wire mismatch")
                    write_new(folder/"request.bin",wire)
                    started=utc()
                    log.append("dispatch",trial=trial,position=int(row["position"]),request_sha256=digest(wire),started=started)
                    sent+=1
                    active[pool.submit(capture,key,wire)]=(row,folder,started)
                    time.sleep(0.15)
                if not active:
                    if not stop and index<len(cells): stop="BUDGET_RESERVATION"
                    break
                completed,_=concurrent.futures.wait(active,return_when=concurrent.futures.FIRST_COMPLETED)
                for future in sorted(completed,key=lambda f:int(active[f][0]["position"])):
                    row,folder,started=active.pop(future)
                    status,headers,raw,transport,finished=future.result()
                    write_new(folder/"response.bin",raw)
                    ob=observed(status,transport,raw)
                    charge=bounded_charge(raw) if not transport else RESERVE
                    settled+=charge
                    rc={"trial":row["trial"],"position":int(row["position"]),"requested_model":MODEL,
                        "started":started,"finished":finished,"http_status":status,"safe_headers":headers,
                        "request_sha256":row["request_sha256"],"response_sha256":digest(raw),
                        "transport":transport,"usage":usage_object(raw),"reserved_charge_nanodollars":charge,"observation":ob}
                    rec=encode(rc)+b"\n"; write_new(folder/"receipt.json",rec)
                    log.append("receipt",trial=row["trial"],receipt_sha256=digest(rec),charge_nanodollars=charge)
                    done_count+=1
                    op_streak=op_streak+1 if ob["class"] in ("OP_HTTP","OP_TRANSPORT","OP_PROTOCOL","ID_MISMATCH") else 0
                    if not stop and (status in (400,401,402,403,404,429) or ob["class"]=="ID_MISMATCH" or op_streak>=4):
                        stop="HTTP_"+str(status) if status in (400,401,402,403,404,429) else ("MODEL_IDENTITY" if ob["class"]=="ID_MISMATCH" else "FOUR_OPERATIONAL_FAILURES")
            if done_count%100==0: print("Recorded",done_count,flush=True)
    state="COMPLETE" if done_count==len(rows) else "INCOMPLETE"
    summary={"state":state,"scheduled":len(rows),"dispatched":sent,"recorded":done_count,"untouched":len(rows)-sent,
             "stop":stop,"accounted_upper_nanodollars":settled}
    log.append("run_end",**summary); log.fp.close()
    write_new(root/"run.json",encode(summary)+b"\n")
    print(encode(summary).decode(),flush=True)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--authorized-usd",required=True,choices=["17.92"])
    p.add_argument("--key-file",required=True,type=Path)
    p.add_argument("--output",required=True,type=Path)
    args=p.parse_args()
    root=args.output.resolve()
    if ROOT==root or ROOT in root.parents or root.exists(): p.error("a new external output directory is required")
    if sys.version_info<(3,9): p.error("Python 3.9+ required")
    rows=verify(); ref=public_freeze()
    lines=args.key_file.read_text().splitlines()
    if len(lines)!=1 or not lines[0].startswith("sk-") or lines[0]!=lines[0].strip(): p.error("invalid key-file format")
    execute(root,lines[0],ref,rows)

if __name__=="__main__": main()
