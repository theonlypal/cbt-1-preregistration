"""Strict JSON and byte manifests, no network access."""
import hashlib
import json
import os
from pathlib import Path

def unique(pairs):
    out = {}
    for key,value in pairs:
        if key in out:
            raise ValueError("duplicate JSON member")
        out[key]=value
    return out

def nonfinite(_):
    raise ValueError("nonfinite number")

def parse(raw):
    return json.loads(raw.decode("utf-8") if isinstance(raw,bytes) else raw,
                      object_pairs_hook=unique,parse_constant=nonfinite)

def encode(obj):
    return json.dumps(obj,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(",",":")).encode()

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def utc():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00","Z")

def write_new(path,data):
    with path.open("xb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())

def manifest(root, name="SHA256SUMS"):
    files=[]
    for path in sorted(root.rglob("*")):
        rel=path.relative_to(root)
        if any(part in {".git","__pycache__",".DS_Store"} for part in rel.parts):
            continue
        if path.is_symlink():
            raise ValueError("unexpected symlink "+str(rel))
        if path.is_file() and rel.as_posix()!=name:
            files.append(digest(path.read_bytes())+"  "+rel.as_posix()+"\n")
    return "".join(files).encode()

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("mode",choices=("build","check"))
    p.add_argument("root",type=Path)
    a=p.parse_args()
    expected=manifest(a.root)
    path=a.root/"SHA256SUMS"
    if a.mode=="build":
        path.write_bytes(expected)
    elif path.read_bytes()!=expected:
        raise SystemExit("Manifest mismatch")
    print("Manifest:",len(expected.splitlines()),"files")
