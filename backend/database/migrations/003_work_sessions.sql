CREATE TABLE work_sessions (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 kind TEXT NOT NULL CHECK(kind IN ('group','individual','legacy')),
 request_key TEXT NOT NULL UNIQUE,
 started_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
 ended_at TEXT,
 summary_json TEXT
) STRICT;
CREATE UNIQUE INDEX one_active_work_group ON work_sessions((1))
 WHERE kind='group' AND ended_at IS NULL;
INSERT INTO work_sessions(kind,request_key,ended_at)
 VALUES ('legacy','schema-v2-history',strftime('%Y-%m-%dT%H:%M:%fZ','now'));
ALTER TABLE movements ADD COLUMN work_session_id INTEGER REFERENCES work_sessions(id);
UPDATE movements SET work_session_id=(SELECT id FROM work_sessions WHERE kind='legacy')
 WHERE origin='native';
CREATE TRIGGER native_requires_work_session BEFORE INSERT ON movements
WHEN NEW.origin='native' AND NEW.work_session_id IS NULL
BEGIN SELECT RAISE(ABORT,'El movimiento debe asociarse a una sesión'); END;
CREATE TRIGGER movement_work_session_immutable BEFORE UPDATE OF work_session_id ON movements
WHEN NEW.work_session_id IS NOT OLD.work_session_id
BEGIN SELECT RAISE(ABORT,'La sesión original es inmutable'); END;
CREATE TABLE work_events (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 session_id INTEGER NOT NULL REFERENCES work_sessions(id),
 movement_id INTEGER NOT NULL REFERENCES movements(id),
 client_id INTEGER NOT NULL REFERENCES clients(id),
 client_name TEXT NOT NULL,
 action TEXT NOT NULL CHECK(action IN ('create','edit','delete')),
 recorded_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
 before_json TEXT,
 after_json TEXT,
 affected_before_json TEXT NOT NULL,
 affected_after_json TEXT NOT NULL,
 delta_debit INTEGER NOT NULL,
 delta_credit INTEGER NOT NULL
) STRICT;
CREATE INDEX work_events_session ON work_events(session_id,id);
CREATE TRIGGER work_events_no_update BEFORE UPDATE ON work_events
BEGIN SELECT RAISE(ABORT,'El registro de actividad es inmutable'); END;
CREATE TRIGGER work_events_no_delete BEFORE DELETE ON work_events
BEGIN SELECT RAISE(ABORT,'El registro de actividad es inmutable'); END;
CREATE TRIGGER work_events_open_session BEFORE INSERT ON work_events
WHEN (SELECT ended_at FROM work_sessions WHERE id=NEW.session_id) IS NOT NULL
BEGIN SELECT RAISE(ABORT,'La sesión ya fue finalizada'); END;
CREATE TRIGGER work_sessions_closed_immutable BEFORE UPDATE ON work_sessions
WHEN OLD.ended_at IS NOT NULL
BEGIN SELECT RAISE(ABORT,'El resumen finalizado es inmutable'); END;
CREATE TRIGGER work_sessions_identity_immutable
BEFORE UPDATE OF id,kind,request_key,started_at ON work_sessions
BEGIN SELECT RAISE(ABORT,'La identidad de la sesión es inmutable'); END;
CREATE TRIGGER work_sessions_no_delete BEFORE DELETE ON work_sessions
BEGIN SELECT RAISE(ABORT,'El historial de sesiones se conserva'); END;
PRAGMA user_version=3;
