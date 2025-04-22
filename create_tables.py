from database import Base, engine
from models import Claim

Base.metadata.create_all(bind=engine)
