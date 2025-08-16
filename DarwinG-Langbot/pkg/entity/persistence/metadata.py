import sqlalchemy

from .base import Base


initial_metadata = [
    {
        'key': 'database_version',
        'value': '0',
    },
]


class Metadata(Base):
    """Database metadata"""

    __tablename__ = 'metadata'

    key = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True)
    value = sqlalchemy.Column(sqlalchemy.String(255))
