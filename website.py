import sqlite3

import flask
import markdown

import model


app = flask.Flask(__name__)


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


@app.route("/")
def home():
    events = model.Events(get_db()).get_all()
    error = flask.request.args.get("error")
    return flask.render_template("home.html", error=error, events=events)


@app.route("/<name>")
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
        guestname=flask.request.args.get("guestname"),
        guesterror=flask.request.args.get("error"),
        guestcomment=flask.request.args.get("comment"),
        guestgoing=flask.request.args.get("going", "True") != "False",
        attending=[(guest.name, guest.comment) for guest in guests if guest.going],
        bailing=[(guest.name, guest.comment) for guest in guests if not guest.going],
    )


@app.route("/<name>/edit")
def edit_event(name: str):
    db = get_db()

    try:
        event = model.Events(db).get(name)
    except LookupError:
        return f"event {name!r} not found", 404

    return flask.render_template(
        "edit_event.html",
        name=name,
        title=event.title,
        style=event.style,
        desc=event.desc,
        error=flask.request.args.get("error"),
    )


@app.route("/<name>/delete")
def delete_event(name: str):
    db = get_db()

    try:
        event = model.Events(db).get(name)
    except LookupError:
        return f"event {name!r} not found", 404

    return flask.render_template(
        "delete_event.html",
        name=name,
        style=event.style,
        error=flask.request.args.get("error"),
    )


@app.route("/<event_name>/<name>")
def edit_guest(event_name: str, name: str):
    db = get_db()

    try:
        event = model.Events(db).get(event_name)
    except LookupError:
        return f"event {event_name!r} not found", 404
    
    try:
        guest = model.Guests(db).get(event.id, name)
    except LookupError:
        return f"guest {name!r} for event {event_name!r} not found", 404

    return flask.render_template(
        "edit_guest.html",
        event_name=event.name,
        style=event.style,
        name=guest.name,
        going=guest.going,
        comment=guest.comment,
        error=flask.request.args.get("error"),
    )


@app.route("/<event_name>/<name>/delete")
def delete_guest(event_name: str, name: str):
    db = get_db()

    try:
        event = model.Events(db).get(event_name)
    except LookupError:
        return f"event {event_name!r} not found", 404
    
    try:
        guest = model.Guests(db).get(event.id, name)
    except LookupError:
        return f"guest {name!r} for event {event_name!r} not found", 404

    return flask.render_template(
        "delete_guest.html",
        event_name=event.name,
        style=event.style,
        name=guest.name,
        error=flask.request.args.get("error"),
    )


@app.route("/api/event", methods=["POST"])
def api_create_event():
    name = flask.request.form["name"]

    if not name:
        url = flask.url_for("home", error="name must not be empty")
        return flask.redirect(url)

    events = model.Events(get_db())

    try:
        events.create(
            name=name,
            password=flask.request.form["password"],
            style="",
            title=name,
            desc="# default event\n\nchange me"
        )
    except model.AlreadyExistsError:
        url = flask.url_for(
            "home", error="there is already an event with that name",
        )
        return flask.redirect(url)

    url = flask.url_for("edit_event", name=name)
    return flask.redirect(url)


@app.route("/api/event/<name>", methods=["POST"])
def api_update_event(name: str):
    if not name:
        return "not found", 404

    events = model.Events(get_db())
    try:
        events.update(
            name=name,
            password=flask.request.form["password"],
            style=flask.request.form["style"],
            title=flask.request.form["title"].strip(),
            desc=flask.request.form["desc"],
        )
    except LookupError:
        url = flask.url_for("home")
        return flask.redirect(url)
    except PermissionError:
        url = flask.url_for("edit_event", name=name, error="bad password")
        return flask.redirect(url)

    url = flask.url_for("event", name=name)
    return flask.redirect(url)


@app.route("/api/event/<name>/delete", methods=["POST"])
def api_delete_event(name: str):
    if not name:
        return "not found", 404

    events = model.Events(get_db())
    try:
        events.delete(name=name, password=flask.request.form["password"])
    except LookupError:
        url = flask.url_for("home")
        return flask.redirect(url)
    except PermissionError:
        url = flask.url_for("delete_event", name=name, error="bad password")
        return flask.redirect(url)

    url = flask.url_for("home")
    return flask.redirect(url)


@app.route("/api/event/<event_name>/guest", methods=["POST"])
def api_create_guest(event_name: str):
    if not event_name:
        return "not found", 404

    name = flask.request.form["name"].strip()
    comment = flask.request.form["comment"].strip()
    going = flask.request.form["going"] == "going"

    if not name:
        url = flask.url_for(
            "event",
            name=event_name,
            guestname=name,
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
            password=flask.request.form["password"],
            going=going,
            comment=comment,
        )
    except model.AlreadyExistsError:
        url = flask.url_for(
            "event",
            name=event_name,
            guestname=name,
            going=going,
            comment=comment,
            error="there is already a guest with that name",
        )
        return flask.redirect(url)

    url = flask.url_for(
        "event",
        name=event_name,
        guestname=name,
        going=going,
        comment=comment,
    )
    return flask.redirect(url)


@app.route("/api/event/<event_name>/guest/<name>", methods=["POST"])
def api_update_guest(event_name: str, name: str):
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
        guest_table.update(
            event_id=event.id,
            name=name,
            password=flask.request.form["password"],
            going=going,
            comment=comment,
        )
    except PermissionError:
        url = flask.url_for(
            "edit_guest",
            event_name=event_name,
            name=name,
            error="bad password",
        )
        return flask.redirect(url)
    except LookupError as e:
        url = flask.url_for("event", name=event_name)
        return flask.redirect(url)

    url = flask.url_for("event", name=event_name)
    return flask.redirect(url)


@app.route("/api/event/<event_name>/guest/<name>/delete", methods=["POST"])
def api_delete_guest(event_name: str, name: str):
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
        guest_table.delete(
            event_id=event.id,
            name=name,
            password=flask.request.form["password"],
        )
    except PermissionError:
        url = flask.url_for(
            "delete_guest",
            event_name=event_name,
            name=name,
            error="bad password",
        )
        return flask.redirect(url)
    except LookupError as e:
        url = flask.url_for("event", name=event_name)
        return flask.redirect(url)

    url = flask.url_for("event", name=event_name)
    return flask.redirect(url)


if __name__ == "__main__":
    app.run(debug=True)
