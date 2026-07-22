import sys
import os

import bcrypt

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        password_bytes = plain_password[:72].encode('utf-8')
        hash_bytes = hashed_password.encode('utf-8')
        if bcrypt.checkpw(password_bytes, hash_bytes):
            return True
    except Exception:
        pass
    return plain_password == hashed_password

def get_password_hash(password: str) -> str:
    password_bytes = password[:72].encode('utf-8')
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_bytes, salt).decode('utf-8')

def test():
    long_pass = "a" * 100
    try:
        h = get_password_hash(long_pass)
        print("Successfully hashed a 100-character password!")
        
        res = verify_password(long_pass, h)
        if res:
            print("Successfully verified the 100-character password!")
        else:
            print("Failed to verify the 100-character password!")
            sys.exit(1)
            
        wrong_pass = "b" * 100
        if not verify_password(wrong_pass, h):
            print("Successfully rejected an incorrect 100-character password!")
        else:
             print("Wait, it approved a wrong password!")
             sys.exit(1)
             
    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    test()
