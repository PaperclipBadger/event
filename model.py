from typing import List
import dataclasses
import datetime
import functools
import hashlib
import secrets
import sqlite3


SALT = b"mmmmsalty"
TOKEN_LIFETIME_DAYS = 1


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


@dataclasses.dataclass
class Token:
    id: int
    name: str  # unique
    expires: str


def hash_password(salt: bytes, password: str):
    hash_ = hashlib.sha256()
    hash_.update(password.encode("utf-8"))
    hash_.update(salt)
    hash_.update(SALT)
    return hash_.hexdigest()


class AlreadyExistsError(Exception):
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
            raise LookupError(f"no guest with name {name} for event {event_id}")
        else:
            dict_ = {
                field.name: row["guest" + field.name]
                for field in dataclasses.fields(Guest)
            }
            return Guest(**dict_)
    
    @with_db
    def get_all(self, event_id: int) -> List[Guest]:
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
    def create(
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
            raise AlreadyExistsError(f"guest {name} of event {event_id} already exists")

    @with_db
    def approve_token(self, event_id: int, name: str, token_id: int, password: str) -> None:
        guest = self.get(event_id, name)

        passhash = hash_password(guest.salt, password)
        if passhash == guest.passhash:
            self.db.execute(
                "INSERT INTO guesttoken"
                " (guesttokentoken, guesttokenguest)"
                " VALUES (?, ?)",
                (token_id, guest.id),
            )
        else:
            raise PermissionError(f"bad password for guest {guest!r}")
    
    @with_db
    def check_token(self, event_id: int, name: str, token_id: int) -> bool:
        guest = self.get(event_id, name)

        cursor = self.db.execute(
            "SELECT * FROM guesttoken"
            " WHERE guesttokenguest = ? AND guesttokentoken = ?",
            (guest.id, token_id),
        )
        row = cursor.fetchone()
        return row is not None

    @with_db
    def update(
        self, event_id: int, name: str, going: bool, comment: str,
    ) -> None:
        # raise LookupError if no such guest
        self.get(event_id, name)

        self.db.execute(
            "UPDATE guest"
            " SET guestgoing = ?, guestcomment = ?"
            " WHERE guestname = ? AND guestevent = ?",
            (going, comment, name, event_id),
        )

    @with_db
    def delete(self, event_id: int, name: str) -> None:
        # raise LookupError if no such guest
        self.get(event_id, name)

        self.db.execute(
            "DELETE FROM guest"
            " WHERE guestname = ? AND guestevent = ?",
            (name, event_id),
        )


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
    def get_all(self) -> List[Event]:
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
    def create(
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
                "INSERT INTO event"
                " (eventname, eventsalt, eventpasshash, eventstyle, eventtitle, eventdesc)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (name, salt, passhash, style, title, desc),
            )
        else:
            raise AlreadyExistsError

    @with_db
    def approve_token(self, name: str, token_id: int, password: str) -> None:
        event = self.get(name)

        passhash = hash_password(event.salt, password)
        if passhash == event.passhash:
            self.db.execute(
                "INSERT INTO eventtoken"
                " (eventtokentoken, eventtokenevent)"
                " VALUES (?, ?)",
                (token_id, event.id),
            )
        else:
            raise PermissionError(f"bad password for event {event!r}")
    
    @with_db
    def check_token(self, name: str, token_id: int) -> bool:
        event = self.get(name)

        cursor = self.db.execute(
            "SELECT * FROM eventtoken"
            " WHERE eventtokenevent = ? AND eventtokentoken = ?",
            (event.id, token_id),
        )
        row = cursor.fetchone()
        return row is not None

    @with_db
    def update(
        self,
        name: str,
        style: str,
        title: str,
        desc: str,
    ) -> None:
        # raise LookupError if no such event
        event = self.get(name)

        self.db.execute(
            "UPDATE event"
            " SET eventtitle = ?, eventstyle = ?, eventdesc = ?"
            " WHERE eventname = ?",
            (title, style, desc, name),
        )

    @with_db
    def delete(self, name: str) -> None:
        # raise LookupError if no such event
        event = self.get(name)

        self.db.execute("DELETE FROM event WHERE eventname = ?", (name,))
        self.db.execute("DELETE FROM guest WHERE guestevent = ?", (event.id,))


@dataclasses.dataclass
class Tokens:
    db: sqlite3.Connection

    @with_db
    def get(self, name: str) -> Token:
        cursor = self.db.execute("SELECT * FROM token WHERE tokenname = ?", (name,))
        row = cursor.fetchone()

        if row is None:
            raise LookupError(f"no token with name {name}")

        else:
            return Token(
                id=row["tokenid"],
                name=row["tokenname"],
                expires=datetime.datetime.fromisoformat(row["tokenexpires"]),
            )

    @with_db
    def create(self, name: str) -> None:
        expires = datetime.datetime.now() + datetime.timedelta(days=TOKEN_LIFETIME_DAYS)

        try:
            self.get(name)
        except LookupError:
            self.db.execute(
                "INSERT INTO token"
                " (tokenname, tokenexpires)"
                " VALUES (?, ?)",
                (name, expires.isoformat()),
            )
        else:
            raise AlreadyExistsError
    
    @with_db
    def update(self, name: str) -> None:
        expires = datetime.datetime.now() + datetime.timedelta(days=1)

        self.get(name)

        self.db.execute(
            "UPDATE token"
            " SET tokenexpires = ?"
            " WHERE tokenname = ?",
            (expires.isoformat(), name),
        )

    @with_db
    def delete(self, name: str) -> None:
        # raise LookupError if there is no token
        token = self.get(name)

        self.db.execute("DELETE FROM token WHERE tokenid = ?", (token.id,))
        self.db.execute("DELETE FROM guesttoken WHERE guesttokentoken = ?", (token.id,))
        self.db.execute("DELETE FROM eventtoken WHERE eventtokentoken = ?", (token.id,))