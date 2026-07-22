import sys
import os

# Add the project root to sys.path so we can import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.app.core.security import get_password_hash, verify_password

def test():
    long_pass = "a" * 100
    try:
        # Hash the long password
        h = get_password_hash(long_pass)
        print("Successfully hashed a 100-character password!")
        
        # Verify it
        res = verify_password(long_pass, h)
        if res:
            print("Successfully verified the 100-character password!")
        else:
            print("Failed to verify the 100-character password!")
            sys.exit(1)
            
        # Verify a wrong one
        wrong_pass = "b" * 100
        res2 = verify_password(wrong_pass, h)
        if not res2:
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
