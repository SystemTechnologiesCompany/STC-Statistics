"""Online activation with signed responses and Windows-bound local credentials."""
import base64
import hmac
import json
import os
from pathlib import Path
import secrets
import time
from urllib import request,error,parse
from . import license_windows
from .license_trust import PUBLIC_KEY

CONTACT_URL='https://www.linkedin.com/company/system-technologies-company-stc/posts/?viewAsMember=true'


class LicenseError(Exception):
    def __init__(self,code):
        self.code=code
        super().__init__(code)


def canonical(payload):
    return json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode('utf-8')


def licensing_home():
    if os.environ.get('STC_PORTABLE_ROOT'):
        return Path(os.environ['STC_PORTABLE_ROOT']).resolve().parent/'licensing'
    return Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'STCStatistics/licensing'


def load_config():
    try:
        data=json.loads(Path(__file__).with_name('license_config.json').read_text(encoding='utf-8'))
        return data.get('server_url','')
    except (ValueError,OSError,AttributeError):
        return ''


def require_configured_release(root):
    """Block accidental distribution of an activation gate without its service/key."""
    import ast
    package=Path(root)/'stc_statistics'
    if not (package/'activation.py').is_file():
        return
    try:
        url=json.loads((package/'license_config.json').read_text(encoding='utf-8'))['server_url']
        validate_server_url(url)
        tree=ast.parse((package/'license_trust.py').read_text(encoding='utf-8'))
        key=next(ast.literal_eval(node.value) for node in tree.body
                 if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='PUBLIC_KEY' for t in node.targets))
        if (not isinstance(key,dict) or int(key['n'],16).bit_length()!=3072
                or key['e']!=65537 or not isinstance(key['key_id'],str) or len(key['key_id'])!=24):
            raise ValueError()
    except (OSError,ValueError,TypeError,KeyError,StopIteration,SyntaxError,LicenseError):
        raise ValueError('Release blocked: deploy the STC HTTPS licensing service and run configure-client first. No customer package was created.') from None


def validate_server_url(url, allow_local_http=False):
    try:
        u=parse.urlsplit(url)
        if (u.username or u.password or u.query or u.fragment or not u.hostname
                or any(c.isspace() for c in url)):
            raise ValueError()
        if u.scheme!='https' and not (allow_local_http and u.scheme=='http' and u.hostname in ('127.0.0.1','localhost')):
            raise ValueError()
        u.port
    except (ValueError,TypeError):
        raise LicenseError('STC-L104') from None
    return url.rstrip('/')


class CredentialStore:
    def __init__(self,path=None):
        self.path=Path(path) if path else licensing_home()/'activation.bin'

    def load(self):
        if not self.path.exists():
            return None
        try:
            if self.path.stat().st_size>16384:
                raise ValueError()
            return json.loads(license_windows.protect(self.path.read_bytes(),decrypt=True))
        except (OSError,ValueError,TypeError):
            raise LicenseError('STC-L105') from None

    def save(self,credential):
        try:
            raw=license_windows.protect(canonical(credential))
            self.path.parent.mkdir(parents=True,exist_ok=True)
            temporary=self.path.with_name('activation-'+secrets.token_hex(8)+'.tmp')
            try:
                temporary.write_bytes(raw)
                from .update_installer import replace_with_retry
                replace_with_retry(temporary,self.path)
            finally:
                temporary.unlink(missing_ok=True)
        except OSError:
            raise LicenseError('STC-L107') from None


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        return None


class LicenseClient:
    def __init__(self,server_url=None,public_key=None,store=None,identity=None,allow_local_http=False):
        self.url=validate_server_url(load_config() if server_url is None else server_url,allow_local_http)
        self.public_key=PUBLIC_KEY if public_key is None else public_key
        if not self.public_key:
            raise LicenseError('STC-L104')
        self.store=store or CredentialStore()
        try:
            self.device=identity if identity is not None else license_windows.device_id()
        except OSError:
            raise LicenseError('STC-L105') from None

    def post(self,route,body):
        req=request.Request(self.url+route,data=canonical(body),headers={'Content-Type':'application/json','Accept':'application/json'},method='POST')
        try:
            with request.build_opener(NoRedirect()).open(req,timeout=20) as response:
                raw=response.read(32769)
                if len(raw)>32768:
                    raise ValueError()
                return json.loads(raw)
        except error.HTTPError as exc:
            if exc.code==429:
                raise LicenseError('STC-L106') from None
            if exc.code in (401,403,409):
                try:
                    code=json.loads(exc.read(2048)).get('code')
                    if code in ('STC-L101','STC-L102','STC-L103'):
                        raise LicenseError(code) from None
                except (ValueError,AttributeError):
                    pass
            raise LicenseError('STC-L104') from None
        except (OSError,ValueError):
            raise LicenseError('STC-L104') from None

    def verify(self,envelope,nonce):
        try:
            payload=envelope['payload']
            signature=base64.b64decode(envelope['signature'],validate=True)
            if (envelope['key_id']!=self.public_key['key_id'] or
                    not license_windows.verify_signature(self.public_key,canonical(payload),signature)):
                raise ValueError()
            if (payload.get('type')!='stc-license-access-v1' or payload.get('active') is not True
                    or not hmac.compare_digest(payload['nonce'],nonce)
                    or not hmac.compare_digest(payload['device_id'],self.device)
                    or not isinstance(payload.get('license_id'),str)):
                raise ValueError()
            now=time.time()
            if not (now-360<=payload['issued_at']<=now+120 and now<payload['expires_at']<=now+600):
                raise ValueError()
            return payload
        except (KeyError,ValueError,TypeError,OSError):
            raise LicenseError('STC-L108') from None

    def activate(self,code):
        nonce=secrets.token_hex(24)
        payload=self.verify(self.post('/v1/activate',{'code':code.strip().upper(),'device_id':self.device,'nonce':nonce}),nonce)
        token=payload.get('token')
        if not isinstance(token,str) or len(token)<40:
            raise LicenseError('STC-L108')
        self.store.save({'server_url':self.url,'device_id':self.device,'token':token,'license_id':payload['license_id']})
        return payload

    def check(self):
        credential=self.store.load()
        if not credential:
            raise LicenseError('STC-L100')
        if (not isinstance(credential,dict) or credential.get('server_url')!=self.url
                or credential.get('device_id')!=self.device or not isinstance(credential.get('token'),str)):
            raise LicenseError('STC-L105')
        nonce=secrets.token_hex(24)
        payload=self.verify(self.post('/v1/validate',{'token':credential.get('token',''),'device_id':self.device,'nonce':nonce}),nonce)
        if payload['license_id']!=credential.get('license_id'):
            raise LicenseError('STC-L108')
        return payload
