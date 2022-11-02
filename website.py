import dataclasses
import hashlib
import secrets
import sqlite3

import flask


SALT = b"mmmmsalty"

app = flask.Flask(__name__)


class Guest:
    id: int
    name: str
    going: bool
    salt: bytes
    passhash: str


def hash_password(salt: bytes, password: str):
    hash_ = hashlib.sha256()
    hash_.update(password.encode("utf-8"))
    hash_.update(salt)
    hash_.update(SALT)
    return hash_.hexdigest()


def get_db():
    if 'db' not in flask.g:
        flask.g.db = sqlite3.connect(
            "guests.db",
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        flask.g.db.row_factory = sqlite3.Row

    return flask.g.db


@app.teardown_appcontext
def close_db(exception=None):
    try:
        db = flask.g.pop('db')
    except KeyError:
        pass
    else:
        db.close()


@app.route("/")
def home():
    db = get_db()
    with db:
        guests = db.execute("SELECT * FROM guest").fetchall()

    name = flask.request.args.get("name")
    error = flask.request.args.get("error")
    comment = flask.request.args.get("comment")
    going = flask.request.args.get("going", "True") != "False"

    print(guests)

    return flask.render_template(
        "home.html",
        name=name,
        error=error,
        comment=comment,
        going=going,
        attending=[
            (guest["name"], guest["comment"])
            for guest in guests if guest["going"]
        ],
        bailing=[
            (guest["name"], guest["comment"])
            for guest in guests if not guest["going"]
        ],
    )


@app.route("/api/guest", methods=["POST"])
def guest():
    db = get_db()

    print(flask.request.form)
    name = flask.request.form["name"].strip()
    comment = flask.request.form["comment"].strip()
    going = flask.request.form["going"] == "going"

    if not name:
        return flask.redirect(flask.url_for("home", name=name, going=going, comment=comment, error="name must not be empty"))

    with db:
        guest = db.execute(
            "SELECT * FROM guest WHERE name = ?",
            (name,),
        ).fetchone()

    if guest is None:
        salt = secrets.token_bytes(4)
        passhash = hash_password(
            salt, flask.request.form["password"],
        )

        with db:
            db.execute(
                "INSERT INTO guest (name, going, comment, salt, passhash) VALUES (?, ?, ?, ?, ?)",
                (name, going, comment, salt, passhash),
            )

        return flask.redirect(flask.url_for("home", name=name, going=going, comment=comment))
    else:
        passhash = hash_password(guest["salt"], flask.request.form["password"])
        if passhash == guest["passhash"]:
            with db:
                db.execute(
                    "UPDATE guest SET going = ?, comment = ? WHERE name = ?",
                    (going, comment, name),
                )

            return flask.redirect(flask.url_for("home", name=name, going=going, comment=comment))
        else:
            return flask.redirect(flask.url_for("home", name=name, going=going, comment=comment, error="bad password"))



if __name__ == "__main__":
    app.run(debug=True)
