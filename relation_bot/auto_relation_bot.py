from config import MAIN_DATABASE, RELATION_BOT_DATABASE, NETWORK_SERVER_URL
import httpx
import sqlite3
import random

class AutoRelationBot:
    def __init__(self):
        self.start_node_id = AutoRelationBot.set_start_node_id()
        self.httpx_client = httpx.Client(timeout=10.0)

    @staticmethod
    def set_start_node_id():
        """Set the start node ID for the bot."""
        with sqlite3.connect(MAIN_DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT community FROM subjects WHERE community IS NOT NULL")
            result = cursor.fetchall()
            communities = [c[0] for c in result]
            
            if not communities:
                raise ValueError("No communities found in the subjects table.")
            
            random_community = random.choice(communities)
            print(f"Selected random community: {random_community}")

            cursor.execute("SELECT node_id FROM subjects WHERE community = ? ORDER BY priority_score DESC", (random_community,))
            result = cursor.fetchall()
            if not result:
                raise ValueError(f"No nodes found in the community: {random_community}")
            
            top_50_percent = result[:max(1, len(result)//2)]
            start_node_id = random.choice(top_50_percent)[0]

            print(f"Start node ID set to: {start_node_id}")
            return start_node_id
    
    def get_random_node_id(self) -> str:
        """Fetch a random node ID from the subjects table."""
        with sqlite3.connect(MAIN_DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT node_id FROM subjects ORDER BY RANDOM() LIMIT 1")
            result = cursor.fetchone()
            if result:
                return result[0]
            else:
                raise ValueError("No nodes found in the subjects table.")
    
    def get_neighbors(self, node_id: str) -> list[str]:
        """Fetch neighbors of the given node ID."""
        response = self.httpx_client.get(
                f"{NETWORK_SERVER_URL}/node/neighbors",
                params={"node_id": node_id}
            )
        response.raise_for_status()
        response_data = response.json()
        nodes = response_data.get("nodes", [])
        if not nodes:
            print(f"No neighbors found for node ID: {node_id}")
            return []
        
        neighbors = [node["node_id"] for node in nodes if "node_id" in node]
        print(f"Found {len(neighbors)} neighbors for node ID: {node_id}")
        return neighbors
    

        
if __name__ == "__main__":
    bot = AutoRelationBot()
    print(bot.get_neighbors(bot.start_node_id))