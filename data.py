import requests
import aiohttp
import asyncio
import logging
from tqdm import tqdm
from qdrant_client import QdrantClient
from qdrant_client.http import models
from config import Config

# Setup logging
logging.basicConfig(level=logging.INFO)

# Initialize Qdrant client
qdrant_client = QdrantClient(url=Config.QDRANT_URL) 

# Define the collection name
COLLECTION_NAME = "boxscore"

def fetch_schedule_for_year(sport_id, year):
    base_url = "https://statsapi.mlb.com/api/v1/schedule"
    params = {
        "sportId": sport_id,
        "startDate": f"{year}-01-01",
        "endDate": f"{year}-12-31",
    }
    schedule_collection = []

    while True:
        response = requests.get(base_url, params=params)
        data = response.json()

        # Extract games and add them to the collection
        for date in data.get("dates", []):
            for game in date.get("games", []):
                game_data = {
                    "gamePk": game.get("gamePk")
                }
                schedule_collection.append(game_data)

        # Check if there's a next page of data (pagination)
        if "next" in data.get("links", {}):
            # Get the next URL
            next_url = data.get("links", {}).get("next", {}).get("href")
            params = {}  # reset params, we will use the next URL directly
            base_url = next_url  # Update the base URL to the next page URL
        else:
            # No more pages, break out of the loop
            break

    return schedule_collection

def fetch_schedule_for_years(sport_id, start_year, end_year):
    all_schedule_data = []
    for year in range(start_year, end_year + 1):
        print(f"Fetching data for year: {year}")
        yearly_schedule = fetch_schedule_for_year(sport_id, year)
        all_schedule_data.extend(yearly_schedule)

    return all_schedule_data


async def fetch_boxscore_summary(session, game_pk, max_retries=3):
    url = f"https://statsapi.mlb.com/api/v1/game/{game_pk}/boxscore"
    retries = 0
    
    while retries < max_retries:
        try:
            async with session.get(url, timeout=30) as response:  # Add per-request timeout
                if response.status != 200:
                    logging.warning(f"⚠️ Skipping {game_pk}, HTTP Status: {response.status}")
                    return None  
                
                content_type = response.headers.get("Content-Type", "")
                if "application/json" not in content_type:
                    logging.warning(f"⚠️ Unexpected content for {game_pk}, skipping")
                    return None
                
                data = await response.json()
                
                return {
                    "gamePk": game_pk,
                    "teams": data.get("teams", {}),
                    "info": data.get("info", {}),
                    "topPerformers": data.get("topPerformers", {})
                }
        
        except asyncio.TimeoutError:
            logging.warning(f"⏳ Timeout for {game_pk}, retrying {retries + 1}/{max_retries}")
        except aiohttp.ClientError as e:
            logging.warning(f"⚠️ Network error for {game_pk}: {e}")
        except aiohttp.ContentTypeError:
            logging.warning(f"⚠️ Content error for {game_pk}, skipping")
            return None  
        
        retries += 1
        await asyncio.sleep(2)  
    
    logging.warning(f"❌ Max retries reached for {game_pk}, skipping")
    return None  


async def process_batch(game_pks, batch_size=100):
    boxscore_collections = []
    async with aiohttp.ClientSession() as session:
        for i in tqdm(range(0, len(game_pks), batch_size), desc="Processing batches"):
            batch = game_pks[i:i + batch_size]
            tasks = [fetch_boxscore_summary(session, game_pk['gamePk']) for game_pk in batch]
            results = await asyncio.gather(*tasks)

            # Filter out None values (failed fetches)
            valid_results = [res for res in results if res]
            boxscore_collections.extend(valid_results)
    
    return boxscore_collections

def push_data_to_qdrant(boxscore_collections):
    # Prepare data for Qdrant
    points = []
    for idx, boxscore in enumerate(boxscore_collections):
        points.append(
            models.PointStruct(
                id=idx + 1,
                vector=[0.1]*Config.VECTOR_SIZE,  
                payload=boxscore  
            )
        )

    # Insert data into Qdrant
    qdrant_client.upsert(
        collection_name=COLLECTION_NAME,
        points=points,
    )
    print(f"Inserted {len(points)} records into Qdrant collection '{COLLECTION_NAME}'.")


# Example usage
if __name__ == "__main__":
    sport_id = 1
    start_year = 2008
    end_year = 2024

    # Fetch schedule data
    schedule_data = fetch_schedule_for_years(sport_id, start_year, end_year)

    # Run async process
    async def main():
        return await process_batch(schedule_data, batch_size=100)

    boxscore_collections = asyncio.run(main())

    # Push data to Qdrant
    push_data_to_qdrant(boxscore_collections)
