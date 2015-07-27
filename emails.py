from flask import render_template
from flask.ext.mail import Mail, Message
from threading import Thread
from app import app

def async(f):
	def wrapper(*args, **kwargs):
		thr = Thread(target=f, args=args, kwargs=kwargs)
		thr.start()
	return wrapper

@async
def send_async_email(app, mail, msg):
	with app.app_context():
	    mail.send(msg)

class Email(object):

	def __init__(self):
		self.mail = Mail(app)

	def send_email(self, subject, recipient, text_body, html_body):
		msg = Message(subject, sender='fantasyfooty@andypymont.co.uk', recipients=recipient.split(";"))
		msg.body = text_body
		msg.html = html_body
		send_async_email(app, self.mail, msg)

	def email(self, email_type, parameters):
		f = {
			'startdraft': self.email_draft_start,
			'enddraft': self.email_draft_finish,
			'autopick': self.email_autopick_done,
			'next': self.email_your_pick,
			'upcoming': self.email_upcoming_pick
		}[email_type]

		return f(**parameters)

	def email_draft_start(self, draft, teams):
		for team in teams:
			self.send_email(subject="Fantasy Draft '%s' has begun!" % draft['name'],
							recipient=team['email'],
							text_body=render_template("email_draftstart.txt", draft=draft, team=team),
							html_body=render_template("email_draftstart.html", draft=draft, team=team))

	def email_autopick_done(self, draft, team, pick_description):
		self.send_email(subject="Fantasy Draft '%s': Your pick was auto-completed" % draft['name'],
					    recipient=team['email'],
					    text_body=render_template("email_draftauto.txt", draft=draft, team=team, pick_description=pick_description),
					    html_body=render_template("email_draftauto.html", draft=draft, team=team, pick_description=pick_description))

	def email_your_pick(self, draft, team):
		self.send_email(subject="Fantasy Draft '%s': Time for your pick!" % draft['name'],
						recipient=team['email'],
						text_body=render_template("email_draftnext.txt", draft=draft, team=team),
						html_body=render_template("email_draftnext.html", draft=draft, team=team))

	def email_upcoming_pick(self, draft, team, current_pick, conditional_pick_done):
		self.send_email(subject="Fantasy Draft '%s': Your pick is approaching" % draft['name'],
						recipient=team['email'],
						text_body=render_template("email_draftupcoming.txt", draft=draft, team=team, current_pick=current_pick,
												  conditional_pick_done=conditional_pick_done),
						html_body=render_template("email_draftupcoming.html", draft=draft, team=team, current_pick=current_pick,
												  conditional_pick_done=conditional_pick_done))

	def email_draft_finish(self, draft, teams):
	    for team in teams:
	        self.send_email(subject="Fantasy Draft '%s' has finished!" % draft['name'],
	                        recipient=team['email'],
	                        text_body=render_template("email_draftfinish.txt", draft=draft, team=team),
	                        html_body=render_template("email_draftfinish.html", draft=draft, team=team))

email = Email()
