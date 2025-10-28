import pandas as pd
from sentence_transformers import SentenceTransformer

# 1. Load your model (choose one that suits your needs, e.g., 'all-MiniLM-L6-v2' is fast and good)
#    You might need to download this model the first time it's used.
model = SentenceTransformer('all-MiniLM-L6-v2')

# 2. Define the path to your input CSV and output CSV
input_csv_path = '/home/aviratha/Desktop/test/input_data/postgresql_docs_kb.csv'
output_csv_path = '/home/aviratha/Desktop/test/input_data/postgresql_docs_kb_with_embeddings.csv'

# 3. Read the CSV
df = pd.read_csv(input_csv_path)

# 4. Generate embeddings for the 'content' column
#    You can also combine 'title' and 'content': df['title'] + " " + df['content']
print(f"Generating embeddings for {len(df)} documents...")
embeddings = model.encode(df['content'].tolist(), show_progress_bar=True)

# The embeddings are numpy arrays. pgvector expects them as string representations like '[x,y,z]'
# We need to convert each numpy array to a string.
df['embedding'] = [list(e) for e in embeddings] # Convert numpy array to list, then Pandas will store it nicely

# 5. Save the DataFrame with the new 'embedding' column to a new CSV
df.to_csv(output_csv_path, index=False)

print(f"Embeddings generated and saved to: {output_csv_path}")
print(f"Sample row with embedding:\n{df.head(1).to_string()}")

# You'll also need to know the dimension of your embeddings for the PostgreSQL table creation.
# For 'all-MiniLM-L6-v2', the dimension is 384.
embedding_dimension = embeddings.shape[1]
print(f"Embedding dimension: {embedding_dimension}")