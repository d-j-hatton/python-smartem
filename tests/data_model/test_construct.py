from unittest.mock import MagicMock

from smartem.data_model import (
    Atlas,
    Exposure,
    ExposureInfo,
    FoilHole,
    GridSquare,
    Particle,
    ParticleInfo,
    ParticleSet,
    ParticleSetInfo,
    ParticleSetLinker,
    Project,
    Tile,
    construct,
)


def test_table_chain():
    """Test appending tables to each other for each of the possible chains"""
    # case 1: ExposureInfo
    return_value = construct.table_chain(ExposureInfo, Atlas)
    assert return_value == [ExposureInfo, Exposure, FoilHole, GridSquare, Tile, Atlas]

    # case 2: ParticleSetInfo
    return_value = construct.table_chain(ParticleSetInfo, Atlas)
    assert return_value == [ParticleSetInfo, ParticleSet, Project, Atlas]

    # case 3: ParticleInfo
    return_value = construct.table_chain(ParticleInfo, Atlas)
    assert return_value == [
        ParticleInfo,
        Particle,
        Exposure,
        FoilHole,
        GridSquare,
        Tile,
        Atlas,
    ]

    # case 4: ParticleSetLinker, which has more than one key so should raise ValueError
    try:
        construct.table_chain(ParticleSetLinker, Atlas)
        assert False
    except ValueError:
        assert True


def test_linear_joins():
    """Test joining tables together"""
    session = MagicMock()

    return_value = construct.linear_joins(
        session,
        [ParticleInfo, Particle, Exposure, FoilHole, GridSquare, Tile],
        primary_filter=0,
    )

    # assert the tables are joined, as query loops over join for each table
    assert return_value
    assert len(session.mock_calls) == 8
    session.query.assert_called_once()
    session.query().join.assert_called_once()
    session.query().join().join().join().join().join().filter.assert_called_once()
