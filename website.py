import datetime
import functools
import inspect
import sqlite3
import uuid

import flask
import markdown

import model


app = flask.Flask(__name__)

DEFAULT_STYLE = """
body {
  max-width: 600px;
  margin: auto
}

table, textarea {
  width: 100%;
}

td {
  vertical-align: top;
  padding: 5px;
}
"""

DEFAULT_DESCRIPTION = """
# default event description

This is an event.
This sentence belongs to the same paragraph as the one before.

This sentence starts a new paragraph.

## subheading

Gosh what a great event! Here is a list of things:

- the first thing
- another thing
- your favourite thing

and here's a list with numbers:

1. one
2. two
3. three

Here's [a link](https://youtu.be/dQw4w9WgXcQ).

You should probably change this.
"""


def slugify(s: str) -> str:
    return ''.join((c if c.isalnum() else '-') for c in s)


def get_db():
    if 'db' not in flask.g:
        flask.g.db = sqlite3.connect(
            "events.db",
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


def get_token(db) -> model.Token:
    tokens = model.Tokens(db)
    name = flask.request.cookies.get("token", "")
    token = tokens.get(name)

    if token.expires < datetime.datetime.now():
        tokens.delete(name)
    else:
        tokens.refresh(name)

    return tokens.get(name)


def issue_token(db) -> model.Token:
    tokens = model.Tokens(db)
    while True:
        name = uuid.uuid4().hex
        try:
            tokens.create(name)
        except model.AlreadyExistsError:
            pass
        else:
            break
    return tokens.get(name)


def with_token(func):
    sig = inspect.signature(func)

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        db = get_db()
        try:
            token = get_token(db)
        except LookupError:
            token = issue_token(db)
        
        if "token" in sig.parameters:
            phantom = sig.replace(parameters=(v for v in sig.parameters.values() if v.name != "token"))
            binding = phantom.bind_partial(*args, **kwargs)
            binding.arguments["token"] = token
            response = func(**binding.arguments)
        else:
            response = func(*args, **kwargs)
        
        response = flask.make_response(response)
        response.set_cookie("token", token.name)
        return response

    return wrapper


@app.route("/")
@with_token
def home():
    events = model.Events(get_db()).get_all()
    error = flask.request.args.get("error")
    return flask.render_template("home.html", error=error, events=events)


@app.route("/admin")
@with_token
def admin():
    error = flask.request.args.get("error")
    return flask.render_template("admin.html", error=error)


@app.route("/<name>")
@with_token
def event(name: str):
    db = get_db()

    try:
        event = model.Events(db).get(name)
    except LookupError:
        return f"event {name!r} not found", 404

    guests = model.Guests(db).get_all(event.id)

    return flask.render_template(
        "event.html",
        name=name,
        title=event.title,
        style=event.style,
        desc=markdown.markdown(event.desc),
        error=flask.request.args.get("error"),
        guestname=flask.request.args.get("guestname"),
        guestcomment=flask.request.args.get("comment"),
        guestgoing=flask.request.args.get("going", "True") != "False",
        attending=[(guest.name, guest.title, guest.comment) for guest in guests if guest.going],
        bailing=[(guest.name, guest.title, guest.comment) for guest in guests if not guest.going],
    )


@app.route("/<name>/edit")
@with_token
def edit_event(token: model.Token, name: str):
    db = get_db()
    events = model.Events(db)

    try:
        event = events.get(name)
    except LookupError:
        return f"event {name!r} not found", 404

    authorized = events.check_token(name, token)
    expires = token.expires

    return flask.render_template(
        "edit_event.html",
        name=name,
        title=event.title,
        style=event.style,
        desc=event.desc,
        error=flask.request.args.get("error"),
        authorized=authorized,
        expires=expires,
    )


@app.route("/<name>/delete")
@with_token
def delete_event(token: model.Token, name: str):
    db = get_db()
    events = model.Events(db)

    try:
        event = events.get(name)
    except LookupError:
        return f"event {name!r} not found", 404

    authorized = events.check_token(name, token)
    expires = token.expires

    return flask.render_template(
        "delete_event.html",
        name=name,
        title=event.title,
        style=event.style,
        error=flask.request.args.get("error"),
        authorized=authorized,
        expires=expires,
    )


@app.route("/<event_name>/guest/<name>")
@with_token
def edit_guest(token: model.Token, event_name: str, name: str):
    db = get_db()
    events = model.Events(db)
    guests = model.Guests(db)

    try:
        event = events.get(event_name)
    except LookupError:
        return f"event {event_name!r} not found", 404
    
    try:
        guest = guests.get(event.id, name)
    except LookupError:
        return f"guest {name!r} for event {event_name!r} not found", 404

    authorized = guests.check_token(event.id, name, token)
    expires = token.expires

    return flask.render_template(
        "edit_guest.html",
        event_name=event.name,
        style=event.style,
        name=guest.name,
        title=guest.title,
        going=guest.going,
        comment=guest.comment,
        error=flask.request.args.get("error"),
        authorized=authorized,
        expires=expires,
    )


@app.route("/<event_name>/guest/<name>/delete")
@with_token
def delete_guest(token: model.Token, event_name: str, name: str):
    db = get_db()
    events = model.Events(db)
    guests = model.Guests(db)

    try:
        event = events.get(event_name)
    except LookupError:
        return f"event {event_name!r} not found", 404
    
    try:
        guest = guests.get(event.id, name)
    except LookupError:
        return f"guest {name!r} for event {event_name!r} not found", 404

    authorized = guests.check_token(event.id, name, token)
    expires = token.expires

    return flask.render_template(
        "delete_guest.html",
        event_name=event.name,
        style=event.style,
        name=guest.name,
        title=guest.title,
        error=flask.request.args.get("error"),
        authorized=authorized,
        expires=expires,
    )


@app.route("/api/event", methods=["POST"])
@with_token
def api_create_event(token: model.Token):
    title = flask.request.form["name"].strip()
    name = slugify(title)
    password = flask.request.form["password"]

    if not name:
        url = flask.url_for("home", error="name must not be empty")
        return flask.redirect(url)

    db = get_db()
    events = model.Events(db)

    try:
        events.create(
            name=name,
            password=password,
            style=DEFAULT_STYLE,
            title=title,
            desc=DEFAULT_DESCRIPTION,
        )
    except model.AlreadyExistsError:
        url = flask.url_for(
            "home", error="there is already an event with that name slug",
        )
        return flask.redirect(url)
    
    events.approve_token(name, token, password)

    url = flask.url_for("edit_event", name=name)
    return flask.redirect(url)


@app.route("/api/event/<name>", methods=["POST"])
@with_token
def api_update_event(token: model.Token, name: str):
    print("name", name)
    if not name:
        return "not found", 404

    db = get_db()
    events = model.Events(db)

    try:
        authorized = events.check_token(name, token)
        if not authorized:
            password = flask.request.form.get("password", "")
            try:
                events.approve_token(name, token, password)
            except PermissionError:
                url = flask.url_for("edit_event", name=name, error="bad password or token expired")
                return flask.redirect(url)

        events.update(
            name=name,
            style=flask.request.form["style"],
            title=flask.request.form["title"].strip(),
            desc=flask.request.form["desc"],
        )
    except LookupError:
        pass

    url = flask.url_for("event", name=name)
    return flask.redirect(url)


@app.route("/api/event/<name>/delete", methods=["POST"])
@with_token
def api_delete_event(token: model.Token, name: str):
    if not name:
        return "not found", 404

    db = get_db()
    events = model.Events(db)

    try:
        authorized = events.check_token(name, token)
        if not authorized:
            password = flask.request.form.get("password", "")
            try:
                events.approve_token(name, token, password)
            except PermissionError:
                url = flask.url_for("delete_event", name=name, error="bad password or token expired")
                return flask.redirect(url)

        events.delete(name=name)
    except LookupError:
        pass

    url = flask.url_for("home")
    return flask.redirect(url)


@app.route("/api/event/<event_name>/guest", methods=["POST"])
@with_token
def api_create_guest(token: model.Token, event_name: str):
    if not event_name:
        return "not found", 404

    title = flask.request.form["name"].strip()
    name = slugify(title)
    comment = flask.request.form["comment"].strip()
    going = flask.request.form["going"] == "going"
    password = flask.request.form["password"]

    if not name:
        url = flask.url_for(
            "event",
            name=event_name,
            guestname=title,
            going=going,
            comment=comment,
            error="name must not be empty",
        )
        return flask.redirect(url)

    db = get_db()

    events = model.Events(db)
    try:
        event = events.get(event_name)
    except LookupError:
        return f"no such event {event_name}", 404

    guest_table = model.Guests(db)

    try:
        guest_table.create(
            event_id=event.id,
            name=name,
            title=title,
            password=password,
            going=going,
            comment=comment,
        )
    except model.AlreadyExistsError:
        url = flask.url_for(
            "event",
            name=event_name,
            guestname=title,
            going=going,
            comment=comment,
            error="there is already a guest with that name",
        )
        return flask.redirect(url)

    guest_table.approve_token(event.id, name, token, password)

    url = flask.url_for("event", name=event_name)
    return flask.redirect(url)


@app.route("/api/event/<event_name>/guest/<name>", methods=["POST"])
@with_token
def api_update_guest(token: model.Token, event_name: str, name: str):
    if not event_name or not name:
        return "not found", 404

    comment = flask.request.form["comment"].strip()
    going = flask.request.form["going"] == "going"

    db = get_db()

    events = model.Events(db)
    try:
        event = events.get(event_name)
    except LookupError:
        return f"no such event {event_name}", 404

    guest_table = model.Guests(db)

    try:
        authorized = guest_table.check_token(event.id, name, token)
        if not authorized:
            password = flask.request.form.get("password", "")
            try:
                guest_table.approve_token(event.id, name, token, password)
            except PermissionError:
                url = flask.url_for(
                    "edit_guest",
                    event_name=event_name,
                    name=name,
                    error="bad password or token expired",
                )
                return flask.redirect(url)

        guest_table.update(
            event_id=event.id,
            name=name,
            going=going,
            comment=comment,
        )
    except LookupError as e:
        pass

    url = flask.url_for("event", name=event_name)
    return flask.redirect(url)


@app.route("/api/event/<event_name>/guest/<name>/delete", methods=["POST"])
@with_token
def api_delete_guest(token: model.Token, event_name: str, name: str):
    if not event_name or not name:
        return "not found", 404

    db = get_db()

    events = model.Events(db)
    try:
        event = events.get(event_name)
    except LookupError:
        return f"no such event {event_name}", 404

    guest_table = model.Guests(db)

    try:
        authorized = guest_table.check_token(event.id, name, token)
        if not authorized:
            password = flask.request.form.get("password", "")
            try:
                guest_table.approve_token(event.id, name, token, password)
            except PermissionError:
                url = flask.url_for(
                    "delete_guest",
                    event_name=event_name,
                    name=name,
                    error="bad password or token expired",
                )
                return flask.redirect(url)

        guest_table.delete(
            event_id=event.id,
            name=name,
        )
    except LookupError as e:
        pass

    url = flask.url_for("event", name=event_name)
    return flask.redirect(url)


@app.route("/api/admin", methods=["POST"])
@with_token
def api_admin(token: model.Token):
    password = flask.request.form.get("password")

    try:
        model.Tokens(get_db()).set_admin(token.name, password)
    except PermissionError:
        url = flask.url_for("admin", error="bad password")
        return flask.redirect(url)
    
    url = flask.url_for("home")
    return flask.redirect(url)



@app.route("/api/revoke")
def api_revoke():
    db = get_db()
    try:
        token = get_token(db)
    except LookupError:
        pass
    else:
        model.Tokens(db).delete(token.name)

    token = issue_token(db)

    url = flask.request.args.get("redirect", flask.url_for('home'))
    response = flask.redirect(url)
    response.set_cookie("token", token.name)
    return response

if __name__ == "__main__":
    app.run(debug=True)
