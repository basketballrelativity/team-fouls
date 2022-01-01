"""
team_fouls.py

This script contains a function to calculate
team fouls accumulated by quarter (or overtime period)
along with any free throws resulting from additional
fouls accumulated in the penalty
"""

from typing import Union, Dict, List
import time
import re
import argparse

import numpy as np
import pandas as pd

from py_ball import playbyplay, boxscore, scoreboard


# Header information needed for py_ball
HEADERS = {'Connection': 'keep-alive',
           'Host': 'stats.nba.com',
           'Origin': 'http://stats.nba.com',
           'Upgrade-Insecure-Requests': '1',
           'Referer': 'stats.nba.com',
           'x-nba-stats-origin': 'stats',
           'x-nba-stats-token': 'true',
           'Accept-Language': 'en-US,en;q=0.9',
           "X-NewRelic-ID": "VQECWF5UChAHUlNTBwgBVw==",
           'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6)' +\
                         ' AppleWebKit/537.36 (KHTML, like Gecko)' + \
                         ' Chrome/81.0.4044.129 Safari/537.36'}


# These indicate EVENTMSGACTIONTYPE values that increment team fouls
TEAM_FOUL_INDICATORS = [1, 2, 3, 5, 6, 9, 14, 15, 26, 27, 28, 29]
# These indicate EVENTMSGACTIONTYPE values that would result in FTAs only
# if a team is in the penalty
NON_SHOOTING_FOULS = [1, 3, 27, 28]

TWO_MINUTES = 120 # Seconds
QUARTERS = 4
REG_GAME_LENGTH = 720*QUARTERS # Game length in seconds
THREE_QUARTER_LENGTH = 720*(QUARTERS - 1) # Length of three quarters in seconds
OT_LENGTH = 300 # OT period length in seconds


def get_game_ids(date: str) -> List:
	""" get_game_ids returns the NBA game IDs
	that take place on the provided date

	@param date (str): Date in MM/DD/YYYY format

	Returns:

		- game_id_list (list): List of game IDs
	"""

	scores = scoreboard.ScoreBoard(headers=HEADERS,
                               	   endpoint='scoreboardv2',
                                   league_id='00',
                               	   game_date=date,
                               	   day_offset='0')

	games = scores.data['GameHeader']
	game_id_list = [x['GAME_ID'] for x in games]

	return game_id_list


def pull_team_ids(game_id: str) -> Union[int, int, bool, List]:
	""" This function pulls the JSON file for a
	game's play-by-play data and converts it into
	a Pandas DataFrame

	@param game_id (str): 10-digit string \
        that represents a unique game. The format is two leading zeroes, \
        followed by a season indicator number ('1' for preseason, \
        '2' for regular season, '4' for the post-season), \
        then the trailing digits of the season in which the game \
        took place (e.g. '17' for the 2017-18 season). The following \
        5 digits increment from '00001' in order as the season progresses. \
        For example, '0021600001' is the **game_id** of the first game \
        of the 2016-17 NBA regular season.

	Returns:

		- home_id (int): 10-digit integer that uniquely identifies the
			home team
		- away_id (int): 10-digit integer that uniquely identifies the
			away team
		- home_winner (bool): Boolean indicating whether the home team
			won or not
		- line (list): List containing line score information by team
	"""

	box = boxscore.BoxScore(headers=HEADERS, endpoint='boxscoresummaryv2', game_id=game_id)
	metadata = box.data["GameSummary"]
	line = box.data["LineScore"]
	home_id, away_id = metadata[0]["HOME_TEAM_ID"], metadata[0]["VISITOR_TEAM_ID"]

	# Find winner by comparing point totals
	if line[0]["TEAM_ID"] == home_id:
		home_points = line[0]["PTS"]
		away_points = line[1]["PTS"]
	else:
		home_points = line[1]["PTS"]
		away_points = line[0]["PTS"]

	if pd.notnull(home_points) and pd.notnull(away_points):
		home_winner = home_points > away_points
	else:
		home_winner = None

	return home_id, away_id, home_winner, line


def pull_pbp_file(game_id: str) -> pd.DataFrame:
	""" This function pulls the JSON file for a
	game's play-by-play data and converts it into
	a Pandas DataFrame

	@param game_id (str): 10-digit string \
        that represents a unique game. The format is two leading zeroes, \
        followed by a season indicator number ('1' for preseason, \
        '2' for regular season, '4' for the post-season), \
        then the trailing digits of the season in which the game \
        took place (e.g. '17' for the 2017-18 season). The following \
        5 digits increment from '00001' in order as the season progresses. \
        For example, '0021600001' is the **game_id** of the first game \
        of the 2016-17 NBA regular season.

	Returns:

		- pbp_df (DataFrame): DataFrame containing play-by-play
			data for the game corresponding to game_id
	"""

	plays = playbyplay.PlayByPlay(headers=HEADERS, endpoint='playbyplayv2', game_id=game_id)
	pbp_df = pd.DataFrame(plays.data['PlayByPlay'])

	return pbp_df


def str_to_time(time_str: str, period: int) -> int:
    """ This function converts a period and time to seconds remaining
    in the quarter


	@param time_str (str): Game time in MM:SS format
	@param period (int): Game quarter (5 is OT1, 6 is OT2, etc.)

	Returns

		- seconds_left_period (int): Seconds left in the given period
    """

    split_time = time_str.split(':')
    seconds_left_period = int(split_time[0]) * 60 + int(split_time[1])

    return seconds_left_period


def add_fouls(foul_dict: Dict, quarter_time: int) -> Dict:
	""" This function adds fouls to a team's total and their
	L2M total if applicable

	@param foul_dict (dict): Dictionary containing the number of fouls
		and L2M fouls a team has accumulated
	@param quarter_time (int): Time remaining in the quarter

	Returns:

		- foul_dict (int): Incremented number of team fouls
			and L2M fouls in the quarter
	"""

	foul_dict["fouls"] += 1
	if quarter_time <= TWO_MINUTES:
		foul_dict["l2m"] += 1

	return foul_dict


def is_in_penalty(foul_dict: Dict, period: int, penalty: bool) -> Union[bool, int]:
	""" This function determines if a team is in the penalty

	@param foul_dict (dict): Dictionary containing the number of fouls
		and L2M fouls a team has accumulated
	@param period (int): Game quarter (5 is OT1, 6 is OT2, etc.)
	@param penalty (bool): Boolean indicating whether the
		team is in the penalty

	Returns:

		- penalty (bool): Boolean indicating whether the
			team is in the penalty
		- period_fouls (int): Number of fouls to reach the penalty
	"""

	period_fouls = 4 if period <= 4 else 3

	if foul_dict["fouls"] >= period_fouls or foul_dict["l2m"] >= 1:
		penalty = True
	else:
		penalty = False

	return penalty, period_fouls


def process_foul_df(pbp_df: pd.DataFrame) -> pd.DataFrame:
	""" This function filters the play-by-play data
	to team fouls only

	@params pbp_df (DataFrame): DataFrame with play-by-play
		data

	Returns:

		- foul_df (DataFrame): DataFrame containing only
			team fouls
	"""

	# EVENTMSGTYPE = 6 corresponds to fouls
	foul_df = pbp_df[pbp_df["EVENTMSGTYPE"]==6]

	# Offensive charges (EVENTMSGTYPE = 6, EVENTMSGACTIONTYPE = 26)
	# can be team fouls in certain instances and non-team fouls in others.
	# The following peaks at the descriptions
	# for team foul indicators to see which charges to keep
	foul_df["keep_charge"] = [1 if action_type == 26
							  and ((re.search(".T[0-9]", str(home_desc)))
							  		or (re.search(".T[0-9]", str(away_desc)))
							  		or (".PN" in str(home_desc))
							  		or (".PN" in str(away_desc)))
							  else 0
							  for action_type, home_desc, away_desc in zip(foul_df["EVENTMSGACTIONTYPE"],
							  											   foul_df["HOMEDESCRIPTION"],
							  											   foul_df["VISITORDESCRIPTION"])]
	# Isolating to only fouls of interest
	foul_df = foul_df[(foul_df["EVENTMSGACTIONTYPE"] != 26) |
					  ((foul_df["EVENTMSGACTIONTYPE"] == 26) &
					   ((foul_df["keep_charge"]==1)))]

	return foul_df


def initialize_status_variables(home_id: int, away_id: int, period: int) -> Union[Dict, Dict, Dict]:
	""" This function simply initializes many variables
	that will be used to track and store team foul information

	@param home_id (int): 10-digit integer that uniquely identifies the
		home team
	@param away_id (int): 10-digit integer that uniquely identifies the
		away team
	@param period (int): Game quarter (5 is OT1, 6 is OT2, etc.)

	Returns:

		- home_dict (dict): Dictionary containing the number of fouls
			and L2M fouls a team has accumulated for the home team
		- away_dict (dict): Dictionary containing the number of fouls
			and L2M fouls a team has accumulated for the away team
		- penalty_dict (dict): Dictionary containing fouls
			committed, time spent in the penalty, and FT
			surrendered for each team in a game
	"""

	home_dict = {"fouls": 0, "l2m": 0, "penalty": False}
	away_dict = {"fouls": 0, "l2m": 0, "penalty": False}
	penalty_dict = {}
	penalty_dict[home_id] = {}
	penalty_dict[away_id] = {}
	penalty_dict[home_id]["fouls"] = {}
	penalty_dict[away_id]["fouls"] = {}
	penalty_dict[home_id]["free_throws"] = {}
	penalty_dict[away_id]["free_throws"] = {}
	penalty_dict[home_id]["time"] = {}
	penalty_dict[away_id]["time"] = {}
	penalty_dict[home_id]["game_event"] = {}
	penalty_dict[away_id]["game_event"] = {}
	penalty_dict[home_id]["time"][period] = 0
	penalty_dict[away_id]["time"][period] = 0
	penalty_dict[home_id]["free_throws"][period] = 0
	penalty_dict[away_id]["free_throws"][period] = 0

	return home_dict, away_dict, penalty_dict


def reset_status_variables(home_id: int, away_id: int, period: int, penalty_dict: Dict) -> Union[Dict, Dict, Dict, int]:
	""" This function resets the status variables when a quarter
	turns over

	@param home_id (int): 10-digit integer that uniquely identifies the
		home team
	@param away_id (int): 10-digit integer that uniquely identifies the
		away team
	@param period (int): Game quarter (5 is OT1, 6 is OT2, etc.)
	@param penalty_dict (dict): Dictionary containing team foul
		related data

	Returns:

		- home_dict (dict): Dictionary containing the number of fouls
			and L2M fouls a team has accumulated for the home team
		- away_dict (dict): Dictionary containing the number of fouls
			and L2M fouls a team has accumulated for the away team
		- penalty_dict (dict): Dictionary containing fouls
			committed, time spent in the penalty, and FT
			surrendered for each team in a game
		- period (int): Period incremented by one
	"""

	home_dict = {"fouls": 0, "l2m": 0, "penalty": False}
	away_dict = {"fouls": 0, "l2m": 0, "penalty": False}

	period += 1
	penalty_dict[home_id]["time"][period] = 0
	penalty_dict[away_id]["time"][period] = 0
	penalty_dict[home_id]["free_throws"][period] = 0
	penalty_dict[away_id]["free_throws"][period] = 0


	return home_dict, away_dict, penalty_dict, period


def update_status_variables(
	play: pd.Series, period: int, team_id: int, foul_dict: Dict, penalty_dict: Dict
) -> Union[Dict, Dict]:
	""" This function updates team foul and penalty information
	for the team in team_id

	@param play (pd.Series): Pandas series that contains information
		for a single play
	@param period (int): Game quarter (5 is OT1, 6 is OT2, etc.)
	@param team_id (int): Unique identifier of team committing a foul
	@param foul_dict (dict):  Dictionary containing the number of fouls
		and L2M fouls a team has accumulated
	@param penalty_dict (dict): Dictionary containing team foul
		related data

	Returns:

		- foul_dict (dict): Dictionary containing updated
			foul numbers
		- penalty_dict (dict): Dictionary containing updated
			team foul related data
	"""

	# Time remaining in quarter
	time_remaining = str_to_time(play["PCTIMESTRING"], period)

	# Increment fouls and check if team is in the penalty
	foul_dict = add_fouls(foul_dict, time_remaining)
	check_penalty, penalty_fouls = is_in_penalty(foul_dict, period, time_remaining)

	# Increment two FTA if a non-shooting team foul occurs for a team in the penalty
	if foul_dict["penalty"] and play["EVENTMSGACTIONTYPE"] in NON_SHOOTING_FOULS:
		penalty_dict[team_id]["free_throws"][period] += 2

	# Flip a team into the penalty if they aren't already there, storing the
	# time remaining and event number for future processing
	if check_penalty and not foul_dict["penalty"]:
		penalty_dict[team_id]["time"][period] = time_remaining
		penalty_dict[team_id]["game_event"][period] = play["EVENTNUM"]
		foul_dict["penalty"] = True

	return foul_dict, penalty_dict


def team_foul_tracker(
		game_id: str, home_id: int, away_id: int, home_winner: bool
) -> Union[Dict, int, pd.DataFrame]:
	""" This function calculates the number of team fouls accumulated
	by team per quarter (or overtime period). In addition, other metadata
	of interest related to team fouls is tracked and stored

	@param game_id (str): 10-digit string \
        that represents a unique game. The format is two leading zeroes, \
        followed by a season indicator number ('1' for preseason, \
        '2' for regular season, '4' for the post-season), \
        then the trailing digits of the season in which the game \
        took place (e.g. '17' for the 2017-18 season). The following \
        5 digits increment from '00001' in order as the season progresses. \
        For example, '0021600001' is the **game_id** of the first game \
        of the 2016-17 NBA regular season.
	@param home_id (int): 10-digit integer that uniquely identifies the
		home team
	@param away_id (int): 10-digit integer that uniquely identifies the
		away team
	@param home_winner (bool): Boolean indicating whether the home team won
		the game

	Returns:

		- penalty_dict (dict): Dictionary containing
			team foul related data
		- winner_id (int): ID of winning team
		- pbp_df (DataFrame): DataFrame with play-by-play
		data
	"""

	pbp_df = pull_pbp_file(game_id)

	# Isolate fouls
	foul_df = process_foul_df(pbp_df)
	
	# Status variables
	period = 1
	home_dict, away_dict, penalty_dict = initialize_status_variables(home_id, away_id, period)

	# Loop through each foul
	for _, row in foul_df.iterrows():
		if period != row["PERIOD"]:
			# Reset foul information if the period turns over
			penalty_dict[home_id]["fouls"][period] = home_dict["fouls"]
			penalty_dict[away_id]["fouls"][period] = away_dict["fouls"]
			home_dict, away_dict, penalty_dict, period = reset_status_variables(home_id, away_id, period, penalty_dict)


		# Update team fouls and penalty status for the corresponding team
		if row["EVENTMSGACTIONTYPE"] in TEAM_FOUL_INDICATORS:
			if row["PLAYER1_TEAM_ID"] == home_id:
				home_dict, penalty_dict = update_status_variables(row, period, home_id, home_dict, penalty_dict)
			else:
				away_dict, penalty_dict = update_status_variables(row, period, away_id, away_dict, penalty_dict)

	# Store team foul totals for final period
	penalty_dict[home_id]["fouls"][period] = home_dict["fouls"]
	penalty_dict[away_id]["fouls"][period] = away_dict["fouls"]

	# Find ID of winning team
	winner_id = home_id if home_winner else away_id

	return penalty_dict, winner_id, pbp_df


def process_output(penalty_dict: Dict, winner_id: bool) -> pd.DataFrame:
	""" This function extracts useful information from the penalty
	dictionary output from team_foul_tracker

	@params penalty_dict (dict): Dictionary containing fouls
		committed, time spent in the penalty, and FT
		surrendered for each team in a game
	@params winner_id (bool): ID of winning team

	Returns:

		- full_df (DataFrame): DataFrame containing
			team foul and penalty information
	"""

	teams = list(penalty_dict.keys())
	full_df = pd.DataFrame()
	for team in teams:
		# Find the opponent
		other_team = [x for x in teams if x != team][0]
		team_dict = penalty_dict[team]
		other_team_dict = penalty_dict[other_team]

		game_length = REG_GAME_LENGTH + OT_LENGTH * (len(team_dict["fouls"]) - QUARTERS)
		
		# Calculate team foul related data to export. Because of the way team_foul_tracker is constructed,
		# the time spent in the penalty, fouls accumulated, and FTs surrendered is for a team's defense.
		# The following dataframe uses this logic to store defensive data (fouls committed, opponent time-
		# in-bonus, and ft allowed) from a team's own penalty dictionary and stores offensive data (fouls against,
		# own time-in-bonus, and ft gained)
		temp_df = pd.DataFrame({"team_id": [team],
								"game_length": [game_length],
								"fouls_committed": [np.sum([team_dict["fouls"][x] for x in team_dict["fouls"]])],
								"fouls_3q_committed": [np.sum([team_dict["fouls"][x] for x in team_dict["fouls"] if x < 4])],
								"opp_tib": [np.sum([team_dict["time"][x] for x in team_dict["time"]])],
								"opp_3q_tib": [np.sum([team_dict["time"][x] for x in team_dict["time"] if x < 4])],
								"ft_allowed": [np.sum([team_dict["free_throws"][x] for x in team_dict["free_throws"]])],
								"ft_3q_allowed": [np.sum([team_dict["free_throws"][x] for x in team_dict["free_throws"] if x < 4])],
								"fouls_against": [np.sum([other_team_dict["fouls"][x] for x in other_team_dict["fouls"]])],
								"fouls_3q_against": [np.sum([other_team_dict["fouls"][x] for x in other_team_dict["fouls"] if x < 4])],
								"own_tib": [np.sum([other_team_dict["time"][x] for x in other_team_dict["time"]])],
								"own_3q_tib": [np.sum([other_team_dict["time"][x] for x in other_team_dict["time"] if x < 4])],
								"ft_gained": [np.sum([other_team_dict["free_throws"][x] for x in other_team_dict["free_throws"]])],
								"ft_3q_gained": [np.sum([other_team_dict["free_throws"][x] for x in other_team_dict["free_throws"] if x < 4])],
								"win": [1 if team == winner_id else 0]})
		full_df = pd.concat([full_df, temp_df])

	# Normalizing time-in-bonus by game length
	full_df["opp_percent_tib"] = full_df["opp_tib"] / full_df["game_length"]
	full_df["own_percent_tib"] = full_df["own_tib"] / full_df["game_length"]

	# Normalizing 3q time-in-bonus by three-quarters length
	full_df["opp_percent_3q_tib"] = full_df["opp_3q_tib"] / THREE_QUARTER_LENGTH
	full_df["own_percent_3q_tib"] = full_df["own_3q_tib"] / THREE_QUARTER_LENGTH

	return full_df


def persist_shooting_team(pbp_df: pd.DataFrame) -> pd.DataFrame:
	""" This function persists the shooting team forward until the
	next shot attempt so as to track offensive rebounds

	@params pbp_df (DataFrame): DataFrame with play-by-play
		data

	Returns:

		- pbp_df (DataFrame): DataFrame with a SHOOTING_TEAM
			column tracking the previous shooting team
	"""

	shooting_team_list = []
	shooting_team = None
	for _, row in pbp_df.iterrows():
		if row["EVENTMSGTYPE"] in [1, 2, 3]:
			shooting_team = row["PLAYER1_TEAM_ID"]
			shooting_team_list.append(shooting_team)
		else:
			shooting_team_list.append(shooting_team)

	pbp_df["SHOOTING_TEAM"] = shooting_team_list

	return pbp_df


def possession_types(pbp_df: pd.DataFrame) -> pd.DataFrame:
	""" This function signals FGA, FTA, TOV and OREB
	in each row of a play-by-play file

	@params pbp_df (DataFrame): DataFrame with play-by-play
		data

	Returns:

		- pbp_df (DataFrame): DataFrame with FGA, FTA,
			TOV, and OREB indicators for each play
	"""

	pbp_df["FGA"] = [1 if event_msg_type <= 2 else 0 for event_msg_type in pbp_df["EVENTMSGTYPE"]]
	pbp_df["FTA"] = [1 if event_msg_type == 3 else 0 for event_msg_type in pbp_df["EVENTMSGTYPE"]]
	pbp_df["TOV"] = [1 if event_msg_type == 5 else 0 for event_msg_type in pbp_df["EVENTMSGTYPE"]]
	pbp_df["OREB"] = [1 if event_msg_type == 4 and reb_team == shoot_team else 0
					  for event_msg_type, reb_team, shoot_team in zip(pbp_df["EVENTMSGTYPE"],
					  												  pbp_df["PLAYER1_TEAM_ID"],
					  												  pbp_df["SHOOTING_TEAM"])]

	return pbp_df


def possession_and_pts_estimate(pbp_df: pd.DataFrame) -> Union[int, float]:
	""" This function calculates the points scored and possessions
	used in the pbp_df provided. Possessions are calculated by the
	simple heuristic motivated here: http://vishub.org/officedocs/18024.pdf

	@params pbp_df (DataFrame): DataFrame with play-by-play
		data

	Returns:

		- points (int): Points scored
		- poss (float): Possessions used
	"""

	poss = 0.976 * (np.sum(pbp_df["FGA"]) +
					0.44*(np.sum(pbp_df["FTA"])) -
					np.sum(pbp_df["OREB"]) +
					np.sum(pbp_df["TOV"]))
	points = np.sum(pbp_df["POINT"])

	return points, poss


def calc_pts_and_poss(pbp_df: pd.DataFrame, team_id: int, event_num: int, period: int, home: bool) -> Dict:
	"""  This function calculates the points and posessions
	(and ultimately off/def rating) from a play-by-play dataset
	and a corresponding event_num

	@params pbp_df (DataFrame): DataFrame with play-by-play
		data
	@params team_id (int): 10-digit integer that uniquely identifies
		a team
	@params event_num (int): Integer corresponding to an event
		number in the pbp_df
	@params period (int): Integer corresponding to a period
		of interest
	@params home (bool): Boolean indicating whether the team
		of interest is the home team
	"""

	# Find the right description for offense and defense
	if home:
		off_desc = "HOMEDESCRIPTION"
		def_desc = "VISITORDESCRIPTION"
	else:
		off_desc = "VISITORDESCRIPTION"
		def_desc = "HOMEDESCRIPTION"

	# Possessions
	pbp_df = possession_types(pbp_df)

	# Isolate offense and defense relative to team of interest for a period
	off_df = pbp_df[(pbp_df["PLAYER1_TEAM_ID"]==team_id) & (pbp_df["PERIOD"]==period)]
	def_df = pbp_df[(pbp_df["PLAYER1_TEAM_ID"]!=team_id) & (pbp_df["PERIOD"]==period)]

	# Points
	off_df["POINT"] = [3 if event_msg_type == 1 and " 3PT " in desc
					   else 2 if event_msg_type == 1
					   else 1 if event_msg_type == 3 and "MISS " not in desc
					   else 0
					   for event_msg_type, desc in zip(off_df["EVENTMSGTYPE"], off_df[off_desc])]
	def_df["POINT"] = [3 if event_msg_type == 1 and " 3PT " in desc
					   else 2 if event_msg_type == 1
					   else 1 if event_msg_type == 3 and "MISS " not in desc
					   else 0
					   for event_msg_type, desc in zip(def_df["EVENTMSGTYPE"], def_df[def_desc])]

	# If event_num is None, the team isn't in the penalty for the entire quarter
	if event_num is None:
		off_points_np, off_poss_np = possession_and_pts_estimate(off_df)
		def_points_np, def_poss_np = possession_and_pts_estimate(def_df)

		off_poss_p = 0
		def_poss_p = 0
		off_points_p = 0
		def_points_p = 0
	else:
		# Split on event_num at which team enters the penalty
		off_np_df = off_df[off_df["EVENTNUM"] < event_num]
		def_np_df = def_df[def_df["EVENTNUM"] < event_num]

		off_p_df = off_df[off_df["EVENTNUM"] >= event_num]
		def_p_df = def_df[def_df["EVENTNUM"] >= event_num]

		off_points_np, off_poss_np = possession_and_pts_estimate(off_np_df)
		def_points_np, def_poss_np = possession_and_pts_estimate(def_np_df)

		off_points_p, off_poss_p = possession_and_pts_estimate(off_p_df)
		def_points_p, def_poss_p = possession_and_pts_estimate(def_p_df)

	# Storing points and possession by penalty status
	return_dict = {"off_rating": {"penalty": {"poss": off_poss_p, "points": off_points_p},
								  "no_penalty": {"poss": off_poss_np, "points": off_points_np},},
				   "def_rating": {"penalty": {"poss": def_poss_p, "points": def_points_p},
								  "no_penalty": {"poss": def_poss_np, "points": def_points_np},}}

	return return_dict


def process_pbp(pbp_df: pd.DataFrame, penalty_dict: Dict, home_id: int) -> pd.DataFrame:
	""" This function processes the play-by-play data for a game
	to calculate possessions and off/def rating for teams

	@params pbp_df (DataFrame): DataFrame with play-by-play
		data
	@params penalty_dict (dict): Dictionary containing fouls
		committed, time spent in the penalty, and FT
		surrendered for each team in a game
	@params home_id (bool): ID of home team

	Returns:

		- rating_df (DataFrame): DataFrame containing points and possession
		 	data in penalty and non-penalty situations for a team
		 	on the offensive and defensive side of the ball
	"""

	# Initialize features and variables needed
	pbp_df = persist_shooting_team(pbp_df)
	max_period = max(pbp_df["PERIOD"])

	teams = list(penalty_dict.keys())
	full_df = pd.DataFrame()
	for team in teams:
		# Find the opponent
		other_team = [x for x in teams if x != team][0]
		team_dict = penalty_dict[team]
		other_team_dict = penalty_dict[other_team]

		# Is this the home team?
		home = team == home_id
		for periods in range(1, max_period + 1):
			# If the team enters the penalty in a period, the "other team" will
			# have an entry in its penalty dictionary. If not, the dictionary
			# will have no  entry 
			if periods in other_team_dict["game_event"]:
				event_num = other_team_dict["game_event"][periods]
			else:
				event_num = None

			# Calculate points and possessions for team inside and outside of the penalty
			rating_dict = calc_pts_and_poss(pbp_df, team, event_num, periods, home)

			# Store points and possessions for the team
			temp_df = pd.DataFrame({"team_id": [team],
									"period": [periods],
									"off_poss_np": [rating_dict["off_rating"]["no_penalty"]["poss"]],
									"off_points_np": [rating_dict["off_rating"]["no_penalty"]["points"]],
									"off_poss_p": [rating_dict["off_rating"]["penalty"]["poss"]],
									"off_points_p": [rating_dict["off_rating"]["penalty"]["points"]],})
			full_df = pd.concat([full_df, temp_df])

	# Aggregate data over each period
	team_df = pd.DataFrame(full_df.groupby("team_id")[["off_poss_p",
													   "off_points_p",
													   "off_poss_np",
													   "off_points_np"]].agg(["sum"])).reset_index()
	team_df.columns = ["team_id", "off_poss_p", "off_points_p", "off_poss_np", "off_points_np",]

	# Store points and possessions inside and outside of the penalty for a team
	# on the offensive and defensive side of the ball
	rating_df = pd.DataFrame({
		"team_id": teams,
		"off_points_p": [team_df[team_df["team_id"]==teams[0]]["off_points_p"].iloc[0],
						 team_df[team_df["team_id"]==teams[1]]["off_points_p"].iloc[0],],
		"off_poss_p": [team_df[team_df["team_id"]==teams[0]]["off_poss_p"].iloc[0],
						 team_df[team_df["team_id"]==teams[1]]["off_poss_p"].iloc[0],],
		"def_points_p": [team_df[team_df["team_id"]==teams[1]]["off_points_p"].iloc[0],
						 team_df[team_df["team_id"]==teams[0]]["off_points_p"].iloc[0],],
		"def_poss_p": [team_df[team_df["team_id"]==teams[1]]["off_poss_p"].iloc[0],
						 team_df[team_df["team_id"]==teams[0]]["off_poss_p"].iloc[0],],
		"off_points_np": [team_df[team_df["team_id"]==teams[0]]["off_points_np"].iloc[0],
						 team_df[team_df["team_id"]==teams[1]]["off_points_np"].iloc[0],],
		"off_poss_np": [team_df[team_df["team_id"]==teams[0]]["off_poss_np"].iloc[0],
						 team_df[team_df["team_id"]==teams[1]]["off_poss_np"].iloc[0],],
		"def_points_np": [team_df[team_df["team_id"]==teams[1]]["off_points_np"].iloc[0],
						 team_df[team_df["team_id"]==teams[0]]["off_points_np"].iloc[0],],
		"def_poss_np": [team_df[team_df["team_id"]==teams[1]]["off_poss_np"].iloc[0],
						 team_df[team_df["team_id"]==teams[0]]["off_poss_np"].iloc[0],]
		})

	return rating_df


def loop_through_games(start_date: str, end_date: str) -> pd.DataFrame:
	""" This function loops through dates and extracts
	team foul and penalty data for each game

	@param start_date (str): Date on which games of interest start
		(YYYY-MM-DD)
	@param end_date (str): Data on which games of interest end
		(YYYY-MM-DD)

	Returns:

		- total_df (DataFrame): DataFrame containing team performance
			and team penalty information
	"""

	total_df = pd.DataFrame()


	for x in pd.date_range(start=start_date, end=end_date):
		# Convert dates into properly formatted strings
		date_obj = x.date()
		date_str = date_obj.strftime("%m/%d/%Y")
		print("Pulling " + date_str + " games")
		game_id_list = get_game_ids(date_str)

		# Looping through games on each data
		for game_id in game_id_list:
			print("Processing: " + str(game_id))
			home_id, away_id, home_winner, line_score = pull_team_ids(game_id)
			time.sleep(4) # Give the NBA API a break
			if home_winner is not None:
				# Track team fouls
				penalty_dict, winner_id, pbp_df = team_foul_tracker(game_id, home_id, away_id, home_winner)
				# Extract team foul data of interest
				full_df = process_output(penalty_dict, winner_id)
				# Extract performance in/out of penalty
				rating_df = process_pbp(pbp_df, penalty_dict, home_id)

				# Store relevant information
				full_df["game_id"] = [game_id]*len(full_df)
				rating_df["game_id"] = [game_id]*len(rating_df)
				full_df = full_df.merge(rating_df, on=["game_id", "team_id"])
				total_df = pd.concat([total_df, full_df])

	return total_df


def parse_args():
	""" This function parses the command line arguments

	Returns:

		- args.start_date (str): Date on which games of interest start
			(YYYY-MM-DD)
		- args.end_date (str): Data on which games of interest end
			(YYYY-MM-DD)
	"""

	parser = argparse.ArgumentParser(description='Start and end dates')
	parser.add_argument('--start_date',
	                    help='Date on which games of interest start (YYYY-MM-DD)')
	parser.add_argument('--end_date',
	                    help='Date on which games of interest end (YYYY-MM-DD)')

	args = parser.parse_args()
	if not (args.start_date and args.end_date):
		raise Exception("Invalid args: must provde --start_date and --end_date")

	return args.start_date, args.end_date


def main():
	""" main, ya cowboy
	"""

	start_date, end_date = parse_args()
	total_df = loop_through_games(start_date, end_date)
	total_df.to_csv("team_fouls_" + start_date + "_to_" + end_date + ".csv", index=False)


if __name__ == "__main__":
	main()
