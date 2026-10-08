import os
import sqlite3
from pathlib import Path

TABLES=['meta','facilities','customers','employees','routes','route_stops','vehicles','schedules','trips','reservations','tickets','payments','maintenance','parts','work_order_parts','telemetry','incidents','complaints','satisfaction','documents']


def main():
    import pyodbc
    connection=os.environ.get('SMARTMOVE_SQLSERVER_CONNECTION')
    if not connection:raise SystemExit('Set SMARTMOVE_SQLSERVER_CONNECTION outside the source repository.')
    root=Path(__file__).resolve().parents[1]
    source=sqlite3.connect(root/'data/smartmove.db')
    target=pyodbc.connect(connection,autocommit=False)
    try:
        cursor=target.cursor()
        for table in TABLES:
            if cursor.execute(f'SELECT COUNT(*) FROM dbo.[{table}]').fetchone()[0]:
                raise RuntimeError(f'{table} is not empty; refusing to overwrite the database.')
        for table in TABLES:
            selected=source.execute(f'SELECT * FROM {table}')
            columns=[x[0] for x in selected.description]
            command=f'INSERT INTO dbo.[{table}] ('+','.join('['+c+']' for c in columns)+') VALUES ('+','.join('?' for _ in columns)+')'
            while batch:=selected.fetchmany(2000):
                if table=='incidents':
                    index=columns.index('reported_by');batch=[tuple(None if i==index else x for i,x in enumerate(r)) for r in batch]
                cursor.executemany(command,batch)
            print('Imported',table)
        target.commit()
    except Exception:
        target.rollback()
        raise
    finally:
        target.close();source.close()


if __name__=='__main__':main()
