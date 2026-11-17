import copy
from sqlalchemy import create_engine, select, event
from sqlalchemy.orm import sessionmaker
from screenshotlegal.infrastructure.db.models import MODELS

class Repository:
    def __init__(self, url):
        self.engine = create_engine(url, connect_args={'check_same_thread': False, 'timeout': 30})
        @event.listens_for(self.engine, 'connect')
        def configure(conn, _):
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('PRAGMA foreign_keys=ON')
        self.session = sessionmaker(self.engine, expire_on_commit=False)

    def get(self, table, id):
        with self.session() as s:
            row = s.get(MODELS[table], id)
            if row is None:
                raise KeyError(f'{table}: {id}')
            return copy.deepcopy(row.body)

    def list(self, table, case_id=None, run_id=None):
        model = MODELS[table]
        query = select(model)
        if case_id is not None:
            query = query.where(model.case_id == case_id)
        if run_id is not None:
            query = query.where(model.run_id == run_id)
        with self.session() as s:
            return [copy.deepcopy(x.body) for x in s.scalars(query)]

    def put(self, table, id, body, case_id='', run_id='', immutable=False):
        self.batch([(table, id, body, case_id, run_id, immutable)])

    def batch(self, records, *, connection=None):
        with self.session(bind=connection if connection is not None else self.engine) as s, s.begin():
            for table, id, body, case_id, run_id, immutable in records:
                model = MODELS[table]
                old = s.get(model, id)
                if old and immutable:
                    if old.body != body:
                        raise ValueError('Immutable result cannot be overwritten')
                    continue
                if old:
                    old.body = copy.deepcopy(body)
                else:
                    s.add(model(id=id, case_id=case_id, run_id=run_id, body=copy.deepcopy(body)))

    def optional(self, table, id):
        try:
            return self.get(table, id)
        except KeyError:
            return None

    def delete(self, table, id):
        with self.session.begin() as session:
            row = session.get(MODELS[table], id)
            if row is None:
                raise KeyError('Record not found')
            session.delete(row)
