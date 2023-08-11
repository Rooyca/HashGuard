from sqlalchemy import create_engine, Column, String, Integer, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os

DATABASE_URL = "sqlite:///" + os.getenv("DATABASE_URL", "file_integrity.db")

Base = declarative_base()
engine = create_engine(DATABASE_URL)

class File(Base):
    __tablename__ = 'files'

    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String)
    path = Column(String)
    hash = Column(String)
    old_hash = Column(String, default=None)
    last_modified = Column(DateTime)

def create_table():
    Base.metadata.create_all(engine)

def insert_file(filename, path, hash_value):
    Session = sessionmaker(bind=engine)
    session = Session()

    file_data = File(
        filename=filename,
        path=path,
        hash=hash_value,
        last_modified=datetime.now()
    )

    session.add(file_data)
    session.commit()
    session.close()

def update_file(filename, path, hash_value):
    Session = sessionmaker(bind=engine)
    session = Session()

    file_data = session.query(File).filter_by(filename=filename, path=path).first()
    if file_data:
        file_data.old_hash = file_data.hash
        file_data.hash = hash_value
        file_data.last_modified = datetime.now()

        session.commit()
    session.close()

def get_file(filename, path):
    Session = sessionmaker(bind=engine)
    session = Session()

    file_data = session.query(File).filter_by(filename=filename, path=path).first()

    session.close()
    return file_data

def get_files():
    Session = sessionmaker(bind=engine)
    session = Session()

    result = session.query(File).all()

    session.close()
    return result