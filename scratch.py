from sqlalchemy import create_engine, text
import os
import dotenv

dotenv.load_dotenv()
engine = create_engine(os.getenv('DATABASE_URL'))
with engine.connect() as conn:
    res = conn.execute(text("SELECT unnest(enum_range(NULL::skilllevel));")).fetchall()
    print("VALID ENUMS ARE:", res)
