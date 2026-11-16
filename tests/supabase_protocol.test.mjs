import assert from 'node:assert/strict';
import {test} from 'node:test';
import {generateKeyPairSync,verify,constants} from 'node:crypto';
import {readFileSync} from 'node:fs';
import {createHandler,databaseRPC} from '../supabase/functions/stc-license/handler.ts';
import {canonical,loadSigner,sha256} from '../supabase/functions/stc-license/protocol.ts';

const {privateKey,publicKey}=generateKeyPairSync('rsa',{modulusLength:3072});
const pem=privateKey.export({type:'pkcs8',format:'pem'});
const env=name=>name==='STC_LICENSE_SIGNING_KEY' ? pem : undefined;
const license_id='12345678-1234-1234-1234-123456789abc';
const code='STC-ABCDEFGH-IJKLMNOP-QRSTUVWX-YZ234567';
const body={code,device_id:'a'.repeat(64),nonce:'b'.repeat(48)};
function req(route='/v1/activate',data=body) {
  return new Request('https://example.test/functions/v1/stc-license'+route,
    {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
}

test('activation signs a Python-compatible payload and only sends hashes to SQL',async()=>{
  let args;
  const handler=createHandler(env,async input=>{args=input;return {status:200,license_id};});
  const res=await handler(req());
  assert.equal(res.status,200);
  const envelope=await res.json();
  assert.equal(envelope.payload.nonce,body.nonce);
  assert.equal(envelope.payload.device_id,body.device_id);
  assert.match(envelope.payload.token,/^[A-Za-z0-9_-]{43}$/);
  assert.equal(args.p_credential_hash,await sha256(code));
  assert.equal(args.p_token_hash,await sha256(envelope.payload.token));
  assert(!JSON.stringify(args).includes(code));
  assert(verify('sha256',Buffer.from(canonical(envelope.payload)),{
    key:publicKey,padding:constants.RSA_PKCS1_PSS_PADDING,saltLength:32},Buffer.from(envelope.signature,'base64')));
  const digest=await sha256(new Uint8Array(publicKey.export({type:'spki',format:'der'})));
  assert.equal(envelope.key_id,digest.slice(0,24));
  assert.equal(res.headers.get('cache-control'),'no-store');
});

test('raw DER base64 secret works as well as PEM',async()=>{
  const sign=await loadSigner(privateKey.export({type:'pkcs8',format:'der'}).toString('base64'));
  const result=await sign({active:true});
  assert.equal(result.signature.length,512);
});

test('validation authenticates the saved token and returns no replacement token',async()=>{
  const handler=createHandler(env,async input=>{
    assert.equal(input.p_operation,'validate');
    assert.equal(input.p_token_hash,null);
    return {status:200,license_id};
  });
  const result=await (await handler(req('/v1/validate',{token:'x'.repeat(43),device_id:body.device_id,nonce:body.nonce}))).json();
  assert.equal(result.payload.active,true);
  assert.equal(result.payload.token,undefined);
});

test('safe denial codes preserve server rejection and rate limits',async()=>{
  for (const [status,code] of [[401,'STC-L101'],[409,'STC-L102'],[403,'STC-L103'],[429,'STC-L106']]) {
    const handler=createHandler(env,async()=>({status,code}));
    const res=await handler(req());
    assert.equal(res.status,status);
    assert.deepEqual(await res.json(),{code});
  }
});

test('malformed and oversized input never reaches the database',async()=>{
  const handler=createHandler(env,async()=>{assert.fail('must not call SQL');});
  for (const data of [[],{}, {...body,nonce:'bad'}, {...body,device_id:'bad'}, {...body,code:'wrong'}, {...body,extra:'x'.repeat(5000)}]) {
    const res=await handler(req('/v1/activate',data));
    assert(res.status>=400);
  }
});

test('unconfigured signing fails closed before assigning a seat; exceptions stay private',async()=>{
  const missing=createHandler(()=>undefined,async()=>assert.fail('must not assign seat'));
  const response=await missing(req());
  assert.equal(response.status,503);
  assert.deepEqual(await response.json(),{code:'STC-L104'});
  const failure=createHandler(env,async()=>{throw Error('private database credentials');});
  assert.deepEqual(await (await failure(req())).json(),{code:'STC-L104'});
});

test('there are no public issue/revoke/transfer routes, and health is credential-free',async()=>{
  const handler=createHandler(env,async()=>assert.fail('must not call SQL'));
  for (const path of ['/admin','/v1/issue','/v1/revoke','/v1/transfer']) {
    assert.equal((await handler(req(path))).status,404);
  }
  assert.equal((await handler(new Request('https://example.test/stc-license/health'))).status,200);
});

test('privileged database key stays on server and new keys are not sent as bearer tokens',async()=>{
  for (const key of ['sb_secret_test','eyJlegacy-test']) {
    const vars={SUPABASE_URL:'https://example.test',SUPABASE_SECRET_KEYS:JSON.stringify({default:key})};
    const rpc=databaseRPC(name=>vars[name],async(url,options)=>{
      assert.equal(url,'https://example.test/rest/v1/rpc/stc_license_access');
      assert.equal(options.headers.apikey,key);
      assert.equal(options.headers.Authorization,key.startsWith('eyJ') ? 'Bearer '+key : undefined);
      return Response.json({status:200,license_id});
    });
    assert.equal((await rpc({})).status,200);
  }
});

test('migration keeps tables/admin functions private and RPC restricted to the backend',()=>{
  const sql=readFileSync(new URL('../supabase/migrations/202611140001_stc_licensing.sql',import.meta.url),'utf8');
  assert.match(sql,/revoke all on schema stc_licensing from public, anon, authenticated, service_role/i);
  assert.match(sql,/revoke all on all functions in schema stc_licensing from public, anon, authenticated, service_role/i);
  assert.match(sql,/revoke all on function public.stc_license_access\(text,text,text,text\) from public, anon, authenticated/i);
  assert.match(sql,/grant execute on function public.stc_license_access\(text,text,text,text\) to service_role/i);
  assert.match(sql,/for update/i);
});
