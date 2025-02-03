import hashlib
import uuid
import re
import requests
from datetime import datetime
from typing import List, Optional, Dict

class ValidationError(Exception):
    pass

class Utils:
    @staticmethod
    def generate_uuid():
        return str(uuid.uuid4())

    @staticmethod
    def hash_password(password):
        return hashlib.sha256(password.encode()).hexdigest()
    
    @staticmethod
    def validate_email(email):
        pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
        if not re.match(pattern, email):
            raise ValidationError("Invalid email format")
    
    @staticmethod
    def validate_password(password):
        if len(password) < 8:
            raise ValidationError("Password must be at least 8 characters long")

    @staticmethod
    def fetch_player_details(player_id):
        url = f"https://statsapi.mlb.com/api/v1/people/{player_id}"
        response = requests.get(url)
        
        if response.status_code != 200:
            raise Exception(f"Failed to fetch details for player ID: {player_id}")
        
        data = response.json().get("people", [])[0]
        
        return {
            "Player ID": player_id,
            "Name": data.get("fullName", "Unknown"),
            "Team": data.get("currentTeam", {}).get("name", "Free Agent"),
            "Position": data.get("primaryPosition", {}).get("name", "Unknown"),
            "Bats": data.get("batSide", {}).get("description", "Unknown"),
            "Throws": data.get("pitchHand", {}).get("description", "Unknown")
        }

        
    @staticmethod
    def fetch_team_roster(game_pk):
        # Fetch boxscore to get player IDs
        boxscore_url = f"https://statsapi.mlb.com/api/v1/game/{game_pk}/boxscore"
        response = requests.get(boxscore_url)
        
        if response.status_code != 200:
            raise Exception(f"Failed to fetch boxscore for game ID: {game_pk}")
        
        boxscore_data = response.json()
        
        # Prepare roster dictionaries for home and away teams
        game_roster = {
            "home_team": [],
            "away_team": []
        }
        
        # Home team players
        home_players = boxscore_data.get("teams", {}).get("home", {}).get("players", {})
        for player_id, player_data in home_players.items():
            player_details = Utils.fetch_player_details(player_id.split("ID")[1])
            game_roster["home_team"].append(player_details)
        
        # Away team players
        away_players = boxscore_data.get("teams", {}).get("away", {}).get("players", {})
        for player_id, player_data in away_players.items():
            player_details = Utils.fetch_player_details(player_id.split("ID")[1])
            game_roster["away_team"].append(player_details)
        
        return game_roster


    @staticmethod
    def fetch_boxscore_summary(game_pk):
        url = f"https://statsapi.mlb.com/api/v1/game/{game_pk}/boxscore"
        response = requests.get(url)
        data = response.json()

        # Extract game details
        home_team = data.get("teams", {}).get("home", {})
        away_team = data.get("teams", {}).get("away", {})

        # Parsing game summary details
        game_info = data.get("info", [])

        # Extracting player details (name and score)
        home_players = home_team.get("players", {})
        away_players = away_team.get("players", {})

        home_total_runs = 0
        away_total_runs = 0

        # Prepare data to upload to Qdrant
        boxscore_data = []

        # Add home team players to the collection
        for player_id, player in home_players.items():
            person = player.get("person", {})
            stats = player.get("stats", {}).get("batting", {})
            home_total_runs += stats.get("runs", 0)

            player_data = {
                "team": home_team.get("team", {}).get("name", "Home Team"),
                "player_id": person.get("id"),
                "full_name": person.get("fullName"),
                "role": "batter",
                "runs": stats.get("runs", 0),
                "hits": stats.get("hits", 0),
                "batting_average": stats.get("battingAverage", 0),
            }
            boxscore_data.append(player_data)

        # Add away team players to the collection
        for player_id, player in away_players.items():
            person = player.get("person", {})
            stats = player.get("stats", {}).get("batting", {})
            
            away_total_runs += stats.get("runs", 0)

            player_data = {
                "team": away_team.get("team", {}).get("name", "Away Team"),
                "player_id": person.get("id"),
                "full_name": person.get("fullName"),
                "role": "batter",
                "runs": stats.get("runs", 0),
                "hits": stats.get("hits", 0),
                "batting_average": stats.get("battingAverage", 0),
            }
            boxscore_data.append(player_data)

        return boxscore_data
       
    @staticmethod
    def calculate_player_points(boxscore_data, requested_player_ids):
        player_points = {}
        total_game_points = 0

        # Identify unique teams
        teams = list(set(player['team'] for player in boxscore_data))
        if len(teams) != 2:
            raise ValueError("Boxscore data should contain exactly two teams.")
        
        home_team, away_team = teams  # Assign the two teams

        # Calculate total runs for each team
        home_total_runs = sum(player['runs'] for player in boxscore_data if player['team'] == home_team)
        away_total_runs = sum(player['runs'] for player in boxscore_data if player['team'] == away_team)

        # Determine the winning team
        winning_team = home_team if home_total_runs > away_total_runs else away_team

        # Calculate points for each requested player
        for player in boxscore_data:
            if player['player_id'] not in requested_player_ids:
                continue

            # Base point calculations
            points = 0
            team_multiplier = 1.5 if player['team'] == winning_team else 1

            # Points for performance metrics
            points += player['runs'] * 2  # 2 points per run
            points += player['hits'] * 3  # 3 points per hit

            # Batting average bonus
            batting_average = player.get('batting_average', 0)
            if isinstance(batting_average, (int, float)):
                points += int(batting_average * 100)  # Bonus based on batting average

            # Final point calculation
            final_points = int(points * team_multiplier)

            # Update player points and total game points
            player_points[player['player_id']] = max(0, final_points)
            total_game_points += final_points

        return player_points, total_game_points


    @staticmethod
    def get_points_for_game(game_pk, requested_player_ids):
        # Fetch boxscore data
        boxscore_data = Utils.fetch_boxscore_summary(game_pk)
        
        # Calculate points
        player_points, total_game_points = Utils.calculate_player_points(
            boxscore_data, 
            requested_player_ids
        )

        return {
            "playerPoints": player_points,
            "totalGamePoints": total_game_points
        }

    