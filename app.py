import os
from flask import Flask

app = Flask(__name__)
app.config.update(dict(
	DATABASE=os.path.join(app.root_path, 'db', 'fantasydrafts.db'),
	MAIL_SERVER='smtp.gmail.com',
	MAIL_PORT=465,
	MAIL_USE_SSL=True,
	MAIL_USERNAME='gmail_username',
	MAIL_PASSWORD='password',
))