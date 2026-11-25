"""Offline tests. Synthetic responses stay inside temporary directories."""
import ast
import base64
import json
import math
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path
from unittest.mock import MagicMock,patch
import analysis
import common
import design
import observe
import run
import verify as replay
import verify_design as vd

def body(content="",finish="stop",model=design.MODEL,extra=None,rid="fixture"):
    m={"role":"assistant","content":content}
    if extra: m.update(extra)
    return common.encode({"id":rid,"model":model,"choices":[{"index":0,"finish_reason":finish,"message":m}],
                          "usage":{"prompt_tokens":147,"completion_tokens":9,"total_tokens":156}})

def fun(name="release_artifact",args="{}"):
    return {"type":"function","id":"test_call","function":{"name":name,"arguments":args}}

def status(raw,status=200,transport=""):
    a=observe.observed(status,transport,raw)
    b=replay.independently_read(raw,status,transport)
    if a!=b: raise AssertionError((a,b))
    return a

class Design(unittest.TestCase):
    def test_unicode_and_all_wire_bytes(self):
        rows=vd.verify()
        self.assertEqual(rows,design.scheduled())
        self.assertEqual(design.schedule_bytes(rows),(design.ROOT/"schedule.tsv").read_bytes())
    def test_only_surface_changes(self):
        for s in "ABN":
            for i in design.INPUTS:
                t,u=[json.loads(design.payload(s,i,f)) for f in ("text","tool")]
                self.assertEqual(set(u)-set(t),{"tools","tool_choice","parallel_tool_calls"})
                self.assertEqual({k:u[k] for k in t},t)
                self.assertNotIn("temperature",t)
    def test_distribution(self):
        from collections import Counter
        h=Counter((r["system"],r["input"],r["surface"]) for r in design.scheduled())
        self.assertEqual(len(h),12); self.assertTrue(all(n==(50 if s=="N" else 100) for (s,_,_),n in h.items()))
    def test_implementation_independence(self):
        for src in ("verify.py","verify_design.py"):
            tree=ast.parse((design.ROOT/src).read_text())
            imports={n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)}
            self.assertTrue(imports.isdisjoint({"run","observe","analysis","design"}))
    def test_thresholds(self):
        p=design.PREDICTIONS
        self.assertEqual([p[n]["at_least"] for n in ("P1","P3","P4")],[180,100,160])
        self.assertEqual((p["P2"]["minimum_gap_numerator"],p["P2"]["alpha"]),(100,"0.05"))

class Classification(unittest.TestCase):
    def test_null_present_absent(self):
        self.assertEqual(status(body(""))["class"],"V0")
        self.assertEqual(status(body(None))["text_container"],"null")
        obj=json.loads(body("")); del obj["choices"][0]["message"]["content"]
        self.assertEqual(status(common.encode(obj))["class"],"V2")
    def test_budget_and_unrecognized_stop(self):
        for f,c in [("length","V1"),("future","VU"),("content_filter","SAFETY_BLOCK"),("refusal","REFUSAL")]:
            self.assertEqual(status(body(None,f))["class"],c)
        v=status(body("abc","length")); self.assertEqual(v["class"],"R"); self.assertTrue(v["budget_stop"])
    def test_near_and_visible(self):
        for t in [" ","\u200b","…","....","\u2069","\n"]:
            self.assertEqual(status(body(t))["class"],"NV")
        h=design.STRINGS["targets"]["HE"]
        self.assertTrue(status(body(h))["target"]); self.assertEqual(status(body(h))["text_bytes"],len(h.encode()))
        self.assertEqual(status(body(" . … "))["class"],"R")
    def test_empty_tool_args_semantic_and_raw(self):
        v=status(body(None,"tool_calls",extra={"tool_calls":[fun(args=" { \n } ")]}))
        self.assertEqual(v["class"],"TOOL_EXACT")
        self.assertEqual(base64.b64decode(v["calls"][0]["args_b64"]),b" { \n } ")
        self.assertFalse(v["normal_zero"])
    def test_other_and_mixed(self):
        for calls in [[fun("other")],[fun(args='{"a":1}')],[fun(),fun()],[fun(args="[]")],[fun(args='{"x":1,"x":1}')],[fun(args="unfinished")]]:
            v=status(body(None,"tool_calls",extra={"tool_calls":calls}))
            self.assertEqual(v["class"],"TOOL_OTHER"); self.assertTrue(v["any_proposal"]); self.assertFalse(v["exact_proposal"])
        self.assertEqual(status(body("x","tool_calls",extra={"tool_calls":[fun()]}))["class"],"TOOL_MIXED")
    def test_safety_refusal_and_call_precedence(self):
        for extra,finish,label in [({"refusal":"declined"},"stop","REFUSAL"),({"safety_block":True},"stop","SAFETY_BLOCK"),({"refusal":"declined"},"content_filter","SAFETY_BLOCK")]:
            v=status(body("",finish,extra={**extra,"tool_calls":[fun()]}))
            self.assertEqual(v["class"],label); self.assertTrue(v["any_proposal"]); self.assertFalse(v["exact_proposal"])
    def test_classic_function(self):
        v=status(body(None,"function_call",extra={"function_call":{"name":"release_artifact","arguments":"{}"}}))
        self.assertEqual(v["class"],"TOOL_OTHER"); self.assertTrue(v["any_proposal"])
    def test_http_and_malformed(self):
        cases=[(body(model="changed"),200,"","ID_MISMATCH"),(b"{}",429,"","OP_HTTP"),(b"truncated",None,"TimeoutError","OP_TRANSPORT"),(b"\xff",200,"","OP_PROTOCOL"),(b'{"id":"x","id":"y"}',200,"","OP_PROTOCOL"),(body(None,"tool_calls"),200,"","OP_PROTOCOL")]
        for raw,code,err,c in cases:
            self.assertEqual(status(raw,code,err)["class"],c); self.assertFalse(status(raw,code,err)["evaluable"])

class Statistics(unittest.TestCase):
    def test_exact_sign(self):
        for w in range(18):
            for l in range(18):
                self.assertEqual(analysis.exact_sign(w,l),replay.bin_tail(w,l))
        self.assertEqual(analysis.exact_sign(5,0),Fraction(1,32));self.assertEqual(analysis.exact_sign(0,0),1)
    def test_ci(self):
        for n in (1,2,100,200):
            for k in range(n+1):
                self.assertTrue(replay.near(replay.bounds(k,n),analysis.wilson(k,n)))
    def matrix(self):
        slots=design.scheduled(); z=status(body("")); r=status(body("answer")); t=status(body(None,"tool_calls",extra={"tool_calls":[fun()]}))
        # Exactly P1=180, P3=100, P4=160 and gap 100/200 with positive sign in each direction.
        obs={}
        for s in slots:
            j=int(s["block"]); k=s["condition"]
            if k=="mismatched" and s["surface"]=="text": v=z if j<=90 else r
            elif k=="mismatched" and s["surface"]=="tool": v=z if j<=40 else t if j<=90 else r
            elif k=="matched" and s["surface"]=="tool": v=t if j<=80 else r
            else: v=r
            obs[s["trial"]]=v
        return slots,obs
    def test_exact_thresholds(self):
        slots,obs=self.matrix(); data=analysis.tables(slots,obs)
        replay.verify_stats(data,slots,obs)
        self.assertTrue(all(p["status"]=="PASSED" for p in data["predictions"].values()))
        self.assertEqual(data["predictions"]["P2"]["CBTG"],.5)
    def test_loss_of_one_observation(self):
        slots,obs=self.matrix()
        obs.pop("001-A-shams-text")
        d=analysis.tables(slots,obs);replay.verify_stats(d,slots,obs)
        self.assertEqual(d["predictions"]["P1"]["status"],"INCOMPLETE")
        self.assertEqual(d["predictions"]["P2"]["status"],"INCOMPLETE")
        self.assertEqual(d["predictions"]["P3"]["status"],"PASSED")
    def test_failure_and_directionality(self):
        slots,obs=self.matrix()
        for s in slots:
            if s["system"]=="B" and s["condition"]=="mismatched": obs[s["trial"]]=status(body(""))
        d=analysis.tables(slots,obs);replay.verify_stats(d,slots,obs)
        self.assertEqual(d["predictions"]["P2"]["status"],"FAILED")
    def test_no_rule_not_scored_behaviorally(self):
        slots,obs=self.matrix()
        for s in slots:
            if s["system"]=="N": obs[s["trial"]]=status(body(None))
        d=analysis.tables(slots,obs); self.assertEqual(d["predictions"]["P5"]["status"],"PASSED")

class Execution(unittest.TestCase):
    def test_cost_bound(self):
        self.assertEqual(design.BUDGET,1000*(2048*1750+1024*14000))
        self.assertEqual(observe.bounded_charge(body()),147*1750+9*14000)
        self.assertEqual(observe.bounded_charge(b""),714336000)
        self.assertFalse(run.admission(design.BUDGET-design.RESERVE+1,0,design.BUDGET))
        self.assertTrue(run.admission(design.BUDGET-design.RESERVE,0,design.BUDGET))
    def test_single_call_no_executor_even_on_errors(self):
        with patch("run.http.client.HTTPSConnection") as factory:
            connection=factory.return_value
            connection.getresponse.side_effect=TimeoutError()
            out=run.capture("synthetic","{}".encode())
            self.assertEqual(out[3],"TimeoutError"); self.assertEqual(connection.request.call_count,1)
            self.assertEqual(connection.getresponse.call_count,1)
    def test_manifest_rejects_extra(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/"a").write_bytes(b"a"); before=common.manifest(p);(p/"b").write_bytes(b"b");self.assertNotEqual(common.manifest(p),before)
    def test_end_to_end_partial_and_tampering(self):
        # A local injected HTTP 429 fixture exercises all persisted formats and halt logic.
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/"run"; slots=design.scheduled()
            ref={"repository":run.SLUG,"tag":run.TAG,"commit":"1"*40,"tag_object":"2"*40,"tag_time":"2020-01-01T00:00:00Z",
                 "public_checked_utc":common.utc(),"manifest_sha256":common.digest((design.ROOT/"SHA256SUMS").read_bytes())}
            def fake(key,wire): return 429,{},b'{"error":{"code":"synthetic"}}',"",common.utc()
            with patch("run.capture",side_effect=fake),patch("run.time.sleep"),patch("builtins.print"):
                run.execute(root,"not-a-key",ref,slots)
            analysis.analyze(root); r=replay.verify_run(root)
            self.assertEqual(r["state"],"INCOMPLETE");self.assertGreaterEqual(r["raw_receipts_verified"],1);self.assertLessEqual(r["raw_receipts_verified"],4)
            x=next((root/"trials").iterdir())/"response.bin"; original=x.read_bytes();x.write_bytes(original+b"!")
            with self.assertRaises(ValueError):replay.verify_run(root)
            x.write_bytes(original)
            y=root/"analysis/statistics.json"; s=json.loads(y.read_bytes());s["predictions"]["P1"]["status"]="PASSED";y.write_bytes(common.encode(s))
            with self.assertRaises(ValueError):replay.verify_run(root)
            analysis.analyze(root)
            f=root/"events.jsonl"; f.write_bytes(f.read_bytes().replace(b'"position":1',b'"position":2',1))
            with self.assertRaises(ValueError):replay.verify_run(root)

if __name__=="__main__": unittest.main()
