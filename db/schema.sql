drop table if exists drafts;
create table drafts (
	id text primary key,
	name text not null,
	positions text,
	rounds integer
);

drop table if exists players;
create table players (
	id integer primary key autoincrement,
	draftid text,
	firstname text,
	surname text,
	searchable_name text,
	team text,
	position text,
	picked integer
);

drop table if exists teams;
create table teams (
	id integer primary key autoincrement,
	draftid text,
	draftorder integer,
	name text,
	email text,
	key text
);

drop table if exists conditional_picks;
create table conditional_picks (
	draftid text,
	pickno int,
	choices text,
	primary key (draftid, pickno)
);

drop table if exists chat;
create table chat (
	id integer primary key autoincrement,
	draftid text,
	tstamp timestamp not null,
	sender text,
	message text
);