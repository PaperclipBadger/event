import argparse

import sqlite3


DROP = """
DROP TABLE IF EXISTS event;
DROP TABLE IF EXISTS guest;
DROP TABLE IF EXISTS token;
DROP TABLE IF EXISTS eventtoken;
DROP TABLE IF EXISTS guesttoken;
"""

SCRIPT = """
CREATE TABLE IF NOT EXISTS event (
  eventid INTEGER PRIMARY KEY AUTOINCREMENT,
  eventname TEXT UNIQUE NOT NULL,
  eventsalt TEXT NOT NULL,
  eventpasshash TEXT NOT NULL,
  eventtitle TEXT NOT NULL,
  eventstyle TEXT NOT NULL,
  eventdesc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS guest  (
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

CREATE TABLE IF NOT EXISTS token (
  tokenid INTEGER PRIMARY KEY AUTOINCREMENT,
  tokenname TEXT NOT NULL,
  tokenadmin BOOLEAN NOT NULL,
  tokenexpires TEXT NOT NULL,
  UNIQUE (tokenname)
);

CREATE TABLE IF NOT EXISTS eventtoken (
  eventtokenid INTEGER PRIMARY KEY AUTOINCREMENT,
  eventtokenevent INTEGER NOT NULL,
  eventtokentoken INTEGER NOT NULL,
  FOREIGN KEY (eventtokenevent) REFERENCES event(eventid),
  FOREIGN KEY (eventtokentoken) REFERENCES token(tokenid)
);

CREATE TABLE IF NOT EXISTS guesttoken (
  guesttokenid INTEGER PRIMARY KEY AUTOINCREMENT,
  guesttokenguest INTEGER NOT NULL,
  guesttokentoken INTEGER NOT NULL,
  FOREIGN KEY (guesttokenguest) REFERENCES guest(guestid),
  FOREIGN KEY (guesttokentoken) REFERENCES token(tokenid)
);
"""


parser = argparse.ArgumentParser()
parser.add_argument("--reset", action="store_true")
args = parser.parse_args()


db = sqlite3.connect(
    "events.db",
    detect_types=sqlite3.PARSE_DECLTYPES,
)

if args.reset:
  db.executescript(DROP)

db.executescript(SCRIPT)