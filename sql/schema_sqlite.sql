PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS facilities (
 id INTEGER PRIMARY KEY,name TEXT NOT NULL,city TEXT NOT NULL,province TEXT NOT NULL,
 latitude REAL NOT NULL CHECK(latitude BETWEEN -90 AND 90),longitude REAL NOT NULL CHECK(longitude BETWEEN -180 AND 180),
 kind TEXT NOT NULL CHECK(kind IN ('Hub','Terminal')),active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)));
CREATE TABLE IF NOT EXISTS customers (
 id INTEGER PRIMARY KEY,name TEXT NOT NULL,email TEXT NOT NULL UNIQUE,province TEXT NOT NULL,loyalty_tier TEXT NOT NULL DEFAULT 'Standard',created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS employees (
 id INTEGER PRIMARY KEY,code TEXT NOT NULL UNIQUE,name TEXT NOT NULL,job TEXT NOT NULL,facility_id INTEGER NOT NULL REFERENCES facilities(id),active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)));
CREATE TABLE IF NOT EXISTS users (
 id INTEGER PRIMARY KEY AUTOINCREMENT,email TEXT NOT NULL UNIQUE,name TEXT NOT NULL,role TEXT NOT NULL CHECK(role IN ('Admin','Manager','Driver','Engineer','Analyst','Customer')),
 password_hash TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'Active' CHECK(status IN ('Active','Pending','Disabled')),
 employee_id INTEGER REFERENCES employees(id),customer_id INTEGER REFERENCES customers(id),auth_version INTEGER NOT NULL DEFAULT 1,
 failed_attempts INTEGER NOT NULL DEFAULT 0,locked_until TEXT,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS permissions (role TEXT NOT NULL,module TEXT NOT NULL,action TEXT NOT NULL,PRIMARY KEY(role,module,action));
CREATE TABLE IF NOT EXISTS sessions (token_hash TEXT PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,csrf_hash TEXT NOT NULL,auth_version INTEGER NOT NULL,created_at TEXT NOT NULL,expires_at TEXT NOT NULL,ip TEXT,user_agent TEXT);
CREATE TABLE IF NOT EXISTS account_tokens (token_hash TEXT PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,kind TEXT NOT NULL,expires_at TEXT NOT NULL,used INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS routes (
 id INTEGER PRIMARY KEY,name TEXT NOT NULL UNIQUE,origin_id INTEGER NOT NULL REFERENCES facilities(id),destination_id INTEGER NOT NULL REFERENCES facilities(id),
 distance_km REAL NOT NULL CHECK(distance_km>0),duration_min INTEGER NOT NULL CHECK(duration_min>0),fare_cents INTEGER NOT NULL CHECK(fare_cents>=0),status TEXT NOT NULL DEFAULT 'Active' CHECK(status IN ('Active','Paused','Planned')),CHECK(origin_id<>destination_id));
CREATE TABLE IF NOT EXISTS route_stops (route_id INTEGER NOT NULL REFERENCES routes(id),facility_id INTEGER NOT NULL REFERENCES facilities(id),stop_order INTEGER NOT NULL,PRIMARY KEY(route_id,stop_order));
CREATE TABLE IF NOT EXISTS vehicles (
 id INTEGER PRIMARY KEY,code TEXT NOT NULL UNIQUE,type TEXT NOT NULL CHECK(type IN ('Coach','Transit Bus','Minibus','Paratransit')),
 capacity INTEGER NOT NULL CHECK(capacity BETWEEN 1 AND 100),facility_id INTEGER NOT NULL REFERENCES facilities(id),
 status TEXT NOT NULL CHECK(status IN ('Active','Maintenance','Standby')),odometer_km REAL NOT NULL CHECK(odometer_km>=0),
 energy TEXT NOT NULL CHECK(energy IN ('Diesel','Electric','Hybrid')),last_service TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS schedules (id INTEGER PRIMARY KEY,route_id INTEGER NOT NULL REFERENCES routes(id),departure_hour INTEGER NOT NULL CHECK(departure_hour BETWEEN 0 AND 23),days TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS trips (
 id INTEGER PRIMARY KEY,code TEXT NOT NULL UNIQUE,route_id INTEGER NOT NULL REFERENCES routes(id),vehicle_id INTEGER NOT NULL REFERENCES vehicles(id),driver_id INTEGER NOT NULL REFERENCES employees(id),
 departure_utc TEXT NOT NULL,expected_arrival_utc TEXT NOT NULL,actual_arrival_utc TEXT,
 status TEXT NOT NULL CHECK(status IN ('Completed','Scheduled','In progress','Cancelled')),passenger_count INTEGER NOT NULL DEFAULT 0 CHECK(passenger_count>=0),
 capacity INTEGER NOT NULL CHECK(capacity>0),delay_min REAL NOT NULL DEFAULT 0 CHECK(delay_min>=0),revenue_cents INTEGER NOT NULL DEFAULT 0 CHECK(revenue_cents>=0),
 operating_cost_cents INTEGER NOT NULL DEFAULT 0 CHECK(operating_cost_cents>=0),fuel_liters REAL CHECK(fuel_liters>=0),
 weather_index REAL NOT NULL,congestion_index REAL NOT NULL,peak_hour INTEGER NOT NULL, CHECK(passenger_count<=capacity),CHECK(expected_arrival_utc>departure_utc));
CREATE TABLE IF NOT EXISTS reservations (
 id INTEGER PRIMARY KEY,customer_id INTEGER NOT NULL REFERENCES customers(id),trip_id INTEGER NOT NULL REFERENCES trips(id),
 seats INTEGER NOT NULL CHECK(seats BETWEEN 1 AND 8),price_cents INTEGER NOT NULL CHECK(price_cents>=0),
 status TEXT NOT NULL CHECK(status IN ('Booked','Completed','Cancelled')),created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS tickets (id INTEGER PRIMARY KEY,reservation_id INTEGER NOT NULL UNIQUE REFERENCES reservations(id),reference TEXT NOT NULL UNIQUE,status TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS payments (id INTEGER PRIMARY KEY,reservation_id INTEGER NOT NULL UNIQUE REFERENCES reservations(id),amount_cents INTEGER NOT NULL CHECK(amount_cents>=0),status TEXT NOT NULL CHECK(status IN ('Simulated paid','Simulated refund')),created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS maintenance (
 id INTEGER PRIMARY KEY,vehicle_id INTEGER NOT NULL REFERENCES vehicles(id),engineer_id INTEGER REFERENCES employees(id),opened_at TEXT NOT NULL,completed_at TEXT,
 category TEXT NOT NULL,status TEXT NOT NULL CHECK(status IN ('Open','In progress','Completed')),cost_cents INTEGER NOT NULL DEFAULT 0 CHECK(cost_cents>=0),summary TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS parts (id INTEGER PRIMARY KEY,name TEXT NOT NULL UNIQUE,quantity INTEGER NOT NULL CHECK(quantity>=0),unit_cost_cents INTEGER NOT NULL CHECK(unit_cost_cents>=0));
CREATE TABLE IF NOT EXISTS work_order_parts (maintenance_id INTEGER NOT NULL REFERENCES maintenance(id),part_id INTEGER NOT NULL REFERENCES parts(id),quantity INTEGER NOT NULL CHECK(quantity>0),PRIMARY KEY(maintenance_id,part_id));
CREATE TABLE IF NOT EXISTS telemetry (
 id INTEGER PRIMARY KEY,vehicle_id INTEGER NOT NULL REFERENCES vehicles(id),captured_at TEXT NOT NULL,engine_temp REAL,brake_wear REAL,battery_voltage REAL,
 km_since_service REAL,vibration REAL,fault_7d INTEGER CHECK(fault_7d IN (0,1)),UNIQUE(vehicle_id,captured_at));
CREATE TABLE IF NOT EXISTS incidents (
 id INTEGER PRIMARY KEY,trip_id INTEGER REFERENCES trips(id),vehicle_id INTEGER NOT NULL REFERENCES vehicles(id),reported_by INTEGER REFERENCES users(id),
 incident_time TEXT NOT NULL,location TEXT NOT NULL,type TEXT NOT NULL,severity TEXT NOT NULL CHECK(severity IN ('Low','Medium','High')),
 status TEXT NOT NULL CHECK(status IN ('Active','Ongoing','Resolved')),description TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS complaints (
 id INTEGER PRIMARY KEY,customer_id INTEGER NOT NULL REFERENCES customers(id),trip_id INTEGER REFERENCES trips(id),category TEXT NOT NULL,summary TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('Open','Investigating','Resolved')),created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS satisfaction (id INTEGER PRIMARY KEY,customer_id INTEGER NOT NULL REFERENCES customers(id),trip_id INTEGER NOT NULL REFERENCES trips(id),score INTEGER NOT NULL CHECK(score BETWEEN 1 AND 5),survey_date TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS notifications (id INTEGER PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,role TEXT,title TEXT NOT NULL,body TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS notification_reads (notification_id INTEGER NOT NULL REFERENCES notifications(id),user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,PRIMARY KEY(notification_id,user_id));
CREATE TABLE IF NOT EXISTS documents (id INTEGER PRIMARY KEY,title TEXT NOT NULL,category TEXT NOT NULL,body TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audit_log (
 id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,actor TEXT NOT NULL,action TEXT NOT NULL,entity TEXT NOT NULL,entity_id TEXT,before_json TEXT,after_json TEXT,created_at TEXT NOT NULL,ip TEXT,user_agent TEXT);
CREATE TABLE IF NOT EXISTS jobs (id INTEGER PRIMARY KEY AUTOINCREMENT,kind TEXT NOT NULL,status TEXT NOT NULL,message TEXT,started_at TEXT NOT NULL,finished_at TEXT);
CREATE INDEX IF NOT EXISTS ix_trips_departure ON trips(departure_utc);
CREATE INDEX IF NOT EXISTS ix_trips_route_date ON trips(route_id,departure_utc);
CREATE INDEX IF NOT EXISTS ix_trips_driver ON trips(driver_id,departure_utc);
CREATE INDEX IF NOT EXISTS ix_reservations_trip ON reservations(trip_id,status);
CREATE INDEX IF NOT EXISTS ix_reservations_customer ON reservations(customer_id);
CREATE INDEX IF NOT EXISTS ix_telemetry_time ON telemetry(captured_at);
CREATE INDEX IF NOT EXISTS ix_sessions_user ON sessions(user_id);
CREATE INDEX IF NOT EXISTS ix_audit_time ON audit_log(created_at);
