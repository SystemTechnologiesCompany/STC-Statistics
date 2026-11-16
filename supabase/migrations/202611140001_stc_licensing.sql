-- Run as postgres in the Supabase SQL Editor, or with supabase db push.
-- This creates only STC licensing objects; it does not modify Auth or other apps.
begin;
create schema if not exists extensions;
create extension if not exists pgcrypto with schema extensions;
create schema if not exists stc_licensing;
revoke all on schema stc_licensing from public, anon, authenticated, service_role;

create table if not exists stc_licensing.licenses (
    id uuid primary key default gen_random_uuid(),
    buyer_ref text not null check (length(buyer_ref) between 1 and 200),
    code_hash text unique not null check (code_hash ~ '^[0-9a-f]{64}$'),
    device_id text check (device_id ~ '^[0-9a-f]{64}$'),
    token_hash text unique check (token_hash ~ '^[0-9a-f]{64}$'),
    revoked boolean not null default false,
    created_at timestamptz not null default now(),
    activated_at timestamptz,
    expires_at timestamptz
);
create table if not exists stc_licensing.rate_limits (
    bucket timestamptz not null,
    key text not null,
    attempts integer not null,
    primary key (bucket, key)
);
create table if not exists stc_licensing.audit (
    id bigint generated always as identity primary key,
    license_id uuid not null references stc_licensing.licenses(id),
    action text not null,
    at timestamptz not null default now()
);
alter table stc_licensing.licenses enable row level security;
alter table stc_licensing.rate_limits enable row level security;
alter table stc_licensing.audit enable row level security;
revoke all on all tables in schema stc_licensing from public, anon, authenticated, service_role;
revoke all on all sequences in schema stc_licensing from public, anon, authenticated, service_role;

-- 32 independent base32 characters = 160 bits of cryptographic randomness.
create or replace function stc_licensing.new_code() returns text
language plpgsql set search_path = '' as $$
declare
    alphabet constant text := 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';
    bytes bytea := extensions.gen_random_bytes(32);
    code text := 'STC';
    i integer;
begin
    for i in 0..31 loop
        if i % 8 = 0 then code := code || '-'; end if;
        code := code || substr(alphabet, (get_byte(bytes,i) & 31)+1, 1);
    end loop;
    return code;
end;
$$;

-- These admin functions are callable only by the database owner in SQL Editor.
create or replace function stc_licensing.issue_license(p_buyer text, p_days integer default null)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare
    code text := stc_licensing.new_code();
    identifier uuid;
begin
    if p_buyer is null or length(trim(p_buyer)) not between 1 and 200
       or (p_days is not null and p_days not between 1 and 36500) then
        raise exception 'Provide a buyer reference and optional positive expiry days (maximum 36500)';
    end if;
    insert into stc_licensing.licenses(buyer_ref,code_hash,expires_at)
    values(trim(p_buyer),encode(extensions.digest(code,'sha256'),'hex'),
           case when p_days is null then null else now()+make_interval(days=>p_days) end)
    returning id into identifier;
    insert into stc_licensing.audit(license_id,action) values(identifier,'issued');
    return jsonb_build_object('license_id',identifier,'code',code);
end;
$$;

create or replace function stc_licensing.revoke_license(p_id uuid)
returns void language plpgsql security definer set search_path = '' as $$
begin
    update stc_licensing.licenses set revoked=true where id=p_id;
    if not found then raise exception 'Unknown license'; end if;
    insert into stc_licensing.audit(license_id,action) values(p_id,'revoked');
end;
$$;

create or replace function stc_licensing.transfer_license(p_id uuid)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare code text := stc_licensing.new_code();
begin
    update stc_licensing.licenses
    set code_hash=encode(extensions.digest(code,'sha256'),'hex'), device_id=null,
        token_hash=null, activated_at=null, revoked=false where id=p_id;
    if not found then raise exception 'Unknown license'; end if;
    insert into stc_licensing.audit(license_id,action) values(p_id,'transferred_new_code');
    return jsonb_build_object('license_id',p_id,'replacement_code',code);
end;
$$;
revoke all on all functions in schema stc_licensing from public, anon, authenticated, service_role;

-- Edge-only RPC: row locking makes simultaneous first activations single-seat.
-- Denials return normally so rate-limit writes commit instead of rolling back.
create or replace function public.stc_license_access(
    p_operation text, p_credential_hash text, p_device text, p_token_hash text default null
) returns jsonb language plpgsql security definer set search_path = '' as $$
declare
    seat stc_licensing.licenses%rowtype;
    bucket_time timestamptz := date_trunc('minute',now());
    counter integer;
    over_limit boolean := false;
begin
    if p_operation is null or p_operation not in ('activate','validate')
       or p_credential_hash is null or p_credential_hash !~ '^[0-9a-f]{64}$'
       or p_device is null or p_device !~ '^[0-9a-f]{64}$'
       or (p_operation='activate' and (p_token_hash is null or p_token_hash !~ '^[0-9a-f]{64}$')) then
        return jsonb_build_object('status',400,'code','STC-L101');
    end if;
    delete from stc_licensing.rate_limits where bucket < bucket_time-interval '5 minutes';
    -- Stable lock order: global bucket first, then credential bucket.
    insert into stc_licensing.rate_limits as r(bucket,key,attempts)
    values(bucket_time,'global:'||p_operation,1)
    on conflict(bucket,key) do update set attempts=r.attempts+1 returning attempts into counter;
    over_limit := counter > case when p_operation='activate' then 300 else 3000 end;
    insert into stc_licensing.rate_limits as r(bucket,key,attempts)
    values(bucket_time,p_operation||':'||p_credential_hash,1)
    on conflict(bucket,key) do update set attempts=r.attempts+1 returning attempts into counter;
    over_limit := over_limit or counter > case when p_operation='activate' then 5 else 60 end;
    if over_limit then return jsonb_build_object('status',429,'code','STC-L106'); end if;

    if p_operation='activate' then
        select * into seat from stc_licensing.licenses where code_hash=p_credential_hash for update;
    else
        select * into seat from stc_licensing.licenses where token_hash=p_credential_hash for update;
    end if;
    if not found then return jsonb_build_object('status',401,'code','STC-L101'); end if;
    if seat.revoked or (seat.expires_at is not null and seat.expires_at<=now()) then
        return jsonb_build_object('status',403,'code','STC-L103');
    end if;
    if seat.device_id is not null and seat.device_id<>p_device then
        return jsonb_build_object('status',409,'code','STC-L102');
    end if;
    if p_operation='activate' then
        update stc_licensing.licenses set device_id=p_device,token_hash=p_token_hash,activated_at=now() where id=seat.id;
        insert into stc_licensing.audit(license_id,action) values(seat.id,'activated');
    elsif seat.device_id is null then
        return jsonb_build_object('status',401,'code','STC-L101');
    end if;
    return jsonb_build_object('status',200,'license_id',seat.id);
end;
$$;
revoke all on function public.stc_license_access(text,text,text,text) from public, anon, authenticated;
grant execute on function public.stc_license_access(text,text,text,text) to service_role;
commit;
