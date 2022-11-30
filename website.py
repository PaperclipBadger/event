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
        "edit.html",
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
        "delete.html",
        name=name,
        error=flask.request.args.get("error"),
    )


@app.route("/api/event", methods=["POST"])
def api_add_event():
    name = flask.request.form["name"]

    if not name:
        url = flask.url_for("home", error="name must not be empty")
        return flask.redirect(url), 400

    events = model.Events(get_db())

    try:
        events.add(
            name=name,
            password=flask.request.form["password"],
            style="",
            title=name,
            desc="# default event\n\nchange me"
        )
    except model.EventAlreadyExistsError:
        url = flask.url_for(
            "home", error="there is already an event with that name",
        )
        return flask.redirect(url), 400

    url = flask.url_for("edit_event", name=name)
    return flask.redirect(url)


@app.route("/api/event/<name>", methods=["POST"])
def api_update_event(name: str):
    assert name

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
        url = flask.url_for("edit_event", name=name, error=f"no such event {name!r}")
        return flask.redirect(url), 401
    except PermissionError:
        url = flask.url_for("edit_event", name=name, error="bad password")
        return flask.redirect(url), 401

    url = flask.url_for("event", name=name)
    return flask.redirect(url)


@app.route("/api/event/<name>/delete", methods=["POST"])
def api_delete_event(name: str):
    assert name

    events = model.Events(get_db())
    try:
        events.delete(name=name, password=flask.request.form["password"])
    except LookupError:
        url = flask.url_for("delete_event", name=name, error=f"no such event {name!r}")
        return flask.redirect(url), 401
    except PermissionError:
        url = flask.url_for("delete_event", name=name, error="bad password")
        return flask.redirect(url), 401

    url = flask.url_for("home")
    return flask.redirect(url)


@app.route("/api/guest", methods=["POST"])
def api_add_or_update_guest():
    event_name = flask.request.form["event"]
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
        return flask.redirect(url), 400

    db = get_db()

    events = model.Events(db)
    try:
        event = events.get(event_name)
    except LookupError:
        return f"no such event {event_name}", 400 

    guest_table = model.Guests(db)

    try:
        guest_table.add_or_update(
            event_id=event.id,
            name=name,
            password=flask.request.form["password"],
            going=going,
            comment=comment,
        )
    except PermissionError:
        url = flask.url_for(
            "event",
            name=event_name,
            guestname=name,
            going=going,
            comment=comment,
            error="bad password",
        )
        return flask.redirect(url), 401

    url = flask.url_for(
        "event",
        name=event_name,
        guestname=name,
        going=going,
        comment=comment,
    )
    return flask.redirect(url)


if __name__ == "__main__":
    app.run(debug=True)
