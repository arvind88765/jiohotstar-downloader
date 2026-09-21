#!/usr/bin/env python3
"""
JioHotstar Downloader GUI  v5  — with L3 Widevine CDM
Made by Rvind  |  DRM layer by Nono

pip install requests pywidevine
python hotstar_gui_drm.py
"""

import sys, os, re, json, time, hmac, hashlib, subprocess, threading, uuid, datetime, signal, base64, struct
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

try:
    import requests
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "requests", "-q"])
    import requests

# ─────────────────────────────────────────────────────────────
#  CONSTANTS / HELPERS
# ─────────────────────────────────────────────────────────────

APP_DIR  = os.path.dirname(os.path.abspath(__file__))
CFG_FILE = os.path.join(APP_DIR, "hotstar_cfg.json")
DID_FILE = os.path.join(APP_DIR, ".hotstar_did")

_HMAC_KEY = b"\x05\xfc\x1a\x01\xca\xc9\x4b\xc4\x12\xfc\x53\x12\x07\x75\xf9\xee"
FP_SAMPLE = (
    'MDA3MGYyZTAtZGYxMS00ODhjLThlNmItYjczYmEwNjNhYjIz.BPicufgJ44ZZHXqTv8pNoJXgX2WYShUBEW8vws'
    '__IjBu1VBsW5t32-Q0A8EFjVP0Wl7fvAEIDtfDMTqUQHJ5bNIRd9uO6-6mviC7-Axb9ZSwD3VCAclSrxGotyIgc'
    'axpXZSC9w6rijZGqbp8Hr3FkiHZTG6fqCdlVifI0ONKxowYqWKwfL9PqzngxBW4IGLm6k__sMgoPTDTEdUJDM3A'
    'gsFd2RIdw4WpU8ydA1OnXiyjlrqIJvNQ0riuqrLILC4UQ4j3oU_-yNwQPO1NRChLMCiQzLsG8Gr35oMPhcxoKur'
    '0Rv3M7oJR-PaFVrtwZhnreWtZ3Yyj5ySkkhFFh7qHENQRRj-paiWnaNny4BLhlcWPji1Lb6sZLTdjQAEvXTL38K'
    'MiFBcgxkaVgRAFhCiuTVqx4LPQ3oicviTI5LdocPAfGHunCSPwi-nnML_hEAXRlw3GXGZcsmujLeMgrJVwyn05y'
)

def get_device_id():
    if os.path.exists(DID_FILE):
        return open(DID_FILE).read().strip()
    did = str(uuid.uuid4())[:23]
    open(DID_FILE, 'w').write(did)
    return did

DEVICE_ID = get_device_id()

def make_auth():
    st = int(time.time()); exp = st + 6000
    msg = f"st={st}~exp={exp}~acl=/*"
    return f"{msg}~hmac={hmac.new(_HMAC_KEY, msg.encode(), hashlib.sha256).hexdigest()}"

def android_hdrs(token=None):
    h = {
        "User-Agent":          "Hotstar;in.startv.hotstar/26.09.05.0.11013 (Android/14)",
        "Content-Type":        "application/x-protobuf",
        "X-Country-Code":      "in", "X-HS-App": "11013",
        "X-HS-APP-ID":         "c86aad81-d602-46e5-b6a0-6d3891199063",
        "X-HS-Client":         "platform:android;app_id:in.startv.hotstar;app_version:26.09.05.0;os:Android;os_version:14;schema_version:0.0.1797;brand:Samsung;model:SM-S918B;carrier:airtel;network_data:NETWORK_TYPE_WIFI",
        "X-HS-Device-Id":      DEVICE_ID, "X-HS-Platform": "android",
        "X-HS-Schema-Version": "0.0.1797", "X-HS-FP-Info": FP_SAMPLE,
        "hotstarauth":         make_auth(),
    }
    if token: h["X-HS-Usertoken"] = token
    return h

def web_hdrs(token=None, ps=None):
    h = {
        "User-Agent":    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
        "Accept":        "application/json, text/plain, */*",
        "Content-Type":  "application/json",
        "Origin":        "https://www.hotstar.com",
        "Referer":       "https://www.hotstar.com/in",
        "x-country-code":"in", "x-hs-app": "260905000",
        "x-hs-client":   "platform:web;app_version:26.09.05.0;browser:Chrome;schema_version:0.0.1797;os:Windows;os_version:10;browser_version:137;network_data:4g",
        "x-hs-platform": "web", "hotstarauth": make_auth(),
    }
    if token: h["x-hs-usertoken"] = token
    if ps:    h["x-hs-proxystate"] = ps
    return h

def find_jwt(data):
    src = data if isinstance(data, str) else (data.decode('utf-8','replace') if isinstance(data,bytes) else str(data))
    hits = [h for h in re.findall(r'eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+', src) if len(h)>200]
    return max(hits, key=len) if hits else None

def jwt_exp(tok):
    try:
        import base64
        p = tok.split('.')[1]; p += '='*(4-len(p)%4)
        return json.loads(base64.b64decode(p))['exp']
    except: return 0

def tok_valid(tok): return bool(tok) and jwt_exp(tok) > time.time()+60
def tok_str(tok):
    h = (jwt_exp(tok)-time.time())/3600
    return f"{h:.1f}h remaining" if h>0 else "expired"

# ─────────────────────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────────────────────

DEFAULT_CFG = {
    "token_file":      os.path.join(APP_DIR, "hotstar_token.json"),
    "output_dir":      r"E:\Downloads",
    "n_m3u8dl_path":   r"E:\N_m3u8DL-RE.exe",
    "ytdlp_path":      "yt-dlp",
    "ffmpeg_path":     "ffmpeg",
    "threads":         16,
    "grab_subs":       False,
    "engine":          "auto",       # "auto" | "n_m3u8dl" | "ytdlp" | "ffmpeg"
    "cdm_path":        "",           # path to Widevine L3 .wvd device file
    "shaka_path":      "packager",   # shaka-packager binary (or full path)
    "mp4decrypt_path": "mp4decrypt", # Bento4 mp4decrypt binary (or full path)
    "decrypt_tool":    "auto",       # "auto" | "n_m3u8dl_inline" | "shaka" | "mp4decrypt"
}

def load_cfg():
    c = dict(DEFAULT_CFG)
    if os.path.exists(CFG_FILE):
        try: c.update(json.load(open(CFG_FILE)))
        except: pass
    return c

def save_cfg(c): json.dump(c, open(CFG_FILE,'w'), indent=2)

def load_token(cfg):
    path = cfg.get("token_file","")
    candidates = [path, os.path.join(APP_DIR,"hotstar_token.json"), os.path.join(APP_DIR,"hs_token.json")]
    for p in candidates:
        if p and os.path.exists(p):
            try:
                d = json.load(open(p)); t = d.get("user_token","")
                if tok_valid(t): return t, p
            except: pass
    return None, None

def save_token(tok, phone, cfg):
    path = cfg.get("token_file", os.path.join(APP_DIR,"hotstar_token.json"))
    json.dump({"user_token":tok,"phone":phone,"saved_at":int(time.time()),"expires_at":jwt_exp(tok)},
              open(path,'w'), indent=2)
    return path

# ─────────────────────────────────────────────────────────────
#  LOGIN
# ─────────────────────────────────────────────────────────────

def api_guest():
    try:
        r = requests.post("https://apix.hotstar.com/v2/freshstart",
            params={"client_capabilities":json.dumps({"package":["dash","hls"],"container":["fmp4","ts"],
                "encryption":["plain","widevine"],"video_codec":["h264"],"ladder":["phone"],
                "resolution":["sd","hd","fhd"],"dynamic_range":["sdr"]}),
                "drm_parameters":json.dumps({"widevine_security_level":["HW_SECURE_ALL","SW_SECURE_DECODE"],
                "hdcp_version":["HDCP_V2_2"]}),"subs":"null","login":"UNKNOWN"},
            headers=android_hdrs(), data=b'', timeout=15)
        g = r.headers.get("x-hs-updatedusertoken") or find_jwt(r.content)
        if g: return g, None
    except: pass
    try:
        r = requests.post("https://www.hotstar.com/api/internal/bff/v2/start",
            params={"journey":"login"}, headers=web_hdrs(),
            json={"deeplink_url":"","context":{"url":"type.googleapis.com/context.StateContext","value":"CgQaAggC"},"app_launch_count":1},
            timeout=15)
        g = r.headers.get("x-hs-updatedusertoken")
        ps = r.headers.get("x-hs-setproxystate")
        if g: return g, ps
    except: pass
    return None, None

def api_send_otp(phone, guest, ps=None):
    try:
        r = requests.post(
            "https://www.hotstar.com/api/internal/bff/v2/pages/1/spaces/1/widgets/8",
            params={"action":"sendOtp","pageRef":"myspace","page_enum":"onboarding_login","qrCode":"true"},
            headers=web_hdrs(token=guest, ps=ps),
            json={"body":{"@type":"type.googleapis.com/feature.login.InitiatePhoneLoginRequest",
                          "initiate_by":0,"recaptcha_token":"","phone_number":phone}},
            timeout=15)
        if r.status_code in (200,201,202):
            d = {}
            try: d = r.json()
            except: pass
            if "error" not in d: return True,"web"
    except: pass
    try:
        pb = phone.encode()
        inner = b'\x0a'+bytes([len(pb)])+pb
        outer = b'\x0a'+bytes([len(inner)])+inner
        r = requests.post("https://apix.hotstar.com/v2/pages/1/spaces/1/widgets/8",
            params={"action":"sendOtp"}, headers=android_hdrs(guest), data=outer, timeout=15)
        if r.status_code==200: return True,"android"
    except: pass
    return False,None

def api_verify_otp(phone, otp, guest, ps=None, method="web"):
    if method=="web":
        try:
            r = requests.post(
                "https://www.hotstar.com/api/internal/bff/v2/pages/1/spaces/1/widgets/9",
                params={"action":"verifyOtp","pageRef":"myspace","page_enum":"onboarding_login","qrCode":"true"},
                headers=web_hdrs(token=guest, ps=ps),
                json={"body":{"@type":"type.googleapis.com/feature.login.VerifyPhoneLoginRequest",
                              "verification_code":otp,
                              "login_device_meta":{"device_name":"Chrome Browser on Windows"},
                              "phone_number":phone}},
                timeout=15)
            tok = r.headers.get("x-hs-updatedusertoken") or find_jwt(r.text)
            if tok and len(tok)>200: return tok
        except: pass
    try:
        pb,ob = phone.encode(),otp.encode()
        inner = b'\x0a'+bytes([len(pb)])+pb+b'\x12'+bytes([len(ob)])+ob
        outer = b'\x0a'+bytes([len(inner)])+inner
        r = requests.post("https://apix.hotstar.com/v2/pages/1/spaces/1/widgets/9",
            params={"action":"verifyOtp"}, headers=android_hdrs(guest), data=outer, timeout=15)
        tok = r.headers.get("x-hs-updatedusertoken") or find_jwt(r.content)
        if tok and len(tok)>200: return tok
    except: pass
    return None

# ─────────────────────────────────────────────────────────────
#  STREAM / QUALITY
# ─────────────────────────────────────────────────────────────

# Updated CLIENT_CAPS — now includes widevine so API returns DRM streams too
CLIENT_CAPS = json.dumps({
    "package":       ["dash","hls"],
    "container":     ["fmp4","fmp4br","ts"],
    "ads":           ["non_ssai"],
    "audio_channel": ["stereo"],
    "encryption":    ["plain","widevine"],   # ← was ["plain"] only
    "video_codec":   ["h264"],
    "ladder":        ["phone","web","tv"],
    "resolution":    ["sd","hd","fhd"],
    "dynamic_range": ["sdr"]
})

# Updated DRM_PARAMS — include L3 software level so license server accepts our CDM
DRM_PARAMS = json.dumps({
    "widevine_security_level": ["HW_SECURE_ALL","SW_SECURE_DECODE","SW_SECURE_CRYPTO"],
    "hdcp_version":            ["HDCP_V2_2"]
})

def _parse_player_config(data):
    """
    Navigate the BFF response structure to find the PlayerWidget player_config dict.
    Returns the player_config dict or None.

    Path (from yt-dlp analysis):
      data['page']['spaces']['player']['widget_wrappers'][i]['widget']['data']['player_config']
      where widget_wrappers[i]['template'] == 'PlayerWidget'
    """
    try:
        wrappers = (data.get("page") or {}).get("spaces") or {}
        # spaces can be a dict of section→data or just player
        player_section = wrappers.get("player") or wrappers
        ww_list = None
        if isinstance(player_section, dict):
            ww_list = player_section.get("widget_wrappers") or []
        if not ww_list and isinstance(wrappers, dict):
            # sometimes under data.spaces directly
            for v in wrappers.values():
                if isinstance(v, dict):
                    ww = v.get("widget_wrappers") or []
                    if ww: ww_list = ww; break
        if not ww_list: return None
        for ww in ww_list:
            if not isinstance(ww, dict): continue
            if ww.get("template") in ("PlayerWidget", "player", None):
                pc = ((ww.get("widget") or {}).get("data") or {}).get("player_config")
                if pc: return pc
        # last resort: first ww
        for ww in ww_list:
            pc = ((ww.get("widget") or {}).get("data") or {}).get("player_config")
            if pc: return pc
    except Exception:
        pass
    return None


def _extract_from_player_config(pc):
    """
    From a player_config dict extract (mpd_url, m3u8_url, licence_url).
    Searches media_asset + media_asset_v2, primary + fallback lists.
    Each playback set has:
      - content_url  : the stream URL
      - playback_tags: semicolon-separated "key:value" string
      - licence_url  : the Widevine license URL (pre-authenticated!)
    """
    mpd = m3u8 = licence_url = None
    drm_mpd = drm_m3u8 = drm_lic = None  # prefer DRM streams for key fetch

    for asset_key in ("media_asset", "media_asset_v2"):
        asset = pc.get(asset_key) or {}
        for group_key in ("primary", "fallback"):
            items = asset.get(group_key) or []
            if isinstance(items, dict):  # sometimes it's a dict not list
                items = list(items.values())
            for ps in items:
                if not isinstance(ps, dict): continue
                curl = ps.get("content_url") or ps.get("playbackUrl") or ps.get("playback_url") or ""
                tags = ps.get("playback_tags") or ps.get("tagsCombination") or ""
                lic  = (ps.get("licence_url") or ps.get("licenceUrl") or
                        ps.get("license_url") or ps.get("licenseUrl") or "")

                # parse playback_tags for encryption and licence_url
                tag_dict = {}
                for part in tags.split(";"):
                    kv = part.split(":", 1)
                    if len(kv) == 2: tag_dict[kv[0].strip()] = kv[1].strip()
                if not lic:
                    lic = tag_dict.get("licence_url") or tag_dict.get("license_url") or ""

                is_widevine = tag_dict.get("encryption", "").lower() == "widevine"
                is_plain    = tag_dict.get("encryption", "plain").lower() in ("plain", "")

                if ".mpd" in curl:
                    if is_widevine:
                        if not drm_mpd: drm_mpd = curl
                        if not drm_lic and lic: drm_lic = lic
                    elif not mpd:
                        mpd = curl
                elif ".m3u8" in curl:
                    if is_widevine:
                        if not drm_m3u8: drm_m3u8 = curl
                    elif not m3u8:
                        m3u8 = curl
                # Collect any licence_url even from non-DRM sets (shouldn't happen but safety net)
                if not licence_url and lic: licence_url = lic

    # Prefer DRM stream URLs (that's what we actually want to decrypt)
    final_mpd = drm_mpd or mpd
    final_lic  = drm_lic or licence_url
    return final_mpd, m3u8, final_lic


def fetch_stream(content_id, token):
    """
    Returns (mpd_url, m3u8_url, licence_url, status_code).
    licence_url comes directly from the playback API — it is pre-authenticated
    (contains hdnea/time-limited tokens) and only requires a raw POST of the
    Widevine challenge to retrieve the license.
    """
    common_params = {
        "content_id":          content_id,
        "client_capabilities": CLIENT_CAPS,
        "drm_parameters":      DRM_PARAMS,
    }
    attempts = [
        # BFF endpoint (yt-dlp confirmed, returns full player_config with licence_url)
        ("https://www.hotstar.com/api/internal/bff/v2/pages/watch", {}),
        # apix endpoint without filter (fallback)
        ("https://apix.hotstar.com/v2/pages/watch", {}),
        # apix with EPISODE filter (second fallback)
        ("https://apix.hotstar.com/v2/pages/watch", {"filters": "content_type=EPISODE"}),
    ]

    # BFF needs web headers; apix works with android headers
    last_status = 0
    for url, extra in attempts:
        params = {**common_params, **extra}
        hdrs = web_hdrs(token) if "bff" in url else android_hdrs(token)
        try:
            r = requests.get(url, params=params, headers=hdrs, timeout=15)
            last_status = r.status_code
            if r.status_code != 200:
                continue
        except Exception:
            continue

        mpd = m3u8 = licence_url = None

        # ── Try structured JSON parse (BFF path) ──────────────────────────────
        try:
            j = r.json()
            # BFF wraps in "success" key; apix wraps in nothing or "data"
            inner = j.get("success") or j.get("data") or j
            pc = _parse_player_config(inner)
            if pc:
                mpd, m3u8, licence_url = _extract_from_player_config(pc)

            # ── Generic deep-walk fallback (catches old-style playBackSets) ───
            if not (mpd and licence_url):
                def _walk(obj):
                    nonlocal mpd, m3u8, licence_url
                    if isinstance(obj, dict):
                        for k in ("licenceUrl","licenseUrl","licence_url","license_url"):
                            if k in obj and isinstance(obj[k],str) and obj[k].startswith("http"):
                                if not licence_url: licence_url = obj[k]
                        for k in ("playbackUrl","playback_url","content_url"):
                            if k in obj and isinstance(obj[k],str):
                                u = obj[k]
                                if ".mpd"  in u and not mpd:  mpd  = u
                                elif ".m3u8" in u and not m3u8: m3u8 = u
                        for v in obj.values(): _walk(v)
                    elif isinstance(obj, list):
                        for item in obj: _walk(item)
                _walk(inner)

            # ── DEBUG: save raw API response when licence_url is missing ────────
            if not licence_url:
                try:
                    dbg_path = os.path.join(APP_DIR, "hotstar_api_debug.json")
                    with open(dbg_path, "w", encoding="utf-8") as _f:
                        json.dump({"endpoint": url, "inner_keys": list(inner.keys()) if isinstance(inner,dict) else "not-dict",
                                   "raw_preview": r.text[:4000]}, _f, indent=2)
                except Exception:
                    pass
        except Exception:
            pass

        # ── Regex fallback for stream URLs ────────────────────────────────────
        if not mpd:
            raw = r.content
            urls = [u.decode('utf-8','replace') for u in re.findall(rb'https://[A-Za-z0-9.\-_/?=&%~:@+]+', raw)]
            mpd  = next((u for u in urls if '.mpd'  in u and 'hdnea' in u),
                        next((u for u in urls if '.mpd'  in u), None))
            if not m3u8:
                m3u8 = next((u for u in urls if '.m3u8' in u and 'hdnea' in u),
                            next((u for u in urls if '.m3u8' in u), None))

        if mpd:
            return mpd, m3u8, licence_url, 200

    return None, None, None, last_status

def get_duration_secs(mpd_text):
    try:
        m = re.search(r'mediaPresentationDuration="PT(?:(\d+)H)?(?:(\d+)M)?([0-9.]+)S"', mpd_text)
        if m:
            return int(m.group(1) or 0)*3600 + int(m.group(2) or 0)*60 + float(m.group(3) or 0)
    except: pass
    return None

def fmt_size(b):
    if b is None: return "?"
    if b < 1024**2: return f"{b/1024:.0f} KB"
    if b < 1024**3: return f"{b/1024**2:.0f} MB"
    return f"{b/1024**3:.2f} GB"

LANG_NAMES = {
    "hin":"Hindi","tam":"Tamil","tel":"Telugu","eng":"English","kan":"Kannada",
    "mal":"Malayalam","ben":"Bengali","mar":"Marathi","pun":"Punjabi","guj":"Gujarati",
    "urd":"Urdu","arb":"Arabic","fre":"French","spa":"Spanish","ger":"German",
    "jpn":"Japanese","kor":"Korean","chi":"Chinese","zho":"Chinese","por":"Portuguese",
}

def lang_label(code):
    return LANG_NAMES.get(code.lower(), code.upper())

# ─────────────────────────────────────────────────────────────
#  DRM — PSSH EXTRACTION + WIDEVINE KEY FETCHING
# ─────────────────────────────────────────────────────────────

WIDEVINE_SYSTEM_ID = "edef8ba979d64acea3c827dcd51d21ed"  # standard Widevine UUID

def extract_license_url(mpd_text):
    """
    Try to pull the Widevine license URL from the MPD's ContentProtection block.
    Returns URL string or None.
    """
    # <ms:laURL> or <dashif:Laurl> or <pro> with URL, or any laURL= attribute
    patterns = [
        r'<(?:[^:]+:)?[Ll]a[Uu][Rr][Ll][^>]*>(https?://[^<]+)</(?:[^:]+:)?[Ll]a[Uu][Rr][Ll]>',
        r'laURL="(https?://[^"]+)"',
        r'Laurl="(https?://[^"]+)"',
    ]
    for pat in patterns:
        m = re.search(pat, mpd_text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def extract_pssh(mpd_text):
    """
    Pull the Widevine PSSH box (base64) out of an MPD's ContentProtection elements.
    Returns base64-encoded PSSH bytes, or None if not found.

    MPDs have two forms:
      1. <cenc:pssh>BASE64DATA</cenc:pssh>  ← preferred, full PSSH box
      2. <ContentProtection schemeIdUri="urn:uuid:EDEF8BA9-...">  with
         a nested <mspr:pro> or just the KID — we build a minimal PSSH from those
    """
    # ── Form 1: explicit cenc:pssh block ──────────────────────────────────────
    # grab all, pick the one that belongs to Widevine CP block
    cp_blocks = re.findall(
        r'<ContentProtection\b[^>]*schemeIdUri="[^"]*edef8ba9[^"]*"[^>]*>(.*?)</ContentProtection>',
        mpd_text, re.DOTALL | re.IGNORECASE
    )
    for block in cp_blocks:
        m = re.search(r'<(?:[^:]+:)?pssh\b[^>]*>(.*?)</(?:[^:]+:)?pssh>', block, re.DOTALL | re.IGNORECASE)
        if m:
            data = m.group(1).strip()
            if data:
                return data  # already base64

    # ── Form 2: any cenc:pssh anywhere in the MPD ────────────────────────────
    m = re.search(r'<(?:[^:]+:)?pssh\b[^>]*>(.*?)</(?:[^:]+:)?pssh>', mpd_text, re.DOTALL | re.IGNORECASE)
    if m:
        data = m.group(1).strip()
        if data:
            return data

    # ── Form 3: no PSSH element — build minimal Widevine PSSH from KIDs ──────
    # Extract all default_KID values (hex with dashes, like "A1B2C3D4-...")
    kids_hex = re.findall(
        r'default_KID="([0-9a-fA-F\-]{32,36})"', mpd_text
    )
    # Also grab from ContentProtection cenc:default_KID
    kids_hex += re.findall(
        r'cenc:default_KID="([0-9a-fA-F\-]{32,36})"', mpd_text, re.IGNORECASE
    )
    kids_raw = []
    seen = set()
    for k in kids_hex:
        k_clean = k.replace("-","").lower()
        if k_clean not in seen and len(k_clean)==32:
            seen.add(k_clean)
            kids_raw.append(bytes.fromhex(k_clean))
    if not kids_raw:
        return None

    # Construct minimal Widevine PSSH:
    # WidevineCencHeader protobuf: field 2 (key_id, bytes) repeated for each KID
    proto_data = b""
    for kid in kids_raw:
        # protobuf field 2, wire type 2 (length-delimited)
        proto_data += b"\x12" + bytes([len(kid)]) + kid

    # PSSH box layout:
    # 4 bytes size | "pssh" | 4 bytes version+flags | 16 bytes systemID | 4 bytes data_size | data
    system_id = bytes.fromhex(WIDEVINE_SYSTEM_ID)
    data_size  = struct.pack(">I", len(proto_data))
    box_body   = b"pssh" + b"\x00\x00\x00\x00" + system_id + data_size + proto_data
    box_size   = struct.pack(">I", len(box_body) + 4)
    pssh_box   = box_size + box_body

    return base64.b64encode(pssh_box).decode()


def get_widevine_keys(pssh_b64, token, mpd_url, cdm_path="", log_cb=None, license_url=None):
    """
    Fetch Widevine content keys using a software L3 CDM (pywidevine).

    pssh_b64   : base64-encoded PSSH box
    token      : Hotstar user JWT
    mpd_url    : original MPD URL (used as license URL base)
    cdm_path   : path to a .wvd device file; if empty tries default WVD names
    log_cb     : optional callable(str) for progress messages

    Returns list of (kid_hex, key_hex) tuples, empty on failure.
    """
    def _log(msg):
        if log_cb: log_cb(msg)

    # ── 1. Import pywidevine ──────────────────────────────────────────────────
    try:
        from pywidevine.cdm import Cdm
        from pywidevine.device import Device
        from pywidevine.pssh import PSSH
    except ImportError:
        _log("[DRM] pywidevine not found — installing...\n")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "pywidevine", "-q",
                            "--break-system-packages"], timeout=90, check=False)
            subprocess.run([sys.executable, "-m", "pip", "install", "pywidevine", "-q"], timeout=90, check=False)
            from pywidevine.cdm import Cdm
            from pywidevine.device import Device
            from pywidevine.pssh import PSSH
            _log("[DRM] pywidevine installed ✓\n")
        except Exception as e:
            _log(f"[DRM] ✗ Can't install pywidevine: {e}\n")
            return []

    # ── 2. Load WVD device file ───────────────────────────────────────────────
    wvd_candidates = []
    if cdm_path and os.path.exists(cdm_path):
        wvd_candidates.append(cdm_path)
    # also probe common names next to the script
    for name in ["device.wvd", "l3.wvd", "cdm.wvd", "widevine.wvd"]:
        p = os.path.join(APP_DIR, name)
        if os.path.exists(p): wvd_candidates.append(p)
    # XDG / home fallbacks
    for p in [
        os.path.expanduser("~/.wvd/device.wvd"),
        os.path.expanduser("~/device.wvd"),
        os.path.expanduser("~/l3.wvd"),
    ]:
        if os.path.exists(p): wvd_candidates.append(p)

    device = None
    for wvd in wvd_candidates:
        try:
            device = Device.load(wvd)
            _log(f"[DRM] Loaded CDM from {wvd}\n")
            break
        except Exception as e:
            _log(f"[DRM] Failed to load {wvd}: {e}\n")

    if device is None:
        _log("[DRM] ✗ No valid .wvd device file found.\n"
             "      Drop a device.wvd next to this script and retry.\n")
        return []

    # ── 3. Build CDM session & license challenge ──────────────────────────────
    try:
        cdm  = Cdm.from_device(device)
        sess = cdm.open()
        pssh = PSSH(pssh_b64)
        challenge = cdm.get_license_challenge(sess, pssh)
    except Exception as e:
        _log(f"[DRM] ✗ CDM challenge failed: {e}\n")
        return []

    # ── 4. POST to Hotstar license server ────────────────────────────────────
    import urllib.request as _urlreq
    import urllib.error  as _urlerr
    import json          as _json
    import base64        as _b64
    import http.client   as _http_client

    # Content ID — take last numeric segment from MPD URL (episode ID)
    cid_matches = re.findall(r'/(\d{7,12})(?:/|\.)', mpd_url or "")
    content_id = cid_matches[-1] if cid_matches else ""
    _log(f"[DRM] Content ID: {content_id or '(none)'} | Licence URL from API: {license_url or '(none)'}\n")

    # ── Build the ordered license URL list ────────────────────────────────────
    # KEY INSIGHT: licenceUrl from the playback API is pre-authenticated —
    # it contains time-limited hdnea tokens baked into the URL.  Just POST
    # the raw challenge bytes with minimal headers; NO hotstarauth needed.
    # Generic fallback endpoints DO require Hotstar auth headers.
    license_entries = []  # list of (url, use_auth: bool)
    if license_url:
        license_entries.append((license_url, False))   # pre-auth'd URL → no extra auth

    # fallback generic endpoints (need hotstarauth + usertoken)
    fallback_generics = [
        "https://www.hotstar.com/api/internal/bff/v2/licenses/widevine",
        "https://secure-media.hotstar.com/widevine",
        "https://www.hotstar.com/in/api/v2/licenses/widevine",
    ]
    if content_id:
        fallback_generics = [
            f"https://www.hotstar.com/in/api/v2/licenses/widevine/{content_id}",
            f"https://www.hotstar.com/api/internal/bff/v2/licenses/widevine/{content_id}",
        ] + fallback_generics
    seen_u = {license_url} if license_url else set()
    for u in fallback_generics:
        if u not in seen_u:
            license_entries.append((u, True))   # generic → needs auth
            seen_u.add(u)

    # Auth headers for generic fallback endpoints
    _AUTH_HDRS = {
        "User-Agent":      "Hotstar;in.startv.hotstar/25.06.30.0.11580 (Android/12)",
        "hotstarauth":     make_auth(),
        "x-hs-platform":  "android",
        "x-hs-client":    "platform:android;app_id:in.startv.hotstar;app_version:25.06.30.0;os:Android;os_version:12;schema_version:0.0.1523",
        "x-country-code": "IN",
        "Origin":         "https://www.hotstar.com",
        "Referer":        "https://www.hotstar.com/",
    }
    if token:
        _AUTH_HDRS["x-hs-usertoken"] = token
        _AUTH_HDRS["Authorization"]  = f"Bearer {token}"
    if content_id:
        _AUTH_HDRS["x-hs-contentid"] = content_id

    # Minimal headers for pre-authenticated licence URLs
    _MINIMAL_HDRS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept":     "*/*",
        "Origin":     "https://www.hotstar.com",
        "Referer":    "https://www.hotstar.com/in",
    }

    def _read_safely(resp):
        try: return resp.read()
        except _http_client.IncompleteRead as ir: return ir.partial

    def _unwrap(raw):
        if not raw: return None, "empty body"
        if raw[:1] in (b'{', b'['):
            try:
                j = _json.loads(raw)
                for k in ("license","licenseData","widevine_license",
                          "data","keyResponse","licenseToken",
                          "widevineChallenge","widevineLicense"):
                    if isinstance(j, dict) and k in j:
                        decoded = _b64.b64decode(j[k])
                        return decoded, f"JSON key='{k}' → {len(decoded)} bytes"
                keys_found = list(j.keys()) if isinstance(j,dict) else "list"
                preview = raw[:300].decode("utf-8","replace")
                return None, f"JSON no license key — keys={keys_found} | {preview[:150]}"
            except Exception:
                pass
        return raw, f"raw {len(raw)} bytes"

    def _try_post(url, body, content_type, use_auth):
        base = _AUTH_HDRS if use_auth else _MINIMAL_HDRS
        hdrs = dict(base)
        hdrs["Content-Type"] = content_type
        req = _urlreq.Request(url, data=body, headers=hdrs, method="POST")
        try:
            with _urlreq.urlopen(req, timeout=30) as resp:
                return resp.status, _read_safely(resp)
        except _http_client.IncompleteRead as ir:
            return 200, ir.partial
        except _urlerr.HTTPError as he:
            try: body_err = he.read()
            except: body_err = b""
            return he.code, body_err

    lic_resp = None
    raw_challenge = bytes(challenge)
    for lic_url, use_auth in license_entries:
        # For pre-auth'd URL: raw binary only (that's all it needs)
        # For generic fallbacks: try raw then JSON-wrapped
        bodies = [(raw_challenge, "application/octet-stream", "raw")]
        if use_auth:
            bodies.append((
                _json.dumps({"licenseRequest": _b64.b64encode(raw_challenge).decode()}).encode(),
                "application/json", "json-wrapped"
            ))
        for body, ctype, label in bodies:
            try:
                auth_tag = "(auth)" if use_auth else "(pre-auth)"
                _log(f"[DRM] POST {label} {auth_tag} → {lic_url[:80]}\n")
                status, raw = _try_post(lic_url, body, ctype, use_auth)
                if status != 200:
                    preview = raw[:200].decode("utf-8","replace") if raw else ""
                    _log(f"[DRM]   HTTP {status}" + (f" | {preview[:100]}" if preview else "") + "\n")
                    break   # different body won't fix HTTP errors
                data, info = _unwrap(raw)
                _log(f"[DRM]   200 OK → {info}\n")
                if data:
                    lic_resp = data
                    break
            except Exception as e:
                _log(f"[DRM]   error: {e}\n")
                break
        if lic_resp:
            break

    if not lic_resp:
        _log("[DRM] ✗ All license endpoints failed\n")
        cdm.close(sess)
        return []

    # ── 5. Parse license & extract keys ──────────────────────────────────────
    try:
        cdm.parse_license(sess, lic_resp)
        keys = []
        for key in cdm.get_keys(sess):
            if key.type == "CONTENT":
                kid_hex = key.kid.hex
                key_hex = key.key.hex()
                keys.append((kid_hex, key_hex))
                _log(f"[DRM] ✓ Key: {kid_hex}:{key_hex}\n")
        cdm.close(sess)
        if not keys:
            _log("[DRM] ✗ No CONTENT keys in license response\n")
        return keys
    except Exception as e:
        _log(f"[DRM] ✗ License parse failed: {e}\n")
        cdm.close(sess)
        return []


def extract_pssh_from_mpd_url(mpd_url, log_cb=None):
    """Download MPD and extract PSSH. Returns (mpd_text, pssh_b64_or_None)."""
    def _log(msg):
        if log_cb: log_cb(msg)
    try:
        r = requests.get(mpd_url, timeout=12, headers={"Referer":"https://www.hotstar.com/"})
        mpd_text = r.text
        pssh = extract_pssh(mpd_text)
        if pssh:
            _log(f"[DRM] PSSH found ({len(pssh)} chars)\n")
        else:
            _log("[DRM] No PSSH / ContentProtection in MPD — stream is plain\n")
        return mpd_text, pssh
    except Exception as e:
        _log(f"[DRM] MPD fetch error: {e}\n")
        return "", None


def _split_adaptation_sets(mpd_text):
    """
    Split an MPD into individual AdaptationSet blocks.
    Returns list of (as_open_tag_attrs, as_body_text) tuples.
    Handles both self-closing and full AdaptationSet elements.
    """
    blocks = []
    # Split on every <AdaptationSet ... > opening tag
    parts = re.split(r'(<AdaptationSet\b[^>]*>)', mpd_text, flags=re.IGNORECASE)
    # parts[0] = preamble, then pairs of (open_tag, body_until_next_split)
    i = 1
    while i < len(parts) - 1:
        open_tag = parts[i]
        body_and_rest = parts[i+1]
        # body ends at </AdaptationSet>
        end_m = re.search(r'</AdaptationSet>', body_and_rest, re.IGNORECASE)
        body = body_and_rest[:end_m.start()] if end_m else body_and_rest
        # extract attrs from opening tag
        as_attrs = re.search(r'<AdaptationSet\b(.*?)>', open_tag, re.DOTALL | re.IGNORECASE)
        attrs_str = as_attrs.group(1) if as_attrs else ""
        blocks.append((attrs_str, body))
        i += 2
    return blocks


def _get_attr(text, name, default=None):
    """Extract a single XML attribute value from a tag string.
    Handles plain attrs (lang=) and namespaced ones (xml:lang=).
    """
    # Use (?<![:\w]) so we don't match foo:lang= when looking for lang=
    safe_name = re.escape(name)
    m = re.search(rf'(?<![:\w]){safe_name}\s*=\s*"([^"]*)"', text, re.IGNORECASE)
    return m.group(1) if m else default


def parse_m3u8_audio_tracks(m3u8_url):
    """
    Parse HLS master playlist for audio tracks.
    Returns list of {"code": lang_code, "label": display_label, "max_kbps": kbps}
    Handles EXT-X-MEDIA:TYPE=AUDIO lines.
    """
    try:
        r = requests.get(m3u8_url, timeout=12, headers={"Referer": "https://www.hotstar.com/"})
        txt = r.text
        audio_seen = {}   # lang_code -> max_kbps
        for line in txt.splitlines():
            if not line.startswith("#EXT-X-MEDIA"): continue
            if "TYPE=AUDIO" not in line: continue
            # parse key=value pairs
            kv = {}
            for m in re.finditer(r'(\w+)=(?:"([^"]*)"|([\w.-]+))', line):
                kv[m.group(1).upper()] = m.group(2) if m.group(2) is not None else m.group(3)
            lang = kv.get("LANGUAGE", "und").lower()
            # skip Audio Description tracks
            grp  = kv.get("GROUP-ID", "").lower()
            name = kv.get("NAME", "").lower()
            if any(x in name for x in ("description", " ad", "audio desc")): continue
            if any(x in grp  for x in ("description", " ad")): continue
            # Hotstar HLS doesn't have bitrate in EXT-X-MEDIA — default 128
            kbps = 128
            if lang not in audio_seen:
                audio_seen[lang] = kbps
        return [{"code": lang, "label": lang_label(lang), "max_kbps": kbps}
                for lang, kbps in audio_seen.items()]
    except Exception as e:
        print(f"[parse_m3u8_audio_tracks] error: {e}")
        return []


def parse_qualities(mpd_url):
    try:
        r = requests.get(mpd_url, timeout=12, headers={"Referer":"https://www.hotstar.com/"})
        txt = r.text
        dur = get_duration_secs(txt)

        out        = []
        seen_h     = set()
        audio_seen = {}   # lang -> max_kbps
        ad_as_ids  = []   # AdaptationSet IDs of Audio Description tracks (to drop)
        sub_tracks = []
        seen_subs  = set()
        video_global_idx = 0

        for as_attrs, as_body in _split_adaptation_sets(txt):
            # ── determine AdaptationSet type ───────────────────────────────────
            mime    = _get_attr(as_attrs, "mimeType", "")
            ctype   = _get_attr(as_attrs, "contentType", "")
            # Hotstar uses both lang= and xml:lang= depending on content type
            lang    = (_get_attr(as_attrs, "lang", "") or
                       _get_attr(as_attrs, "xml:lang", "") or "und")

            is_video = ("video" in mime) or (ctype.lower() == "video")
            is_audio = ("audio" in mime) or (ctype.lower() == "audio")
            is_text  = ("text"  in mime) or (ctype.lower() == "text")

            # Hotstar sometimes omits mimeType — infer from Representation codecs
            if not (is_video or is_audio or is_text):
                # check first Representation for codec hints
                sample_codecs = _get_attr(as_body[:500], "codecs", "")
                if any(c in sample_codecs.lower() for c in ("avc","hevc","vp9","av1")):
                    is_video = True
                elif any(c in sample_codecs.lower() for c in ("mp4a","ac-3","ec-3","opus")):
                    is_audio = True

            # ── fallback width/height from AdaptationSet level ────────────────
            as_w = _get_attr(as_attrs, "width")
            as_h = _get_attr(as_attrs, "height")

            # ── VIDEO ─────────────────────────────────────────────────────────
            if is_video:
                for rep_attrs in re.findall(r'<Representation\b([^>]+)>', as_body, re.IGNORECASE):
                    # width/height: prefer Representation, fall back to AdaptationSet
                    w_s = _get_attr(rep_attrs, "width")  or as_w
                    h_s = _get_attr(rep_attrs, "height") or as_h
                    bw_s= _get_attr(rep_attrs, "bandwidth")
                    rid = _get_attr(rep_attrs, "id", "")

                    if not (w_s and h_s and bw_s):
                        video_global_idx += 1
                        continue

                    w, h, bw = int(w_s), int(h_s), int(bw_s)

                    # skip thumbnail / sprite-sheet streams
                    if bw < 5000:            # < 5 kbps → thumbnail
                        video_global_idx += 1; continue
                    if h > 0 and (w/h) > 5.0:  # absurd aspect → sprite sheet (e.g. 3200x180)
                        video_global_idx += 1; continue
                    if h < 144:
                        video_global_idx += 1; continue

                    lbl = f"{h}p"
                    if lbl not in seen_h:
                        seen_h.add(lbl)
                        est = int((bw/8) * dur * 1.2) if dur else None
                        out.append({
                            "label": lbl, "height": h, "width": w,
                            "bw": bw, "id": rid,
                            "mpd_video_idx": video_global_idx,
                            "est_size": fmt_size(est),
                            "mbps": bw / 1e6,
                        })
                    video_global_idx += 1

            # ── AUDIO ─────────────────────────────────────────────────────────
            elif is_audio:
                # ── detect Audio Description / AD tracks ──────────────────────
                # MPD marks these with <Role schemeIdUri="..." value="description"/>
                # or value="alternate"/"supplementary". Skip them entirely.
                role_val = ""
                role_m = re.search(
                    r'<Role\b[^>]*value="([^"]*)"',
                    as_body, re.IGNORECASE
                )
                if role_m:
                    role_val = role_m.group(1).lower()
                is_ad_track = role_val in ("description", "alternate", "supplementary", "dub")

                # Also catch by label/accessibility tag (child element)
                label_m = re.search(r'<Label[^>]*>([^<]*)</Label>', as_body, re.IGNORECASE)
                label_txt = label_m.group(1).lower() if label_m else ""
                if any(x in label_txt for x in ("description", " ad", "audio desc")):
                    is_ad_track = True

                # Hotstar puts label="Description" as an attr on the AdaptationSet tag itself
                label_attr = _get_attr(as_attrs, "label", "").lower()
                if label_attr and any(x in label_attr for x in ("description", "audio desc", " ad")):
                    is_ad_track = True

                # Also check Accessibility element (DASH AD standard)
                acc_m = re.search(
                    r'<Accessibility\b[^>]*value="([^"]*)"', as_body, re.IGNORECASE
                )
                if acc_m and "description" in acc_m.group(1).lower():
                    is_ad_track = True

                if is_ad_track:
                    # Collect this AdaptationSet's id so we can drop it by ID
                    # in the N_m3u8DL-RE command (name= filter is unreliable)
                    as_id = _get_attr(as_attrs, "id", "")
                    if as_id:
                        ad_as_ids.append(as_id)
                    continue   # skip AD tracks — don't show in GUI, don't download

                bws = [int(b) for b in re.findall(r'bandwidth="(\d+)"', as_body, re.IGNORECASE)]
                max_kbps = max(bws) / 1000 if bws else 128
                if lang not in audio_seen or max_kbps > audio_seen[lang]:
                    audio_seen[lang] = max_kbps

            # ── SUBTITLES ─────────────────────────────────────────────────────
            elif is_text:
                if lang not in seen_subs:
                    seen_subs.add(lang)
                    sub_tracks.append({"code": lang, "label": lang_label(lang)})

        out.sort(key=lambda x: x["height"], reverse=True)
        audio_tracks = [{"code": lang, "label": lang_label(lang), "max_kbps": kbps}
                        for lang, kbps in audio_seen.items()]

        pssh = extract_pssh(txt)
        return out, dur, audio_tracks, sub_tracks, pssh, ad_as_ids

    except Exception as e:
        print(f"[parse_qualities] error: {e}")
        import traceback; traceback.print_exc()
        return [], None, [], [], None, []

def extract_cid(s):
    s = s.strip().split('?')[0].rstrip('/')
    if s.isdigit(): return s
    # URL structure: /shows/ShowName/SHOW_ID/episode-slug/EPISODE_ID[/watch]
    # strip trailing /watch so it doesn't eat our last segment
    s = re.sub(r'/watch$', '', s, flags=re.IGNORECASE)
    # grab ALL numeric path segments (7-12 digits) and take the LAST one
    # last one is always the episode/movie/content ID
    matches = re.findall(r'/(\d{7,12})(?:/|$)', s)
    return matches[-1] if matches else None

def extract_show_info(url):
    try:
        clean = url.strip().split('?')[0].rstrip('/')
        if clean.endswith('/watch'): clean = clean[:-6]
        clean = re.sub(r'/\d{9,12}$', '', clean)
        parts = [p for p in clean.split('/') if p and not p.isdigit()]
        show, ep = "", ""
        if 'shows' in parts:
            idx = parts.index('shows')
            if idx+1 < len(parts): show = parts[idx+1].replace('-',' ').title()
            if idx+2 < len(parts): ep   = parts[idx+2].replace('-',' ').title()
        elif 'movies' in parts:
            idx = parts.index('movies')
            if idx+1 < len(parts): show = parts[idx+1].replace('-',' ').title()
        elif parts:
            show = parts[-1].replace('-',' ').title()
        return show, ep
    except: return "", ""

_LANG_FULL = {
    "hin":"Hindi","tam":"Tamil","tel":"Telugu","eng":"English","kan":"Kannada",
    "mal":"Malayalam","ben":"Bengali","mar":"Marathi","pun":"Punjabi","guj":"Gujarati",
    "urd":"Urdu","arb":"Arabic","fre":"French","spa":"Spanish","ger":"German",
    "jpn":"Japanese","kor":"Korean","chi":"Chinese","zho":"Chinese","por":"Portuguese",
    "mul":"Multi",
}

def make_filename(url, quality_height, codec="AVC", audio_codes=None, audio_kbps=None,
                  est_size_str=None, has_subs=False, year=None):
    """
    Release-style filename:
    Title (Year) Language TRUE WEB-DL - 1080p - AVC - (DD+5.1 - 640Kbps) - 2.9GB - ESub.mkv
    """
    show, ep = extract_show_info(url)

    # sanitize title
    def san(s): return re.sub(r'[<>:"/\\|?*]', '', s).strip()

    title = san(show[:60]) if show else "Hotstar"

    # year tag
    year_tag = f" ({year})" if year else ""

    # language tag — map 3-letter codes to full names
    lang_tag = ""
    if audio_codes:
        codes = [c.strip().lower() for c in audio_codes if c.strip()]
        if len(codes) == 1:
            lang_tag = " " + _LANG_FULL.get(codes[0], codes[0].title())
        elif codes:
            # multi-audio: list all
            names = [_LANG_FULL.get(c, c.title()) for c in codes]
            lang_tag = " " + " + ".join(names)

    # audio codec/bitrate tag
    kbps = int(audio_kbps) if audio_kbps and audio_kbps > 0 else 0
    if kbps >= 320:
        audio_tag = f"DD+5.1 - {kbps}Kbps"
    elif kbps > 0:
        audio_tag = f"AAC - {kbps}Kbps"
    else:
        audio_tag = "AAC"

    # size tag
    size_tag = f" - {est_size_str}" if est_size_str else ""

    # episode slug
    ep_tag = f" {san(ep[:50])}" if ep else ""

    name = (f"{title}{year_tag}{ep_tag}{lang_tag} TRUE WEB-DL"
            f" - {quality_height}p - {codec} - ({audio_tag}){size_tag}"
            + (" - ESub" if has_subs else "")
            + ".mkv")

    # final sanitize
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    return name

# ─────────────────────────────────────────────────────────────
#  DOWNLOADER  (N_m3u8DL-RE → yt-dlp → ffmpeg)
# ─────────────────────────────────────────────────────────────

def find_exe(candidates):
    """Return first executable that runs, or None."""
    for c in candidates:
        if not c: continue
        try:
            if subprocess.run([c, "--version"], capture_output=True, timeout=5).returncode == 0:
                return c
        except: pass
    return None

def ts_to_secs(ts):
    try:
        p = ts.split(':')
        return int(p[0])*3600 + int(p[1])*60 + float(p[2])
    except: return 0

def run_download(stream_url, out_dir, out_name, quality, cfg, progress_cb, log_cb, cancel_flag,
                 drm_keys=None, ad_as_ids=None, phase_cb=None):
    """
    drm_keys  : list of (kid_hex, key_hex) tuples from Widevine CDM.
                Passed as --key kid:key flags to N_m3u8DL-RE.
    ad_as_ids : list of AdaptationSet IDs (strings) for Audio Description tracks.
                Passed as --drop-audio id~=<id> to exclude AD dubs.
    phase_cb  : optional callable(phase: str) — called with "downloading" or "muxing"
    Returns (True/False, out_path or None)
    """
    os.makedirs(out_dir, exist_ok=True)
    n_path    = cfg.get("n_m3u8dl_path","")
    ytdlp_path= cfg.get("ytdlp_path","yt-dlp")
    ff_path   = cfg.get("ffmpeg_path","ffmpeg")
    threads   = cfg.get("threads", 16)
    subs      = cfg.get("grab_subs", False)
    dur       = cfg.get("_duration")
    height    = quality["height"] if quality else 0
    out_mp4   = os.path.join(out_dir, out_name+".mkv")
    engine    = cfg.get("engine", "auto")
    audio_lang     = cfg.get("audio_lang", "best")
    sub_lang       = cfg.get("sub_lang",   "NONE")
    audio_max_kbps = cfg.get("_audio_max_kbps", {})

    # Build --key flags from DRM keys list
    key_flags = []
    if drm_keys:
        for kid, key in drm_keys:
            key_flags += ["--key", f"{kid}:{key}"]

    _mux_keywords = ("mux", "ffmpeg", "merge", "remux", "writing output")
    def run_proc(cmd, parse_fn):
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, bufsize=1, errors='replace')
            _phase_signalled = [False]  # mutable flag via list
            for line in proc.stdout:
                if cancel_flag.is_set():
                    proc.terminate()
                    try: proc.wait(timeout=3)
                    except: proc.kill()
                    log_cb("\n[!] Cancelled by user\n")
                    return -99
                log_cb(line)
                parse_fn(line)
                # Detect mux phase: N_m3u8DL-RE prints "muxing" or ffmpeg mux lines
                if phase_cb and not _phase_signalled[0]:
                    ll = line.lower()
                    if any(k in ll for k in _mux_keywords):
                        _phase_signalled[0] = True
                        phase_cb("muxing")
            proc.wait()
            return proc.returncode
        except Exception as e:
            log_cb(f"[!] Error: {e}\n")
            return -1

    # ── 1. N_m3u8DL-RE (fastest — aria2c parallel) ──
    use_n = engine in ("auto", "n_m3u8dl")
    if use_n and n_path and os.path.exists(n_path):
        # height → N_m3u8DL-RE res filter; fallback = select video with height ≤ target
        res_map = {
            1080: "res='1920x1080'",
            720:  "res='1280x720'",
            480:  "res='854x480'",
            360:  "res='640x360'",
            270:  "res='480x270'",
            240:  "res='426x240'",
        }
        if height in res_map:
            sel = res_map[height]
        elif height:
            # unknown height — pick closest resolution that fits (height-only filter)
            # N_m3u8DL-RE supports height= filter in newer builds; fall back to best
            sel = f"height<={height}:for=best" if height else None
        else:
            sel = None
        cmd = [n_path, stream_url,
               "--save-name", out_name, "--save-dir", out_dir,
               "--binary-merge", "--del-after-done", "--no-date-info",
               "--thread-count", str(threads),
               "-mt",
               "--mux-after-done", "format=mkv",
               "--header", "Referer: https://www.hotstar.com/",
               "--header", "Origin: https://www.hotstar.com"]

        # ── DRM key flags ────────────────────────────────────────────────────
        if key_flags:
            cmd += key_flags
            log_cb(f"[DRM] Passing {len(drm_keys)} key(s) to N_m3u8DL-RE\n")

        # ── audio selection ──────────────────────────────────────────────────
        # Step 1: drop Audio Description tracks by AdaptationSet ID regex.
        # N_m3u8DL-RE stream IDs contain the AS id as a substring, so id~=<as_id>
        # matches the Description tracks precisely without relying on name= filter.
        if ad_as_ids:
            id_re = "|".join(re.escape(aid) for aid in ad_as_ids)
            cmd += ["--drop-audio", f"id~=({id_re})"]
        else:
            # Fallback: AD detection missed — drop by name regex (case-insensitive ~= match)
            # N_m3u8DL-RE exposes the label="Description" attr as the stream name
            cmd += ["--drop-audio", "name~=(?i)description"]

        # Step 2: single --select-audio flag (N_m3u8DL-RE only accepts one).
        # After dropping AD tracks, for=bestN picks one best track per lang
        # because each lang now has exactly one entry at the top bitrate.
        if audio_lang and audio_lang not in ("best", ""):
            codes = [c.strip() for c in audio_lang.split(",") if c.strip()]
            if len(codes) == 1:
                cmd += ["--select-audio", f"lang={codes[0]}:for=best"]
            else:
                lang_re = "|".join(codes)
                n = len(codes)
                cmd += ["--select-audio", f"lang=({lang_re}):for=best{n}"]
        else:
            cmd += ["--select-audio", "best"]

        if sel: cmd += ["--select-video", sel]
        else:   cmd += ["--select-video", "best"]

        if sub_lang == "ALL" or subs:
            cmd += ["--select-subtitle", "all"]
        elif sub_lang and sub_lang not in ("NONE", ""):
            codes_s = [c.strip() for c in sub_lang.split(",") if c.strip()]
            if len(codes_s) == 1:
                cmd += ["--select-subtitle", f"lang={codes_s[0]}"]
            else:
                sub_re = "|".join(codes_s)
                cmd += ["--select-subtitle", f"lang=({sub_re})"]

        log_cb(f"[N_m3u8DL-RE] {threads} threads | {height}p\n\n")
        pct_re   = re.compile(r'(\d+(?:\.\d+)?)\s*%')
        spd_re   = re.compile(r'(\d+(?:\.\d+)?)\s*(K|M|G)B/s', re.I)
        def parse_n(line):
            pm = pct_re.search(line); sm = spd_re.search(line)
            if pm: progress_cb(float(pm.group(1)), f"{sm.group(1)} {sm.group(2)}B/s" if sm else "")
        rc = run_proc(cmd, parse_n)
        if rc == 0:   progress_cb(100,""); return True, out_mp4
        if rc == -99: return False, None
        if engine == "n_m3u8dl":
            log_cb("[✗] N_m3u8DL-RE failed. Check the log above.\n")
            return False, None
        log_cb("[!] N_m3u8DL-RE failed, trying yt-dlp...\n\n")

    # ── 2. yt-dlp ──
    use_yt = engine in ("auto", "ytdlp")
    ytdlp = None
    if use_yt:
        ytdlp = find_exe([ytdlp_path, "yt-dlp", r"E:\yt-dlp.exe", os.path.join(APP_DIR,"yt-dlp.exe")])
        if not ytdlp:
            log_cb("[~] yt-dlp not found, installing via pip...\n")
            try:
                subprocess.run([sys.executable, "-m", "pip", "install", "yt-dlp", "-q"], timeout=60)
                ytdlp = find_exe(["yt-dlp"])
                if ytdlp: log_cb("[✓] yt-dlp installed\n\n")
            except: pass

    if use_yt and ytdlp:
        if audio_lang and audio_lang not in ("best", ""):
            first_lang = audio_lang.split(",")[0].strip()
            audio_fmt = f"bestaudio[language={first_lang}]/bestaudio"
        else:
            audio_fmt = "bestaudio"
        fmt = (f"bestvideo[height<={height}]+{audio_fmt}/best[height<={height}]"
               if height else f"bestvideo+{audio_fmt}/best")
        cmd = [
            ytdlp, stream_url,
            "-f", fmt,
            "--concurrent-fragments", str(min(threads, 16)),
            "--no-playlist",
            "-o", out_mp4,
            "--add-header", "Referer: https://www.hotstar.com/",
            "--add-header", "Origin: https://www.hotstar.com",
            "--merge-output-format", "mkv",
            "--no-warnings",
            "--newline",
        ]
        # yt-dlp Widevine: pass via --drm-sleep-interval or external downloader
        # yt-dlp itself doesn't accept raw keys; N_m3u8DL-RE is better for DRM
        if key_flags:
            log_cb("[DRM] Note: yt-dlp doesn't support raw key injection — try N_m3u8DL-RE engine for DRM\n")
        log_cb(f"[yt-dlp] {min(threads,16)} concurrent fragments | {height}p\n\n")
        pct_re = re.compile(r'\[download\]\s+(\d+\.?\d*)%.*?(\d+\.?\d*\s*\w+/s)')
        pct_re2= re.compile(r'\[download\]\s+(\d+\.?\d*)%')
        def parse_yt(line):
            m = pct_re.search(line)
            if m: progress_cb(float(m.group(1)), m.group(2)); return
            m = pct_re2.search(line)
            if m: progress_cb(float(m.group(1)), "")
        rc = run_proc(cmd, parse_yt)
        if rc == 0:   progress_cb(100,""); return True, out_mp4
        if rc == -99: return False, None
        if engine == "ytdlp":
            log_cb("[✗] yt-dlp failed. Check the log above.\n")
            return False, None
        log_cb("[!] yt-dlp failed, falling back to ffmpeg\n\n")

    # ── 3. ffmpeg (sequential fallback) ──
    use_ff = engine in ("auto", "ffmpeg")
    ff = find_exe([ff_path, "ffmpeg", r"E:\ffmpeg.exe", r"E:\ffmpeg\bin\ffmpeg.exe"])
    if not ff:
        log_cb("[✗] No downloader found.\n    Install yt-dlp: pip install yt-dlp\n    Or ffmpeg from ffmpeg.org\n")
        return False, None

    mpd_idx = quality.get("mpd_video_idx") if quality else None
    cmd = [ff, "-allowed_extensions","ALL",
           "-headers","Referer: https://www.hotstar.com/\r\nOrigin: https://www.hotstar.com\r\n",
           "-i", stream_url]
    if mpd_idx is not None:
        cmd += ["-map", f"0:v:{mpd_idx}", "-map", "0:a:0"]
    cmd += ["-c","copy", out_mp4, "-y",
            "-progress","pipe:1","-nostats","-loglevel","error"]
    if key_flags:
        log_cb("[DRM] Note: ffmpeg fallback doesn't support raw Widevine key injection\n")
    log_cb(f"[ffmpeg] sequential fallback | {height}p stream #{mpd_idx}\n\n")

    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 text=True, bufsize=1, errors='replace')
        def read_err():
            for l in proc.stderr: log_cb(l)
        threading.Thread(target=read_err, daemon=True).start()
        spd = ""
        for line in proc.stdout:
            if cancel_flag.is_set():
                proc.terminate()
                try: proc.wait(timeout=3)
                except: proc.kill()
                log_cb("\n[!] Cancelled\n")
                return False, None
            m = re.search(r'out_time=(\d+:\d+:\d+\.\d+)', line)
            sm= re.search(r'speed=\s*([0-9.]+)x', line)
            if sm: spd = f"{sm.group(1)}x"
            if m and dur:
                pct = min(ts_to_secs(m.group(1))/dur*100, 99.9)
                progress_cb(pct, spd)
        proc.wait()
        if proc.returncode==0: progress_cb(100,""); return True, out_mp4
    except Exception as e:
        log_cb(f"[!] ffmpeg error: {e}\n")
    return False, None

# ─────────────────────────────────────────────────────────────
#  POST-DOWNLOAD DECRYPTION  (Shaka Packager / mp4decrypt)
# ─────────────────────────────────────────────────────────────

def decrypt_with_shaka(enc_file, out_file, drm_keys, shaka_path="packager", log_cb=None):
    """
    Run Shaka Packager to decrypt a single encrypted mp4/mkv track.

    For a merged file (video+audio muxed) produced by N_m3u8DL-RE or yt-dlp,
    we need to demux → decrypt each track → re-mux via ffmpeg.
    Shaka Packager works on individual streams, so we:
      1. Detect tracks in the file (video / audio) via ffprobe
      2. Run packager once per track with --enable_raw_key_decryption
      3. Re-mux the decrypted tracks with ffmpeg

    drm_keys : list of (kid_hex, key_hex)  — we pass ALL keys; packager picks the right one
    Returns True on success.
    """
    def _log(m):
        if log_cb: log_cb(m)

    shaka = find_exe([shaka_path, "packager", "shaka-packager",
                      r"C:\shaka-packager\packager.exe",
                      os.path.join(APP_DIR, "packager.exe"),
                      os.path.join(APP_DIR, "shaka-packager.exe")])
    if not shaka:
        _log("[Shaka] ✗ packager not found. Install: github.com/shaka-project/shaka-packager\n")
        return False

    if not drm_keys:
        _log("[Shaka] ✗ No DRM keys provided\n")
        return False

    # ── build --keys flag: key_id=KID:key=KEY (separate entries per key) ──
    # Format for raw key decryption: each key is "label=...,key_id=KID,key=KEY"
    # We build one label per key
    key_labels = []
    for i, (kid, key) in enumerate(drm_keys):
        kid_clean = kid.replace("-", "").lower()
        key_clean = key.replace("-", "").lower()
        key_labels.append(f"label={i},key_id={kid_clean},key={key_clean}")

    # ── temp output paths ──
    base, ext = os.path.splitext(enc_file)
    ext = ext or ".mp4"
    tmp_vid = base + "_dec_video.mp4"
    tmp_aud = base + "_dec_audio.mp4"
    ffmpeg  = find_exe(["ffmpeg", r"E:\ffmpeg.exe", r"E:\ffmpeg\bin\ffmpeg.exe"])

    # ── probe streams ──
    try:
        probe = subprocess.run(
            ["ffprobe", "-v","quiet","-print_format","json","-show_streams", enc_file],
            capture_output=True, text=True, timeout=15
        )
        streams = json.loads(probe.stdout).get("streams", [])
    except Exception as e:
        _log(f"[Shaka] ffprobe error: {e} — trying single-stream decrypt\n")
        streams = []

    has_video = any(s.get("codec_type") == "video" for s in streams)
    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    if not streams:
        has_video = has_audio = True  # assume both, let packager figure it out

    decrypted_parts = []

    def _run_shaka_stream(stream_type, tmp_out):
        """Run packager for one stream type."""
        # packager stream descriptor
        stream_desc = (
            f"in={enc_file},"
            f"stream={stream_type},"
            f"output={tmp_out},"
            f"drm_label=CENC"
        )
        cmd = [shaka, stream_desc,
               "--enable_raw_key_decryption",
               "--keys", ",".join(key_labels)]
        _log(f"[Shaka] Decrypting {stream_type} → {os.path.basename(tmp_out)}\n")
        _log(f"[Shaka] cmd: {' '.join(cmd[:3])} ...\n")
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, bufsize=1, errors="replace")
            for line in proc.stdout:
                _log(f"[Shaka] {line}")
            proc.wait()
            if proc.returncode == 0 and os.path.exists(tmp_out):
                _log(f"[Shaka] ✓ {stream_type} decrypted\n")
                return True
            else:
                _log(f"[Shaka] ✗ {stream_type} failed (rc={proc.returncode})\n")
                return False
        except Exception as e:
            _log(f"[Shaka] ✗ {stream_type} error: {e}\n")
            return False

    # Run per-stream decryption
    ok_v = _run_shaka_stream("video", tmp_vid) if has_video else True
    ok_a = _run_shaka_stream("audio", tmp_aud) if has_audio else True

    if has_video and has_audio and ok_v and ok_a and ffmpeg:
        # Re-mux decrypted tracks
        _log(f"[Shaka] Re-muxing to {os.path.basename(out_file)}\n")
        mux_cmd = [ffmpeg, "-y",
                   "-i", tmp_vid, "-i", tmp_aud,
                   "-c", "copy", out_file, "-loglevel", "error"]
        try:
            r = subprocess.run(mux_cmd, capture_output=True, text=True, timeout=120)
            if r.returncode == 0:
                _log("[Shaka] ✓ Re-mux done\n")
            else:
                _log(f"[Shaka] ✗ Re-mux failed: {r.stderr[:200]}\n")
                return False
        except Exception as e:
            _log(f"[Shaka] ✗ Re-mux error: {e}\n")
            return False
        # Clean up temps
        for t in [tmp_vid, tmp_aud]:
            try: os.remove(t)
            except: pass
        return True
    elif has_video and ok_v and not has_audio:
        try:
            os.rename(tmp_vid, out_file)
            return True
        except: pass
    elif has_audio and ok_a and not has_video:
        try:
            os.rename(tmp_aud, out_file)
            return True
        except: pass
    elif has_video and ok_v and not ffmpeg:
        # No ffmpeg to mux, just rename video
        _log("[Shaka] No ffmpeg for mux — saving video track only\n")
        try:
            os.rename(tmp_vid, out_file)
            return True
        except: pass

    _log("[Shaka] ✗ Decryption incomplete\n")
    return False


def decrypt_with_mp4decrypt(enc_file, out_file, drm_keys, mp4decrypt_path="mp4decrypt", log_cb=None):
    """
    Run Bento4 mp4decrypt to decrypt an encrypted mp4 file.

    mp4decrypt --key KID:KEY [--key KID2:KEY2 ...] input.mp4 output.mp4

    drm_keys : list of (kid_hex, key_hex)
    Returns True on success.
    """
    def _log(m):
        if log_cb: log_cb(m)

    mp4d = find_exe([mp4decrypt_path, "mp4decrypt",
                     r"C:\bento4\bin\mp4decrypt.exe",
                     os.path.join(APP_DIR, "mp4decrypt.exe"),
                     os.path.join(APP_DIR, "mp4decrypt")])
    if not mp4d:
        _log("[mp4decrypt] ✗ Not found. Install Bento4: github.com/axiomatic-systems/Bento4\n")
        return False

    if not drm_keys:
        _log("[mp4decrypt] ✗ No DRM keys provided\n")
        return False

    # Build --key flags
    cmd = [mp4d]
    for kid, key in drm_keys:
        kid_clean = kid.replace("-", "").lower()
        key_clean = key.replace("-", "").lower()
        cmd += ["--key", f"{kid_clean}:{key_clean}"]
    cmd += [enc_file, out_file]

    _log(f"[mp4decrypt] {len(drm_keys)} key(s) → {os.path.basename(out_file)}\n")
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, bufsize=1, errors="replace")
        for line in proc.stdout:
            _log(f"[mp4decrypt] {line}")
        proc.wait()
        if proc.returncode == 0 and os.path.exists(out_file):
            _log("[mp4decrypt] ✓ Decryption complete\n")
            return True
        else:
            _log(f"[mp4decrypt] ✗ Failed (rc={proc.returncode})\n")
            return False
    except Exception as e:
        _log(f"[mp4decrypt] ✗ Error: {e}\n")
        return False


def post_decrypt(enc_file, out_file, drm_keys, cfg, log_cb=None):
    """
    Try available decryption tools in order based on cfg['decrypt_tool'].

    Order:
      auto        → tries mp4decrypt first (simple, one-shot), then Shaka Packager
      shaka       → Shaka Packager only
      mp4decrypt  → Bento4 mp4decrypt only

    'n_m3u8dl_inline' means keys were already passed to N_m3u8DL-RE — no post-decrypt needed.

    Returns True if decryption succeeded.
    """
    def _log(m):
        if log_cb: log_cb(m)

    tool = cfg.get("decrypt_tool", "auto")
    shaka_path   = cfg.get("shaka_path",   "packager")
    mp4d_path    = cfg.get("mp4decrypt_path", "mp4decrypt")

    _log(f"\n[Decrypt] Post-download decryption | tool={tool}\n")
    _log(f"[Decrypt] Input:  {enc_file}\n")
    _log(f"[Decrypt] Output: {out_file}\n")

    if tool == "shaka":
        return decrypt_with_shaka(enc_file, out_file, drm_keys, shaka_path, log_cb)

    if tool == "mp4decrypt":
        return decrypt_with_mp4decrypt(enc_file, out_file, drm_keys, mp4d_path, log_cb)

    # auto: try mp4decrypt first (simpler, handles most cases), then Shaka
    _log("[Decrypt] Trying mp4decrypt first...\n")
    if decrypt_with_mp4decrypt(enc_file, out_file, drm_keys, mp4d_path, log_cb):
        return True
    _log("[Decrypt] mp4decrypt failed, trying Shaka Packager...\n")
    return decrypt_with_shaka(enc_file, out_file, drm_keys, shaka_path, log_cb)


# ─────────────────────────────────────────────────────────────
#  THEME
# ─────────────────────────────────────────────────────────────

BG   = "#0d0f18"
BG2  = "#13151f"
BG3  = "#1c1e2e"
BG4  = "#22253a"
ACC  = "#7c6af7"
ACC2 = "#5a48e0"
ACC3 = "#a599ff"
FG   = "#e4e4f0"
FG2  = "#7a7a9d"
FG3  = "#44445a"
GRN  = "#4ade80"
RED  = "#f87171"
YLW  = "#fbbf24"
ORG  = "#fb923c"
FONT  = ("Segoe UI", 10)
FONTB = ("Segoe UI", 10, "bold")
MONO  = ("Consolas", 10)

# ─────────────────────────────────────────────────────────────
#  CUSTOM CHECKBOX WIDGET
# ─────────────────────────────────────────────────────────────

class CheckRow(tk.Frame):
    def __init__(self, parent, var, height_p, width_p, mbps, est_size, is_top=False, **kw):
        super().__init__(parent, bg=BG2, cursor="hand2", **kw)
        self.var = var
        self._hovered = False

        self.cv = tk.Canvas(self, width=18, height=18, bg=BG2,
                             highlightthickness=0, cursor="hand2")
        self.cv.pack(side="left", padx=(6,8), pady=6)
        self._draw()

        q_color = {1080: ACC3, 720: GRN, 480: YLW, 360: ORG}.get(height_p, FG2)
        tk.Label(self, text=f"{height_p}p", bg=BG2, fg=q_color,
                 font=("Consolas", 10, "bold"), width=6, anchor="w").pack(side="left")
        tk.Label(self, text=f"{width_p}×{height_p}", bg=BG2, fg=FG2,
                 font=("Consolas", 9), width=11, anchor="w").pack(side="left")
        tk.Label(self, text=f"{mbps:.1f} Mbps", bg=BG2, fg=FG2,
                 font=("Consolas", 9), width=10, anchor="w").pack(side="left")
        tk.Label(self, text=est_size, bg=BG2, fg=FG2 if not is_top else GRN,
                 font=("Consolas", 9, "bold" if is_top else "normal"), width=10, anchor="w").pack(side="left")

        self._bind_all(self)
        self.var.trace_add("write", lambda *a: self._draw())

    def _bind_all(self, w):
        w.bind("<Button-1>", self._toggle)
        w.bind("<Enter>",    self._on_enter)
        w.bind("<Leave>",    self._on_leave)
        for child in w.winfo_children():
            self._bind_all(child)

    def _toggle(self, e=None): self.var.set(not self.var.get())
    def _on_enter(self, e=None): self._hovered = True; self._set_bg(BG4)
    def _on_leave(self, e=None): self._hovered = False; self._set_bg(BG2)

    def _set_bg(self, c):
        self.configure(bg=c); self.cv.configure(bg=c)
        for w in self.winfo_children():
            try: w.configure(bg=c)
            except: pass

    def _draw(self):
        cv = self.cv; cv.delete("all")
        checked = self.var.get()
        fill  = ACC if checked else BG3
        outline = ACC if checked else FG3
        cv.create_rectangle(1,1,17,17, fill=fill, outline=outline, width=1)
        if checked:
            cv.create_line(3,9, 7,13, fill="#fff", width=2, capstyle="round")
            cv.create_line(7,13,15,5, fill="#fff", width=2, capstyle="round")

# ─────────────────────────────────────────────────────────────
#  MAIN APP
# ─────────────────────────────────────────────────────────────

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("JioHotstar Downloader  •  v6 DRM")
        self.geometry("960x780")
        self.minsize(800,620)
        self.configure(bg=BG)
        try: self.iconbitmap(default='')
        except: pass

        self.cfg        = load_cfg()
        self._guest     = self._ps = self._method = self._phone = None
        self._mpd       = self._m3u8 = None
        self._quals     = []
        self._q_vars    = []
        self._duration  = None
        self._orig_url  = ""
        self._log_open  = False
        self._dl_thread = None
        self._cancel    = threading.Event()
        self._url_list  = []
        self._active_proc = None
        self._drm_keys    = []   # [(kid, key), ...]
        self._pssh        = None
        self._license_url = None  # extracted from MPD ContentProtection
        self._drm_status  = "unknown"  # "none" | "locked" | "unlocked" | "unknown"
        self._ad_as_ids   = []   # AdaptationSet IDs of Audio Description tracks

        self._build_styles()
        self._build_ui()
        self._refresh_status()

    def _build_styles(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure(".", background=BG, foreground=FG, font=FONT)
        s.configure("TFrame", background=BG)
        s.configure("TLabel", background=BG, foreground=FG)
        s.configure("TButton", background=ACC, foreground="#fff",
                    font=FONTB, borderwidth=0, padding=(14,7), relief="flat")
        s.map("TButton",
              background=[("active",ACC2),("disabled",BG3)],
              foreground=[("disabled",FG2)])
        s.configure("Ghost.TButton", background=BG3, foreground=FG2,
                    font=("Segoe UI",9), padding=(10,5), relief="flat", borderwidth=0)
        s.map("Ghost.TButton",
              background=[("active",ACC),("disabled",BG3)],
              foreground=[("active","#fff"),("disabled",FG3)])
        s.configure("Cancel.TButton", background="#7f1d1d", foreground=RED,
                    font=FONTB, padding=(14,7), relief="flat", borderwidth=0)
        s.map("Cancel.TButton", background=[("active","#991b1b")])
        s.configure("DRM.TButton", background="#1a1a2e", foreground=YLW,
                    font=("Segoe UI",9), padding=(10,5), relief="flat", borderwidth=0)
        s.map("DRM.TButton", background=[("active","#2a2a4e")])
        s.configure("TEntry", fieldbackground=BG3, foreground=FG,
                    insertcolor=ACC3, borderwidth=0, relief="flat", padding=6)
        s.configure("TNotebook", background=BG, tabmargins=[0,0,0,0], borderwidth=0)
        s.configure("TNotebook.Tab", background=BG2, foreground=FG2,
                    padding=[22,9], font=FONT, borderwidth=0)
        s.map("TNotebook.Tab",
              background=[("selected",ACC),("active",BG3)],
              foreground=[("selected","#fff"),("active",FG)])
        s.configure("Prog.Horizontal.TProgressbar",
                    troughcolor=BG3, background=ACC, borderwidth=0, thickness=8,
                    lightcolor=ACC, darkcolor=ACC2)
        s.configure("TCheckbutton", background=BG2, foreground=FG, font=FONT)
        s.map("TCheckbutton", background=[("active",BG2)])
        s.configure("TScale", background=BG2, troughcolor=BG3,
                    sliderlength=16, borderwidth=0)

    def _build_ui(self):
        # ── Header ──
        hdr = tk.Frame(self, bg=BG2, height=54)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        lf = tk.Frame(hdr, bg=BG2); lf.pack(side="left", padx=18, pady=12)
        tk.Label(lf, text="▶", bg=BG2, fg=ACC, font=("Segoe UI",15,"bold")).pack(side="left")
        tk.Label(lf, text="  JioHotstar Downloader", bg=BG2, fg=FG,
                 font=("Segoe UI",13,"bold")).pack(side="left")

        rf = tk.Frame(hdr, bg=BG2); rf.pack(side="right", padx=18, pady=14)
        self._status_txt = tk.Label(rf, text="", bg=BG2, fg=FG2, font=("Segoe UI",9))
        self._status_txt.pack(side="right", padx=(0,6))
        self._status_dot = tk.Label(rf, text="●", bg=BG2, fg=RED, font=("Segoe UI",10))
        self._status_dot.pack(side="right")

        tk.Frame(self, bg=ACC, height=2).pack(fill="x")

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)
        self._t_login = ttk.Frame(nb); nb.add(self._t_login, text="  Login  ")
        self._t_dl    = ttk.Frame(nb); nb.add(self._t_dl,    text="  Download  ")
        self._t_cfg   = ttk.Frame(nb); nb.add(self._t_cfg,   text="  Settings  ")
        self._build_login()
        self._build_download()
        self._build_settings()

        # footer removed

    # ───────────────────── LOGIN TAB ─────────────────────

    def _build_login(self):
        f = self._t_login
        col = tk.Frame(f, bg=BG); col.pack(anchor="n", padx=60, pady=28, fill="x")

        card = tk.Frame(col, bg=BG2, padx=30, pady=26); card.pack(fill="x")
        tk.Label(card, text="Phone Login", bg=BG2, fg=ACC,
                 font=("Segoe UI",13,"bold")).grid(row=0,column=0,columnspan=3,sticky="w",pady=(0,20))

        tk.Label(card, text="Phone number  (10 digits, no +91)", bg=BG2, fg=FG2,
                 font=("Segoe UI",9)).grid(row=1,column=0,sticky="w")
        self._phone_e = tk.Entry(card, bg=BG3, fg=FG, insertbackground=ACC3,
                                  font=("Consolas",12), relief="flat", width=18, bd=0)
        self._phone_e.grid(row=2,column=0,pady=(5,0),ipady=7,padx=(0,12),sticky="w")
        self._send_btn = ttk.Button(card, text="Send OTP", command=self._send_otp)
        self._send_btn.grid(row=2,column=1,pady=(5,0),sticky="w")

        tk.Label(card, text="OTP", bg=BG2, fg=FG2,
                 font=("Segoe UI",9)).grid(row=3,column=0,sticky="w",pady=(18,0))
        self._otp_e = tk.Entry(card, bg=BG3, fg=FG, insertbackground=ACC3,
                                font=("Consolas",13), relief="flat", width=12, bd=0, state="disabled")
        self._otp_e.grid(row=4,column=0,pady=(5,0),ipady=7,padx=(0,12),sticky="w")
        self._verify_btn = ttk.Button(card, text="Verify & Login",
                                       command=self._verify_otp, state="disabled")
        self._verify_btn.grid(row=4,column=1,pady=(5,0),sticky="w")

        self._login_msg = tk.Label(card, text="", bg=BG2, fg=FG2,
                                    font=("Segoe UI",9), wraplength=460, justify="left")
        self._login_msg.grid(row=5,column=0,columnspan=3,pady=(18,0),sticky="w")

        tok_card = tk.Frame(col, bg=BG2, padx=22, pady=18); tok_card.pack(fill="x",pady=(16,0))
        tk.Label(tok_card, text="Session", bg=BG2, fg=ACC,
                 font=("Segoe UI",9,"bold")).pack(anchor="w")
        self._tok_detail = tk.Label(tok_card, text="Checking...", bg=BG2, fg=FG2,
                                     font=("Segoe UI",9), wraplength=600, justify="left")
        self._tok_detail.pack(anchor="w",pady=(6,10))
        ttk.Button(tok_card, text="Clear Token", style="Ghost.TButton",
                   command=self._clear_token).pack(anchor="w")

    # ───────────────────── DOWNLOAD TAB ─────────────────────

    def _build_download(self):
        f = self._t_dl
        PAD = dict(padx=14, pady=(10,4))

        # URL card
        uc = tk.Frame(f, bg=BG2); uc.pack(fill="x", **PAD)
        ui = tk.Frame(uc, bg=BG2, padx=16, pady=14); ui.pack(fill="x")
        tk.Label(ui, text="Hotstar URL or Content ID", bg=BG2, fg=FG2,
                 font=("Segoe UI",9)).pack(anchor="w",pady=(0,6))
        ur = tk.Frame(ui, bg=BG2); ur.pack(fill="x")
        self._url_e = tk.Entry(ur, bg=BG3, fg=FG, insertbackground=ACC3,
                                font=MONO, relief="flat", bd=0)
        self._url_e.pack(side="left",fill="x",expand=True,ipady=7,padx=(0,10))
        self._fetch_btn = ttk.Button(ur, text="🔍  Fetch Qualities", command=self._fetch)
        self._fetch_btn.pack(side="left")
        br = tk.Frame(ui, bg=BG2); br.pack(fill="x",pady=(8,0))
        tk.Label(br, text="or add to queue:", bg=BG2, fg=FG2, font=("Segoe UI",8)).pack(side="left")
        ttk.Button(br, text="+ Queue", style="Ghost.TButton",
                   command=self._add_to_queue).pack(side="left",padx=8)
        self._queue_lbl = tk.Label(br, text="Queue: 0 items", bg=BG2, fg=FG2, font=("Segoe UI",8))
        self._queue_lbl.pack(side="left")

        # Quality card
        qc = tk.Frame(f, bg=BG2); qc.pack(fill="x", **PAD)
        qi = tk.Frame(qc, bg=BG2, padx=16, pady=12); qi.pack(fill="x")

        # ── DRM status bar — inline only, no manual fetch button ─────────────
        self._drm_bar = tk.Frame(qi, bg=BG2); self._drm_bar.pack(fill="x", pady=(0,6))
        self._drm_icon = tk.Label(self._drm_bar, text="🔒", bg=BG2, fg=FG3,
                                   font=("Segoe UI",10))
        self._drm_icon.pack(side="left")
        self._drm_lbl  = tk.Label(self._drm_bar, text="", bg=BG2, fg=FG3,
                                   font=("Segoe UI",8))
        self._drm_lbl.pack(side="left", padx=(4,0))

        qt = tk.Frame(qi, bg=BG2); qt.pack(fill="x",pady=(0,6))
        tk.Label(qt, text="Select Qualities to Download", bg=BG2, fg=FG2,
                 font=("Segoe UI",9)).pack(side="left")
        ttk.Button(qt, text="None", style="Ghost.TButton",
                   command=lambda: self._check_all(False)).pack(side="right",padx=(4,0))
        ttk.Button(qt, text="All", style="Ghost.TButton",
                   command=lambda: self._check_all(True)).pack(side="right")
        self._q_frame = tk.Frame(qi, bg=BG2); self._q_frame.pack(fill="x")
        self._q_hint = tk.Label(self._q_frame,
                                 text="← paste a URL and click  Fetch Qualities",
                                 bg=BG2, fg=FG3, font=("Segoe UI",9))
        self._q_hint.pack(anchor="w", pady=6)

        # Output + download card
        dc = tk.Frame(f, bg=BG2); dc.pack(fill="x", **PAD)
        di = tk.Frame(dc, bg=BG2, padx=16, pady=14); di.pack(fill="x")
        tk.Label(di, text="Output Directory", bg=BG2, fg=FG2, font=("Segoe UI",9)).pack(anchor="w",pady=(0,5))
        or_ = tk.Frame(di, bg=BG2); or_.pack(fill="x",pady=(0,12))
        self._out_var = tk.StringVar(value=self.cfg.get("output_dir",""))
        tk.Entry(or_, textvariable=self._out_var, bg=BG3, fg=FG, insertbackground=ACC3,
                  font=MONO, relief="flat", bd=0).pack(side="left",fill="x",expand=True,ipady=6,padx=(0,10))
        ttk.Button(or_, text="Browse", style="Ghost.TButton", command=self._browse_out).pack(side="left")

        tk.Frame(di, bg=BG3, height=1).pack(fill="x", pady=(0,12))

        br2 = tk.Frame(di, bg=BG2); br2.pack(fill="x")
        self._dl_btn = ttk.Button(br2, text="⬇  Download", command=self._start_dl)
        self._dl_btn.pack(side="left")
        self._cancel_btn = ttk.Button(br2, text="✕  Cancel", style="Cancel.TButton",
                                       command=self._cancel_dl)
        self._open_btn = ttk.Button(br2, text="📂 Open Folder", style="Ghost.TButton",
                                     command=self._open_folder, state="disabled")
        self._open_btn.pack(side="left", padx=10)
        self._dl_status = tk.Label(br2, text="", bg=BG2, fg=FG2, font=("Segoe UI",9))
        self._dl_status.pack(side="left")

        pr = tk.Frame(di, bg=BG2); pr.pack(fill="x", pady=(12,0))
        self._prog = ttk.Progressbar(pr, style="Prog.Horizontal.TProgressbar",
                                      orient="horizontal", mode="determinate", maximum=100)
        self._prog.pack(fill="x",expand=True)
        self._prog_txt = tk.Label(di, text="", bg=BG2, fg=FG2, font=("Segoe UI",8))
        self._prog_txt.pack(anchor="w", pady=(4,0))

        lh = tk.Frame(f, bg=BG, cursor="hand2"); lh.pack(fill="x",padx=14,pady=(4,0))
        self._log_lbl_var = tk.StringVar(value="▸  Show log")
        self._log_lbl = tk.Label(lh, textvariable=self._log_lbl_var,
                                   bg=BG, fg=FG2, font=("Segoe UI",9), cursor="hand2")
        self._log_lbl.pack(side="left",pady=3,padx=2)
        for w in (lh, self._log_lbl):
            w.bind("<Button-1>", lambda e: self._toggle_log())

        self._log_frame = tk.Frame(f, bg=BG)
        self._log_box = tk.Text(
            self._log_frame, height=10, state="disabled",
            bg="#080a11", fg="#6a6aaa", font=("Consolas",8),
            borderwidth=0, insertbackground=FG, wrap="word",
            selectbackground=ACC2, selectforeground="#fff")
        sb = tk.Scrollbar(self._log_frame, command=self._log_box.yview)
        self._log_box.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self._log_box.pack(fill="both",expand=True,padx=(14,0),pady=(3,10))

    # ───────────────────── SETTINGS TAB ─────────────────────

    def _build_settings(self):
        f = self._t_cfg
        outer = tk.Frame(f, bg=BG); outer.pack(fill="both",expand=True)
        card = tk.Frame(outer, bg=BG2, padx=26, pady=24); card.pack(fill="x",padx=26,pady=22)
        tk.Label(card, text="Settings", bg=BG2, fg=ACC,
                 font=("Segoe UI",13,"bold")).grid(row=0,column=0,columnspan=4,sticky="w",pady=(0,10))
        self._cfg_vars = {}

        tk.Label(card, text="╌╌  Download Engine  ╌╌", bg=BG2, fg=FG3,
                 font=("Segoe UI",8)).grid(row=1,column=0,columnspan=4,sticky="w",pady=(0,6))

        eng_frame = tk.Frame(card, bg=BG2); eng_frame.grid(row=2,column=0,columnspan=4,sticky="w",pady=(0,12))
        self._engine_var = tk.StringVar(value=self.cfg.get("engine","auto"))

        engines = [
            ("auto",      "🔄  Auto",           "Try N_m3u8DL-RE → yt-dlp → ffmpeg in order"),
            ("n_m3u8dl",  "⚡  N_m3u8DL-RE",    "Fastest · parallel · multi-audio · DRM keys ✓"),
            ("ytdlp",     "📦  yt-dlp",          "Good fallback · single audio · no DRM key inject"),
            ("ffmpeg",    "🔧  ffmpeg",           "Slow but stable · no DRM key inject"),
        ]
        for col,(val,lbl,tip) in enumerate(engines):
            cell = tk.Frame(eng_frame, bg=BG3, padx=10, pady=8, cursor="hand2")
            cell.grid(row=0, column=col, padx=(0,8), sticky="n")
            rb = tk.Radiobutton(cell, text=lbl, variable=self._engine_var, value=val,
                                bg=BG3, fg=FG, selectcolor=BG3, activebackground=BG3,
                                activeforeground=ACC, font=("Segoe UI",9,"bold"),
                                indicatoron=True, bd=0, highlightthickness=0)
            rb.pack(anchor="w")
            tk.Label(cell, text=tip, bg=BG3, fg=FG2,
                     font=("Segoe UI",7), wraplength=130, justify="left").pack(anchor="w",pady=(4,0))
            cell.bind("<Button-1>", lambda e,v=val: self._engine_var.set(v))

        def _refresh_eng_ui(*_):
            selected = self._engine_var.get()
            for col,(val,_,__) in enumerate(engines):
                w = eng_frame.grid_slaves(row=0,column=col)
                if w:
                    w[0].configure(bg=ACC if val==selected else BG3)
                    for child in w[0].winfo_children():
                        child.configure(bg=ACC if val==selected else BG3)
        self._engine_var.trace_add("write", _refresh_eng_ui)
        _refresh_eng_ui()

        tk.Label(card, text="╌╌  Paths  ╌╌", bg=BG2, fg=FG3,
                 font=("Segoe UI",8)).grid(row=3,column=0,columnspan=4,sticky="w",pady=(4,6))

        rows = [
            ("token_file",      "Token File",        "Path to save/load your login token"),
            ("output_dir",      "Output Folder",     "Default download destination"),
            ("n_m3u8dl_path",   "N_m3u8DL-RE exe",   "⚡ Fastest + inline DRM. github.com/nilaoda/N_m3u8DL-RE"),
            ("ytdlp_path",      "yt-dlp exe",         "📦 Fallback. pip install yt-dlp"),
            ("ffmpeg_path",     "ffmpeg exe",          "🔧 Muxing. 'ffmpeg' if in PATH"),
            ("cdm_path",        "WVD Device File",     "🔐 Widevine L3 .wvd for key fetching"),
            ("shaka_path",      "Shaka Packager exe",  "📦 Post-decrypt tool. github.com/shaka-project/shaka-packager"),
            ("mp4decrypt_path", "mp4decrypt exe",       "🔑 Bento4 post-decrypt. github.com/axiomatic-systems/Bento4"),
        ]
        for i,(k,lbl,hint) in enumerate(rows):
            r = i+4
            tk.Label(card, text=lbl, bg=BG2, fg=FG, font=FONTB,
                     width=16, anchor="w").grid(row=r,column=0,sticky="w",pady=7)
            var = tk.StringVar(value=self.cfg.get(k,""))
            self._cfg_vars[k] = var
            tk.Entry(card, textvariable=var, bg=BG3, fg=FG, insertbackground=ACC3,
                      font=("Consolas",9), relief="flat", bd=0, width=46
                      ).grid(row=r,column=1,padx=8,ipady=6,sticky="w")
            ttk.Button(card, text="Browse", style="Ghost.TButton",
                       command=lambda k=k,v=var: self._cfg_browse(k,v)
                       ).grid(row=r,column=2,padx=6)
            tk.Label(card, text=hint, bg=BG2, fg=FG2, font=("Segoe UI",8),
                     wraplength=180).grid(row=r,column=3,padx=8,sticky="w")

        r = len(rows)+4
        tk.Frame(card, bg=BG3, height=1).grid(row=r,column=0,columnspan=4,sticky="ew",pady=14)
        r += 1
        tk.Label(card, text="╌╌  DRM Decrypt Tool  ╌╌", bg=BG2, fg=FG3,
                 font=("Segoe UI",8)).grid(row=r,column=0,columnspan=4,sticky="w",pady=(0,6))
        r += 1
        dec_frame = tk.Frame(card, bg=BG2); dec_frame.grid(row=r,column=0,columnspan=4,sticky="w",pady=(0,12))
        self._decrypt_tool_var = tk.StringVar(value=self.cfg.get("decrypt_tool","auto"))
        dec_tools = [
            ("auto",             "🔄  Auto",            "mp4decrypt → Shaka fallback"),
            ("n_m3u8dl_inline",  "⚡  Inline (N_m3u8DL)","Keys passed during download"),
            ("mp4decrypt",       "🔑  mp4decrypt",       "Bento4 — fast, single-pass"),
            ("shaka",            "📦  Shaka Packager",   "Per-track decrypt + re-mux"),
        ]
        for col,(val,lbl,tip) in enumerate(dec_tools):
            cell2 = tk.Frame(dec_frame, bg=BG3, padx=10, pady=8, cursor="hand2")
            cell2.grid(row=0, column=col, padx=(0,8), sticky="n")
            rb2 = tk.Radiobutton(cell2, text=lbl, variable=self._decrypt_tool_var, value=val,
                                 bg=BG3, fg=FG, selectcolor=BG3, activebackground=BG3,
                                 activeforeground=ACC, font=("Segoe UI",9,"bold"),
                                 indicatoron=True, bd=0, highlightthickness=0)
            rb2.pack(anchor="w")
            tk.Label(cell2, text=tip, bg=BG3, fg=FG2,
                     font=("Segoe UI",7), wraplength=130, justify="left").pack(anchor="w",pady=(4,0))
            cell2.bind("<Button-1>", lambda e,v=val: self._decrypt_tool_var.set(v))

        def _refresh_dec_ui(*_):
            selected = self._decrypt_tool_var.get()
            for col,(val,_,__) in enumerate(dec_tools):
                w = dec_frame.grid_slaves(row=0,column=col)
                if w:
                    c = ACC if val==selected else BG3
                    w[0].configure(bg=c)
                    for child in w[0].winfo_children():
                        child.configure(bg=c)
        self._decrypt_tool_var.trace_add("write", _refresh_dec_ui)
        _refresh_dec_ui()

        r += 1
        tk.Frame(card, bg=BG3, height=1).grid(row=r,column=0,columnspan=4,sticky="ew",pady=(4,14))
        r += 1
        tk.Label(card, text="DL Threads", bg=BG2, fg=FG, font=FONTB,
                 anchor="w").grid(row=r,column=0,sticky="w",pady=8)
        self._threads_var = tk.IntVar(value=self.cfg.get("threads",16))
        tr = tk.Frame(card, bg=BG2); tr.grid(row=r,column=1,sticky="w",pady=8)
        ttk.Scale(tr, from_=4, to=64, variable=self._threads_var, orient="horizontal", length=200,
                  command=lambda v: self._threads_lbl.configure(text=str(int(float(v))))
                  ).pack(side="left")
        self._threads_lbl = tk.Label(tr, text=str(self.cfg.get("threads",16)),
                                      bg=BG2, fg=ACC3, font=("Consolas",10,"bold"), width=3)
        self._threads_lbl.pack(side="left",padx=8)
        r += 1
        tk.Label(card, text="Subtitles", bg=BG2, fg=FG, font=FONTB,
                 anchor="w").grid(row=r,column=0,sticky="w",pady=8)
        self._subs_var = tk.BooleanVar(value=self.cfg.get("grab_subs",False))
        ttk.Checkbutton(card, text="Always grab subtitle tracks (N_m3u8DL-RE only)",
                        variable=self._subs_var).grid(row=r,column=1,columnspan=3,sticky="w")
        r += 1
        tk.Frame(card, bg=BG3, height=1).grid(row=r,column=0,columnspan=4,sticky="ew",pady=14)
        r += 1
        ttk.Button(card, text="Save Settings", command=self._save_cfg
                   ).grid(row=r,column=0,sticky="w")
        self._cfg_msg = tk.Label(card, text="", bg=BG2, fg=GRN, font=("Segoe UI",9))
        self._cfg_msg.grid(row=r,column=1,sticky="w",padx=10)

    # ───────────────────── ACTIONS ─────────────────────

    def _log_w(self, t):
        self._log_box.configure(state="normal")
        self._log_box.insert("end", t)
        self._log_box.see("end")
        self._log_box.configure(state="disabled")

    def _toggle_log(self):
        if self._log_open:
            self._log_frame.pack_forget()
            self._log_lbl_var.set("▸  Show log")
        else:
            self._log_frame.pack(fill="both", expand=True)
            self._log_lbl_var.set("▾  Hide log")
        self._log_open = not self._log_open

    def _refresh_status(self):
        tok, path = load_token(self.cfg)
        if tok:
            s = tok_str(tok)
            self._status_dot.configure(fg=GRN)
            self._status_txt.configure(text=f"Logged in  •  {s}", fg=FG2)
            self._tok_detail.configure(text=f"✓  Valid token  •  {s}\n{path}", fg=GRN)
        else:
            self._status_dot.configure(fg=RED)
            self._status_txt.configure(text="Not logged in", fg=FG2)
            self._tok_detail.configure(text="✗  No token — use Login tab", fg=RED)

    def _clear_token(self):
        p = self.cfg.get("token_file","")
        if p and os.path.exists(p): os.remove(p)
        self._refresh_status()
        self._tok_detail.configure(text="Token cleared.", fg=FG2)

    # ── Login ──

    def _send_otp(self):
        phone = self._phone_e.get().strip().replace("+91","").replace(" ","")
        if not phone.isdigit() or len(phone)!=10:
            self._login_msg.configure(text="✗ Enter a valid 10-digit number", fg=RED); return
        self._phone = phone
        self._send_btn.configure(state="disabled", text="Sending...")
        self._login_msg.configure(text="Getting guest session...", fg=FG2)
        def _w():
            g,ps = api_guest()
            if not g:
                self.after(0, lambda: self._login_msg.configure(text="✗ Guest token failed", fg=RED))
                self.after(0, lambda: self._send_btn.configure(state="normal", text="Send OTP"))
                return
            self._guest, self._ps = g, ps
            ok, m = api_send_otp(phone, g, ps)
            self._method = m
            if ok:
                self.after(0, self._otp_ok)
            else:
                self.after(0, lambda: self._login_msg.configure(text="✗ OTP failed. Check number.", fg=RED))
                self.after(0, lambda: self._send_btn.configure(state="normal", text="Send OTP"))
        threading.Thread(target=_w, daemon=True).start()

    def _otp_ok(self):
        self._login_msg.configure(text=f"✓ OTP sent to +91 {self._phone}", fg=GRN)
        self._send_btn.configure(state="normal", text="Resend OTP")
        self._otp_e.configure(state="normal")
        self._verify_btn.configure(state="normal")
        self._otp_e.focus()

    def _verify_otp(self):
        otp = self._otp_e.get().strip()
        if not otp.isdigit():
            self._login_msg.configure(text="✗ Invalid OTP", fg=RED); return
        self._verify_btn.configure(state="disabled", text="Verifying...")
        def _w():
            tok = api_verify_otp(self._phone, otp, self._guest, self._ps, self._method or "web")
            if tok:
                path = save_token(tok, self._phone, self.cfg)
                self.after(0, lambda: self._login_msg.configure(
                    text=f"✓ Login successful!\nToken: {path}", fg=GRN))
                self.after(0, self._refresh_status)
                self.after(0, lambda: self._verify_btn.configure(state="normal",text="Verify & Login"))
            else:
                self.after(0, lambda: self._login_msg.configure(
                    text="✗ Wrong OTP or expired. Try again.", fg=RED))
                self.after(0, lambda: self._verify_btn.configure(state="normal",text="Verify & Login"))
        threading.Thread(target=_w, daemon=True).start()

    # ── Download ──

    def _browse_out(self):
        d = filedialog.askdirectory(initialdir=self._out_var.get())
        if d: self._out_var.set(d)

    def _add_to_queue(self):
        url = self._url_e.get().strip()
        if url:
            self._url_list.append(url)
            self._queue_lbl.configure(text=f"Queue: {len(self._url_list)} items")
            self._url_e.delete(0,"end")

    def _check_all(self, val):
        for v in self._q_vars: v.set(val)

    def _update_drm_ui(self):
        """Refresh the DRM status bar — inline text only, no button."""
        s = self._drm_status
        if s == "none":
            self._drm_icon.configure(text="🔓", fg=GRN)
            self._drm_lbl.configure(text="DRM: Plain stream — no decryption needed", fg=GRN)
        elif s == "fetching":
            self._drm_icon.configure(text="🔒", fg=YLW)
            self._drm_lbl.configure(text="DRM: Widevine encrypted  •  Fetching decryption keys...", fg=YLW)
        elif s == "locked":
            self._drm_icon.configure(text="🔒", fg=YLW)
            self._drm_lbl.configure(text="DRM: Widevine encrypted  •  Auto-fetching keys...", fg=YLW)
        elif s == "unlocked":
            n = len(self._drm_keys)
            self._drm_icon.configure(text="🗝", fg=GRN)
            self._drm_lbl.configure(text=f"DRM: Widevine encrypted  •  ✓ {n} key(s) fetched — ready to decrypt", fg=GRN)
        elif s == "failed":
            self._drm_icon.configure(text="🔒", fg=RED)
            self._drm_lbl.configure(text="DRM: Widevine encrypted  •  ✗ Key fetch failed — check log", fg=RED)
        else:
            self._drm_icon.configure(text="🔒", fg=FG3)
            self._drm_lbl.configure(text="", fg=FG3)

    def _fetch(self):
        url = self._url_e.get().strip()
        if not url: messagebox.showwarning("No URL","Paste a URL or content ID first."); return
        cid = extract_cid(url)
        if not cid: messagebox.showerror("Bad URL","Can't extract content ID."); return
        tok, _ = load_token(self.cfg)
        if not tok: messagebox.showerror("Not logged in","Login first."); return
        self._orig_url = url

        for w in self._q_frame.winfo_children(): w.destroy()
        tk.Label(self._q_frame, text="Fetching stream info...",
                 bg=BG2, fg=FG2, font=("Segoe UI",9)).pack(anchor="w",pady=6)
        self._q_vars = []
        self._fetch_btn.configure(state="disabled")
        self._drm_keys  = []
        self._pssh      = None
        self._drm_status= "unknown"
        self._ad_as_ids = []
        self._update_drm_ui()

        def _w():
            mpd, m3u8, api_lic_url, status = fetch_stream(cid, tok)
            self.after(0, lambda: self._fetch_btn.configure(state="normal"))
            if status != 200:
                self.after(0, lambda: self._show_err(f"API error {status}")); return
            self._mpd, self._m3u8 = mpd, m3u8
            quals, dur, audio_tracks, sub_tracks, pssh, ad_as_ids = (
                parse_qualities(mpd) if mpd else ([], None, [], [], None, [])
            )
            # For plain (non-DRM) streams the MPD may only list one audio track
            # or the stream may be HLS-only — parse the m3u8 master playlist too
            # and merge any additional language tracks found there.
            if m3u8 and len(audio_tracks) <= 1:
                m3u8_audio = parse_m3u8_audio_tracks(m3u8)
                if len(m3u8_audio) > len(audio_tracks):
                    audio_tracks = m3u8_audio
            self._quals, self._duration = quals, dur
            self._audio_tracks, self._sub_tracks = audio_tracks, sub_tracks
            self._pssh = pssh
            self._ad_as_ids = ad_as_ids   # Description AdaptationSet IDs to drop
            # License URL — prefer playback API response, fallback to MPD ContentProtection
            self._license_url = api_lic_url
            if not self._license_url and mpd:
                try:
                    import requests as _req
                    _r = _req.get(mpd, timeout=10, headers={"Referer":"https://www.hotstar.com/"})
                    self._license_url = extract_license_url(_r.text)
                except Exception:
                    self._license_url = None
            # update DRM status + auto-fetch keys if CDM is available
            if pssh is None:
                self._drm_status = "none"
                self.after(0, lambda: self._update_drm_ui())
            else:
                cdm_path = self.cfg.get("cdm_path", "").strip()
                if cdm_path and os.path.exists(cdm_path):
                    self._drm_status = "fetching"
                    self.after(0, lambda: self._update_drm_ui())
                    # auto-fetch keys in background
                    _pssh2 = pssh; _lic2 = api_lic_url; _mpd2 = mpd or ""; _tok2 = tok
                    def _auto_keys(_pssh=_pssh2, _lic=_lic2, _mpd=_mpd2, _t=_tok2):
                        def _log(m): self.after(0, lambda m=m: self._log_w(m))
                        keys2 = get_widevine_keys(_pssh, _t, _mpd,
                                                  cdm_path=cdm_path, log_cb=_log,
                                                  license_url=_lic)
                        self._drm_keys   = keys2
                        self._drm_status = "unlocked" if keys2 else "failed"
                        self.after(0, self._update_drm_ui)
                    threading.Thread(target=_auto_keys, daemon=True).start()
                else:
                    self._drm_status = "locked"
                    self.after(0, lambda: self._update_drm_ui())
            self.after(0, lambda: self._show_quals(quals, audio_tracks, sub_tracks))
        threading.Thread(target=_w, daemon=True).start()

    def _fetch_keys(self):
        """Fetch Widevine decryption keys in a background thread."""
        if not self._pssh:
            messagebox.showinfo("No DRM","This content has no DRM / PSSH detected."); return
        tok, _ = load_token(self.cfg)
        if not tok:
            messagebox.showerror("Not logged in","Login first."); return

        self._drm_status = "fetching"
        self._update_drm_ui()
        if not self._log_open: self._toggle_log()

        cdm_path    = self.cfg.get("cdm_path","")
        mpd_url     = self._mpd or ""
        pssh        = self._pssh
        license_url = getattr(self, "_license_url", None)

        def _w():
            def _log(msg): self.after(0, lambda m=msg: self._log_w(m))
            _log(f"[DRM] Starting key fetch  |  PSSH: {pssh[:40]}...\n")
            if license_url:
                _log(f"[DRM] ✓ Licence URL from API (pre-auth'd): {license_url[:100]}\n")
            else:
                _log("[DRM] ⚠ No licence URL from API — will try generic fallback endpoints\n")
            keys = get_widevine_keys(pssh, tok, mpd_url, cdm_path=cdm_path,
                                     log_cb=_log, license_url=license_url)
            self._drm_keys   = keys
            self._drm_status = "unlocked" if keys else "failed"
            self.after(0, self._update_drm_ui)
            if keys:
                _log(f"[DRM] ✓ {len(keys)} key(s) ready for download\n")
            else:
                _log("[DRM] ✗ Key fetch failed — check log above\n")

        threading.Thread(target=_w, daemon=True).start()

    def _show_err(self, msg):
        for w in self._q_frame.winfo_children(): w.destroy()
        tk.Label(self._q_frame, text=f"✗ {msg}", bg=BG2, fg=RED, font=("Segoe UI",9)).pack(anchor="w")

    def _make_mini_cb(self, parent, var, label, color=None):
        fg = color or FG
        f = tk.Frame(parent, bg=BG2, cursor="hand2")
        cv = tk.Canvas(f, width=14, height=14, bg=BG2, highlightthickness=0)
        cv.pack(side="left", padx=(0, 3))
        lbl = tk.Label(f, text=label, bg=BG2, fg=fg, font=("Segoe UI", 8))
        lbl.pack(side="left")
        def _draw(*_):
            cv.delete("all")
            on = var.get()
            cv.create_rectangle(1, 1, 13, 13, fill=ACC if on else BG3,
                                 outline=ACC if on else FG3, width=1)
            if on:
                cv.create_line(2, 7, 5, 11, fill="#fff", width=1, capstyle="round")
                cv.create_line(5, 11, 12, 3, fill="#fff", width=1, capstyle="round")
        _draw()
        var.trace_add("write", _draw)
        def _toggle(e=None): var.set(not var.get())
        cv.bind("<Button-1>", _toggle); lbl.bind("<Button-1>", _toggle); f.bind("<Button-1>", _toggle)
        return f

    def _show_quals(self, quals, audio_tracks=None, sub_tracks=None):
        for w in self._q_frame.winfo_children(): w.destroy()
        self._q_vars = []

        audio_tracks = audio_tracks or []
        sub_tracks   = sub_tracks or []
        self._audio_cb_vars = {}
        self._sub_cb_vars   = {}

        if audio_tracks:
            ar = tk.Frame(self._q_frame, bg=BG2); ar.pack(fill="x", pady=(0, 4))
            tk.Label(ar, text="🔊 Audio:", bg=BG2, fg=FG2,
                     font=("Segoe UI", 8, "bold"), width=8, anchor="w").pack(side="left")
            for i, t in enumerate(audio_tracks):
                v = tk.BooleanVar(value=(i == 0))
                self._audio_cb_vars[t["code"]] = v
                self._make_mini_cb(ar, v, t["label"]).pack(side="left", padx=(0, 8))
            def _toggle_all_audio():
                new = not all(v.get() for v in self._audio_cb_vars.values())
                for v in self._audio_cb_vars.values(): v.set(new)
            btn = tk.Label(ar, text="[all]", bg=BG2, fg=ACC, font=("Segoe UI", 7), cursor="hand2")
            btn.pack(side="left", padx=(4, 0))
            btn.bind("<Button-1>", lambda e: _toggle_all_audio())

        if sub_tracks:
            sr = tk.Frame(self._q_frame, bg=BG2); sr.pack(fill="x", pady=(0, 6))
            tk.Label(sr, text="💬 Subs:", bg=BG2, fg=FG2,
                     font=("Segoe UI", 8, "bold"), width=8, anchor="w").pack(side="left")
            for t in sub_tracks:
                v = tk.BooleanVar(value=False)
                self._sub_cb_vars[t["code"]] = v
                self._make_mini_cb(sr, v, t["label"]).pack(side="left", padx=(0, 8))
            def _toggle_all_subs():
                new = not all(v.get() for v in self._sub_cb_vars.values())
                for v in self._sub_cb_vars.values(): v.set(new)
            btn2 = tk.Label(sr, text="[all]", bg=BG2, fg=ACC, font=("Segoe UI", 7), cursor="hand2")
            btn2.pack(side="left", padx=(4, 0))
            btn2.bind("<Button-1>", lambda e: _toggle_all_subs())

        if audio_tracks or sub_tracks:
            tk.Frame(self._q_frame, bg=BG3, height=1).pack(fill="x", pady=(4, 6))

        if quals:
            hdr = tk.Frame(self._q_frame, bg=BG2); hdr.pack(fill="x")
            tk.Label(hdr, text="   ", bg=BG2, width=3).pack(side="left")
            for txt, w in [("Quality",7),("Resolution",12),("Bitrate",11),("Est. Size",10)]:
                tk.Label(hdr, text=txt, bg=BG2, fg=FG3, font=("Segoe UI",8),
                         width=w, anchor="w").pack(side="left")
            tk.Frame(self._q_frame, bg=BG3, height=1).pack(fill="x", pady=(3,3))

            for i, q in enumerate(quals):
                var = tk.BooleanVar(value=(i==0))
                self._q_vars.append(var)
                row = CheckRow(self._q_frame, var,
                               height_p=q["height"], width_p=q["width"],
                               mbps=q["mbps"], est_size=q.get("est_size","?"),
                               is_top=(i==0))
                row.pack(fill="x", pady=1)
        else:
            var = tk.BooleanVar(value=True)
            self._q_vars.append(var)
            row = tk.Frame(self._q_frame, bg=BG2); row.pack(fill="x",pady=4)
            cb_canvas = tk.Canvas(row, width=18, height=18, bg=BG2, highlightthickness=0)
            cb_canvas.pack(side="left",padx=(6,8),pady=6)
            var.set(True)
            def _draw_fb(v=var, cv=cb_canvas):
                cv.delete("all")
                cv.create_rectangle(1,1,17,17, fill=ACC if v.get() else BG3, outline=ACC if v.get() else FG3)
                if v.get():
                    cv.create_line(3,9,7,13, fill="#fff",width=2,capstyle="round")
                    cv.create_line(7,13,15,5, fill="#fff",width=2,capstyle="round")
            _draw_fb()
            var.trace_add("write", lambda *a: _draw_fb())
            tk.Label(row, text="Best available (auto)", bg=BG2, fg=FG, font=MONO, anchor="w").pack(side="left")
            row.bind("<Button-1>", lambda e,v=var: v.set(not v.get()))

    def _cancel_dl(self):
        self._cancel.set()
        self._dl_status.configure(text="Cancelling...", fg=YLW)

    def _start_dl(self):
        if self._dl_thread and self._dl_thread.is_alive():
            messagebox.showinfo("Busy","Download already running."); return
        tok, _ = load_token(self.cfg)
        if not tok: messagebox.showerror("Not logged in","Login first."); return
        stream = self._mpd or self._m3u8
        if not stream: messagebox.showwarning("No stream","Fetch qualities first."); return

        # Auto-fetch keys if DRM locked, no keys yet, but CDM is configured
        if self._drm_status == "locked" and not self._drm_keys:
            cdm_path = self.cfg.get("cdm_path", "").strip()
            pssh     = getattr(self, "_pssh", None)
            if cdm_path and os.path.exists(cdm_path) and pssh:
                # run key fetch in background, then re-trigger download
                if not self._log_open: self._toggle_log()
                self._log_w("[DRM] CDM found — auto-fetching keys, please wait…\n")
                self._dl_btn.configure(state="disabled", text="Fetching keys...")
                tok2        = tok
                mpd_url2    = self._mpd or self._m3u8 or ""
                lic_url2    = getattr(self, "_license_url", None)

                def _auto_fetch_then_download():
                    def _log(m): self.after(0, lambda m=m: self._log_w(m))
                    keys2 = get_widevine_keys(pssh, tok2, mpd_url2,
                                              cdm_path=cdm_path, log_cb=_log,
                                              license_url=lic_url2)
                    def _resume():
                        self._dl_btn.configure(state="normal", text="⬇  Download")
                        if keys2:
                            self._drm_keys   = keys2
                            self._drm_status = "unlocked"
                            self._update_drm_ui()
                            self._log_w(f"[DRM] ✓ {len(keys2)} key(s) — starting download\n")
                            self._start_dl()   # re-call with keys now set
                        else:
                            self._log_w("[DRM] ✗ Key fetch failed — see log above\n")
                            messagebox.showerror("Key Fetch Failed",
                                "Could not get decryption keys.\nCheck log panel for details.")
                    self.after(0, _resume)

                threading.Thread(target=_auto_fetch_then_download, daemon=True).start()
                return   # bail out — will be re-triggered after keys arrive
            else:
                ans = messagebox.askyesno("DRM Warning",
                    "This stream is Widevine-encrypted and no keys have been fetched.\n\n"
                    "No CDM (.wvd) file is set in Settings — can't auto-fetch keys.\n\n"
                    "Set CDM path in Settings and retry?\n\n"
                    "Click 'No' to attempt download anyway (may fail).")
                if ans: return

        selected = [(i,q) for i,(q,v) in enumerate(
            zip(self._quals if self._quals else [None]*len(self._q_vars), self._q_vars)
        ) if v.get()]
        if not selected: messagebox.showwarning("Nothing selected","Check at least one quality."); return

        out_dir = self._out_var.get().strip() or self.cfg.get("output_dir", APP_DIR)
        self.cfg["output_dir"] = out_dir
        cfg_snap = dict(self.cfg)
        cfg_snap["threads"]    = int(self._threads_var.get())
        cfg_snap["grab_subs"]  = self._subs_var.get()
        cfg_snap["engine"]     = self._engine_var.get()
        cfg_snap["_duration"]  = self._duration
        audio_cb = getattr(self, "_audio_cb_vars", {})
        checked_audio = [code for code, v in audio_cb.items() if v.get()]
        cfg_snap["audio_lang"] = ",".join(checked_audio) if checked_audio else "best"
        all_tracks = getattr(self, "_audio_tracks", [])
        cfg_snap["_audio_max_kbps"] = {t["code"]: t.get("max_kbps", 128) for t in all_tracks}
        sub_cb = getattr(self, "_sub_cb_vars", {})
        checked_subs = [code for code, v in sub_cb.items() if v.get()]
        if not sub_cb or not checked_subs:
            cfg_snap["sub_lang"] = "NONE"
        elif len(checked_subs) == len(sub_cb):
            cfg_snap["sub_lang"] = "ALL"
        else:
            cfg_snap["sub_lang"] = ",".join(checked_subs)
        cfg_snap["decrypt_tool"]    = self._decrypt_tool_var.get()
        cfg_snap["shaka_path"]      = self.cfg.get("shaka_path", "packager")
        cfg_snap["mp4decrypt_path"] = self.cfg.get("mp4decrypt_path", "mp4decrypt")

        drm_keys  = list(self._drm_keys)   # snapshot
        ad_as_ids = list(self._ad_as_ids)  # snapshot

        self._cancel.clear()
        self._dl_btn.configure(state="disabled", text="Downloading...")
        self._cancel_btn.pack(side="left", padx=(0,10))
        self._open_btn.configure(state="disabled")
        self._prog.configure(value=0)
        self._prog_txt.configure(text="")
        self._dl_status.configure(text="Starting...", fg=FG2)
        self._log_box.configure(state="normal")
        self._log_box.delete("1.0","end")
        self._log_box.configure(state="disabled")

        orig_url = self._orig_url
        last_out = [None]

        def _work():
            all_ok = True
            for idx,(i,q) in enumerate(selected):
                if self._cancel.is_set(): break
                q_height = q["height"] if q else 0
                q_tag    = f"{q_height}p" if q_height else "best"
                # Build audio code list from cfg for filename
                audio_lang_raw = cfg_snap.get("audio_lang", "best")
                audio_code_list = (
                    [c.strip() for c in audio_lang_raw.split(",") if c.strip()]
                    if audio_lang_raw and audio_lang_raw not in ("best", "") else []
                )
                # Peak audio kbps across selected langs (for filename tag)
                audio_kbps_map = cfg_snap.get("_audio_max_kbps", {})
                peak_kbps = (
                    max((audio_kbps_map.get(c, 0) for c in audio_code_list), default=0)
                    if audio_code_list else max(audio_kbps_map.values(), default=0)
                )
                has_subs = cfg_snap.get("grab_subs", False) or bool(cfg_snap.get("sub_lang") not in ("NONE",""))
                fname    = make_filename(orig_url, q_height, "AVC", audio_code_list,
                                         audio_kbps=peak_kbps, has_subs=has_subs) if orig_url else \
                           f"hotstar_{q_tag}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.mkv"
                # strip .mkv — run_download appends it
                if fname.endswith(".mkv"): fname = fname[:-4]
                self.after(0, lambda t=q_tag, n=idx+1, tot=len(selected):
                    self._dl_status.configure(text=f"[{n}/{tot}] {t}  ⬇ Downloading…", fg=FG2))

                _n = idx+1; _tot = len(selected); _qt = q_tag
                def _phase_cb(phase, n=_n, tot=_tot, qt=_qt):
                    if phase == "muxing":
                        self.after(0, lambda: self._dl_status.configure(
                            text=f"[{n}/{tot}] {qt}  ⚙ Muxing…", fg=YLW))
                    else:
                        self.after(0, lambda: self._dl_status.configure(
                            text=f"[{n}/{tot}] {qt}  ⬇ Downloading…", fg=FG2))

                ok, out_path = run_download(
                    stream, out_dir, fname, q, cfg_snap,
                    lambda pct,spd: self.after(0, lambda p=pct,s=spd: (
                        self._prog.configure(value=p),
                        self._prog_txt.configure(text=f"{p:.1f}%{'   '+s if s else ''}")
                    )),
                    lambda t: self.after(0, lambda t=t: self._log_w(t)),
                    self._cancel,
                    drm_keys=drm_keys,
                    ad_as_ids=ad_as_ids,
                    phase_cb=_phase_cb
                )

                # ── Post-download decryption (Shaka / mp4decrypt) ──────────────
                dec_tool = cfg_snap.get("decrypt_tool", "auto")
                if ok and out_path and drm_keys and dec_tool != "n_m3u8dl_inline":
                    # Only needed when N_m3u8DL-RE couldn't inject keys inline
                    # (yt-dlp / ffmpeg paths always need post-decrypt)
                    engine_used = cfg_snap.get("engine", "auto")
                    need_post_dec = (engine_used not in ("n_m3u8dl", "auto")) or (dec_tool != "auto")
                    # For auto engine: N_m3u8DL-RE already handled inline if it ran;
                    # but if it failed and yt-dlp / ffmpeg ran, we need post-decrypt.
                    # Safest: always try if dec_tool != auto and keys exist.
                    if dec_tool in ("shaka", "mp4decrypt") and os.path.exists(out_path):
                        base_dec, ext_dec = os.path.splitext(out_path)
                        dec_out = base_dec + "_dec" + ext_dec
                        def _post_log(m): self.after(0, lambda m=m: self._log_w(m))
                        self.after(0, lambda: self._dl_status.configure(
                            text="Decrypting...", fg=YLW))
                        dec_ok = post_decrypt(out_path, dec_out, drm_keys, cfg_snap, _post_log)
                        if dec_ok and os.path.exists(dec_out):
                            try:
                                os.remove(out_path)
                                os.rename(dec_out, out_path)
                                _post_log(f"[Decrypt] ✓ Replaced encrypted file with decrypted\n")
                            except Exception as mv_e:
                                _post_log(f"[Decrypt] ✗ Replace failed: {mv_e}\n"
                                          f"[Decrypt] Decrypted file: {dec_out}\n")
                                out_path = dec_out
                        else:
                            _post_log("[Decrypt] ✗ Post-decrypt failed — encrypted file kept\n")
                            ok = False

                if ok: last_out[0] = out_path
                else:  all_ok = False

            def _done():
                self._dl_btn.configure(state="normal", text="⬇  Download")
                self._cancel_btn.pack_forget()
                if self._cancel.is_set():
                    self._dl_status.configure(text="Cancelled", fg=YLW)
                elif all_ok:
                    self._prog.configure(value=100)
                    self._dl_status.configure(text="✓ Done!", fg=GRN)
                    self._open_btn.configure(state="normal")
                else:
                    self._dl_status.configure(text="✗ Failed — check log", fg=RED)
                    if not self._log_open: self._toggle_log()
                self._refresh_status()
            self.after(0, _done)

        self._dl_thread = threading.Thread(target=_work, daemon=True)
        self._dl_thread.start()

    def _open_folder(self):
        d = self._out_var.get() or self.cfg.get("output_dir","")
        if d and os.path.isdir(d):
            if sys.platform=="win32": os.startfile(d)
            else: subprocess.Popen(["xdg-open", d])

    def _cfg_browse(self, key, var):
        if any(x in key for x in ("dir","folder","output")):
            d = filedialog.askdirectory()
            if d: var.set(d)
        else:
            f = filedialog.askopenfilename(filetypes=[("All","*.*"),("Exe","*.exe"),("WVD","*.wvd")])
            if f: var.set(f)

    def _save_cfg(self):
        for k,v in self._cfg_vars.items(): self.cfg[k] = v.get()
        self.cfg["threads"]      = int(self._threads_var.get())
        self.cfg["grab_subs"]    = self._subs_var.get()
        self.cfg["engine"]       = self._engine_var.get()
        self.cfg["decrypt_tool"] = self._decrypt_tool_var.get()
        self._out_var.set(self.cfg.get("output_dir",""))
        save_cfg(self.cfg)
        self._cfg_msg.configure(text="✓ Saved")
        self.after(2000, lambda: self._cfg_msg.configure(text=""))
        self._refresh_status()


if __name__ == "__main__":
    app = App()
    app.mainloop()
