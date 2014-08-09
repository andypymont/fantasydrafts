import datetime
import json
import os
import random
import slugify
import string
import sqlite3

def database(app, g):

	class Database(object):

		def db_connect(self):
			rv = sqlite3.connect(app.config['DATABASE'], detect_types=sqlite3.PARSE_DECLTYPES)
			rv.row_factory = sqlite3.Row
			return rv

		def db_get(self):
			if not hasattr(g, 'sqlite_db'):
				g.sqlite_db = self.db_connect()
			return g.sqlite_db

		@app.teardown_appcontext
		def db_close(self):
			if hasattr(g, 'sqlite_db'):
				g.sqlite_db.close()

		def db_initialise_empty(self):
			with app.app_context():
				db = self.db_get()
				with app.open_resource(os.path.join('db', 'schema.sql'), mode='r') as f:
					db.cursor().executescript(f.read())
				db.commit()

		def select(self, sql, params):
			db = self.db_get()
			return db.execute(sql, params).fetchall()

		def insert(self, sql, param_sets):
			db = self.db_get()
			for params in param_sets:
				db.execute(sql, params)
			db.commit()
			return True

		def update(self, sql, params):
			db = self.db_get()
			db.execute(sql, params)
			db.commit()
			return True

		def get_latest_drafts(self):
			return self.select('select * from drafts order by id desc limit 5', [])

		def new_draft(self, name, positions, rounds, team_names_and_emails):
			draftid = slugify.slugify(name)

			self.insert('insert into drafts (id, name, positions, rounds) values (?, ?, ?, ?)',
							   [(draftid, name, json.dumps(positions), rounds)])

			random_keys = [1, 1]
			while len(random_keys) != len(set(random_keys)):
				random_keys = [''.join(random.choice(string.ascii_lowercase + string.digits) for _ in xrange(10))
							   for t in team_names_and_emails]

			if self.insert('insert into teams (draftid, draftorder, name, email, key) values (?, ?, ?, ?, ?)',
						   [(draftid, n + 1, team['name'], team['email'], random_keys[n])
						   for (n, team) in enumerate(team_names_and_emails)]):
				return draftid

		def get_draft_header(self, id):
			rv = self.select('select * from drafts where id = ?', (id,))[0]
			return dict(id=rv['id'],
						name=rv['name'],
						positions=json.loads(rv['positions']),
						rounds=rv['rounds'])

		def get_draft_table(self, draftid, userteam=None):
			draft = self.get_draft_header(draftid)
			teams = self.get_teams(draftid)
			team_count = len(teams)

			table = [dict(no=rd+1, picks=[dict() for team in teams]) for rd in xrange(draft['rounds'])]

			picks = self.get_picked_players(draftid)
			conditional_picks = self.get_conditional_picks(draftid)
			positions = dict([(pos, n+1) for (n, pos) in enumerate(draft['positions'])])

			# Picks already made:
			for pick in picks:
				rd, x = table_full_pick_no(pick['picked'], team_count)
				cell = table[rd - 1]['picks'][x - 1]
				cell.update(firstname=pick['firstname'],
							surname=pick['surname'],
							team=pick['team'],
							position=pick['position'],
							posno=positions[pick['position']])

			if len(picks) == 0:
				current_pick = 1
			else:
				current_pick = max(pick['picked'] for pick in picks) + 1
			rd, x = table_full_pick_no(current_pick, team_count)

			show_rounds = (rd - 2, rd - 1, rd, rd + 1)
			pick_modals = []

			if not current_pick > (draft['rounds'] * team_count):

			    table[rd - 1]['picks'][x - 1].update(current=True)

    			# Conditional picks:
    			cp = [pick for pick in conditional_picks if pick['pickno'] >= current_pick]
    			for pick in cp:

    				rd, x = table_full_pick_no(pick['pickno'], team_count)
    				if len(pick['choices']) >= (1 + pick['pickno'] - current_pick):
    					table[rd - 1]['picks'][x - 1].update(conditional='done')
    				elif len(pick['choices']) > 0:
    					table[rd - 1]['picks'][x - 1].update(conditional='part')

    			# Set up next picks of current user ready for editing
    			if userteam:
	    			for remaining_pick in remaining_picks(userteam['draftorder'], team_count, draft['rounds'], current_pick)[:2]:

						try:
							current = [pick for pick in conditional_picks if (pick['pickno'] == remaining_pick)][0]['choices'][:10]
						except IndexError:
							current = []

						rd, pick_no = full_pick_no(remaining_pick, team_count)
						pick_modals.append(dict(pick=remaining_pick, rd=rd, pick_within_round=pick_no,
								  				picks_needed=min(1 + remaining_pick - current_pick, 10),
								  				current=current))

						rd, x = table_full_pick_no(remaining_pick, team_count)
						table[rd - 1]['picks'][x - 1].update(mypick=remaining_pick)

			return dict(draft=draft, teams=teams, table=table, show_rounds=show_rounds, pick_modals=pick_modals)

		def get_conditional_picks(self, draftid):
			rv = self.select('select * from conditional_picks where draftid = ?', (draftid,))
			return [dict(draftid=pick['draftid'], pickno=pick['pickno'], choices=json.loads(pick['choices'])) for pick in rv]

		def check_conditional_pick_owner(self, draftid, pickno, key):
			teams = self.select('select * from teams where draftid = ?', (draftid,))
			owner = pick_owner(pickno, len(teams))

			try:
				team = [team for team in teams if team['draftorder'] == owner][0]
				return (team['key'] == key)
			except IndexError:
				return False

		def update_conditional_pick(self, draftid, pickno, choices):
			db = self.db_get()
			choices = json.dumps(choices)

			db.execute('insert or replace into conditional_picks (draftid, pickno, choices) values (?, ?, ?)',
					   (draftid, pickno, choices))
			db.commit()
			return True

		def update_conditional_picks(self, draftid, new_cp):
			db = self.db_get()

			for cp in new_cp:
				choices = json.dumps(cp['choices'])
				db.execute('insert or replace into conditional_picks (draftid, pickno, choices) values (?, ?, ?)',
						   (cp['draftid'], cp['pickno'], choices))

			db.commit()
			return True

		def get_teams(self, draftid, key=None):
			sql, params = 'select * from teams where draftid = ?', (draftid,)

			if not (key is None):
				sql += ' and key = ?'
				params += (key,)

			q = self.select(sql, params)
			return [dict(id=team_row['id'],
						 draftid=team_row['draftid'],
						 draftorder=team_row['draftorder'],
						 name=team_row['name'],
						 email=team_row['email'],
						 key=team_row['key']) for team_row in q]

		def get_players(self, draftid, unpicked_only=False, query=''):
			sql, params = 'select * from players where draftid = ?', [draftid]
			if unpicked_only:
				sql += ' and picked = 0'
			if query != '':
				sql += ' and searchable_name like ?'
				params.append(''.join((r'%', query, r'%')))

			return self.select(sql, params)

		def get_player_from_id(self, draftid, playerid):
			return self.select('select * from players where id = ? and draftid = ?', (playerid, draftid))

		def get_picked_players(self, draftid):
			return self.select('select * from players where draftid = ? and picked > 0 order by picked', (draftid,))

		def pick_player(self, draftid, playerid, picknumber, team_count, team_name):
			rd, pick_within_round = full_pick_no(picknumber, team_count)
			player = self.get_player_from_id(draftid, playerid)[0]
			pick_description = "%s %s (%s, %s)" % (player['firstname'], player['surname'], player['position'], player['team'])

			message_text = "%s drafted %s with pick %s (round %s, pick %s)" % (
							team_name, pick_description, picknumber, rd, pick_within_round)

			if self.update('update players set picked = ? where draftid = ? and id = ?',
						   (picknumber, draftid, playerid)):
				self.new_chat_message(draftid, '', message_text)
				return pick_description

		def get_chat(self, draftid, chatfilter="all"):
			sql, params = dict(all=('select * from chat where draftid = ? order by tstamp desc', (draftid,)),
					   		   chat=('select * from chat where draftid = ? and sender <> ? order by tstamp desc', (draftid, '')),
					   		   picks=('select * from chat where draftid = ? and sender = ? order by tstamp desc', (draftid, '')))[chatfilter]
			return self.select(sql, params)

		def new_chat_message(self, draftid, sender, message, tstamp=None):
			if tstamp is None:
				tstamp = datetime.datetime.now() + datetime.timedelta(hours=1)

			sql, param_sets = ('insert into chat (draftid, tstamp, sender, message) values (?, ?, ?, ?)',
							   [(draftid, tstamp, sender, message)])

			return self.insert(sql, param_sets)

	return Database()

def picks_for_team(draftorder, teams, rounds):
	rv = []
	rounds = range(rounds)

	for rd in rounds:
		if rd in rounds[::2]:
			rv.append((rd * teams) + draftorder)
		else:
			rv.append((rd * teams) + teams - draftorder + 1)

	return rv

def remaining_picks(draftorder, teams, rounds, current_pick):
	return [pick for pick in picks_for_team(draftorder, teams, rounds) if pick >= current_pick]

def pick_owner(pick_no, teams):
	rd, pick_within_round = full_pick_no(pick_no, teams)
	if (rd % 2) == 0: # even round: snaking back
		return teams - pick_within_round + 1
	else:
		return pick_within_round

def next_pick(draftorder, teams, rounds, current_pick):
	remaining_picks = [pick for pick in picks_for_team(draftorder, teams, rounds) if pick >= current_pick]
	next_picks = remaining_picks[:2]

	if len(next_picks) == 2:
	    if (next_picks[0] + 1) == next_picks[1]:
	        return next_picks[1]
	    else:
	        return next_picks[0]
	elif len(next_picks) == 1:
	    return next_picks[0]
	else:
	    return 0

def full_pick_no(pick_no, teams):
	completed_rounds = ((pick_no) - 1) / teams
	pick_within_round = pick_no - (completed_rounds * teams)

	return (completed_rounds + 1, pick_within_round)

def table_full_pick_no(pick_no, teams):
	rd, pick_within_round = full_pick_no(pick_no, teams)

	if (rd % 2) == 0: # even round: snake back
		pick_within_round = teams - pick_within_round + 1

	return (rd, pick_within_round)
