# -*- coding: utf-8 -*-

import datetime, json, os

from flask.ext.script import Manager
from __init__ import app, db, update_draft

manager = Manager(app)

@manager.command
def emptychat():
    print db.update('delete from chat where id = ?', (238,))

@manager.command
def cleardb(confirm=False):
    "Completely clear/recreate the sqlite database - use with caution"
    if confirm:
        db.db_initialise_empty()

@manager.command
def updatedraft(draftid):
    "Update the specified draft. This will send emails - do not over use"
    update_draft(draftid)

@manager.command
def teamkeys(draftid):
    "Display the team keys for the specified draft."
    teams = db.get_teams(draftid)
    for team in teams:
        print '%s: %s' % (team['name'], team['key'])

@manager.command
def conditionalpicklengths(draftid):
    "Display the current length of future conditional picks."
    current_pick = max([pick['picked'] for pick in db.get_players(draftid)]) + 1
    conditional_picks = [cp for cp in db.get_conditional_picks(draftid) if cp['pickno'] >= current_pick]
    for pick in conditional_picks:
        print pick['pickno'], ':', len(pick['choices'])

@manager.command
def pldraft():
    "Create the Premier League draft"
    teams = [
            dict(name='Matt', email='wowcrisps@gmail.com'),
            dict(name='Ben', email='benlarah@gmail.com'),
            dict(name='Dave', email='amusedparrot@gmail.com'),
            dict(name='Tim', email='timpymont@hotmail.com'),
            dict(name='Ahmet', email='ahmet.feridun@ffandp.com'),
            dict(name='Nick', email='darkknight24@hotmail.co.uk'),
            dict(name='Andy', email='andypymont@gmail.com'),
            dict(name='JJ', email='jonathan.hazlehurst@googlemail.com'),
            dict(name='Laura', email='laurapymont@ymail.com'),
            dict(name='Will', email='william.c.smith@hotmail.co.uk'),
            dict(name='Hakan', email='hakan2010@live.com'),
            dict(name='DaneMark', email='markgray84@gmail.com')
        ]

    newpldraft('Fantasy Premier League 2015/16', teams, 15, 2015)

@manager.command
def nfldraft():
    "Create the NFL draft"
    with app.open_resource(os.path.join('db', 'nfl.json'), mode='r') as f:
        teams = json.loads(f.read())

    newnfldraft('Necessary Roughness 2014', teams, 15, 2014)

@manager.command
def drafttable(draftid):
    "Return draft table for inspection"
    print db.get_draft_table(draftid)

def add_player(draftid, firstname, surname, searchable_name, team, position):
    return  db.insert('insert into players (draftid, firstname, surname, searchable_name, team, position, picked) values (?, ?, ?, ?, ?, ?, ?)',
                      ((draftid, firstname, surname, searchable_name, team, position, 0),))

def newdraft(name, team_names_and_emails, positions, rounds, players_filename):
    draftid = db.new_draft(name, positions, rounds, team_names_and_emails)
    if draftid:
		with app.open_resource(os.path.join('db', players_filename), mode='r') as f:
			data = [unicode(line, 'utf-8').split(',') for line in f.read().split('\n')]
		headings, data = data[0], data[1:]

		players = [dict(zip(headings, line)) for line in data]
		params = [(draftid, p['firstname'], p['surname'], p['searchable_name'],
				   p['team'], p['position'], 0) for p in players]

		db.insert(sql='insert into players (draftid, firstname, surname, searchable_name, team, position, picked) values (?, ?, ?, ?, ?, ?, ?)',
				  param_sets=params)

def newnfldraft(name, team_names_and_emails, rounds, year=None):
	if year is None:
		year = datetime.datetime.now().year

	newdraft(name, team_names_and_emails, ["RB", "QB", "WR", "TE", "DST", "K"], rounds, 'nfl%i.csv' % year)

def newpldraft(name, team_names_and_emails, rounds, year=None):
	if year is None:
		year = datetime.datetime.now().year

	newdraft(name, team_names_and_emails, ["F", "M", "G", "D"], rounds, 'pl%i.csv' % year)

if __name__ == "__main__":
    manager.run()