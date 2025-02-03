# config.py
class Config:
    QDRANT_URL = "https://2cb221d4-61ef-40a2-929b-189e39e9581d.europe-west3-0.gcp.cloud.qdrant.io:6333"
    QDRANT_API_KEY = "UgmWZlyD4_n7WLk60RzSND9VCk7hVZsqAZxVhUb6qOt9Gpj2uyMFAA"
    QDRANT_TIMEOUT = 60
    VECTOR_SIZE = 384
    COLLECTION_NAME = "users"
    # SerpAPI Configuration
    SERP_API_KEY = "b4e6f1dffcda9546771bc182c5a990c3433fcdbf29eb0be7a87831a7dfd40191"
    SERP_API_URL = "https://serpapi.com/search"
    MODEL_API_KEY = "AIzaSyAq2_DAPBH0vE8AOkYeO1tpe_z3ZD3AoXU"

    GAMES_COLLECTION = "games"
    MEM0_KEY= "m0-3zcPwM7bxovClqyk0jLGMoCmyNWpYLTLeFv2WgnR"
    PLAYERS_COLLECTION = "players"
    GAME_SCHEDULE_COLLECTION = "gameSchedules"

    FAVOURITE_PLAYERS_COLLECTION = "favouritePlayers"
    PROMPT = """You are an expert in Major League Baseball. Based on the user's question and the provided document for reference, generate a concise, but easy-to-understand response, using the response rules mentioned below:
        - Do not use phrases like 'given data', 'provided data', 'as per the document', etc.
        - Give the response in a single string

    User's Question:
    {}

    Document:
    {}

    Response in JSON format:
    {{"answer": "<YOUR ANSWER>"}}"""