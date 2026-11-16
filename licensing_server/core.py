"""Atomic, single-seat activation. Only hashed codes/tokens are stored in SQLite."""
import base64
import hashlib
import hmac
import json
from pathlib import Path
import re
import secrets
import sqlite3
import time
import uuid
from contextlib import contextmanager
from cryptography.hazmat.primitives import serialization,hashes
from cryptography.hazmat.primitives.asymmetric import rsa,padding


class Denied(Exception):
    def __init__(self,code,status=403):
        self.code,self.status=code,status
        super().__init__(code)


def canonical(data):
    return json.dumps(data,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()


def create_secrets(directory):
    directory=Path(directory)
    directory.mkdir(parents=True,exist_ok=True)
    private=directory/'signing-key.pem'
    pepper=directory/'pepper.key'
    if private.exists() or pepper.exists():
        raise ValueError('Signing material already exists; do not overwrite it')
    key=rsa.generate_private_key(public_exponent=65537,key_size=3072)
    private.write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
    pepper.write_bytes(secrets.token_bytes(32))
    private.chmod(0o600)
    pepper.chmod(0o600)


class Authority:
    def __init__(self,db,private_dir):
        self.db=Path(db)
        self.db.parent.mkdir(parents=True,exist_ok=True)
        self.key=serialization.load_pem_private_key((Path(private_dir)/'signing-key.pem').read_bytes(),password=None)
        if not isinstance(self.key,rsa.RSAPrivateKey) or self.key.key_size!=3072:
            raise ValueError('Expected a 3072-bit RSA signing key')
        self.pepper=(Path(private_dir)/'pepper.key').read_bytes()
        if len(self.pepper)<32:
            raise ValueError('License hash pepper is too short')
        with self.connect() as db:
            db.executescript('''
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS licenses (
                    id TEXT PRIMARY KEY, buyer_ref TEXT NOT NULL,
                    code_hash TEXT UNIQUE NOT NULL, device_id TEXT,
                    token_hash TEXT UNIQUE, revoked INTEGER NOT NULL DEFAULT 0,
                    created INTEGER NOT NULL, activated INTEGER, expires INTEGER
                );
                CREATE TABLE IF NOT EXISTS rate_limits (
                    key TEXT NOT NULL, bucket INTEGER NOT NULL, count INTEGER NOT NULL,
                    PRIMARY KEY(key,bucket)
                );
                CREATE TABLE IF NOT EXISTS audit (
                    at INTEGER NOT NULL, license_id TEXT NOT NULL, action TEXT NOT NULL
                );
            ''')

    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.db,timeout=10,isolation_level=None)
        db.row_factory=sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def digest(self,text):
        return hmac.new(self.pepper,text.encode(),hashlib.sha256).hexdigest()

    def public_key(self):
        n=self.key.public_key().public_numbers()
        der=self.key.public_key().public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo)
        return {'n':format(n.n,'x'),'e':n.e,'key_id':hashlib.sha256(der).hexdigest()[:24]}

    def sign(self,payload):
        signature=self.key.sign(canonical(payload),padding.PSS(mgf=padding.MGF1(hashes.SHA256()),salt_length=32),hashes.SHA256())
        return {'payload':payload,'signature':base64.b64encode(signature).decode(),'key_id':self.public_key()['key_id']}

    @staticmethod
    def new_code():
        raw=base64.b32encode(secrets.token_bytes(20)).decode()
        return 'STC-'+'-'.join(raw[i:i+8] for i in range(0,32,8))

    def issue(self,buyer_ref,days=None):
        if not isinstance(buyer_ref,str) or not 1<=len(buyer_ref)<=200:
            raise ValueError('Provide a buyer reference of 1–200 characters')
        if days is not None and (type(days) is not int or days<1):
            raise ValueError('Expiry days must be positive')
        code=self.new_code()
        identifier=str(uuid.uuid4())
        now=int(time.time())
        with self.connect() as db:
            db.execute('INSERT INTO licenses(id,buyer_ref,code_hash,created,expires) VALUES(?,?,?,?,?)',
                       (identifier,buyer_ref,self.digest(code),now,now+days*86400 if days else None))
            db.execute('INSERT INTO audit VALUES(?,?,?)',(now,identifier,'issued'))
        return identifier,code

    def revoke(self,identifier):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('UPDATE licenses SET revoked=1 WHERE id=?',(identifier,)).rowcount!=1:
                db.rollback()
                raise ValueError('Unknown license')
            db.execute('INSERT INTO audit VALUES(?,?,?)',(int(time.time()),identifier,'revoked'))
            db.commit()

    def transfer(self,identifier):
        """Retire the shared/old code and token before allowing a replacement PC."""
        code=self.new_code()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('UPDATE licenses SET code_hash=?,device_id=NULL,token_hash=NULL,activated=NULL,revoked=0 WHERE id=?',
                          (self.digest(code),identifier)).rowcount!=1:
                db.rollback()
                raise ValueError('Unknown license')
            db.execute('INSERT INTO audit VALUES(?,?,?)',(int(time.time()),identifier,'transferred_new_code'))
            db.commit()
        return code

    def rate_limit(self,operation,ip,credential):
        bucket=int(time.time())//60
        limits=[('ip:'+ip,120 if operation=='activate' else 1200),
                (operation+':'+credential,5 if operation=='activate' else 60)]
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM rate_limits WHERE bucket < ?',(bucket-3,))
            exceeded=False
            for raw,maximum in limits:
                key=self.digest(raw)
                db.execute('INSERT INTO rate_limits VALUES(?,?,1) ON CONFLICT(key,bucket) DO UPDATE SET count=count+1',(key,bucket))
                exceeded |= db.execute('SELECT count FROM rate_limits WHERE key=? AND bucket=?',(key,bucket)).fetchone()[0]>maximum
            db.commit()
        if exceeded:
            raise Denied('STC-L106',429)

    def access(self,operation,body,ip):
        if operation not in ('activate','validate') or not isinstance(body,dict):
            raise Denied('STC-L101',400)
        device=body.get('device_id','')
        nonce=body.get('nonce','')
        if not isinstance(device,str) or not re.fullmatch('[0-9a-f]{64}',device) or not isinstance(nonce,str) or not re.fullmatch('[0-9a-f]{48}',nonce):
            raise Denied('STC-L101',400)
        credential=body.get('code' if operation=='activate' else 'token','')
        if not isinstance(credential,str) or len(credential)>160:
            raise Denied('STC-L101',400)
        if operation=='activate':
            credential=credential.strip().upper()
        self.rate_limit(operation,ip,credential)
        now=int(time.time())
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            field='code_hash' if operation=='activate' else 'token_hash'
            row=db.execute('SELECT * FROM licenses WHERE '+field+'=?',(self.digest(credential),)).fetchone()
            if row is None:
                db.rollback()
                raise Denied('STC-L101',401)
            if row['revoked'] or (row['expires'] is not None and row['expires']<=now):
                db.rollback()
                raise Denied('STC-L103')
            if row['device_id'] is not None and not hmac.compare_digest(row['device_id'],device):
                db.rollback()
                raise Denied('STC-L102',409)
            token=None
            if operation=='activate':
                token=secrets.token_urlsafe(32)
                db.execute('UPDATE licenses SET device_id=?,token_hash=?,activated=? WHERE id=?',(device,self.digest(token),now,row['id']))
                db.execute('INSERT INTO audit VALUES(?,?,?)',(now,row['id'],'activated'))
            elif row['device_id'] is None:
                db.rollback()
                raise Denied('STC-L101',401)
            db.commit()
        payload={'type':'stc-license-access-v1','active':True,'license_id':row['id'],'device_id':device,
                 'nonce':nonce,'issued_at':now,'expires_at':now+300}
        if token:
            payload['token']=token
        return self.sign(payload)
