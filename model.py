import dataclasses
import functools
import hashlib
import secrets
import sqlite3


SALT = b"mmmmsalty"


@dataclasses.dataclass
class Event:
    id: int
    name: str  # unique, used as url
    title: str  # used as page title
    style: str  # css
    desc: str  # markdown, used as page body
    salt: bytes
    passhash: str


@dataclasses.dataclass
class Guest:
    id: int
    event: int  # id of an event
    name: str  # unique given event
    going: bool
    comment: str
    salt: bytes
    passhash: str


def hash_password(salt: bytes, password: str):
    hash_ = hashlib.sha256()
    hash_.update(password.encode("utf-8"))
    hash_.update(salt)
    hash_.update(SALT)
    return hash_.hexdigest()


class PermissionError(Exception):
    """Raised on password check failure."""
    pass


class EventAlreadyExistsError(Exception):
    pass


def with_db(method):
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        with self.db:
            return method(self, *args, **kwargs)

    return wrapper


@dataclasses.dataclass
class Guests:
    db: sqlite3.Connection

    @with_db
    def get(self, event_id: int, name: str) -> Guest:
        cursor = self.db.execute(
            "SELECT * FROM guest WHERE guestname = ? AND guestevent = ?",
            (name, event_id),
        )
        row = cursor.fetchone()

        if row is None:
            raise LookupError(f"no guest with name {name}")
        else:
            dict_ = {
                field.name: row["guest" + field.name]
                for field in dataclasses.fields(Guest)
            }
            return Guest(**dict_)
    
    @with_db
    def get_all(self, event_id: int) -> list[Guest]:
        cursor = self.db.execute(
            "SELECT * FROM guest WHERE guestevent = ?",
            (event_id,),
        )
        rows = cursor.fetchall()

        guests = []

        for row in rows:
            dict_ = {
                field.name: row["guest" + field.name]
                for field in dataclasses.fields(Guest)
            }
            guests.append(Guest(**dict_))
        
        return guests

    @with_db
    def add_or_update(
        self, event_id: int, name: str, password: str, going: bool, comment: str,
    ) -> None:
        try:
            guest = self.get(event_id, name)
        except LookupError:
            salt = secrets.token_bytes(4)
            passhash = hash_password(salt, password)
            self.db.execute(
                "INSERT INTO guest"
                " (guestname, guestevent, guestgoing, guestcomment, guestsalt, guestpasshash)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (name, event_id, going, comment, salt, passhash),
            )
        else:
            passhash = hash_password(guest.salt, password)
            if passhash == guest.passhash:
                self.db.execute(
                    "UPDATE guest"
                    " SET guestgoing = ?, guestcomment = ?"
                    " WHERE guestname = ? AND guestevent = ?",
                    (going, comment, name, event_id),
                )
            else:
                raise PermissionError(f"bad password for guest {name!r} of event {event_id!r}")


@dataclasses.dataclass
class Events:
    db: sqlite3.Connection

    @with_db
    def get(self, name: str) -> Event:
        cursor = self.db.execute("SELECT * FROM event WHERE eventname = ?", (name,))
        row = cursor.fetchone()

        if row is None:
            raise LookupError(f"no event with name {name}")

        else:
            dict_ = {
                field.name: row["event" + field.name]
                for field in dataclasses.fields(Event)
            }
            return Event(**dict_)
    
    @with_db
    def get_all(self) -> list[Event]:
        cursor = self.db.execute("SELECT * FROM event")
        rows = cursor.fetchall()

        events = []

        for row in rows:
            dict_ = {
                field.name: row["event" + field.name]
                for field in dataclasses.fields(Event)
            }
            events.append(Event(**dict_))
        
        return events
    
    @with_db
    def add(
        self,
        name: str,
        password: str,
        style: str,
        title: str,
        desc: str,
    ) -> None:
        try:
            self.get(name)
        except LookupError:
            salt = secrets.token_bytes(4)
            passhash = hash_password(salt, password)
            self.db.execute(
                "INSERT INTO event "
                " (eventname, eventsalt, eventpasshash, eventstyle, eventtitle, eventdesc)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (name, salt, passhash, style, title, desc),
            )
        else:
            raise EventAlreadyExistsError
    
    @with_db
    def update(
        self,
        name: str,
        password: str,
        style: str,
        title: str,
        desc: str,
    ) -> None:
        event = self.get(name)

        passhash = hash_password(event.salt, password)
        if passhash == event.passhash:
            self.db.execute(
                "UPDATE event "
                " SET eventtitle = ?, eventstyle = ?, eventdesc = ?"
                " WHERE eventname = ?",
                (title, style, desc, name),
            )
        else:
            raise PermissionError(f"bad password for event {event!r}")