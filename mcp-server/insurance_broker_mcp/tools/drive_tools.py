"""
Cloud storage integration — Google Drive + SharePoint (Microsoft 365).

GOOGLE DRIVE
─────────────
Tools: broker_drive_upload / broker_drive_list / broker_drive_get_link
Auth:  Service Account JSON → GOOGLE_APPLICATION_CREDENTIALS_JSON env var
Setup:
  1. Google Cloud Console → IAM → Service Accounts → Create → Download JSON key
  2. Paste full JSON as single line into GOOGLE_APPLICATION_CREDENTIALS_JSON
  3. Share target Drive folder with the service account email (Editor role)
  4. Copy folder ID from folder URL → GOOGLE_DRIVE_FOLDER_ID

SHAREPOINT (Microsoft 365)
───────────────────────────
Tools: broker_sharepoint_upload / broker_sharepoint_list / broker_sharepoint_get_link
Auth:  App Registration in Azure AD → Client Credentials flow
Setup:
  1. Azure Portal → App registrations → New registration
  2. API permissions → Sites.ReadWrite.All (application) → Grant admin consent
  3. Certificates & secrets → New client secret
  4. Set: SHAREPOINT_TENANT_ID, SHAREPOINT_CLIENT_ID, SHAREPOINT_CLIENT_SECRET
  5. Set: SHAREPOINT_SITE_URL (e.g. https://company.sharepoint.com/sites/Brokeraj)
  6. Set: SHAREPOINT_FOLDER_PATH (e.g. /Shared Documents/Oferte)
"""
import os
import json
import mimetypes
from pathlib import Path
from typing import Optional
from fastmcp import FastMCP

# ─── Config: Google Drive ─────────────────────────────────────────────────────
_CREDS_JSON  = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON", "")
_FOLDER_ID   = os.environ.get("GOOGLE_DRIVE_FOLDER_ID", "")
_SCOPES      = ["https://www.googleapis.com/auth/drive.file"]

# ─── Config: SharePoint ───────────────────────────────────────────────────────
_SP_TENANT_ID     = os.environ.get("SHAREPOINT_TENANT_ID", "")
_SP_CLIENT_ID     = os.environ.get("SHAREPOINT_CLIENT_ID", "")
_SP_CLIENT_SECRET = os.environ.get("SHAREPOINT_CLIENT_SECRET", "")
_SP_SITE_URL      = os.environ.get("SHAREPOINT_SITE_URL", "")       # e.g. https://company.sharepoint.com/sites/Brokeraj
_SP_FOLDER_PATH   = os.environ.get("SHAREPOINT_FOLDER_PATH", "/Shared Documents/Oferte")

OUTPUT_DIR = Path(__file__).parent.parent.parent / "output"


# ─── Internal helper ──────────────────────────────────────────────────────────

def _get_drive_service():
    """Build and return authenticated Google Drive v3 service.

    Raises ImportError if google-api-python-client is not installed.
    Raises ValueError if credentials or folder ID are missing.
    Raises google.auth.exceptions.* on auth errors.
    """
    if not _CREDS_JSON:
        raise ValueError(
            "GOOGLE_APPLICATION_CREDENTIALS_JSON not set in .env. "
            "Add the full service account JSON content as a single-line value."
        )
    if not _FOLDER_ID:
        raise ValueError(
            "GOOGLE_DRIVE_FOLDER_ID not set in .env. "
            "Copy the folder ID from the Google Drive URL and add it."
        )

    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build

    creds_dict = json.loads(_CREDS_JSON)
    creds = Credentials.from_service_account_info(creds_dict, scopes=_SCOPES)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def _mime_for(path: Path) -> str:
    """Return MIME type for a file path."""
    mime, _ = mimetypes.guess_type(str(path))
    if mime:
        return mime
    ext = path.suffix.lower()
    return {
        ".pdf":  "application/pdf",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".txt":  "text/plain",
        ".csv":  "text/csv",
        ".png":  "image/png",
        ".jpg":  "image/jpeg",
    }.get(ext, "application/octet-stream")


def _resolve_local_path(filename: str) -> Optional[Path]:
    """Resolve a filename to an absolute path in the output directory.

    Accepts:
    - Bare filename:     "Offer_CLI001_2026-03-10.pdf"
    - Relative path:     "output/Offer_CLI001_2026-03-10.pdf"
    - Absolute path:     "/full/path/to/file.pdf"
    """
    p = Path(filename)
    if p.is_absolute() and p.exists():
        return p
    candidate = OUTPUT_DIR / p.name
    if candidate.exists():
        return candidate
    if p.exists():
        return p.resolve()
    return None


# ─── Implementation functions ─────────────────────────────────────────────────

def _upload_to_drive_impl(filename: str, drive_filename: Optional[str] = None) -> str:
    """Upload a local file to Google Drive and return a shareable link."""
    local_path = _resolve_local_path(filename)
    if not local_path:
        return (
            f"❌ **Fișier negăsit:** `{filename}`\n\n"
            f"Verifică că fișierul există în directorul `output/` sau specifică calea completă."
        )

    dest_name = drive_filename or local_path.name
    mime_type = _mime_for(local_path)

    try:
        service = _get_drive_service()
    except ImportError:
        return (
            "⚠️ **Librăria Google Drive nu este instalată.**\n\n"
            "Rulați: `pip install google-api-python-client google-auth-oauthlib google-auth-httplib2`"
        )
    except ValueError as e:
        return f"⚠️ **Configurație lipsă:** {e}"
    except Exception as e:
        return f"❌ **Eroare autentificare Google:** {str(e)[:200]}"

    try:
        from googleapiclient.http import MediaFileUpload

        file_metadata = {
            "name": dest_name,
            "parents": [_FOLDER_ID],
        }
        media = MediaFileUpload(str(local_path), mimetype=mime_type, resumable=False)

        uploaded = service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id, name, webViewLink, size",
        ).execute()

        # Make file readable by anyone with the link
        service.permissions().create(
            fileId=uploaded["id"],
            body={"type": "anyone", "role": "reader"},
        ).execute()

        file_id   = uploaded.get("id", "N/A")
        view_link = uploaded.get("webViewLink", f"https://drive.google.com/file/d/{file_id}/view")
        size_kb   = int(uploaded.get("size", 0)) // 1024

        return (
            f"✅ **Fișier încărcat în Google Drive**\n\n"
            f"- **Nume:** {dest_name}\n"
            f"- **Dimensiune:** {size_kb} KB\n"
            f"- **Link partajabil:** {view_link}\n"
            f"- **ID Drive:** `{file_id}`\n\n"
            f"Linkul poate fi trimis direct clientului sau adăugat în email."
        )

    except Exception as e:
        return f"❌ **Upload eșuat:** {str(e)[:300]}"


def _list_drive_files_impl(limit: int = 20, name_filter: Optional[str] = None) -> str:
    """List files in the configured Google Drive folder."""
    try:
        service = _get_drive_service()
    except ImportError:
        return "⚠️ Librăria Google Drive nu este instalată. Rulați: `pip install google-api-python-client google-auth-oauthlib google-auth-httplib2`"
    except ValueError as e:
        return f"⚠️ **Configurație lipsă:** {e}"
    except Exception as e:
        return f"❌ **Eroare autentificare:** {str(e)[:200]}"

    try:
        query = f"'{_FOLDER_ID}' in parents and trashed=false"
        if name_filter:
            query += f" and name contains '{name_filter}'"

        result = service.files().list(
            q=query,
            pageSize=min(limit, 50),
            fields="files(id, name, mimeType, size, modifiedTime, webViewLink)",
            orderBy="modifiedTime desc",
        ).execute()

        files = result.get("files", [])
        if not files:
            return "📂 **Google Drive — folder gol.** Nu există fișiere în folderul configurat."

        lines = [f"## 📂 Google Drive — {len(files)} fișiere\n"]
        for f in files:
            size_kb = int(f.get("size", 0)) // 1024 if f.get("size") else 0
            mod     = f.get("modifiedTime", "")[:10]
            link    = f.get("webViewLink", "")
            name    = f.get("name", "")
            lines.append(f"- **[{name}]({link})** — {size_kb} KB — {mod}")

        return "\n".join(lines)

    except Exception as e:
        return f"❌ **Eroare listare fișiere:** {str(e)[:300]}"


def _get_drive_link_impl(filename: str) -> str:
    """Search for a file by name in the configured folder and return its shareable link."""
    try:
        service = _get_drive_service()
    except ImportError:
        return "⚠️ Librăria Google Drive nu este instalată."
    except ValueError as e:
        return f"⚠️ **Configurație lipsă:** {e}"
    except Exception as e:
        return f"❌ **Eroare autentificare:** {str(e)[:200]}"

    try:
        query = f"'{_FOLDER_ID}' in parents and name='{filename}' and trashed=false"
        result = service.files().list(
            q=query,
            pageSize=5,
            fields="files(id, name, webViewLink, modifiedTime)",
            orderBy="modifiedTime desc",
        ).execute()

        files = result.get("files", [])
        if not files:
            return (
                f"❌ **Fișierul `{filename}` nu a fost găsit în Google Drive.**\n\n"
                f"Verificați că fișierul a fost încărcat cu `broker_drive_upload`."
            )

        f = files[0]
        link = f.get("webViewLink", f"https://drive.google.com/file/d/{f['id']}/view")
        return (
            f"📎 **Link Google Drive pentru `{f['name']}`:**\n\n"
            f"{link}\n\n"
            f"*(modificat: {f.get('modifiedTime','')[:10]})*"
        )

    except Exception as e:
        return f"❌ **Eroare căutare:** {str(e)[:300]}"


# ─── SharePoint: Internal helpers ────────────────────────────────────────────

def _sp_missing_config() -> Optional[str]:
    """Return error message if SharePoint config is incomplete, else None."""
    missing = [k for k, v in {
        "SHAREPOINT_TENANT_ID":     _SP_TENANT_ID,
        "SHAREPOINT_CLIENT_ID":     _SP_CLIENT_ID,
        "SHAREPOINT_CLIENT_SECRET": _SP_CLIENT_SECRET,
        "SHAREPOINT_SITE_URL":      _SP_SITE_URL,
    }.items() if not v]
    if missing:
        return (
            f"⚠️ **SharePoint nu este configurat.** Variabile lipsă din .env: "
            f"`{'`, `'.join(missing)}`\n\n"
            f"Consultați secțiunea SHAREPOINT din drive_tools.py pentru instrucțiuni de setup."
        )
    return None


def _sp_get_token() -> str:
    """Obtain Azure AD access token via client credentials flow."""
    import urllib.request
    import urllib.parse

    url = f"https://login.microsoftonline.com/{_SP_TENANT_ID}/oauth2/v2.0/token"
    data = urllib.parse.urlencode({
        "grant_type":    "client_credentials",
        "client_id":     _SP_CLIENT_ID,
        "client_secret": _SP_CLIENT_SECRET,
        "scope":         "https://graph.microsoft.com/.default",
    }).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())["access_token"]


def _sp_get_site_id(token: str) -> str:
    """Resolve SharePoint site URL to Graph API site ID."""
    import urllib.request
    from urllib.parse import urlparse

    parsed = urlparse(_SP_SITE_URL)
    hostname = parsed.hostname                       # company.sharepoint.com
    site_path = parsed.path.lstrip("/")              # sites/Brokeraj

    url = f"https://graph.microsoft.com/v1.0/sites/{hostname}:/{site_path}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())["id"]


def _sp_upload_impl(filename: str, sp_filename: Optional[str] = None) -> str:
    """Upload a local file to the configured SharePoint folder via Microsoft Graph."""
    err = _sp_missing_config()
    if err:
        return err

    local_path = _resolve_local_path(filename)
    if not local_path:
        return (
            f"❌ **Fișier negăsit:** `{filename}`\n\n"
            f"Verifică că fișierul există în directorul `output/`."
        )

    dest_name   = sp_filename or local_path.name
    folder_path = _SP_FOLDER_PATH.rstrip("/")

    try:
        import urllib.request

        token   = _sp_get_token()
        site_id = _sp_get_site_id(token)

        # PUT upload (simple upload, works up to 4 MB)
        upload_url = (
            f"https://graph.microsoft.com/v1.0/sites/{site_id}"
            f"/drive/root:{folder_path}/{dest_name}:/content"
        )
        file_bytes = local_path.read_bytes()
        mime_type  = _mime_for(local_path)
        req = urllib.request.Request(
            upload_url,
            data=file_bytes,
            method="PUT",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type":  mime_type,
            },
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())

        web_url = result.get("webUrl", "")
        size_kb = int(result.get("size", 0)) // 1024

        # Create a sharing link (anyone with link — view)
        share_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drive/items/{result['id']}/createLink"
        share_req = urllib.request.Request(
            share_url,
            data=json.dumps({"type": "view", "scope": "organization"}).encode(),
            method="POST",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type":  "application/json",
            },
        )
        try:
            with urllib.request.urlopen(share_req, timeout=10) as sr:
                share_result = json.loads(sr.read())
                share_link = share_result.get("link", {}).get("webUrl", web_url)
        except Exception:
            share_link = web_url

        return (
            f"✅ **Fișier încărcat în SharePoint**\n\n"
            f"- **Nume:** {dest_name}\n"
            f"- **Folder:** {folder_path}\n"
            f"- **Dimensiune:** {size_kb} KB\n"
            f"- **Link SharePoint:** {share_link}\n\n"
            f"Linkul este accesibil organizației. Poate fi inclus în email sau trimis direct clientului intern."
        )

    except Exception as e:
        return f"❌ **Upload SharePoint eșuat:** {str(e)[:300]}"


def _sp_list_impl(limit: int = 20, name_filter: Optional[str] = None) -> str:
    """List files in the configured SharePoint folder."""
    err = _sp_missing_config()
    if err:
        return err

    folder_path = _SP_FOLDER_PATH.rstrip("/")

    try:
        import urllib.request

        token   = _sp_get_token()
        site_id = _sp_get_site_id(token)

        list_url = (
            f"https://graph.microsoft.com/v1.0/sites/{site_id}"
            f"/drive/root:{folder_path}:/children"
            f"?$top={min(limit, 50)}&$orderby=lastModifiedDateTime desc"
            f"&$select=name,size,lastModifiedDateTime,webUrl"
        )
        req = urllib.request.Request(list_url, headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())

        items = result.get("value", [])
        if name_filter:
            items = [i for i in items if name_filter.lower() in i.get("name", "").lower()]

        if not items:
            return f"📂 **SharePoint `{folder_path}` — folder gol** sau nu există fișiere care să corespundă filtrului."

        lines = [f"## 📂 SharePoint — {len(items)} fișiere\n*(folder: {folder_path})*\n"]
        for item in items:
            size_kb = int(item.get("size", 0)) // 1024
            mod     = item.get("lastModifiedDateTime", "")[:10]
            link    = item.get("webUrl", "")
            name    = item.get("name", "")
            lines.append(f"- **[{name}]({link})** — {size_kb} KB — {mod}")

        return "\n".join(lines)

    except Exception as e:
        return f"❌ **Eroare listare SharePoint:** {str(e)[:300]}"


def _sp_get_link_impl(filename: str) -> str:
    """Search for a file by name in the SharePoint folder and return its link."""
    err = _sp_missing_config()
    if err:
        return err

    folder_path = _SP_FOLDER_PATH.rstrip("/")

    try:
        import urllib.request

        token   = _sp_get_token()
        site_id = _sp_get_site_id(token)

        item_url = (
            f"https://graph.microsoft.com/v1.0/sites/{site_id}"
            f"/drive/root:{folder_path}/{filename}"
            f"?$select=name,webUrl,lastModifiedDateTime"
        )
        req = urllib.request.Request(item_url, headers={"Authorization": f"Bearer {token}"})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                item = json.loads(resp.read())
        except Exception:
            return (
                f"❌ **Fișierul `{filename}` nu a fost găsit în SharePoint.**\n\n"
                f"Verificați că fișierul a fost încărcat cu `broker_sharepoint_upload`."
            )

        link = item.get("webUrl", "")
        mod  = item.get("lastModifiedDateTime", "")[:10]
        return (
            f"📎 **Link SharePoint pentru `{item.get('name', filename)}`:**\n\n"
            f"{link}\n\n"
            f"*(modificat: {mod})*"
        )

    except Exception as e:
        return f"❌ **Eroare căutare SharePoint:** {str(e)[:300]}"


# ─── Public aliases (for Chainlit direct import) ──────────────────────────────
upload_to_drive_fn       = _upload_to_drive_impl
list_drive_files_fn      = _list_drive_files_impl
get_drive_link_fn        = _get_drive_link_impl
sp_upload_fn             = _sp_upload_impl
sp_list_fn               = _sp_list_impl
sp_get_link_fn           = _sp_get_link_impl


# ─── MCP registration ─────────────────────────────────────────────────────────
def register_drive_tools(mcp: FastMCP):

    @mcp.tool(
        name="broker_drive_upload",
        description=(
            "Upload a generated file (offer PDF, report XLSX/DOCX, etc.) to the broker's "
            "Google Drive folder. The file must exist in the local output/ directory. "
            "Returns a shareable link that can be sent directly to the client. "
            "Requires GOOGLE_APPLICATION_CREDENTIALS_JSON and GOOGLE_DRIVE_FOLDER_ID in .env."
        ),
    )
    def broker_drive_upload(
        filename: str,
        drive_filename: Optional[str] = None,
    ) -> str:
        """
        Args:
            filename: Local filename or path (e.g. 'Offer_CLI001_2026-03-10.pdf').
                      Searched first in output/ directory, then as absolute path.
            drive_filename: Optional name to use in Google Drive (default: same as local).
        """
        return _upload_to_drive_impl(filename, drive_filename)

    @mcp.tool(
        name="broker_drive_list",
        description=(
            "List files in the broker's configured Google Drive folder. "
            "Returns file names, sizes, modification dates, and shareable links. "
            "Optionally filter by partial file name."
        ),
    )
    def broker_drive_list(
        limit: int = 20,
        name_filter: Optional[str] = None,
    ) -> str:
        """
        Args:
            limit: Max number of files to return (default 20, max 50).
            name_filter: Optional partial name to filter results (e.g. 'Offer', 'ASF').
        """
        return _list_drive_files_impl(limit, name_filter)

    @mcp.tool(
        name="broker_drive_get_link",
        description=(
            "Get a shareable Google Drive link for a specific file by name. "
            "Use this after uploading to retrieve the link again, or to check if "
            "a file already exists in Drive."
        ),
    )
    def broker_drive_get_link(filename: str) -> str:
        """
        Args:
            filename: Exact filename to search for in Google Drive (e.g. 'Offer_CLI001_2026-03-10.pdf').
        """
        return _get_drive_link_impl(filename)

    # ── SharePoint tools ──────────────────────────────────────────────────────

    @mcp.tool(
        name="broker_sharepoint_upload",
        description=(
            "Upload a generated file (offer PDF, report XLSX/DOCX, etc.) to the broker's "
            "SharePoint folder via Microsoft Graph API. The file must exist in the local output/ directory. "
            "Returns a SharePoint link accessible within the organization. "
            "Requires SHAREPOINT_TENANT_ID, SHAREPOINT_CLIENT_ID, SHAREPOINT_CLIENT_SECRET, "
            "SHAREPOINT_SITE_URL, and SHAREPOINT_FOLDER_PATH in .env."
        ),
    )
    def broker_sharepoint_upload(
        filename: str,
        sp_filename: Optional[str] = None,
    ) -> str:
        """
        Args:
            filename: Local filename or path (e.g. 'Offer_CLI001_2026-03-10.pdf').
                      Searched first in output/ directory, then as absolute path.
            sp_filename: Optional name to use in SharePoint (default: same as local).
        """
        return _sp_upload_impl(filename, sp_filename)

    @mcp.tool(
        name="broker_sharepoint_list",
        description=(
            "List files in the broker's configured SharePoint folder. "
            "Returns file names, sizes, modification dates, and SharePoint links. "
            "Optionally filter by partial file name."
        ),
    )
    def broker_sharepoint_list(
        limit: int = 20,
        name_filter: Optional[str] = None,
    ) -> str:
        """
        Args:
            limit: Max number of files to return (default 20, max 50).
            name_filter: Optional partial name to filter results (e.g. 'Offer', 'ASF').
        """
        return _sp_list_impl(limit, name_filter)

    @mcp.tool(
        name="broker_sharepoint_get_link",
        description=(
            "Get a SharePoint link for a specific file by exact name. "
            "Use this after uploading to retrieve the link, or to check if a file exists in SharePoint."
        ),
    )
    def broker_sharepoint_get_link(filename: str) -> str:
        """
        Args:
            filename: Exact filename to search for in SharePoint (e.g. 'Offer_CLI001_2026-03-10.pdf').
        """
        return _sp_get_link_impl(filename)
