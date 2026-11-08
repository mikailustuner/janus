# Note token keys: setup and rotation

The QR code on a doctor note carries a signed token (`doctor-loop` design §6). The server signs and verifies it with
keys from the environment. Nothing else about the token is secret: it holds codes only, no personal data.

## Settings
| Variable | Meaning |
|---|---|
| `JANUS_NOTE_KEYS` | `kid:base64url` pairs, comma-separated. Each key decodes to at least 32 bytes and differs from `JANUS_NOISE_KEY`. A key id is 1 to 8 characters of `a-z0-9`. |
| `JANUS_NOTE_SIGNING_KEY_ID` | The key id used for new tokens. It must be one of the ids in `JANUS_NOTE_KEYS`. |
| `JANUS_OUTCOME_CONSENT_VERSIONS` | Consent text versions the outcome loop accepts (separate from the donation consent). |
| `JANUS_PUBLIC_BASE_URL` | Optional `https://host[/path]`, at most 40 bytes; the API then returns the QR address `<base>/o#<token>`. |

With no keys the outcome loop is off (503 `notes_unavailable`); the note document still works.

Generate a key: `python -c "import secrets,base64; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip('='))"`.
Keep keys in the secret store, never in the repository, a log or an issue.

## Rotation
A token is valid for 28 to 35 days (it expires on the Monday five weeks after its issue week).
1. Add a new pair to `JANUS_NOTE_KEYS` and keep the old one.
2. Switch `JANUS_NOTE_SIGNING_KEY_ID` to the new id and restart the API. New tokens use the new key; old tokens still verify.
3. After at least 35 days, remove the old pair. Tokens signed with it are then rejected (`invalid_token`).
To retire a key at once (suspected leak), remove it immediately: its tokens stop working, and the doctors holding them
cannot report; issue new notes.

## Checks after a change
`GET /health` stays `ok`. Issue a token on a test note (`POST /notes/token`), open the form (`POST /outcomes/form`) and
withdraw it (`POST /notes/withdraw`). Print a note and scan its QR code at 50 mm on paper with two phones before launch
(`docs/pre-launch-checklist.md`).
