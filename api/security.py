from __future__ import annotations
import base64, hashlib, hmac, json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4
try:
    import jwt as _pyjwt
except ImportError:
    _pyjwt = None
from api.exceptions import AuthenticationError
from core.settings import SETTINGS
from services import auth_service
ALGORITHM="HS256"
@dataclass(frozen=True)
class AuthContext:
    username:str; role:str; therapist_username:str|None; subscription_status:str; metadata:dict[str,Any]; profile:dict[str,Any]

def secret_key()->str: return SETTINGS.secret_key

def create_access_token(username:str)->str: return _create_token(username,"access",timedelta(minutes=SETTINGS.access_token_expire_minutes))
def create_refresh_token(username:str,family_id:str|None=None)->str: return _create_token(username,"refresh",timedelta(days=SETTINGS.refresh_token_expire_days),family_id=family_id)
def verify_access_token(token:str)->dict[str,Any]:
    p=_decode_token(token)
    if p.get('typ')!='access': raise AuthenticationError('Invalid access token')
    return p

def verify_refresh_token(token:str)->dict[str,Any]:
    p=_decode_token(token)
    if p.get('typ')!='refresh': raise AuthenticationError('Invalid refresh token')
    return p

def auth_context_for_username(username:str)->AuthContext:
    username=auth_service.normalize_username(username)
    if not username or not auth_service.user_exists(username): raise AuthenticationError('Unknown user')
    md=auth_service.load_user_metadata(username)
    if SETTINGS.strict_production_mode and not md.get('tenant_id'): raise AuthenticationError('Missing tenant_id')
    b=auth_service.load_account_bundle(username)
    return AuthContext(username, str(md.get('role') or 'client'), auth_service.normalize_username(md.get('therapist_username') or '') or None, str(md.get('subscription_status') or 'inactive'), md, b['profile'])

def _create_token(username, token_type, exp_delta, family_id=None):
    now=datetime.now(timezone.utc); payload={'sub':auth_service.normalize_username(username),'typ':token_type,'iat':int(now.timestamp()),'nbf':int(now.timestamp()),'exp':int((now+exp_delta).timestamp()),'iss':SETTINGS.token_issuer,'jti':str(uuid4())}
    if family_id: payload['family_id']=family_id
    return _pyjwt.encode(payload, secret_key(), algorithm=ALGORITHM) if _pyjwt else _encode_hs256(payload, secret_key())

def _decode_token(token):
    try:
        payload=_pyjwt.decode(token, secret_key(), algorithms=[ALGORITHM], issuer=SETTINGS.token_issuer) if _pyjwt else _decode_hs256(token, secret_key())
    except Exception as exc:
        raise AuthenticationError('Invalid or expired token') from exc
    if not auth_service.normalize_username(payload.get('sub','')): raise AuthenticationError('Invalid token subject')
    if payload.get('typ') not in {'access','refresh'}: raise AuthenticationError('Invalid token type')
    return payload

def _b64url(d:bytes)->str: return base64.urlsafe_b64encode(d).rstrip(b'=').decode('ascii')
def _b64url_decode(d:str)->bytes: return base64.urlsafe_b64decode((d+'='*(-len(d)%4)).encode('ascii'))
def _encode_hs256(payload,key):
    header={'alg':ALGORITHM,'typ':'JWT'}; s='.'.join([_b64url(json.dumps(header,separators=(',',':')).encode()),_b64url(json.dumps(payload,separators=(',',':')).encode())]); sig=hmac.new(key.encode(), s.encode('ascii'), hashlib.sha256).digest(); return f"{s}.{_b64url(sig)}"
def _decode_hs256(token,key):
    h,p,s=token.split('.'); inp=f'{h}.{p}'; exp=hmac.new(key.encode(), inp.encode('ascii'), hashlib.sha256).digest()
    if not hmac.compare_digest(_b64url(exp),s): raise AuthenticationError('Invalid token signature')
    payload=json.loads(_b64url_decode(p)); now=int(datetime.now(timezone.utc).timestamp())
    if int(payload.get('exp',0))<now or int(payload.get('nbf',0))>now: raise AuthenticationError('Expired token')
    if payload.get('iss')!=SETTINGS.token_issuer: raise AuthenticationError('Invalid token issuer')
    return payload
