import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from typing import Tuple, Dict, Any, Optional

CONFIG_FILE = Path("master_admin/data/email_config.json")

DEFAULT_CONFIG: Dict[str, Any] = {
    "enabled": False,
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
    "use_tls": True,
    "use_ssl": False,
    "username": "",
    "password": "",
    "from_name": "Techlahoma Bison Bash",
    "from_email": "",
    "subject_template": "Your Bison Bash Player Pass & 4-Digit PIN",
    "body_template": (
        "Hi {name},\n\n"
        "Welcome to Bison Bash! Here is your digital venue pass:\n\n"
        "----------------------------------------\n"
        "YOUR 4-DIGIT PIN: {pin}\n"
        "STARTING BALANCE: {balance} Credits\n"
        "----------------------------------------\n\n"
        "Punch this 4-digit PIN into any betting kiosk, N64 tournament station, "
        "or game booth on the venue floor to play.\n\n"
        "See you at the races!\n"
        "The Techlahoma Team"
    )
}

def load_email_config() -> Dict[str, Any]:
    """Loads email settings from JSON, returning defaults if not found."""
    if not CONFIG_FILE.exists():
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        save_email_config(DEFAULT_CONFIG)
        return dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            merged = dict(DEFAULT_CONFIG)
            merged.update(data)
            return merged
    except Exception:
        return dict(DEFAULT_CONFIG)

def save_email_config(config: Dict[str, Any]) -> None:
    """Saves email settings to JSON."""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

def send_email(to_email: str, subject: str, body: str, config: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
    """
    Sends an email using the configured SMTP settings.
    Returns (success: bool, message: str).
    """
    if config is None:
        config = load_email_config()

    smtp_host = config.get("smtp_host", "").strip()
    smtp_port = int(config.get("smtp_port", 587))
    username = config.get("username", "").strip()
    password = config.get("password", "").strip()
    from_name = config.get("from_name", "Techlahoma Bison Bash").strip()
    from_email = config.get("from_email", "").strip() or username
    use_tls = bool(config.get("use_tls", True))
    use_ssl = bool(config.get("use_ssl", False))

    if not smtp_host:
        return False, "SMTP Host is not configured."
    if not from_email:
        return False, "Sender (From) Email is not configured."

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{from_name} <{from_email}>" if from_name else from_email
        msg["To"] = to_email

        part = MIMEText(body, "plain", "utf-8")
        msg.attach(part)

        if use_ssl:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=12)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=12)

        server.ehlo()
        if use_tls and not use_ssl:
            server.starttls()
            server.ehlo()

        if username and password:
            server.login(username, password)

        server.sendmail(from_email, [to_email], msg.as_string())
        server.quit()
        return True, "Email sent successfully!"
    except Exception as e:
        return False, f"SMTP Error: {str(e)}"

def send_test_email(to_email: str, config: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
    """Sends a quick test email to verify SMTP credentials."""
    subject = "Techlahoma Bison Bash - SMTP Test Successful"
    body = (
        "Congratulations!\n\n"
        "Your email configuration for Bison Bash is working properly.\n"
        "Attendees will receive their 4-digit PIN passes through this server."
    )
    return send_email(to_email, subject, body, config)

def send_player_pass_email(player: Dict[str, Any]) -> Tuple[bool, str]:
    """Sends a pass email containing the player's 4-digit PIN and balance."""
    config = load_email_config()
    if not config.get("enabled", False):
        return False, "Email dispatch is currently disabled in settings."

    to_email = player.get("email", "").strip()
    if not to_email:
        return False, "Player has no email on record."

    name = player.get("name", "Player")
    pin = player.get("pin", "----")
    balance = player.get("balance", 100)

    subject_tmpl = config.get("subject_template", DEFAULT_CONFIG["subject_template"])
    body_tmpl = config.get("body_template", DEFAULT_CONFIG["body_template"])

    try:
        subject = subject_tmpl.format(name=name, pin=pin, balance=balance)
    except Exception:
        subject = DEFAULT_CONFIG["subject_template"].format(name=name, pin=pin, balance=balance)

    try:
        body = body_tmpl.format(name=name, pin=pin, balance=balance)
    except Exception:
        body = DEFAULT_CONFIG["body_template"].format(name=name, pin=pin, balance=balance)

    return send_email(to_email, subject, body, config)
