# STC Statistics: Supabase activation setup

Project: `zwjhjfgoiofbiyguhcbx`  
API: `https://zwjhjfgoiofbiyguhcbx.supabase.co/functions/v1/stc-license`

Customers do not create Supabase accounts. They enter their purchased STC UNIC CODE; later launches verify the Windows-protected activation token. STC alone operates Supabase. GitHub Releases remains the update host.

Status: the developer completed the dashboard setup and supplied successful live verification output for signed activation, saved-token validation and second-seat rejection. The desktop public key is provisioned. No authenticated Supabase management access has been shared with the assistant. Version 0.5.6 is prepared in `releases/0.5.6/` as an application-only update; no EXE has been rebuilt or update published. The steps below remain the setup/recovery procedure. Do not generate a replacement signing key for this existing deployment.

## 1. Create the private database objects

Open [this project's SQL Editor](https://supabase.com/dashboard/project/zwjhjfgoiofbiyguhcbx/sql/new). Create a new query, paste the **entire** contents of `supabase/migrations/202611140001_stc_licensing.sql`, and click Run as the default postgres database owner. Keep the surrounding transaction. Do not paste this SQL into a Python notebook.

This creates a private `stc_licensing` schema, license/audit/rate-limit tables, private admin functions, and one backend-only RPC. It does not change Auth signup settings or other application tables. Tables use RLS and no public policies; the RPC explicitly denies anon/authenticated roles. Do not expose this private schema in Data API settings and do not add permissive policies to fix an error.

Next run `supabase/tests/licensing.sql` in a separate SQL Editor query. It checks permissions, binding, second-seat rejection, token rotation, revocation, transfers, expiry and throttling. Its transaction rolls back all temporary test rows. Expect a successful result and an STC licensing passed notice. These SQL tests have not yet been executed against your remote database.

## 2. Add the signing secret privately

From the STC Statistics folder in PowerShell, if not already prepared:

```powershell
.venv\Scripts\python.exe -m pip install -r licensing_server\requirements.txt
.venv\Scripts\python.exe supabase_setup.py prepare
```

Preparation reuses the existing private signing key; it does not rotate it or generate real buyer codes. A fresh key must not replace an already deployed key without a planned client key migration.

Open [Edge Function Secrets](https://supabase.com/dashboard/project/zwjhjfgoiofbiyguhcbx/functions/secrets). Add:

- Name: `STC_LICENSE_SIGNING_KEY`
- Value: the text after `STC_LICENSE_SIGNING_KEY=` in your local `.licensing_private/supabase/edge-secrets.env` file. It is one base64 line. Paste only the value in the dashboard Value field.

Do not send this value in chat, screenshots or email. Keep `.licensing_private/` out of GitHub and all app/update packages. Back up the signing key securely. There is no need to send STC's Supabase secret key to the desktop app: the Edge Function uses Supabase's server-side injected key, preferring named secret keys and supporting the legacy injected service-role key for compatibility.

## 3. Deploy the activation function

Open [Edge Functions](https://supabase.com/dashboard/project/zwjhjfgoiofbiyguhcbx/functions). Create a function using the dashboard editor, named **`stc-license`**. Replace its sample `index.ts` with the entire generated file `supabase/dashboard/stc-license.ts` and deploy.

For **this function only**, turn **Verify JWT off**. Customers have license credentials rather than Supabase Auth JWTs. Our handler checks the license code/token and the database enforces assignment and rate limits. Leaving the platform JWT check on prevents the app from reaching our handler. Do not turn off JWT checks on unrelated functions, and never put a service-role key in the app to work around a 401.

Visit:

`https://zwjhjfgoiofbiyguhcbx.supabase.co/functions/v1/stc-license/health`

Expect `{"service":"STC licensing","status":"ok"}`. This proves routing, not signing/database access. The signed activation test below is still required.

CLI alternative (run locally; log in privately when prompted, never paste the access token in chat):

```powershell
supabase login
supabase link --project-ref zwjhjfgoiofbiyguhcbx
# Apply migrations only once. If you already used SQL Editor, skip db push
# until you reconcile CLI migration history with the manually applied migration.
supabase db push
supabase secrets set --env-file .licensing_private/supabase/edge-secrets.env
supabase functions deploy stc-license --project-ref zwjhjfgoiofbiyguhcbx --no-verify-jwt
```

## 4. Test activation before enabling a customer release

In SQL Editor, issue a temporary test seat:

```sql
select stc_licensing.issue_license('STC-INTERNAL-DEPLOYMENT-TEST');
```

Keep the returned license ID and code private. On this development PC:

```powershell
.venv\Scripts\python.exe supabase_setup.py verify
```

Enter the test code at the hidden prompt. The command checks a real signed activation response, saved-token validation and rejection of a different device fingerprint. **Only after all succeed** does it configure the desktop's public verification key. The temporary credential stays in the private setup directory, separate from the customer's normal activation store. This test assigns the seat to this Windows account/PC; revoke it afterwards:

```sql
select stc_licensing.revoke_license('YOUR-TEST-LICENSE-ID'::uuid);
```

Do not use the deployment test code as a customer code. Also test a real second PC/account before selling the release. Local simulated device rejection is not a physical second-PC test.

## 5. Sell and manage licenses

Run privately in SQL Editor:

```sql
-- Perpetual one-seat license. For expiry, optionally pass a second argument, e.g. 365.
select stc_licensing.issue_license('UNIVERSITY-INVOICE-001');

-- Review seat status without exposing code/token hashes.
select id,buyer_ref,revoked,created_at,activated_at,expires_at,
       device_id is not null as assigned
from stc_licensing.licenses order by created_at desc;

select stc_licensing.revoke_license('LICENSE-ID'::uuid);
select stc_licensing.transfer_license('LICENSE-ID'::uuid);
```

Issue/transfer returns a code once. Deliver it privately after payment. A transfer retires both the old code and old saved token, permits another PC/account, and does not extend expiry. Keep purchase verification separate from the technical transfer operation. Only STC's database owner can call these admin functions; there is no public admin endpoint.

In Supabase, high-entropy random codes (160 bits) and tokens (256 bits) are stored only as SHA-256 hashes; raw values are not kept. This differs from the alternative Python server's peppered HMAC storage. No raw Windows IDs, datasets or notebook contents are sent. Do not log request bodies or raw codes. Rate limits are per credential plus global minute ceilings; they do not rely on potentially spoofed forwarded IP headers. Monitor function usage/availability, protect STC dashboard access, and maintain tested database/signing-key backups before university rollout.

## 6. Deliver through the existing updater

After live verification and a customer-device check, select the next app version, create the application-only update ZIP and `update.json`, then publish both to GitHub Releases through the normal workflow. Do not publish an activation build before Supabase is working. Internet is required when opening the app; revocation/expiry is checked at launch. Modified source, old unlicensed builds and fully cloned Windows installations remain outside this protection; see [LICENSING.md](LICENSING.md).

## Local verification

```powershell
node --test tests/supabase_protocol.test.mjs
.venv\Scripts\python.exe -m unittest discover -s tests -p test_supabase_setup.py
```

Node tests exercise the actual handler/signing modules with a substituted database RPC. Python verifies a genuine Node-generated RSA-PSS signature through Windows CNG and checks that failed verification cannot provision the client. SQL transaction/concurrency and deployed Deno behavior still require the Supabase migration/tests/live activation above; no local Postgres or Deno CLI is installed here.

References: [Edge Functions](https://supabase.com/docs/guides/functions), [function configuration](https://supabase.com/docs/guides/functions/function-configuration), [server secrets](https://supabase.com/docs/guides/functions/secrets), [database function privileges](https://supabase.com/docs/guides/database/functions).
