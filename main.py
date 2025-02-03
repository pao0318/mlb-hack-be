from fastapi import FastAPI, HTTPException,APIRouter, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from auth import AuthService
import requests
from utils import ValidationError,Utils
import google.generativeai as genai
from config import Config
from database import Database
import statsapi
from typing import List, Optional, Dict
import json
import uvicorn
import logging
import os


from rag_utils.embedder import generate_embedding
from rag_utils.qdrant_util import QdrantClient
from rag_utils.retriever import retrieve_documents
from mem0 import MemoryClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


client = MemoryClient(api_key=Config.MEM0_KEY)
genai.configure(api_key=Config.MODEL_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash", generation_config = {"response_mime_type": "application/json"})

qdrant_client = QdrantClient(
    url = Config.QDRANT_URL, 
    api_key = Config.QDRANT_API_KEY,
    timeout = Config.QDRANT_TIMEOUT
)
collection_name = Config.PLAYERS_COLLECTION
rag_prompt = Config.PROMPT

app = FastAPI(title="User Authentication API")
app.add_middleware(
    CORSMiddleware,
    # allow_origins=["http://localhost:3000"],
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
auth_service = AuthService()
db = Database()


class UserSignup(BaseModel):
    email: str
    name: str
    password: str
    fav_team: str

class YearRequest(BaseModel):
    year: int
    
class TeamRosterRequest(BaseModel):
    gameId: int
    homeTeamId: int
    awayTeamId: int

class PlayerStatsRequest(BaseModel):
    player_name: str
    season: int

class Player(BaseModel):
    name: str
    player_id: int
    jerseyNumber: str
    position: str
    teamId: int

class SaveFavouritePlayersRequest(BaseModel):
    team: str
    gameId: str
    userTaggedId: str
    players: List[Player]

class UserLogin(BaseModel):
    email: str
    password: str

class QueryRequest(BaseModel):
    query: str

class PointsRequest(BaseModel):
    gameId: str
    playerIds: List[int]

class UserQueryRAG(BaseModel):
    query: str



@app.post("/signup")
async def signup(user_data: UserSignup):
    try:
        result = auth_service.signup(
            email=user_data.email,
            name=user_data.name,
            password=user_data.password,
            fav_team=user_data.fav_team
        )
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/login")
async def login(user_data: UserLogin):
    try:
        result = auth_service.login(
            email=user_data.email,
            password=user_data.password
        )
        if not result["success"]:
            raise HTTPException(status_code=401, detail=result["message"])
        return result
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/previousGames")
def find_games(request: YearRequest):
    """
    Fetch games for the given year from MLB StatsAPI.
    """
    try:
        year = request.year
        games_from_api = statsapi.schedule(start_date=f"{year}-10-01", end_date=f"{year}-12-31")

        if not games_from_api:
            raise HTTPException(status_code=404, detail="No games found for the given year.")

        return {"games": games_from_api[:15]}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving games: {str(e)}")


@app.get("/upcomingGames")
def find_games():
    """
    Fetch games for the given year from MLB StatsAPI.
    """

    try:
        result = db.findUpcomingMatchesFromDB()
        return {"result":result}
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/fetchTeamRosters")
def fetch_team_rosters(team_request: TeamRosterRequest):
    try:
        # Fetch game roster containing both home and away team players
        game_roster = Utils.fetch_team_roster(team_request.gameId)
        
        return {
            "homeTeam": {
                "team_id": team_request.homeTeamId,
                "players": game_roster.get("home_team", []),
            },
            "awayTeam": {
                "team_id": team_request.awayTeamId,
                "players": game_roster.get("away_team", []),
            },
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"An unexpected error occurred: {str(e)}"
        )

@app.post("/saveSelectedPlayers")
async def save_favourite_players(request: SaveFavouritePlayersRequest):
    try:
        result = db.insert_fav_players(request)
        if not result.get("success", False):
            raise HTTPException(status_code=400, detail=result.get("message", "Save failed"))
        
        return result
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/findSelectedGames/{userTaggedId}")
def find_selectedGames(userTaggedId:str):
    try:
        result = db.fetchAllSelectedGames(userTaggedId)
        return {"result":result}
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/points")
def process_points_request(request: PointsRequest):
    try:
        return Utils.get_points_for_game(request.gameId, request.playerIds)
    except Exception as e:
        return {"error": str(e)}
    

@app.post("/search")
async def serpai(request: QueryRequest):
    query = request.query

    try:
        # Add the query to MemoryClient
        client.add(query, user_id="alex")
        
        # Search for the query in MemoryClient
        memory_result = client.search(query, user_id="alex")
        logger.info(f"MemoryClient search result: {memory_result}")

        # Prepare params for SerpAPI request
        params = {
            "q": query,
            "api_key": Config.SERP_API_KEY,
        }

        # Make the request to SerpAPI
        response = requests.get(Config.SERP_API_URL, params=params)
        response.raise_for_status() 

        serpapi_result = response.json()
        organic_results = serpapi_result.get("organic_results", [])

        if organic_results:
            # Return the first organic result
            return organic_results[0]
        else:
            logger.warning(f"No organic results found for query: {query}")
            raise HTTPException(status_code=404, detail="No results found")

    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch results from SerpAPI: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch results from SerpAPI")

    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred")

@app.post("/generate-response")
async def generate_response(request: QueryRequest):
    """Generate a response using the Generative AI model."""
    content = request.query
    try:
        # Generate the content
        ai_response = model.generate_content(content)

        # Extract relevant data from the response
        response_data = {
            "query": content ,
            "ai_response": ai_response.text if ai_response.text else "No response generated."
        }

        return response_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating AI response: {str(e)}")

# Step 3: FastAPI route for RAG response
@app.post("/getResponseFromRAG")
def get_response_from_rag(request: UserQueryRAG):
    try:
        user_query = request.query
   
         # Step 1: Ask model which collection(s) to query
        collection_decision = determine_relevant_collection(user_query)
        # Step 2: Generate query embedding
        query_embedding = generate_embedding(user_query)

        # Step 3: Retrieve only relevant documents
        game_docs, player_docs = [], []
        if collection_decision in ["games", "both"]:
            game_docs = retrieve_documents(qdrant_client, Config.GAMES_COLLECTION, query_embedding)
        if collection_decision in ["players", "both"]:
            player_docs = retrieve_documents(qdrant_client, Config.PLAYERS_COLLECTION, query_embedding)

        # Step 4: Summarize retrieved documents using Config.PROMPT
        summary = summarize_documents(user_query, game_docs, player_docs)
        print(f"Generated summary: {summary}")

        return {"response": summary}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")



def summarize_documents(query: str, game_docs: List[dict], player_docs: List[dict]) -> str:
    """ Summarizes retrieved game and player details for a response. """

    # Extract relevant info from retrieved documents
    document_texts = []
    for doc in game_docs + player_docs:  
        payload = getattr(doc, "payload", {})  
        payload_str = json.dumps(payload, indent=2)  
        document_texts.append(payload_str)

    # Merge retrieved documents into a single text block
    retrieved_text = "\n".join(document_texts)

    # Use the predefined structured prompt from Config
    formatted_prompt = Config.PROMPT.format(query, retrieved_text)

    try:
        response = model.generate_content(formatted_prompt)
    except Exception as e:
        print("Caught thiw.", e)

    # Ensure JSON output compliance
    return response.text if response else '{"answer": "Failed to generate summary."}'


def determine_relevant_collection(query: str) -> str:
    """ Ask the model whether the query relates to games, players, or both. """
    
    classification_prompt = f"""
    You are an expert in Major League Baseball. Determine whether the following user query is related to:
    - "games" (if it is about match results, scores, teams, or events)
    - "players" (if it is about individual player statistics, performance, or records)
    - "both" (if it requires information from both categories)
    
    User Query: {query}
    
    Respond with only one word: "games", "players", or "both".
    """

    response = model.generate_content(classification_prompt)
    return response.text.strip().lower()

@app.post("/playerCareerStats")
def get_player_career_stats(payload: PlayerStatsRequest):
    """
    Fetch the career stats of a specific player using their name.

    :param payload: Request payload containing player_name and season.
    :return: JSON containing player's career stats or an error message.
    """
    try:
        # Fetch all players for the given season
        players = statsapi.get(
            "sports_players", {"season": payload.season, "gameType": "R"}
        )["people"]

        # Find the player by full name
        player = next(
            (p for p in players if p["fullName"].lower() == payload.player_name.lower()),
            None,
        )

        if not player:
            raise HTTPException(
                status_code=404,
                detail=f"Player '{payload.player_name}' not found for season {payload.season}.",
            )

        # Fetch player's career stats (hitting)
        player_id = player["id"]
        raw_stats = statsapi.player_stats(player_id, "hitting", "career")

        # Parse the stats text response into a structured JSON
        stats = parse_career_stats(raw_stats)

        return stats
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred: {str(e)}",
        )


def parse_career_stats(stats_text: str) -> dict:
    stats_lines = stats_text.split("\n")
    parsed_stats = {}

    # Parse each line for key-value pairs
    for line in stats_lines:
        if ": " in line:
            key, value = line.split(": ", 1)
            key = key.strip()
            value = value.strip()

            # Convert numeric values where possible
            if value.replace(".", "", 1).isdigit():
                value = float(value) if "." in value else int(value)

            parsed_stats[key] = value

    return parsed_stats


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)