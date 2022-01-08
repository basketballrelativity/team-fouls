"""
team_fouls_utils.py

This function contains helpful functions for
pulling in basketball data for use by
team_fouls.py
"""

from typing import Union, List, Dict
import pandas as pd

from py_ball import playbyplay, boxscore, scoreboard, player

from team_fouls_constants import TWO_MINUTES


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

def get_shot_data(season: str, game_id: str, league_id: str) -> List:
	""" get_game_ids returns the NBA game IDs
	that take place on the provided date

	@param season (str): Season in YYYY-ZZ format for NBA
		and G-League, YYYY format for WNBA
	@param game_id (str): Unique identifier for the game
	@param league_id (str): One of '00' (NBA), '10' (WNBA),
		'20' (G League)

	Returns:

		- shot_df (DataFrame): DataFrame containing all
			shot data
	"""

	shots = player.Player(headers=HEADERS,
                          endpoint='shotchartdetail',
                          league_id=league_id,
                          player_id='0',
                          game_id=game_id,
                          season=season)

	shot_df = pd.DataFrame(shots.data['Shot_Chart_Detail'])

	return shot_df


def get_game_ids(date: str, league_id: str) -> List:
	""" get_game_ids returns the NBA game IDs
	that take place on the provided date

	@param date (str): Date in MM/DD/YYYY format
	@param league_id (str): One of '00' (NBA), '10' (WNBA),
		'20' (G League)

	Returns:

		- game_id_list (list): List of game IDs
	"""

	scores = scoreboard.ScoreBoard(headers=HEADERS,
                               	   endpoint='scoreboardv2',
                                   league_id=league_id,
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


def add_fouls(foul_dict: Dict, period: int, quarter_time: int, team_id: int, penalty_dict: Dict) -> Dict:
	""" This function adds fouls to a team's total and their
	L2M total if applicable

	@param foul_dict (dict): Dictionary containing the number of fouls
		and L2M fouls a team has accumulated
	@param period (int): Game quarter (5 is OT1, 6 is OT2, etc.)
	@param quarter_time (int): Time remaining in the quarter
	@param team_id (int): Unique identifier of team committing a foul
	@param penalty_dict (dict): Dictionary containing team foul
		related data

	Returns:

		- foul_dict (int): Incremented number of team fouls
			and L2M fouls in the quarter
		- penalty_dict (dict): Dictionary containing updated
			team foul related data
	"""

	foul_dict["fouls"] += 1
	penalty_dict[team_id]["time_to_foul"][period][foul_dict["fouls"]] = foul_dict["last_foul_time"] - quarter_time
	foul_dict["last_foul_time"] = quarter_time
	if quarter_time <= TWO_MINUTES:
		foul_dict["l2m"] += 1

	return foul_dict, penalty_dict


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
