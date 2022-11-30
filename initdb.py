import sqlite3


SCRIPT = """
DROP TABLE IF EXISTS event;
DROP TABLE IF EXISTS guest;

CREATE TABLE event (
  eventid INTEGER PRIMARY KEY AUTOINCREMENT,
  eventname TEXT UNIQUE NOT NULL,
  eventsalt TEXT NOT NULL,
  eventpasshash TEXT NOT NULL,
  eventtitle TEXT NOT NULL,
  eventstyle TEXT NOT NULL,
  eventdesc TEXT NOT NULL
);

CREATE TABLE guest (
  guestid INTEGER PRIMARY KEY AUTOINCREMENT,
  guestevent INTEGER NOT NULL,
  guestname TEXT NOT NULL,
  guestgoing BOOLEAN NOT NULL,
  guestcomment TEXT NOT NULL,
  guestsalt TEXT NOT NULL,
  guestpasshash TEXT NOT NULL,
  FOREIGN KEY (guestevent) REFERENCES event(eventid),
  UNIQUE (guestevent, guestname)
);
"""


if __name__ == "__main__":
    db = sqlite3.connect(
        "events.db",
        detect_types=sqlite3.PARSE_DECLTYPES,
    )
    db.executescript(SCRIPT)