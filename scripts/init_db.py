from app.db.engine import get_engine
from app.db.schema import metadata

def main():
    engine = get_engine()
    metadata.drop_all(engine)
    metadata.create_all(engine)
    print("DB schema created.")

if __name__ == "__main__":
    main()
