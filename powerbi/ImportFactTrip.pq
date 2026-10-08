let
    Source = Csv.Document(File.Contents(SmartMoveFolder & "\exports\fact_trip.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Typed = Table.TransformColumnTypes(Headers, {{"id", Int64.Type}, {"route_id", Int64.Type}, {"vehicle_id", Int64.Type}, {"driver_id", Int64.Type}, {"date_key", Int64.Type}, {"time_key", Int64.Type}, {"passenger_count", Int64.Type}, {"capacity", Int64.Type}, {"revenue_cents", Int64.Type}, {"operating_cost_cents", Int64.Type}, {"delay_min", type number}, {"on_time", Int64.Type}, {"completed", Int64.Type}, {"profit_cad", type number}})
in
    Typed
