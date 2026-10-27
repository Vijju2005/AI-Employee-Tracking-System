"""
EBT System — Flask Extensions
Centralized extension instances to avoid circular imports.
"""

from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_mail import Mail

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()
mail = Mail()

login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to access this page."
login_manager.login_message_category = "warning"
