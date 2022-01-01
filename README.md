# team-fouls
Exploration and modeling of team foul accumulation in professional basketball

## Instructions

`team_fouls.py` ingests a `--start_date` and `--end_date` command line argument to loop through NBA games played between those dates (inclusive). For each game, the script iterates over play-by-play data and extracts data related to team fouls accumulated by team and quarter, along with team performance in and out of the penalty. The output is a `.csv` file written to the local directory in the format `team_fouls_[start_date]_to_[end_date].csv`. Here's an example of how to run the script:

```
python team_fouls.py --start_date 2020-12-22 --end_date 2021-05-16
```

The above would run through each game in the 2020-21 NBA regular season.
