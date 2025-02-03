from qdrant_client import QdrantClient
from qdrant_client.http import models
from config import Config
import uuid

class Database:
    def __init__(self):
        self.client = QdrantClient(
            url=Config.QDRANT_URL,
            api_key=Config.QDRANT_API_KEY
        )

    def find_user_by_email(self, email):
        """Find a user by email"""
        result = self.client.scroll(
            collection_name=Config.COLLECTION_NAME,
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="email",
                        match=models.MatchValue(value=email)
                    )
                ]
            )
        )
        return result[0][0].payload if result[0] else None

    def insert_user(self, user_data):
        """Insert a new user"""
        try:
            self.client.upsert(
                collection_name=Config.COLLECTION_NAME,
                points=[
                    models.PointStruct(
                        id=user_data["user_id"],
                        vector=[0.1] * Config.VECTOR_SIZE,
                        payload=user_data
                    )
                ]
            )
            return True
        except Exception as e:
            print(f"Insert error: {e}")
            return False

    def findUpcomingMatchesFromDB(self):
        """Find 5 upcoming matches from the database."""
        try:
            result, next_page = self.client.scroll(
                collection_name=Config.GAMES_COLLECTION,
                scroll_filter=models.Filter(
                    must=[
                    ]
                ),
                limit=10
            )
            return [item.payload for item in result] if result else []
        except Exception as e:
            print(f"Error finding matches: {e}")
            return []

    def insert_fav_players(self, request):
        """Insert favourite players as a single point"""
        try:
            # Prepare payload with all players
            payload = {
                "team": request.team,
                "players": [player.model_dump() for player in request.players],
                "userTaggedId":request.userTaggedId,
                "gameId": request.gameId
            }
            
            # Upsert as a single point
            self.client.upsert(
                collection_name=Config.FAVOURITE_PLAYERS_COLLECTION,
                points=[
                    models.PointStruct(
                        id=str(uuid.uuid4()),
                        vector=[0.1] * Config.VECTOR_SIZE,
                        payload=payload
                    )
                ]
            )
            
            return {
                "success": True, 
                "message": f"{len(request.players)} players saved",
                "count": len(request.players)
            }
        except Exception as e:
            print(f"Insert error: {e}")
            return {
                "success": False, 
                "message": str(e)
            }

    def fetchAllSelectedGames(self, userTaggedId):
        """Find selected Games by userTaggedId"""
        try:
            # Use scroll to fetch all records matching the filter
            result = self.client.scroll(
                collection_name=Config.FAVOURITE_PLAYERS_COLLECTION,
                scroll_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="userTaggedId",
                            match=models.MatchValue(value=userTaggedId)
                        )
                    ]
                )
            )

            return result[0]
        except Exception as e:
            print(f"Error fetching selected games: {e}")
            return []  # Return empty list on error

