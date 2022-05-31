from typing import Any, Dict, List, Optional, Type

from sqlalchemy.orm import Query, Session

from smartem.data_model import Base, _tables

_tables_dict: Dict[str, Type[Base]] = {tab.__tablename__: tab for tab in _tables}  # type: ignore


def _foreign_key(table: Type[Base]) -> str:
    keys: List[str] = []
    for c in table.__table__.columns:  # type: ignore
        keys.extend(fk.column.name for fk in c.foreign_keys)
    if len(keys) > 1:
        raise ValueError(f"Table {table} has more than one foreign key")
    return keys[0]


def _primary_keys(table: Type[Base]) -> List[str]:
    return [c.name for c in table.__table__.columns if c.primary_key]  # type: ignore


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


def linear_joins(
    session: Session,
    tables: List[Type[Base]],
    primary_filter: Any = None,
    skip: Optional[List[Type[Base]]] = None,
) -> Query:
    if not skip:
        skip = []
    query = session.query(*tables)
    for i, tab in enumerate(tables[:-1]):
        if tab in skip or tables[i + 1] in skip:
            continue
        try:
            query = query.join(
                tables[i + 1],
                getattr(tables[i + 1], _foreign_key(tab))
                == getattr(tab, _foreign_key(tab)),
            )
        except IndexError:
            pass
    if primary_filter is not None:
        try:
            # primary_key = _primary_keys(tables[-1])[0]
            primary_key = _foreign_key(tables[-1])
        except IndexError:
            return query
        query = query.filter(getattr(tables[-1], primary_key) == primary_filter)
    return query
