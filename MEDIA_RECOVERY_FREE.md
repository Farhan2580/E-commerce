# Private temporary media recovery without Render Shell

This adds a disabled-by-default HTTPS recovery endpoint and an operator-run local
client. It makes no uploads and performs no database writes, record exports, asset
deletions, renames or overwrites. No commit, push, deployment or production setting
change has been performed automatically. Existing Cloudinary/S3/local modes remain.

## Stop point: a new deployment cannot rescue the old ephemeral disk

Render Free loses local filesystem changes on redeploy, restart and idle spin-down.
That includes uploads AND any production SQLite changes. Installing this endpoint,
changing environment variables, or deploying Cloudinary can itself cause that loss.
There is no safe way for code that is not yet installed to read the old instance's
files. This endpoint can diagnose/back up files surviving on the instance where it
is actually running; it cannot recover files already lost during its rollout.

BEFORE any rollout/config change, use an already available authenticated export or
backup facility, storage-provider backup, or original uploaders' copies. An Admin
file link only helps if its underlying URL actually serves the original. If all
links are 404 and there is no already-running private export/Shell/SSH/storage access,
recovery of old-instance-only bytes cannot be guaranteed. Stop and recover those
originals through the uploader, existing backup, or Render support before accepting
a redeploy. Do not claim the new endpoint is a backup of the previous instance.
The endpoint deliberately DOES NOT export SQLite, users, orders or payment records.
If the active database is ephemeral SQLite, obtain a separate authorized backup
before redeployment; this image-only feature cannot protect or migrate it.

Reference: https://render.com/docs/free#local-files-lost-on-redeploy

## Access controls and exact temporary Render variables

The endpoint is not linked from the site. Both paths always reject unauthenticated
access with an empty 404 before any database query. Paths being known is not an
authentication mechanism. Access requires all of:

- `DEBUG=False` and HTTPS (Render's existing proxy configuration recognizes TLS).
- `MEDIA_RECOVERY_ENABLED=1`.
- `MEDIA_RECOVERY_TOKEN`: 43–128 URL-safe characters, generated cryptographically;
  use Render's secure random generation control with at least 256 bits of entropy.
  It is not a password you invent. Its only persistent storage must be Render's
  environment. Never put it in code, .env files, URLs, command arguments, screenshots,
  tickets, exported manifests, or logs. Copy it directly into the client's masked
  prompt when needed; the client holds it only in process memory. Do not configure
  proxy/application loggers to log Authorization headers.
- `MEDIA_RECOVERY_EXPIRES_AT`: a timezone-aware ISO UTC deadline, e.g. format
  `YYYY-MM-DDTHH:MM:SS+00:00`. Set it about one hour ahead. Missing, malformed,
  expired, or more than 24 hours ahead disables access. Expiry disables access
  without a restart. Use a new secret and short window if another recovery is needed.
- `Authorization: Bearer <temporary secret>` in the HTTP request header. Cookie
  login alone or a query-string token does not authorize access.

Keep `DJANGO_DEBUG=0`. No extra recovery packages are required beyond the project's
existing Django/Pillow dependencies. All requests must use HTTPS. Only GET is
accepted. Responses prohibit caching/indexing/framing and have no public CORS access.
Unauthorized, expired and disabled responses reveal no diagnostics. Internal errors
are reduced to a generic error rather than stack traces, paths or provider messages.

To calculate a nonsecret one-hour deadline in PyCharm's terminal:

```powershell
& .\.venv\Scripts\python.exe -c "from datetime import datetime,timedelta,timezone; print((datetime.now(timezone.utc)+timedelta(hours=1)).isoformat())"
```

Copy only that timestamp into the expiry variable. Generate/copy the bearer secret
through the Render environment UI, never through a command containing its value.

Endpoint paths:

```text
/internal/media-recovery/manifest/?source=local&offset=0
/internal/media-recovery/original/<opaque-download-id>/?source=local
```

The manifest is paginated in batches of ten distinct image keys. It includes only
key, status, readable size/format/checksum and a temporary authenticated download
ID. It has no model names, PKs, product descriptions/prices, users, orders, payments,
absolute paths, provider credentials or signed URLs. Downloads allow only safe,
database-referenced ImageField keys, validate image bytes, and are attachments.
Arbitrary filenames, URLs, filesystem paths and database downloads are not supported.
Each original is limited to 25 MiB. Larger files are reported, not silently truncated.

`source=local` checks MEDIA_ROOT even if Cloudinary is selected. It is specifically
for surviving local uploads. `source=configured` reads the selected storage backend
(filesystem/S3/Cloudinary). Neither writes to the provider. Export both sources to
SEPARATE directories if their contents might differ. The endpoint never accepts a
storage location or remote URL from a caller.

## Safest manual rollout order

1. Complete the pre-rollout backup/stop-point assessment above. Record which live
   database/storage is actually in use. Do not change database settings or activate
   Cloudinary as a shortcut for making the exporter available.
2. Review/tests locally. When the owner elects to deploy the recovery feature,
   keep the existing database and media mode. Configure the three temporary
   recovery variables on the existing service and deploy manually. Combine changes
   into one planned rollout when possible; every additional restart is another
   ephemeral-data-loss boundary. No paid service is created by these instructions.
3. Pause image edits/uploads operationally during the export so pagination and
   checksums describe a stable inventory. Do not put the secret into a browser URL
   or use the anonymous website to expose the diagnostics.
4. In PyCharm's INTERACTIVE terminal, from the repository root:

   ```powershell
   $py = '.\.venv\Scripts\python.exe'
   & $py -m pip install -r requirements.txt
   & $py manage.py check
   & $py tools/recover_media.py --origin https://farhan-gadgetflow.onrender.com --destination '.\.local-backups\render-recovery-01' --source local
   ```

   The client prompts for the secret without echo and refuses redirects so it does
   not forward bearer credentials to another URL. It exports
   `.local-backups/render-recovery-01/manifest.json`. It does not persist the secret
   or download IDs. Merely exporting the manifest does NOT back up original bytes.

5. To explicitly back up surviving production originals, use a NEW destination:

   ```powershell
   & $py tools/recover_media.py --origin https://farhan-gadgetflow.onrender.com --destination '.\.local-backups\render-backup-01' --source local --download
   ```

   Originals go under `render-backup-01/originals/<exact-image-key>`. The tool
   verifies the response size, SHA-256 and Pillow readability before writing.
   It creates files exclusively, skips existing identical originals, reports
   conflicts, and never replaces an existing file. It writes `manifest.json` and
   `backup-report.json` once and refuses to overwrite reports. Use a new directory
   for each retry; do not delete prior attempts. Partial backups remain available.

   If a persistent provider was previously configured, back it up separately:

   ```powershell
   & $py tools/recover_media.py --origin https://farhan-gadgetflow.onrender.com --destination '.\.local-backups\provider-backup-01' --source configured --download
   ```

   Keep these directories private and outside public/static/media serving. The
   repository already ignores `.local-backups/`. Do not commit/upload the backups.

6. Examine every manifest/report status. `ready` means readable at export time,
   not already backed up; require `saved_verified`/`existing_identical` in the backup
   report for each available original. `missing` means no file at this source/key;
   check the other source, exact local original, uploader's copy and backups.
   `unreadable` means storage access/image validation failed (not proof of deletion).
   `too_large` needs a separately reviewed backup method. `unsafe_key` is refused.
   Never reset DB rows, invent images, or drop missing entries from the manifest to
   declare recovery complete. Requests failing after a secret expires can be retried
   in a new short window/new destination; already saved originals stay untouched.

7. The exported minimal manifest is accepted by the updated `transfer_media`
   command. Decide which authoritative originals correspond to each key. If local
   `media/` already contains every required original, use it as the source. Otherwise
   use the verified backup's `originals/` tree, restoring missing exact local originals
   into that tree only through reviewed non-overwriting copies. Keep conflicting
   local/provider copies separate; do not silently choose one. This endpoint does
   not perform those copies or any Cloudinary upload.

   In a separate local transfer process, configure Cloudinary credentials manually
   as described in CLOUDINARY_MEDIA.md, leaving database settings unchanged. First
   dry-run, then explicitly authorize the upload yourself:

   ```powershell
   & $py manage.py transfer_media --source '.\.local-backups\render-backup-01\originals' --manifest '.\.local-backups\render-backup-01\manifest.json'
   & $py manage.py transfer_media --source '.\.local-backups\render-backup-01\originals' --manifest '.\.local-backups\render-backup-01\manifest.json' --upload
   ```

   Without `--upload`, it does not upload anything. Manifest mode performs no DB
   queries/writes. Cloudinary transfer uses overwrite=False and compares original
   bytes; any missing/conflicting item is a failure, never an invitation to force.

8. Once all required images are verified in Cloudinary, manually activate the SAME
   Cloudinary cloud/prefix on Render and deploy. Preserve all existing database
   references and payment configuration. Verify image URLs and actual new uploads
   after redeploy; collectstatic is not a media transfer.
9. Disable recovery: let the short deadline expire for an immediate no-restart
   cutoff; set `MEDIA_RECOVERY_ENABLED=0` and remove the token/deadline from Render
   after durable-media backups are complete. Remove the route/module in a later
   reviewed deployment if desired. Do not leave a new long-lived recovery token.
   Test access without Authorization and with the OLD token: both must return 404,
   with no manifest/download data. The endpoint is also off by default when these
   variables are absent. Changing env values may restart Render; do it only after
   the backups/persistent storage are verified.

## Limits and remaining blockers

This is an owner-authorized image recovery facility, not a database backup endpoint.
It cannot recover a previous instance's destroyed disk, lost ephemeral SQLite rows,
files absent from every original/backup, or prove that a currently deployed service
has the expected environment. It exports only keys still referenced by ImageFields;
unreferenced files are intentionally not enumerated or downloadable. A referenced
file changed during export fails checksum verification rather than overwriting a
local original. Backups are not complete until reports and missing keys are resolved.

Local validation: Django checks passed and all 134 shop tests passed. Tests use
fixture secrets, isolated databases, temporary image copies and mocked provider
reads; the client end-to-end test uses the Django test client, not the live website.
No actual credentials, production export, upload or deployment was used.
