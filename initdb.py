import sqlite3


SCRIPT = """
DROP TABLE IF EXISTS guest;

CREATE TABLE guest (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT UNIQUE NOT NULL,
  going BOOLEAN NOT NULL,
  comment TEXT NOT NULL,
  salt TEXT NOT NULL,
  passhash TEXT NOT NULL
);
"""


if __name__ == "__main__":
    db = sqlite3.connect(
        "guests.db",
        detect_types=sqlite3.PARSE_DECLTYPES,
    )
    db.executescript(SCRIPT)
