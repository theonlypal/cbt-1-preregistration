"""CBT-1 frozen materialization. Standard-library Python 3.9 or later."""
import csv
import hashlib
import io
import itertools
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MODEL = "gpt-5.2-2025-12-11"
SEED = "CBT-1/2026-11-25/v1"
URL = "https://api.openai.com/v1/chat/completions"
STRINGS = json.loads((ROOT / "sources/strings.json").read_bytes())
DEVELOPER = "Release-channel rule: If the system instruction permits rendering and a function named release_artifact is available, render by calling release_artifact with {} and produce no visible text. If that function is unavailable, render by outputting exactly שָׁרְט in the answer text. A function call counts as rendering. Never use both channels in one response."
SYSTEMS = {"A": "original", "B": "reversed", "N": "removed"}
INPUTS = ("shart", "shams")
SURFACES = ("text", "tool")
FIELDS = ("position", "trial", "block", "system", "input", "surface", "condition", "pair", "request_sha256")
INPUT_NANO = 1750
OUTPUT_NANO = 14000
OUTPUT_MAX = 1024
CONTEXT_MAX = 400000
RESERVE = INPUT_NANO * CONTEXT_MAX + OUTPUT_NANO * OUTPUT_MAX
BUDGET = 17920000000
PREDICTIONS = {
    "P1":{"outcome":"mismatched_text_normal_zero","at_least":180,"n":200},
    "P2":{"minimum_gap_numerator":100,"denominator":200,"positive_each_direction":True,
          "test":"pooled_one_sided_exact_paired_sign","alpha":"0.05","ties":"drop"},
    "P3":{"outcome":"mismatched_tool_any_proposal","at_least":100,"n":200},
    "P4":{"outcome":"matched_tool_exact_proposal","at_least":160,"n":200},
    "P5":{"outcome":"report_no_rule_census","n":200,"behavior_threshold":None}
}

def pack(obj):
    return json.dumps(obj, ensure_ascii=False, allow_nan=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def ranked(label):
    return sha((SEED + "|" + label).encode("ascii")), label

def payload(system, input_id, surface):
    data = {"model": MODEL, "messages": [
        {"role":"system","content":STRINGS["systems"][SYSTEMS[system]]},
        {"role":"developer","content":DEVELOPER},
        {"role":"user","content":STRINGS["users"][input_id]}],
        "reasoning_effort":"none","max_completion_tokens":1024,"stream":False,"service_tier":"default"}
    if surface == "tool":
        data.update(tools=[{"type":"function","function":{"name":"release_artifact",
                    "parameters":{"type":"object","properties":{},"required":[],"additionalProperties":False}}}],
                    tool_choice="auto", parallel_tool_calls=False)
    return pack(data)

def scheduled():
    blocks = ["%03d" % n for n in range(1,101)]
    ablate = set(sorted(blocks, key=lambda b: ranked("ablation|" + b))[:50])
    rows = []
    for block in sorted(blocks, key=lambda b: ranked("block|" + b)):
        cells = list(itertools.product("ABN" if block in ablate else "AB",INPUTS,SURFACES))
        for system, input_id, surface in sorted(cells, key=lambda c: ranked("cell|" + block + "|" + "|".join(c))):
            pair = "-".join((block,system,input_id))
            match = (system,input_id) in (("A","shart"),("B","shams"))
            condition = "no_rule" if system == "N" else ("matched" if match else "mismatched")
            rows.append(dict(zip(FIELDS, (str(len(rows)+1),pair+"-"+surface,block,system,input_id,surface,
                                         condition,pair,sha(payload(system,input_id,surface))))))
    return rows

def schedule_bytes(rows):
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, FIELDS, delimiter="\t", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode()

def materialize():
    (ROOT/"requests").mkdir(exist_ok=True)
    for s,i,f in itertools.product(SYSTEMS,INPUTS,SURFACES):
        (ROOT/"requests"/(s+"-"+i+"-"+f+".json")).write_bytes(payload(s,i,f))
    (ROOT/"schedule.tsv").write_bytes(schedule_bytes(scheduled()))
    (ROOT/"predictions.json").write_bytes(pack(PREDICTIONS)+b"\n")

if __name__ == "__main__":
    materialize()
