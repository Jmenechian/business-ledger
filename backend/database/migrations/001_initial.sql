CREATE TABLE clients (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 name TEXT NOT NULL CHECK(length(trim(name)) BETWEEN 1 AND 200),
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
) STRICT;

-- ANY retains SQLite numeric types from a future explicit import without coercion.
CREATE TABLE movements (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 client_id INTEGER NOT NULL REFERENCES clients(id),
 origin TEXT NOT NULL CHECK(origin IN ('imported', 'native')),
 kind TEXT NOT NULL CHECK(kind IN ('historical', 'delivery', 'payment')),
 description TEXT NOT NULL,
 quantity INTEGER,
 unit_price ANY,
 reference TEXT,
 business_date TEXT,
 created_at TEXT,
 debit ANY NOT NULL CHECK(typeof(debit) IN ('integer', 'real')),
 credit ANY NOT NULL CHECK(typeof(credit) IN ('integer', 'real')),
 balance ANY NOT NULL CHECK(typeof(balance) IN ('integer', 'real')),
 request_key TEXT,
 request_hash TEXT,
 UNIQUE(client_id, request_key),
 CHECK(origin = 'imported' OR (
  kind IN ('delivery', 'payment') AND created_at IS NOT NULL AND
  request_key IS NOT NULL AND length(request_key) BETWEEN 1 AND 128 AND
  request_hash IS NOT NULL AND length(request_hash) = 64 AND
  typeof(debit) = 'integer' AND debit BETWEEN 0 AND 9007199254740991 AND
  typeof(credit) = 'integer' AND credit BETWEEN 0 AND 9007199254740991 AND
  typeof(balance) = 'integer' AND balance BETWEEN -9007199254740991 AND 9007199254740991 AND
  length(trim(description)) BETWEEN 1 AND 500 AND
  ((kind = 'delivery' AND quantity > 0 AND quantity <= 9007199254740991 AND quantity IS NOT NULL AND
    typeof(unit_price) = 'integer' AND unit_price > 0 AND
    debit = quantity * unit_price AND credit = 0) OR
   (kind = 'payment' AND quantity IS NULL AND unit_price IS NULL AND debit = 0 AND credit > 0))
 ))
) STRICT;
CREATE INDEX movements_client_order ON movements(client_id, id);

CREATE TRIGGER imported_no_update BEFORE UPDATE ON movements
WHEN OLD.origin = 'imported'
BEGIN SELECT RAISE(ABORT, 'El historial importado no se puede modificar'); END;
CREATE TRIGGER imported_no_delete BEFORE DELETE ON movements
WHEN OLD.origin = 'imported'
BEGIN SELECT RAISE(ABORT, 'El historial importado no se puede eliminar'); END;
CREATE TRIGGER movement_identity_no_update BEFORE UPDATE OF origin, client_id, id ON movements
WHEN NEW.origin != OLD.origin OR NEW.client_id != OLD.client_id OR NEW.id != OLD.id
BEGIN SELECT RAISE(ABORT, 'La identidad del movimiento es inmutable'); END;
CREATE TRIGGER import_before_native BEFORE INSERT ON movements
WHEN NEW.origin = 'imported' AND EXISTS (
 SELECT 1 FROM movements WHERE client_id = NEW.client_id AND origin = 'native'
)
BEGIN SELECT RAISE(ABORT, 'No se puede importar historial después de registrar movimientos nuevos'); END;

PRAGMA application_id = 1112294471;
PRAGMA user_version = 1;
