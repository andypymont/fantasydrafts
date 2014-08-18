import os

from emails import email
from flask import abort, g, jsonify, redirect, render_template, request, url_for
from datamodel import db, pick_owner
from app import app

try:
	from settings import settings
	app.config.update(settings)
except ImportError:
	pass

@app.template_filter('chatname')
def filter_chatname(name):
	return name.replace(' ', '&nbsp;')

@app.template_filter('chatdate')
def filter_chatdate(value):
	return value.strftime('%d/%m/%Y&nbsp;%H:%M')

@app.template_filter('pickbutton_contents')
def filter_pickbutton_contents(value):
	if 'conditional' in value:
		status = value['conditional']
	else:
		status = ''

	symbols = {'': '&nbsp;',
			   'done': '<span class="glyphicon glyphicon-ok"></span>',
			   'part': '?'}

	if 'current' in value:
		if 'mypick' in value:
			return '&nbsp;<br>click to pick<br><small>&nbsp;</small>'
		else:
			return '&nbsp;<br>current pick<br><small>&nbsp;</small>'
	else:
		if 'mypick' in value:

			return {'': '&nbsp;<br>click to pick<br><small>&nbsp;</small>',
					'done': 'click to edit<br>%s<br><small>&nbsp;</small>' % symbols[status],
					'part': 'click to edit<br>%s<br><small>&nbsp;</small>' % symbols[status]}[status]

		else:
			return '&nbsp;<br>%s<br><small>&nbsp;</small>' % symbols[status]

@app.route('/')
def index():
	latest_drafts = db.get_latest_drafts()
	return render_template('index.html', drafts=latest_drafts)

@app.route('/drafts/<draftid>/')
def draft_overview(draftid):
	try:
		userteam = db.get_teams(draftid, request.args.get('u', ''))[0]
	except IndexError:
		userteam = dict()

	chatfilter = request.args.get('chatfilter', 'all')

	draft = db.get_draft_table(draftid, userteam)
	chat = db.get_chat(draftid, chatfilter)

	return render_template('overview.html', draftid=draftid, draftname=draft['draft']['name'], chatlines=chat,
										    teams=draft['teams'], rounds=draft['table'], show_rounds=draft['show_rounds'],
										    userteam=userteam, pick_modals=draft['pick_modals'], chatfilter=chatfilter)

@app.route('/drafts/<draftid>/chat/', methods=['POST'])
def submit_chat(draftid):
	try:
		userteam = db.get_teams(draftid, request.args.get('u', ''))[0]
	except IndexError:
		abort(401)

	if request.form['chatmessage'].replace(' ','') != '':
	    db.new_chat_message(draftid, userteam['name'], request.form['chatmessage'])

	return redirect(url_for('draft_overview', draftid=draftid, u=request.args.get('u', '')))

@app.route('/drafts/<draftid>/pick/<int:pickno>', methods=['POST'])
def submit_pick(draftid, pickno):
	key = request.args.get('u', '')
	if db.check_conditional_pick_owner(draftid, pickno, key):
		picks = sorted([pick for pick in request.form.keys() if pick.startswith('pick%sdraftpick' % pickno)])

		cp = []
		for pick in picks:
		    if request.form[pick]:
			    cp.append(int(request.form[pick]))

		if len(cp) == len(set(cp)):
			db.update_conditional_pick(draftid, pickno, cp)

			picks = db.get_picked_players(draftid)

			if len(picks) == 0:
				current_pick = 1
			else:
				current_pick = max(pick['picked'] for pick in picks) + 1

			if current_pick == pickno:
				update_draft(draftid)

	return redirect(url_for('draft_overview', draftid=draftid, u=request.args.get('u', '')))

@app.route('/drafts/<draftid>/json/players/remaining')
def json_remaining_players(draftid):
	query = request.args.get('q', '')
	remaining_players = db.get_players(draftid=draftid, unpicked_only=True, query=query)[:10]
	return jsonify({'players': [dict(id=player['id'], text="%s %s (%s, %s)" % (player['firstname'], player['surname'],
									 										   player['position'], player['team']))
								for player in remaining_players]
		})

@app.route('/drafts/<draftid>/json/players/')
def json_player(draftid):
	playerid = request.args.get('id', 0)
	players = db.get_player_from_id(draftid, playerid)
	return jsonify({'players': [dict(id=player['id'],
									 text="%s %s (%s, %s)" % (player['firstname'], player['surname'],
									 						  player['position'], player['team']))
								for player in players]})

def update_draft(draftid):
	draft = db.get_draft_header(draftid)
	picks = db.get_picked_players(draftid)
	teams = db.get_teams(draftid)

	if len(picks) == 0:
		original_current_pick = current_pick = 1
	else:
		original_current_pick = current_pick = max(pick['picked'] for pick in picks) + 1

	conditional_picks = [pick for pick in db.get_conditional_picks(draftid) if pick['pickno'] >= current_pick]
	emails = []

	teams = dict([(team['draftorder'], team) for team in teams])
	picked_ids = [pick['id'] for pick in picks]

	team_count = len(teams)

	current_team = teams[pick_owner(current_pick, team_count)]

	while True:
		# remove invalid picks:
		for pick in conditional_picks:
			pick.update(choices=[choice for choice in pick['choices'] if not (choice in picked_ids)])

		# check for a pick to be processed and do it if possible:
		cp = [pick for pick in conditional_picks if pick['pickno'] == current_pick]

		if cp:
			cp = cp[0] # should be one result for current pick
			current_team = teams[pick_owner(current_pick, team_count)]

			if len(cp['choices']) > 0:
				pick_description = db.pick_player(draftid, cp['choices'][0], current_pick, team_count, current_team['name'])
				if pick_description:
					picked_ids.append(cp['choices'][0])
					if current_pick > original_current_pick:
						emails.append(('autopick', dict(draft=draft, team=current_team, pick_description=pick_description)))
					current_pick += 1
				else: # pick not successfully saved - let's finish here
					break
			else:
				break

		else: # no more conditional picks - update done
			break

	if (current_pick == 1):
	    emails.append(('startdraft', dict(draft=draft, teams=teams.values())))

	if (current_pick > (team_count * draft['rounds'])):
	    emails.append(('enddraft', dict(draft=draft, teams=teams.values())))
	else:
	    current_team = teams[pick_owner(current_pick, team_count)]
	    emails.append(('next', dict(draft=draft, team=current_team)))

	if not ((current_pick + 1) > (team_count * draft['rounds'])):
		cp = [pick for pick in conditional_picks if  pick['pickno'] == (current_pick + 1)]

		try:
			cp_done = (len(cp[0]['choices']) >= 2)
		except IndexError:
			cp_done = False

		emails.append(('upcoming', dict(draft=draft, team=teams[pick_owner(current_pick + 1, team_count)], current_pick=current_pick,
		    								conditional_pick_done=cp_done)))

	db.update_conditional_picks(draftid, conditional_picks)

	for (email_type, parameters) in emails:
		email.email(email_type, parameters)

if __name__ == "__main__":
	app.run(debug=True)