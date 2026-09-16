import os
import sqlite3
from datetime import date, timedelta
from functools import wraps

from flask import Flask, g, redirect, render_template, request, send_from_directory, session, url_for

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "arbeitsplan.db")

DATABASE_URL = os.environ.get("DATABASE_URL")
USE_POSTGRES = bool(DATABASE_URL)

if USE_POSTGRES:
    import psycopg2
    import psycopg2.extras

    INTEGRITY_ERRORS = (psycopg2.IntegrityError,)
else:
    INTEGRITY_ERRORS = (sqlite3.IntegrityError,)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "bitte-in-produktion-aendern")

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "chef123")

WOCHENTAGE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag"]

SCHEMA_SQLITE = """
    CREATE TABLE IF NOT EXISTS mitarbeiter (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        aktiv INTEGER NOT NULL DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS schichten (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mitarbeiter_id INTEGER NOT NULL REFERENCES mitarbeiter(id) ON DELETE CASCADE,
        woche_start TEXT NOT NULL,
        wochentag INTEGER NOT NULL,
        notiz TEXT DEFAULT '',
        UNIQUE(mitarbeiter_id, woche_start, wochentag)
    );
"""

SCHEMA_POSTGRES = """
    CREATE TABLE IF NOT EXISTS mitarbeiter (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        aktiv INTEGER NOT NULL DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS schichten (
        id SERIAL PRIMARY KEY,
        mitarbeiter_id INTEGER NOT NULL REFERENCES mitarbeiter(id) ON DELETE CASCADE,
        woche_start TEXT NOT NULL,
        wochentag INTEGER NOT NULL,
        notiz TEXT DEFAULT '',
        UNIQUE(mitarbeiter_id, woche_start, wochentag)
    );
"""


class PostgresConnection:
    """Duenner Wrapper, der psycopg2 wie sqlite3.Connection benutzbar macht."""

    def __init__(self, dsn):
        self._conn = psycopg2.connect(dsn, cursor_factory=psycopg2.extras.RealDictCursor)

    def execute(self, sql, params=()):
        cur = self._conn.cursor()
        cur.execute(sql.replace("?", "%s"), params)
        return cur

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


def get_db():
    if "db" not in g:
        if USE_POSTGRES:
            g.db = PostgresConnection(DATABASE_URL)
        else:
            g.db = sqlite3.connect(DB_PATH)
            g.db.row_factory = sqlite3.Row
            g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    if USE_POSTGRES:
        conn = psycopg2.connect(DATABASE_URL)
        conn.cursor().execute(SCHEMA_POSTGRES)
        conn.commit()
        conn.close()
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.executescript(SCHEMA_SQLITE)
        conn.commit()
        conn.close()


def montag_der_woche(bezugstag: date) -> date:
    return bezugstag - timedelta(days=bezugstag.weekday())


def parse_woche_start(woche_str: str) -> date:
    try:
        d = date.fromisoformat(woche_str)
    except (ValueError, TypeError):
        d = date.today()
    return montag_der_woche(d)


def login_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login", next=request.path))
        return view_func(*args, **kwargs)

    return wrapped


@app.context_processor
def inject_globals():
    return {"is_admin": bool(session.get("is_admin"))}


@app.route("/")
def index():
    heute = date.today()
    return redirect(url_for("woche_ansehen", woche=montag_der_woche(heute).isoformat()))


@app.route("/sw.js")
def service_worker():
    return send_from_directory(app.static_folder, "sw.js", mimetype="application/javascript")


@app.route("/manifest.webmanifest")
def manifest():
    return send_from_directory(app.static_folder, "manifest.webmanifest", mimetype="application/manifest+json")


@app.route("/woche/<woche>")
def woche_ansehen(woche):
    woche_start = parse_woche_start(woche)
    db = get_db()

    tage = []
    for i, name in enumerate(WOCHENTAGE):
        tag_datum = woche_start + timedelta(days=i)
        eintraege = db.execute(
            """
            SELECT m.name AS name, s.notiz AS notiz
            FROM schichten s
            JOIN mitarbeiter m ON m.id = s.mitarbeiter_id
            WHERE s.woche_start = ? AND s.wochentag = ?
            ORDER BY LOWER(m.name)
            """,
            (woche_start.isoformat(), i),
        ).fetchall()
        tage.append({"name": name, "datum": tag_datum, "eintraege": eintraege})

    return render_template(
        "view.html",
        tage=tage,
        woche_start=woche_start,
        woche_ende=woche_start + timedelta(days=4),
        vorherige_woche=(woche_start - timedelta(days=7)).isoformat(),
        naechste_woche=(woche_start + timedelta(days=7)).isoformat(),
        heute_woche=montag_der_woche(date.today()).isoformat(),
    )


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    fehler = None
    if request.method == "POST":
        passwort = request.form.get("passwort", "")
        if passwort == ADMIN_PASSWORD:
            session["is_admin"] = True
            ziel = request.args.get("next") or url_for("admin_woche")
            return redirect(ziel)
        fehler = "Falsches Passwort."
    return render_template("login.html", fehler=fehler)


@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("index"))


@app.route("/admin")
@login_required
def admin_root():
    return redirect(url_for("admin_woche", woche=montag_der_woche(date.today()).isoformat()))


@app.route("/admin/woche/<woche>", methods=["GET"])
@login_required
def admin_woche_view(woche):
    return _admin_woche(woche)


@app.route("/admin/woche", methods=["GET"])
@login_required
def admin_woche():
    return _admin_woche(montag_der_woche(date.today()).isoformat())


def _admin_woche(woche):
    woche_start = parse_woche_start(woche)
    db = get_db()

    mitarbeiter = db.execute(
        "SELECT id, name FROM mitarbeiter WHERE aktiv = 1 ORDER BY LOWER(name)"
    ).fetchall()

    zugewiesen = db.execute(
        "SELECT mitarbeiter_id, wochentag FROM schichten WHERE woche_start = ?",
        (woche_start.isoformat(),),
    ).fetchall()
    zugewiesen_set = {(row["mitarbeiter_id"], row["wochentag"]) for row in zugewiesen}

    tage = [
        {"index": i, "name": name, "datum": woche_start + timedelta(days=i)}
        for i, name in enumerate(WOCHENTAGE)
    ]

    return render_template(
        "admin.html",
        mitarbeiter=mitarbeiter,
        tage=tage,
        zugewiesen_set=zugewiesen_set,
        woche_start=woche_start,
        vorherige_woche=(woche_start - timedelta(days=7)).isoformat(),
        naechste_woche=(woche_start + timedelta(days=7)).isoformat(),
        heute_woche=montag_der_woche(date.today()).isoformat(),
    )


@app.route("/admin/woche/<woche>/speichern", methods=["POST"])
@login_required
def admin_woche_speichern(woche):
    woche_start = parse_woche_start(woche)
    db = get_db()

    mitarbeiter_ids = [row["id"] for row in db.execute("SELECT id FROM mitarbeiter").fetchall()]

    db.execute("DELETE FROM schichten WHERE woche_start = ?", (woche_start.isoformat(),))

    for mid in mitarbeiter_ids:
        for tag_index in range(5):
            feld = f"schicht_{mid}_{tag_index}"
            if request.form.get(feld):
                db.execute(
                    "INSERT INTO schichten (mitarbeiter_id, woche_start, wochentag) VALUES (?, ?, ?)",
                    (mid, woche_start.isoformat(), tag_index),
                )
    db.commit()

    return redirect(url_for("admin_woche_view", woche=woche_start.isoformat()))


@app.route("/admin/mitarbeiter/hinzufuegen", methods=["POST"])
@login_required
def mitarbeiter_hinzufuegen():
    name = request.form.get("name", "").strip()
    woche = request.form.get("woche") or montag_der_woche(date.today()).isoformat()
    if name:
        db = get_db()
        try:
            db.execute("INSERT INTO mitarbeiter (name) VALUES (?)", (name,))
            db.commit()
        except INTEGRITY_ERRORS:
            db.rollback()
    return redirect(url_for("admin_woche_view", woche=woche))


@app.route("/admin/mitarbeiter/<int:mitarbeiter_id>/entfernen", methods=["POST"])
@login_required
def mitarbeiter_entfernen(mitarbeiter_id):
    woche = request.form.get("woche") or montag_der_woche(date.today()).isoformat()
    db = get_db()
    db.execute("UPDATE mitarbeiter SET aktiv = 0 WHERE id = ?", (mitarbeiter_id,))
    db.commit()
    return redirect(url_for("admin_woche_view", woche=woche))


init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
