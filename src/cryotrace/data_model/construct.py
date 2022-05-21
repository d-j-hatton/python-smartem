from typing import Dict, List, Optional, Type

from sqlalchemy.orm import Query, Session

from cryotrace.data_model import Base, _tables

_tables_dict: Dict[str, Type[Base]] = {tab.__tablename__: tab for tab in _tables}  # type: ignore


def _foreign_key(table: Type[Base]) -> str:
    keys: List[str] = []
    for c in table.__table__.columns:  # type: ignore
        keys.extend(fk.column.name for fk in c.foreign_keys)
    if len(keys) > 1:
        raise ValueError(f"Table {table} has more than one foreign key")
    return keys[0]


def _analyse_table(start: Type[Base]) -> Optional[Type[Base]]:
    next_tables: List[Type[Base]] = []
    for c in start.__table__.columns:  # type: ignore
        next_tables.extend(_tables_dict[fk.column.table.name] for fk in c.foreign_keys)
    if len(next_tables) > 1:
        raise ValueError(
            f"Table {start} has more than one foreign key, it cannot be followed"
        )
    if not next_tables:
        return None
    return next_tables[0]


def table_chain(start: Type[Base], end: Type[Base]) -> List[Type[Base]]:
    tables = [start]
    current_table = start
    while current_table != end:
        new_table = _analyse_table(current_table)
        if new_table is None:
            break
        current_table = new_table
        tables.append(current_table)
    return tables


def linear_joins(tables: List[Type[Base]], session: Session) -> Query:
    query = session.query(*tables)
    for i, tab in enumerate(tables[:-1]):
        query = query.join(
            tab,
            getattr(tab, _foreign_key(tab))
            == getattr(tables[i + 1], _foreign_key(tables[i + 1])),
        )
    return query
