class User:
    def __init__(self, email, name, password_hash, fav_team, user_id):
        self.email = email
        self.name = name
        self.password_hash = password_hash
        self.fav_team = fav_team
        self.user_id = user_id
    
    def to_dict(self):
        return {
            "email": self.email,
            "name": self.name,
            "password_hash": self.password_hash,
            "fav_team": self.fav_team,
            "user_id": self.user_id
        }
        