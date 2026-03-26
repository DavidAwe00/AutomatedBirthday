from flask_login import LoginManager
from werkzeug.security import generate_password_hash, check_password_hash

login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.login_message = "Please log in to access Birthday Bot."
login_manager.login_message_category = "info"


def init_auth(app, db):
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        from models import User
        return User.query.get(int(user_id))


def create_admin(db, password: str):
    """Create or update the single admin user."""
    from models import User
    user = User.query.filter_by(username="admin").first()
    if not user:
        user = User(username="admin", password_hash=generate_password_hash(password))
        db.session.add(user)
    else:
        user.password_hash = generate_password_hash(password)
    db.session.commit()
    return user


def verify_password(password: str) -> bool:
    from models import User
    user = User.query.filter_by(username="admin").first()
    if not user:
        return False
    return check_password_hash(user.password_hash, password)


def admin_exists() -> bool:
    from models import User
    return User.query.filter_by(username="admin").first() is not None
