# STC UNIC CODE licensing

Status: Supabase deployment and the developer's live verification are complete. The developer supplied successful output for signed activation, saved-token validation and second-seat rejection; the desktop public key is provisioned. Version 0.5.6 is prepared as an application-only release candidate. It is not automatically published or installed, and the existing EXE remains unchanged. Have a valid STC UNIC CODE before installing, and test a physical second PC/account before selling the release.

**Selected hosting: Supabase.** Follow [SUPABASE_SETUP.md](SUPABASE_SETUP.md) for this project's database, Edge Function, private signing secret and live test. Customers do not create accounts. The Docker/Python instructions below are an alternative backend, not an additional service required with Supabase.

## Buyer experience

Every normal launch checks the saved license online. Valid activation opens the workspace automatically. First-time buyers enter the code STC gives them after purchase. The English/French screen includes the STC logo, masked code entry, retry, and the supplied [STC LinkedIn page](https://www.linkedin.com/company/system-technologies-company-stc/posts/?viewAsMember=true).

One code binds atomically to **one PC and one Windows account**. A second PC/account is rejected. Windows DPAPI encrypts the saved token for that account and PC. Copying program folders or the activation file to a different PC/account does not provide normal access. The purchase code is never saved locally. Each startup requires a signed server response bound to a fresh random challenge and the device hash.

Internet is required at startup. If verification fails, the workspace stays locked and projects remain on disk. Revocation and expiry take effect at the next launch, without interrupting an analysis already running. Deleting local credentials does not release the server's seat assignment. STC must approve a transfer and issue a replacement code.

The service receives the activation code, a random token on later checks, a challenge, and a hash derived from Windows MachineGuid/user SID. It does not receive datasets, notebooks, raw Windows IDs, or user/computer names. Use an internal purchase reference instead of unnecessary personal information. Codes/tokens are HMAC-hashed in SQLite. Private keys, the hashing pepper and database stay on STC's server. Only the public verification key and HTTPS endpoint go in the desktop app. There is no remote admin API.

## Protection limits

This enforces a seat, not proof of a physical person's identity. It cannot prevent use of the buyer's Windows session. Modified Python, a fully cloned Windows installation, and older unlicensed releases remain possible bypasses. Do not advertise impossible-to-bypass protection. A later commercial build should package and sign the application and restrict editable source; that is a separate packaging task. GitHub Releases hosts updates but cannot host this private activation database.

## Deploy the service

STC needs a Docker Compose server, a hostname pointing to it, and inbound TCP 80/443. The example uses Caddy HTTPS and persistent storage on one server. Replace `licenses.example.com` with an actual hostname. From the repository root on that server:

```bash
export LICENSE_DOMAIN=licenses.example.com
docker compose -f licensing_server/compose.yaml build
docker compose -f licensing_server/compose.yaml run --rm api python -m licensing_server.manage --data /data init
docker compose -f licensing_server/compose.yaml up -d
```

Run `init` once: it refuses to overwrite existing secrets. Do not delete `license_data`. Back up the database and private directory together with a consistent SQLite backup or a stopped service, restrict access, and test restoration. Losing the pepper/key breaks existing activations. Never upload these secrets to GitHub, release ZIPs or buyer PCs.

The container uses an unprivileged user and no published API port. Caddy is the only exposed listener. Forwarded IPs are trusted only from the fixed proxy address. Change the reserved subnet if it conflicts with your network. Check `https://YOUR_HOST/health`, trusted TLS, time synchronization, restart persistence and access from university PCs before rollout. Monitor availability/disk use; for larger deployments add infrastructure connection limits and monitoring. This initial service is not a high-availability cluster.

## Issue and manage codes

Run privately on the server. Issue/transfer prints the real code once: deliver it privately, never in release notes, public posts or screenshots. Codes cannot be recovered from their stored hashes.

```bash
# A perpetual seat; optionally add --days 365 for expiry.
docker compose -f licensing_server/compose.yaml exec api python -m licensing_server.manage --data /data issue --buyer UNIVERSITY-INVOICE-001

# Lists references and license IDs, without codes/tokens.
docker compose -f licensing_server/compose.yaml exec api python -m licensing_server.manage --data /data list

# Replace LICENSE_ID with the ID from issue/list.
docker compose -f licensing_server/compose.yaml exec api python -m licensing_server.manage --data /data revoke LICENSE_ID
docker compose -f licensing_server/compose.yaml exec api python -m licensing_server.manage --data /data transfer LICENSE_ID
```

Transfer invalidates the old code/token and returns a replacement for another PC. It does not extend expiry. Verify the purchase before authorizing a transfer. For university labs, issue one code per agreed seat; multi-seat institutional licensing is a separate policy.

For private development, install `licensing_server/requirements.txt`, run `python -m licensing_server.manage --data licensing_data init`, issue a code, and run `python -m licensing_server.server --data licensing_data`. Its default HTTP loopback listener is for development; the production desktop rejects HTTP.

## Configure the desktop and release

After deploying HTTPS, export public material on the server:

```bash
docker compose -f licensing_server/compose.yaml exec -T api python -m licensing_server.manage --data /data export-public --url https://YOUR_HOST > license-public.json
```

Copy only `license-public.json` to the development PC. From the STC Statistics source directory:

```powershell
.venv\Scripts\python.exe -m licensing_server.manage configure-client --root . --public-config license-public.json
```

This writes `stc_statistics/license_config.json` and `license_trust.py` without needing private server data. Verify hostname/key and test a seat against real HTTPS. Release packaging refuses an unconfigured activation build; this static guard does not prove the service is reachable, so the live test remains required.

Only then select the next version, run tests and create/publish an application patch through the existing GitHub release workflow. No EXE rebuild or release publication has been performed for this change. Existing unlicensed releases cannot be remotely made licensed.

An update introducing activation loads the saved workspace into memory before acknowledging startup while activation is pending. It exposes no workbench until verification succeeds, then restores the saved project/page through the normal recovery flow. The checkpoint stays on disk if activation is closed. A checkpoint or rollback does not grant a license.

## Support codes

| Code | Meaning/action |
| --- | --- |
| STC-L100 | No activation yet; enter the purchased code. |
| STC-L101 | Code/token not recognized; verify spelling/purchase. |
| STC-L102 | Assigned to another PC/account; arrange a transfer with STC. |
| STC-L103 | Revoked or expired; contact STC. |
| STC-L104 | Service/configuration/network unavailable. |
| STC-L105 | Saved Windows credential cannot be used; reactivate on the licensed account. |
| STC-L106 | Too many attempts; wait one minute. |
| STC-L107 | Local activation could not be saved. |
| STC-L108 | Signature/challenge validation failed; verify configuration and system clocks. |

Activation messages are bilingual and contain safe support codes, not exceptions, endpoints or tokens. Never request full codes in public support.
