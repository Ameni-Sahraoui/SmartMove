SET XACT_ABORT ON;

GO

IF OBJECT_ID(N'dbo.meta', N'U') IS NULL
BEGIN
CREATE TABLE dbo.[meta] ([key] NVARCHAR(160) PRIMARY KEY,[value] NVARCHAR(4000) NOT NULL);
END;
GO

IF OBJECT_ID(N'dbo.facilities', N'U') IS NULL
BEGIN
CREATE TABLE dbo.[facilities] (
 id INT PRIMARY KEY,[name] NVARCHAR(160) NOT NULL,[city] NVARCHAR(4000) NOT NULL,[province] NVARCHAR(4000) NOT NULL,
 latitude FLOAT(53) NOT NULL CHECK(latitude BETWEEN -90 AND 90),longitude FLOAT(53) NOT NULL CHECK(longitude BETWEEN -180 AND 180),
 [kind] NVARCHAR(160) NOT NULL CHECK(kind IN ('Hub','Terminal')),active INT NOT NULL DEFAULT 1 CHECK(active IN (0,1)));
END;
GO

IF OBJECT_ID(N'dbo.customers', N'U') IS NULL
BEGIN
CREATE TABLE dbo.[customers] (
 id INT PRIMARY KEY,[name] NVARCHAR(160) NOT NULL,[email] NVARCHAR(160) NOT NULL UNIQUE,[province] NVARCHAR(4000) NOT NULL,[loyalty_tier] NVARCHAR(160) NOT NULL DEFAULT 'Standard',[created_at] NVARCHAR(40) NOT NULL);
END;
GO

IF OBJECT_ID(N'dbo.employees', N'U') IS NULL
BEGIN
CREATE TABLE dbo.[employees] (
 id INT PRIMARY KEY,[code] NVARCHAR(160) NOT NULL UNIQUE,[name] NVARCHAR(160) NOT NULL,[job] NVARCHAR(160) NOT NULL,facility_id INT NOT NULL REFERENCES dbo.[facilities](id),active INT NOT NULL DEFAULT 1 CHECK(active IN (0,1)));
END;
GO

IF OBJECT_ID(N'dbo.users', N'U') IS NULL
BEGIN
CREATE TABLE dbo.[users] (
 id INT IDENTITY(1,1) PRIMARY KEY,[email] NVARCHAR(160) NOT NULL UNIQUE,[name] NVARCHAR(160) NOT NULL,[role] NVARCHAR(160) NOT NULL CHECK(role IN ('Admin','Manager','Driver','Engineer','Analyst','Customer')),
 [password_hash] NVARCHAR(4000) NOT NULL,[status] NVARCHAR(160) NOT NULL DEFAULT 'Active' CHECK(status IN ('Active','Pending','Disabled')),
 employee_id INT REFERENCES dbo.[employees](id),customer_id INT REFERENCES dbo.[customers](id),auth_version INT NOT NULL DEFAULT 1,
 failed_attempts INT NOT NULL DEFAULT 0,[locked_until] NVARCHAR(4000),[created_at] NVARCHAR(40) NOT NULL);
END;
GO

IF OBJECT_ID(N'dbo.permissions', N'U') IS NULL
BEGIN
CREATE TABLE dbo.[permissions] ([role] NVARCHAR(160) NOT NULL,[module] NVARCHAR(160) NOT NULL,[action] NVARCHAR(160) NOT NULL,PRIMARY KEY(role,module,action));
END;
GO

IF OBJECT_ID(N'dbo.sessions', N'U') IS NULL
BEGIN
CREATE TABLE dbo.[sessions] ([token_hash] NVARCHAR(64) PRIMARY KEY,user_id INT NOT NULL REFERENCES dbo.[users](id),[csrf_hash] NVARCHAR(64) NOT NULL,auth_version INT NOT NULL,[created_at] NVARCHAR(40) NOT NULL,[expires_at] NVARCHAR(40) NOT NULL,[ip] NVARCHAR(4000),[user_agent] NVARCHAR(4000));
END;
GO

IF OBJECT_ID(N'dbo.account_tokens', N'U') IS NULL
BEGIN
CREATE TABLE dbo.[account_tokens] ([token_hash] NVARCHAR(64) PRIMARY KEY,user_id INT NOT NULL REFERENCES dbo.[users](id),[kind] NVARCHAR(160) NOT NULL,[expires_at] NVARCHAR(40) NOT NULL,used INT NOT NULL DEFAULT 0);
END;
GO

IF OBJECT_ID(N'dbo.routes', N'U') IS NULL
BEGIN
CREATE TABLE dbo.[routes] (
 id INT PRIMARY KEY,[name] NVARCHAR(160) NOT NULL UNIQUE,origin_id INT NOT NULL REFERENCES dbo.[facilities](id),destination_id INT NOT NULL REFERENCES dbo.[facilities](id),
 distance_km FLOAT(53) NOT NULL CHECK(distance_km>0),duration_min INT NOT NULL CHECK(duration_min>0),fare_cents INT NOT NULL CHECK(fare_cents>=0),[status] NVARCHAR(160) NOT NULL DEFAULT 'Active' CHECK(status IN ('Active','Paused','Planned')),CHECK(origin_id<>destination_id));
END;
GO

IF OBJECT_ID(N'dbo.route_stops', N'U') IS NULL
BEGIN
CREATE TABLE dbo.[route_stops] (route_id INT NOT NULL REFERENCES dbo.[routes](id),facility_id INT NOT NULL REFERENCES dbo.[facilities](id),stop_order INT NOT NULL,PRIMARY KEY(route_id,stop_order));
END;
GO

IF OBJECT_ID(N'dbo.vehicles', N'U') IS NULL
BEGIN
CREATE TABLE dbo.[vehicles] (
 id INT PRIMARY KEY,[code] NVARCHAR(160) NOT NULL UNIQUE,[type] NVARCHAR(160) NOT NULL CHECK(type IN ('Coach','Transit Bus','Minibus','Paratransit')),
 capacity INT NOT NULL CHECK(capacity BETWEEN 1 AND 100),facility_id INT NOT NULL REFERENCES dbo.[facilities](id),
 [status] NVARCHAR(160) NOT NULL CHECK(status IN ('Active','Maintenance','Standby')),odometer_km FLOAT(53) NOT NULL CHECK(odometer_km>=0),
 [energy] NVARCHAR(4000) NOT NULL CHECK(energy IN ('Diesel','Electric','Hybrid')),[last_service] NVARCHAR(40) NOT NULL);
END;
GO

IF OBJECT_ID(N'dbo.schedules', N'U') IS NULL
BEGIN
CREATE TABLE dbo.[schedules] (id INT PRIMARY KEY,route_id INT NOT NULL REFERENCES dbo.[routes](id),departure_hour INT NOT NULL CHECK(departure_hour BETWEEN 0 AND 23),[days] NVARCHAR(4000) NOT NULL);
END;
GO

IF OBJECT_ID(N'dbo.trips', N'U') IS NULL
BEGIN
CREATE TABLE dbo.[trips] (
 id INT PRIMARY KEY,[code] NVARCHAR(160) NOT NULL UNIQUE,route_id INT NOT NULL REFERENCES dbo.[routes](id),vehicle_id INT NOT NULL REFERENCES dbo.[vehicles](id),driver_id INT NOT NULL REFERENCES dbo.[employees](id),
 [departure_utc] NVARCHAR(40) NOT NULL,[expected_arrival_utc] NVARCHAR(40) NOT NULL,[actual_arrival_utc] NVARCHAR(40),
 [status] NVARCHAR(160) NOT NULL CHECK(status IN ('Completed','Scheduled','In progress','Cancelled')),passenger_count INT NOT NULL DEFAULT 0 CHECK(passenger_count>=0),
 capacity INT NOT NULL CHECK(capacity>0),delay_min FLOAT(53) NOT NULL DEFAULT 0 CHECK(delay_min>=0),revenue_cents INT NOT NULL DEFAULT 0 CHECK(revenue_cents>=0),
 operating_cost_cents INT NOT NULL DEFAULT 0 CHECK(operating_cost_cents>=0),fuel_liters FLOAT(53) CHECK(fuel_liters>=0),
 weather_index FLOAT(53) NOT NULL,congestion_index FLOAT(53) NOT NULL,peak_hour INT NOT NULL, CHECK(passenger_count<=capacity),CHECK(expected_arrival_utc>departure_utc));
END;
GO

IF OBJECT_ID(N'dbo.reservations', N'U') IS NULL
BEGIN
CREATE TABLE dbo.[reservations] (
 id INT PRIMARY KEY,customer_id INT NOT NULL REFERENCES dbo.[customers](id),trip_id INT NOT NULL REFERENCES dbo.[trips](id),
 seats INT NOT NULL CHECK(seats BETWEEN 1 AND 8),price_cents INT NOT NULL CHECK(price_cents>=0),
 [status] NVARCHAR(160) NOT NULL CHECK(status IN ('Booked','Completed','Cancelled')),[created_at] NVARCHAR(40) NOT NULL);
END;
GO

IF OBJECT_ID(N'dbo.tickets', N'U') IS NULL
BEGIN
CREATE TABLE dbo.[tickets] (id INT PRIMARY KEY,reservation_id INT NOT NULL UNIQUE REFERENCES dbo.[reservations](id),[reference] NVARCHAR(160) NOT NULL UNIQUE,[status] NVARCHAR(160) NOT NULL);
END;
GO

IF OBJECT_ID(N'dbo.payments', N'U') IS NULL
BEGIN
CREATE TABLE dbo.[payments] (id INT PRIMARY KEY,reservation_id INT NOT NULL UNIQUE REFERENCES dbo.[reservations](id),amount_cents INT NOT NULL CHECK(amount_cents>=0),[status] NVARCHAR(160) NOT NULL CHECK(status IN ('Simulated paid','Simulated refund')),[created_at] NVARCHAR(40) NOT NULL);
END;
GO

IF OBJECT_ID(N'dbo.maintenance', N'U') IS NULL
BEGIN
CREATE TABLE dbo.[maintenance] (
 id INT PRIMARY KEY,vehicle_id INT NOT NULL REFERENCES dbo.[vehicles](id),engineer_id INT REFERENCES dbo.[employees](id),[opened_at] NVARCHAR(40) NOT NULL,[completed_at] NVARCHAR(40),
 [category] NVARCHAR(160) NOT NULL,[status] NVARCHAR(160) NOT NULL CHECK(status IN ('Open','In progress','Completed')),cost_cents INT NOT NULL DEFAULT 0 CHECK(cost_cents>=0),[summary] NVARCHAR(4000) NOT NULL);
END;
GO

IF OBJECT_ID(N'dbo.parts', N'U') IS NULL
BEGIN
CREATE TABLE dbo.[parts] (id INT PRIMARY KEY,[name] NVARCHAR(160) NOT NULL UNIQUE,quantity INT NOT NULL CHECK(quantity>=0),unit_cost_cents INT NOT NULL CHECK(unit_cost_cents>=0));
END;
GO

IF OBJECT_ID(N'dbo.work_order_parts', N'U') IS NULL
BEGIN
CREATE TABLE dbo.[work_order_parts] (maintenance_id INT NOT NULL REFERENCES dbo.[maintenance](id),part_id INT NOT NULL REFERENCES dbo.[parts](id),quantity INT NOT NULL CHECK(quantity>0),PRIMARY KEY(maintenance_id,part_id));
END;
GO

IF OBJECT_ID(N'dbo.telemetry', N'U') IS NULL
BEGIN
CREATE TABLE dbo.[telemetry] (
 id INT PRIMARY KEY,vehicle_id INT NOT NULL REFERENCES dbo.[vehicles](id),[captured_at] NVARCHAR(40) NOT NULL,engine_temp FLOAT(53),brake_wear FLOAT(53),battery_voltage FLOAT(53),
 km_since_service FLOAT(53),vibration FLOAT(53),fault_7d INT CHECK(fault_7d IN (0,1)),UNIQUE(vehicle_id,captured_at));
END;
GO

IF OBJECT_ID(N'dbo.incidents', N'U') IS NULL
BEGIN
CREATE TABLE dbo.[incidents] (
 id INT PRIMARY KEY,trip_id INT REFERENCES dbo.[trips](id),vehicle_id INT NOT NULL REFERENCES dbo.[vehicles](id),reported_by INT REFERENCES dbo.[users](id),
 [incident_time] NVARCHAR(40) NOT NULL,[location] NVARCHAR(4000) NOT NULL,[type] NVARCHAR(160) NOT NULL,[severity] NVARCHAR(4000) NOT NULL CHECK(severity IN ('Low','Medium','High')),
 [status] NVARCHAR(160) NOT NULL CHECK(status IN ('Active','Ongoing','Resolved')),[description] NVARCHAR(4000) NOT NULL);
END;
GO

IF OBJECT_ID(N'dbo.complaints', N'U') IS NULL
BEGIN
CREATE TABLE dbo.[complaints] (
 id INT PRIMARY KEY,customer_id INT NOT NULL REFERENCES dbo.[customers](id),trip_id INT REFERENCES dbo.[trips](id),[category] NVARCHAR(160) NOT NULL,[summary] NVARCHAR(4000) NOT NULL,
 [status] NVARCHAR(160) NOT NULL CHECK(status IN ('Open','Investigating','Resolved')),[created_at] NVARCHAR(40) NOT NULL);
END;
GO

IF OBJECT_ID(N'dbo.satisfaction', N'U') IS NULL
BEGIN
CREATE TABLE dbo.[satisfaction] (id INT PRIMARY KEY,customer_id INT NOT NULL REFERENCES dbo.[customers](id),trip_id INT NOT NULL REFERENCES dbo.[trips](id),score INT NOT NULL CHECK(score BETWEEN 1 AND 5),[survey_date] NVARCHAR(40) NOT NULL);
END;
GO

IF OBJECT_ID(N'dbo.notifications', N'U') IS NULL
BEGIN
CREATE TABLE dbo.[notifications] (id INT PRIMARY KEY,user_id INT REFERENCES dbo.[users](id),[role] NVARCHAR(160),[title] NVARCHAR(4000) NOT NULL,[body] NVARCHAR(4000) NOT NULL,[created_at] NVARCHAR(40) NOT NULL);
END;
GO

IF OBJECT_ID(N'dbo.notification_reads', N'U') IS NULL
BEGIN
CREATE TABLE dbo.[notification_reads] (notification_id INT NOT NULL REFERENCES dbo.[notifications](id),user_id INT NOT NULL REFERENCES dbo.[users](id),PRIMARY KEY(notification_id,user_id));
END;
GO

IF OBJECT_ID(N'dbo.documents', N'U') IS NULL
BEGIN
CREATE TABLE dbo.[documents] (id INT PRIMARY KEY,[title] NVARCHAR(4000) NOT NULL,[category] NVARCHAR(160) NOT NULL,[body] NVARCHAR(4000) NOT NULL,[updated_at] NVARCHAR(40) NOT NULL);
END;
GO

IF OBJECT_ID(N'dbo.audit_log', N'U') IS NULL
BEGIN
CREATE TABLE dbo.[audit_log] (
 id INT IDENTITY(1,1) PRIMARY KEY,user_id INT,[actor] NVARCHAR(4000) NOT NULL,[action] NVARCHAR(160) NOT NULL,[entity] NVARCHAR(4000) NOT NULL,[entity_id] NVARCHAR(4000),[before_json] NVARCHAR(4000),[after_json] NVARCHAR(4000),[created_at] NVARCHAR(40) NOT NULL,[ip] NVARCHAR(4000),[user_agent] NVARCHAR(4000));
END;
GO

IF OBJECT_ID(N'dbo.jobs', N'U') IS NULL
BEGIN
CREATE TABLE dbo.[jobs] (id INT IDENTITY(1,1) PRIMARY KEY,[kind] NVARCHAR(160) NOT NULL,[status] NVARCHAR(160) NOT NULL,[message] NVARCHAR(4000),[started_at] NVARCHAR(40) NOT NULL,[finished_at] NVARCHAR(40));
END;
GO

CREATE INDEX ix_trips_departure ON dbo.trips(departure_utc);

CREATE INDEX ix_trips_route_date ON dbo.trips(route_id,departure_utc);

CREATE INDEX ix_reservations_customer ON dbo.reservations(customer_id);

GO
