from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

class User(UserMixin):
    def __init__(self, username, password_hash=None):
        self.id = username
        self.username = username
        self.password_hash = password_hash
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# 简单的用户存储（生产环境应使用数据库）
class UserStore:
    def __init__(self):
        self.users = {}
    
    def add_user(self, username, password):
        user = User(username)
        user.set_password(password)
        self.users[username] = user
        return user
    
    def get_user(self, username):
        return self.users.get(username)
    
    def user_exists(self, username):
        return username in self.users

user_store = UserStore()
