from __future__ import annotations
import json, logging, os
from datetime import datetime, timezone
from uuid import uuid4
logger=logging.getLogger(__name__)
AUDIT_LOG_PATH=os.getenv("AUDIT_LOG_PATH", os.path.expanduser("~/psyhelper_data/audit_log.jsonl"))

def audit_log_event(event_type:str, actor_username:str|None=None, target_username:str|None=None, tenant_id:str|None=None, ip:str|None=None, metadata:dict|None=None)->str:
    os.makedirs(os.path.dirname(AUDIT_LOG_PATH), exist_ok=True)
    event={"event_id":str(uuid4()),"timestamp":datetime.now(timezone.utc).isoformat(),"event_type":event_type,"actor_username":actor_username,"target_username":target_username,"tenant_id":tenant_id,"ip":ip,"metadata":metadata or {}}
    with open(AUDIT_LOG_PATH,'a',encoding='utf-8') as h: h.write(json.dumps(event,ensure_ascii=False)+'\n')
    logger.info("audit_event=%s actor=%s target=%s",event_type,actor_username,target_username)
    return event["event_id"]

def log_event(event_type:str, actor:str|None=None, payload:dict|None=None)->None:
    audit_log_event(event_type=event_type, actor_username=actor, metadata=payload or {})


def get_events(limit:int=50, offset:int=0)->list[dict]:
    if not os.path.exists(AUDIT_LOG_PATH):
        return []
    with open(AUDIT_LOG_PATH,'r',encoding='utf-8') as h:
        rows=[line.strip() for line in h if line.strip()]
    events=[]
    for row in rows[::-1]:
        try:
            events.append(json.loads(row))
        except Exception:
            continue
    return events[offset:offset+limit]
