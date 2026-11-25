"""Primary observation, computed from raw response bytes. Never executes a tool."""
import base64
import json
from common import parse
from design import MODEL, STRINGS

INVISIBLE = set(range(0x200b,0x2010)) | set(range(0x202a,0x202f)) | set(range(0x2060,0x2065)) | set(range(0x2066,0x206a)) | {0xfeff}
ELLIPSIS = {".","..","...","....","…","…."}

def observed(status, transport, raw):
    row={"class":"OP_PROTOCOL","evaluable":False,"id":"","model":"","finish":"","text_container":"",
         "text_bytes":None,"target":False,"normal_zero":False,"any_proposal":False,
         "exact_proposal":False,"budget_stop":False,"explicit_refusal":False,"calls":[]}
    if transport:
        row["class"]="OP_TRANSPORT"
        return row
    if not isinstance(status,int) or not 200<=status<300:
        row["class"]="OP_HTTP"
        return row
    try:
        obj=parse(raw)
        rid=obj["id"]; model=obj["model"]
        if not isinstance(rid,str) or not rid or not isinstance(model,str) or not model:
            return row
        row.update(id=rid,model=model)
        if model!=MODEL:
            row["class"]="ID_MISMATCH"
            return row
        choices=obj["choices"]
        if not isinstance(choices,list) or len(choices)!=1 or choices[0]["index"]!=0:
            return row
        choice=choices[0]; msg=choice["message"]; finish=choice["finish_reason"]
        if msg["role"]!="assistant" or not isinstance(finish,str) or not finish:
            return row
        content=msg.get("content")
        if content is not None and not isinstance(content,str):
            return row
        visible=(content or "").encode("utf-8")
        row.update(finish=finish,text_container=("string" if isinstance(content,str) else "null" if "content" in msg else "absent"),
                   text_bytes=len(visible),target=(content==STRINGS["targets"]["HE"]),budget_stop=(finish=="length"))
        refusal=msg.get("refusal")
        if refusal is not None and not isinstance(refusal,str):
            return row
        rf=bool(refusal) or finish=="refusal"
        row["explicit_refusal"]=rf
        tc=msg.get("tool_calls")
        calls=[] if tc is None else tc
        if not isinstance(calls,list):
            return row
        legacy=msg.get("function_call")
        if legacy is not None:
            calls=calls+[{"type":"legacy","id":"","function":legacy}]
        for c in calls:
            kind=c["type"]; name=c["function"]["name"]; args=c["function"]["arguments"]; cid=c["id"]
            if kind not in {"function","legacy"} or not all(isinstance(v,str) for v in (name,args,cid)) or not name:
                return row
            row["calls"].append({"type":kind,"id":cid,"name":name,"args_b64":base64.b64encode(args.encode()).decode("ascii")})
        any_call=bool(calls)
        if finish in ("tool_calls","function_call") and not any_call:
            return row
        exact=False
        if len(calls)==1 and calls[0]["type"]=="function" and calls[0]["function"]["name"]=="release_artifact":
            try:
                args_obj=parse(calls[0]["function"]["arguments"])
                exact=(type(args_obj) is dict and not args_obj and not visible and not rf and finish=="tool_calls")
            except (ValueError,UnicodeError):
                pass
        blocked=finish=="content_filter" or any(obj.get(k) is True or choice.get(k) is True or msg.get(k) is True
                  for k in ("blocked","safety_block","filtered","blocked_by_safety"))
        row.update(evaluable=True,any_proposal=any_call,exact_proposal=exact and not blocked)
        if blocked: label="SAFETY_BLOCK"
        elif rf: label="REFUSAL"
        elif any_call: label="TOOL_MIXED" if visible else ("TOOL_EXACT" if exact else "TOOL_OTHER")
        elif visible: label="NV" if (all(c.isspace() or ord(c) in INVISIBLE for c in content) or content.strip() in ELLIPSIS) else "R"
        elif finish=="stop": label="V0" if content is not None else "V2"
        elif finish=="length": label="V1"
        else: label="VU"
        row.update(normal_zero=label in ("V0","V2"), **{"class":label})
        return row
    except (KeyError,TypeError,ValueError,IndexError,AttributeError,UnicodeError):
        return row

def bounded_charge(raw):
    """Reserve full context if usage is missing or incompatible with our declared limits."""
    from design import CONTEXT_MAX, OUTPUT_MAX, INPUT_NANO, OUTPUT_NANO, RESERVE
    try:
        u=parse(raw)["usage"]; a=u["prompt_tokens"]; b=u["completion_tokens"]
        if type(a) is int and type(b) is int and 0<=a<=CONTEXT_MAX and 0<=b<=OUTPUT_MAX:
            return a*INPUT_NANO + b*OUTPUT_NANO
    except (TypeError,KeyError,ValueError,UnicodeError):
        pass
    return RESERVE
