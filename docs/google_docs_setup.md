# Google Docs proposal export — setup

The proposal card has an **Open in Google Docs** button next to the
`.docx` download. It renders the same proposal, uploads it to Google
Drive converted to a native Google Doc, and redirects the advisor to
the editable document.

The button only appears once the integration is configured. Until then
the app runs exactly as before (`.docx` / PDF / HTML unchanged).

## How it works

`app/google_docs.py` authenticates with a Google **service account** and
uploads the rendered `.docx` bytes to Drive with
`mimeType = application/vnd.google-apps.document`, which makes Drive
convert it to a Google Doc. The endpoints are:

- `GET /api/clients/{id}/proposal.gdoc` — existing-client proposals
- `GET /api/prospect/proposal.gdoc` — prospect (no DB record) proposals
- `GET /api/google-docs/status` — config diagnostics

## Recommended setup: Shared Drive (no Workspace admin needed)

1. **GCP project** — at <https://console.cloud.google.com> create a
   project (or reuse one), then enable the **Google Drive API**
   (APIs & Services → Library → Google Drive API → Enable).

2. **Service account** — APIs & Services → Credentials → Create
   credentials → Service account. Name it e.g. `teroxx-proposals`.
   No project roles are needed. Open the account → Keys → Add key →
   Create new key → JSON. A `.json` file downloads. Note the
   `client_email` inside it (looks like
   `teroxx-proposals@PROJECT.iam.gserviceaccount.com`).

3. **Shared Drive** — in Google Drive, signed in as
   `aleksander.biesaga@teroxx.com`, create a Shared Drive called
   e.g. `Teroxx Proposals`. Open it → Manage members → add the service
   account `client_email` as **Content manager**.

4. **Folder ID** — open the Shared Drive (or a subfolder inside it).
   The ID is the last path segment of the URL:
   `https://drive.google.com/drive/folders/<THIS_IS_THE_ID>`.

5. **Render env vars** — on the `teroxx-portfolio-app` service
   (Dashboard → Environment, set each key individually — never bulk
   edit, it wipes other secrets):

   | Key | Value |
   |-----|-------|
   | `GOOGLE_SERVICE_ACCOUNT_JSON` | base64 of the JSON key file (see below) |
   | `GOOGLE_DRIVE_FOLDER_ID` | the folder ID from step 4 |
   | `GOOGLE_DOCS_SHARE` | `none` (Shared Drive membership grants access) |

   Encode the key as a single line:
   ```bash
   base64 -i teroxx-proposals-XXXX.json | tr -d '\n'
   ```
   (raw JSON also works, but base64 avoids newline issues in the
   dashboard).

6. **Redeploy** — Render env-var changes need a fresh deploy to take
   effect. After it deploys, hit `/api/google-docs/status` while logged
   in; `configured` should be `true`.

Docs created this way are owned by the Shared Drive, so every Shared
Drive member sees them. Set `GOOGLE_DOCS_SHARE=domain` instead if you
also want anyone at `teroxx.com` with the link to be able to edit.

## Alternative: domain-wide delegation (files in a real user's Drive)

Use this if you want the docs owned by `aleksander.biesaga@teroxx.com`
and showing up in his My Drive. It needs a one-time Google Workspace
admin grant.

1. Do steps 1–2 above. In the service account details, note the
   **Unique ID** (numeric client ID).
2. In the **Google Admin console** → Security → Access and data
   control → API controls → Domain-wide delegation → Add new: paste the
   Unique ID and the scope `https://www.googleapis.com/auth/drive`.
3. Render env vars: `GOOGLE_SERVICE_ACCOUNT_JSON` (as above) plus
   `GOOGLE_IMPERSONATE_SUBJECT = aleksander.biesaga@teroxx.com`.
   `GOOGLE_DRIVE_FOLDER_ID` is optional — set it to a My Drive folder
   ID, or leave it unset to drop docs in the Drive root.

## Env var reference

| Key | Required | Notes |
|-----|----------|-------|
| `GOOGLE_SERVICE_ACCOUNT_JSON` | yes | Service account key, raw JSON or base64 JSON. The button stays hidden until this is set. |
| `GOOGLE_DRIVE_FOLDER_ID` | no | Target folder (Shared Drive folder or My Drive folder). |
| `GOOGLE_IMPERSONATE_SUBJECT` | no | Workspace user to impersonate (domain-wide delegation only). |
| `GOOGLE_DOCS_SHARE` | no | `none` (default), `domain`, or `anyone`. Link-sharing applied to each created doc. |
| `GOOGLE_DOCS_SHARE_DOMAIN` | no | Domain for `GOOGLE_DOCS_SHARE=domain`. Default `teroxx.com`. |

The service account private key is a secret — keep it out of
`render.yaml` (which is committed). Set it only via the Render
dashboard or the single-key env-var API.
