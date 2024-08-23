import os
from dotenv import load_dotenv
from sqlalchemy import create_engine

from sqlalchemy.orm import sessionmaker


load_dotenv()
mysql_uri = "mysql://{}:{}@{}/{}".format(os.environ['DB_USER'], os.environ['DB_PASSWORD'], os.environ['DB_HOST'], os.environ['DB_NAME'])
engine = create_engine(mysql_uri)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
