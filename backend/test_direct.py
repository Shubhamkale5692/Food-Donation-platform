import traceback

def run():
    try:
        from app.interfaces.auth_router import login
        from app.domain.schemas import LoginRequest
        from app.infrastructure.database import SessionLocal
        db = SessionLocal()
        req = LoginRequest(email="nonexistent@example.com", password="pass")
        res = login(credentials=req, db=db)
        print("RESULT:")
        print(res)
    except Exception as e:
        with open("trace.txt", "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())

if __name__ == "__main__":
    run()
