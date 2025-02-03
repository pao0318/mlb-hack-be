from database import Database
from utils import Utils, ValidationError
from models import User

class AuthService:
    def __init__(self):
        self.db = Database()
        self.db.create_collection()
    def signup(self, email, name, password, fav_team):
        """Register a new user"""
        try:
            # Validate input
            Utils.validate_email(email)
            # Check if user exists
            if self.db.find_user_by_email(email):
                return {"success": False, "message": "Email already registered"}
            # Create new user
            user = User(
                email=email,
                name=name,
                password_hash=Utils.hash_password(password),
                fav_team=fav_team,
                user_id=Utils.generate_uuid()
            )
            
            # Save user
            if self.db.insert_user(user.to_dict()):
                return {
                    "success": True,
                    "message": "User registered successfully",
                    "user_id": user.user_id
                }
            return {"success": False, "message": "Error during registration"}
            
        except ValidationError as e:
            return {"success": False, "message": str(e)}
        except Exception as e:
            return {"success": False, "message": f"Unexpected error: {str(e)}"}
    
    def login(self, email, password):
        """Authenticate a user"""
        try:
            Utils.validate_email(email)
            
            user_data = self.db.find_user_by_email(email)
            if not user_data:
                return {"success": False, "message": "User not found"}
            
            if user_data["password_hash"] == Utils.hash_password(password):
                return {
                    "success": True,
                    "message": "Login successful",
                    "user": {
                        "user_id": user_data["user_id"],
                        "email": user_data["email"],
                        "name": user_data["name"],
                        "fav_team": user_data["fav_team"]
                    }
                }
            return {"success": False, "message": "Invalid password"}
            
        except ValidationError as e:
            return {"success": False, "message": str(e)}
        except Exception as e:
            return {"success": False, "message": f"Unexpected error: {str(e)}"}

    
