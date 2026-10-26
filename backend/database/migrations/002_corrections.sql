ALTER TABLE movements ADD COLUMN revision INTEGER NOT NULL DEFAULT 1 CHECK(revision > 0);
ALTER TABLE movements ADD COLUMN modified_at TEXT;
ALTER TABLE movements ADD COLUMN deleted_at TEXT;
CREATE TRIGGER movement_metadata_no_update
BEFORE UPDATE OF created_at, request_key, request_hash ON movements
WHEN NEW.created_at IS NOT OLD.created_at OR NEW.request_key IS NOT OLD.request_key
 OR NEW.request_hash IS NOT OLD.request_hash
BEGIN SELECT RAISE(ABORT, 'Los metadatos originales son inmutables'); END;
CREATE TRIGGER native_no_physical_delete BEFORE DELETE ON movements WHEN OLD.origin='native'
BEGIN SELECT RAISE(ABORT, 'La clave de reintento debe conservarse'); END;
PRAGMA user_version=2;
