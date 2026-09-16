# Arbeitsplan-App

Einfache Web-App für den Wochen-Arbeitsplan (Montag bis Freitag). Der Chef trägt
über einen passwortgeschützten Bereich ein, wer an welchem Tag arbeitet. Alle
Mitarbeiter sehen den Plan über einen normalen Link – ohne eigenen Login.

## Funktionen

- Öffentliche Ansicht (`/`): zeigt die aktuelle Woche, Mo–Fr, mit den
  eingetragenen Mitarbeitern pro Tag. Vor/Zurück-Buttons für andere Wochen.
- Chef-Login (`/admin/login`): geschützt mit einem Passwort.
- Bearbeiten (`/admin`): Tabelle mit Mitarbeitern × Wochentagen zum Ankreuzen,
  ein Klick auf "Woche speichern" reicht.
- Mitarbeiter verwalten: neue Mitarbeiter hinzufügen, alte entfernen.

## Lokal ausführen

```bash
cd arbeitsplan-app
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Die App läuft dann unter http://localhost:5000

Chef-Login-Passwort standardmäßig: `chef123` (bitte ändern, siehe unten).

## Chef-Passwort ändern

Das Passwort wird über eine Umgebungsvariable gesetzt:

```bash
export ADMIN_PASSWORD="dein-neues-passwort"
python app.py
```

Ohne gesetzte Variable gilt das Standardpasswort `chef123`.

## Online stellen, damit alle Mitarbeiter den Link nutzen können

Am einfachsten geht das kostenlos über [Render.com](https://render.com):

1. Diesen Ordner (`arbeitsplan-app`) in ein GitHub-Repository hochladen.
2. Auf Render: "New +" → "Web Service" → das Repository auswählen.
3. Build Command: `pip install -r requirements.txt`
4. Start Command: `gunicorn app:app`
5. Unter "Environment" zwei Variablen setzen:
   - `ADMIN_PASSWORD` = dein gewünschtes Chef-Passwort
   - `SECRET_KEY` = eine beliebige lange Zufallszeichenkette
6. Deploy klicken. Render gibt dir einen Link (z.B. `https://euer-plan.onrender.com`),
   den du den Mitarbeitern schicken kannst.

**Wichtig:** Auf dem kostenlosen Render-Plan wird die Festplatte bei jedem neuen
Deploy zurückgesetzt – die SQLite-Datenbank (`arbeitsplan.db`) würde dann
geleert. Solange ihr nach dem ersten Deploy keine Codeänderungen mehr
hochladet, ist das kein Problem. Falls ihr später öfter Änderungen deployen
wollt, sagt Bescheid – dann wechseln wir die Datenbank auf eine kostenlose
Render-Postgres-Instanz, die das übersteht.

## Datenablage

Alle Daten liegen in der Datei `arbeitsplan.db` (SQLite) im selben Ordner –
kein separater Datenbankserver nötig.
