import bcrypt
from functools import wraps
from flask import session, redirect, url_for, request


def hash_password(plain_password):
    return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password, hashed_password):
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "token" not in session:
            return redirect(url_for("login_page"))
        from python import db
        if not db.is_token_valid(session["token"]):
            session.clear()
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated_function
