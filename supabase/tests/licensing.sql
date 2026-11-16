-- Run after the migration in SQL Editor as postgres. All test changes roll back.
-- No customer licenses are modified; no generated test codes are printed.
begin;
create function pg_temp.assert_status(result jsonb, expected integer) returns void
language plpgsql as $$
begin
  if (result->>'status')::integer is distinct from expected then
    raise exception 'Licensing test failed: expected status %, got %',expected,result->>'status';
  end if;
end;
$$;
do $$
declare
  issued jsonb;
  code text;
  code_hash text;
  identifier uuid;
  response jsonb;
  replacement jsonb;
  device_a text := repeat('a',64);
  device_b text := repeat('b',64);
  token_a text := repeat('1',64);
  token_b text := repeat('2',64);
  i integer;
begin
  if has_schema_privilege('anon','stc_licensing','USAGE')
     or has_schema_privilege('authenticated','stc_licensing','USAGE')
     or has_function_privilege('anon','public.stc_license_access(text,text,text,text)','EXECUTE')
     or has_function_privilege('authenticated','public.stc_license_access(text,text,text,text)','EXECUTE')
     or has_function_privilege('service_role','stc_licensing.issue_license(text,integer)','EXECUTE')
     or not has_function_privilege('service_role','public.stc_license_access(text,text,text,text)','EXECUTE') then
    raise exception 'Licensing test failed: database privileges are incorrect';
  end if;
  issued := stc_licensing.issue_license('ROLLBACK-ONLY-TEST');
  identifier := (issued->>'license_id')::uuid;
  code := issued->>'code';
  if code !~ '^STC-([A-Z2-7]{8}-){3}[A-Z2-7]{8}$' then
    raise exception 'Licensing test failed: invalid generated code';
  end if;
  code_hash := encode(extensions.digest(code,'sha256'),'hex');
  response := public.stc_license_access('activate',code_hash,device_a,token_a);
  perform pg_temp.assert_status(response,200);
  if response->>'license_id' is distinct from identifier::text then raise exception 'Wrong license ID'; end if;
  perform pg_temp.assert_status(public.stc_license_access('activate',code_hash,device_b,token_b),409);
  perform pg_temp.assert_status(public.stc_license_access('validate',token_a,device_a),200);
  perform pg_temp.assert_status(public.stc_license_access('validate',token_a,device_b),409);
  perform pg_temp.assert_status(public.stc_license_access('activate',code_hash,device_a,token_b),200);
  perform pg_temp.assert_status(public.stc_license_access('validate',token_a,device_a),401);
  perform pg_temp.assert_status(public.stc_license_access('validate',token_b,device_a),200);
  perform stc_licensing.revoke_license(identifier);
  perform pg_temp.assert_status(public.stc_license_access('validate',token_b,device_a),403);
  replacement := stc_licensing.transfer_license(identifier);
  perform pg_temp.assert_status(public.stc_license_access('activate',code_hash,device_a,token_a),401);
  perform pg_temp.assert_status(public.stc_license_access('validate',token_b,device_a),401);
  code_hash := encode(extensions.digest(replacement->>'replacement_code','sha256'),'hex');
  perform pg_temp.assert_status(public.stc_license_access('activate',code_hash,device_b,token_a),200);
  update stc_licensing.licenses set expires_at=now()-interval '1 second' where id=identifier;
  perform pg_temp.assert_status(public.stc_license_access('validate',token_a,device_b),403);
  code_hash := encode(extensions.digest(gen_random_uuid()::text,'sha256'),'hex');
  for i in 1..5 loop
    perform pg_temp.assert_status(public.stc_license_access('activate',code_hash,device_a,token_b),401);
  end loop;
  perform pg_temp.assert_status(public.stc_license_access('activate',code_hash,device_a,token_b),429);
  raise notice 'STC licensing: privileges, binding, rejection, rotation, revoke, transfer, expiry and throttling passed.';
end;
$$;
rollback;
