import csv
import sys
import os
from dotenv import load_dotenv
import psycopg2
import google.generativeai as genai
from psycopg2.extras import execute_batch
import time
from pathlib import Path # Use Pathlib for a more robust path

# --- Imports remain at the top ---

class EmbeddingLoader:
    """
    A class to load documents from a CSV, generate embeddings using Gemini,
    and upsert them into a pgvector-enabled PostgreSQL database.
    """
    def __init__(self,
                 csv_path='./mcp_server/create_embeddings/public_apis.csv',
                 postgres_url="postgresql://postgres:password@localhost:5432/postgres",
                 table_name='public_apis',
                 embedding_model='text-embedding-004',
                 embedding_dim=768,
                 batch_size=100,
                 embedding_cols=['name', 'description', 'params'],
                 id_col='name'):
        
        # --- Configuration is now stored on the instance ---
        self.csv_path = csv_path
        self.postgres_url = postgres_url
        self.table_name = table_name
        self.embedding_model = embedding_model
        self.embedding_dim = embedding_dim
        self.batch_size = batch_size
        self.embedding_cols = embedding_cols
        self.id_col = id_col
        
        # --- State variables ---
        self.conn = None
        self.cur = None

    def _configure_gemini(self):
        """Configures the Gemini client using an environment variable."""
        print("Configuring Gemini...")
        gemini_api_key_env = "GOOGLE_API_KEY"
        
        # Use Pathlib for a more robust path
        try:
            script_dir = Path(__file__).resolve().parent
            env_path = script_dir.parent.parent / ".env.local"
        except NameError:
            # Fallback for interactive shells
            print("Warning: __file__ not defined. Using current directory.")
            env_path = Path.cwd() / ".env.local"

        print(f"Loading .env file from: {env_path}")
        load_dotenv(dotenv_path=env_path)
        
        api_key = os.environ.get(gemini_api_key_env)
        if not api_key:
            print(f"Error: {gemini_api_key_env} not set. Check your .env file.")
            raise ValueError(f"{gemini_api_key_env} not set")
        
        genai.configure(api_key=api_key)
        print("Gemini configured successfully. ✅")

    def _get_db_connection(self):
        """Connects to Postgres and sets up the table."""
        print("Connecting to PostgreSQL...")
        try:
            self.conn = psycopg2.connect(self.postgres_url)
            self.cur = self.conn.cursor()
            
            # 1. Enable pgvector extension
            self.cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            
            # 2. Create the table with the correct embedding dimension
            create_table_sql = f"""
            CREATE TABLE IF NOT EXISTS {self.table_name} (
                id SERIAL PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                content_for_embedding TEXT,
                embedding vector({self.embedding_dim}),
                url TEXT NOT NULL,
                params_description TEXT,
                response_shape TEXT
            );
            """
            self.cur.execute(create_table_sql)
            
            self.conn.commit()
            print(f"Database setup complete. Table '{self.table_name}' is ready. ✅")
        except Exception as e:
            print(f"Error connecting to or setting up database: {e}")
            print("Please ensure PostgreSQL is running, pgvector is installed, and credentials are correct.")
            raise # Re-raise the exception to stop execution

    def _process_and_embed_batch(self, batch):
        """Processes a batch of rows: embeds content via Gemini and upserts to DB."""
        
        # 1. Prepare data
        rows_for_upsert = []
        contents_to_embed = []
        
        for row in batch:
            try:
                content = " | ".join(
                    f"{col}: {row[col]}" for col in self.embedding_cols if row.get(col)
                ).strip()
                doc_id = row.get(self.id_col)
                
                if not content or not doc_id or not row.get('url'):
                    print(f"Skipping row: missing required name, content, or url. ID: {doc_id}")
                    continue
                
                contents_to_embed.append(content)
                rows_for_upsert.append({
                    "name": doc_id,
                    "content_for_embedding": content,
                    "url": row.get('url'),
                    "params_description": row.get('params'),
                    "response_shape": row.get('response_type_shape')
                })
                
            except KeyError as e:
                print(f"Warning: Missing column {e} in row. Skipping row.")

        if not contents_to_embed:
            print("No valid data in this batch to process.")
            return 0
            
        # 2. Generate embeddings using Gemini
        try:
            result = genai.embed_content(
                model=self.embedding_model,
                content=contents_to_embed,
                task_type="RETRIEVAL_DOCUMENT"
            )
            embeddings = result['embedding'] 
            
        except Exception as e:
            print(f"Error calling Gemini API: {e}")
            print("Retrying after 5 seconds...")
            time.sleep(5)
            try:
                result = genai.embed_content(
                    model=self.embedding_model,
                    content=contents_to_embed,
                    task_type="RETRIEVAL_DOCUMENT"
                )
                embeddings = result['embedding']
            except Exception as e2:
                print(f"Fatal error on batch embedding: {e2}")
                raise e2 # Raise error to be caught by run() for rollback

        
        # 3. Prepare for upsert
        upsert_sql = f"""
        INSERT INTO {self.table_name} (
            name, content_for_embedding, embedding, 
            url, params_description, response_shape
        )
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (name) DO UPDATE SET
            content_for_embedding = EXCLUDED.content_for_embedding,
            embedding = EXCLUDED.embedding,
            url = EXCLUDED.url,
            params_description = EXCLUDED.params_description,
            response_shape = EXCLUDED.response_shape;
        """
        
        records_to_upsert = [
            (
                row['name'],
                row['content_for_embedding'],
                emb,
                row['url'],
                row['params_description'],
                row['response_shape']
            ) for row, emb in zip(rows_for_upsert, embeddings)
        ]
        
        # 4. Execute batch upsert (let the 'run' method handle commit/rollback)
        execute_batch(self.cur, upsert_sql, records_to_upsert)
        return len(records_to_upsert)

    def run(self):
        """The main execution method to run the full embedding process."""
        try:
            self._configure_gemini()
            self._get_db_connection()
            
            total_rows_processed = 0
            
            print(f"Opening CSV file: {self.csv_path}...")
            with open(self.csv_path, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                batch = []
                for i, row in enumerate(reader):
                    batch.append(row)
                    if len(batch) >= self.batch_size:
                        print(f"Processing rows {i+1-self.batch_size} to {i+1}...")
                        try:
                            processed = self._process_and_embed_batch(batch)
                            self.conn.commit() # Commit after each successful batch
                            total_rows_processed += processed
                        except Exception as e:
                            print(f"Error processing batch, rolling back: {e}")
                            self.conn.rollback() # Rollback this failed batch
                        batch = [] # Reset batch
                
                # Process any remaining rows
                if batch:
                    print(f"Processing final {len(batch)} rows...")
                    try:
                        processed = self._process_and_embed_batch(batch)
                        self.conn.commit()
                        total_rows_processed += processed
                    except Exception as e:
                        print(f"Error processing final batch, rolling back: {e}")
                        self.conn.rollback()

        except FileNotFoundError:
            print(f"Error: CSV file not found at {self.csv_path}")
            sys.exit(1)
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            sys.exit(1)
        finally:
            if self.cur:
                self.cur.close()
            if self.conn:
                self.conn.close()
            print("Database connection closed.")
            print("--- Process Complete ---")
            print(f"Total documents successfully upserted: {total_rows_processed} 🚀")

# --- This is now the entry point ---
if __name__ == "__main__":
    try:
        loader = EmbeddingLoader() # You can override defaults here
        loader.run()
    except Exception as e:
        print(f"Failed to start loader: {e}")
        sys.exit(1)