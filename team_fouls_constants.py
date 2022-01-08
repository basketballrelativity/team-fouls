"""
team_fouls_constants.py

This function contains constants needed
to process team fouls
"""

# These indicate EVENTMSGACTIONTYPE values that increment team fouls
TEAM_FOUL_INDICATORS = [1, 2, 3, 5, 6, 9, 14, 15, 26, 27, 28, 29]
# These indicate EVENTMSGACTIONTYPE values that would result in FTAs only
# if a team is in the penalty
NON_SHOOTING_FOULS = [1, 3, 27, 28]

# League IDs
LEAGUE_ID_MAP = {"NBA": "00", "WNBA": "10", "G": "20"}
QUARTER_LENGTH = {"00": 720, "10": 600, "20": 720} # Quarter length in seconds
OT_LENGTH = {"00": 300, "10": 300, "20": 120} # OT period length in seconds

TWO_MINUTES = 120 # Seconds
QUARTERS = 4
