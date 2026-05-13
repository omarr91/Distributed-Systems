from sentence_transformers import SentenceTransformer
import faiss
import numpy as np

# =========================================================
# 1. LOAD EMBEDDING MODEL
# =========================================================

embed_model = SentenceTransformer(
    "BAAI/bge-small-en-v1.5"
)

# =========================================================
# 2. DOCUMENT
# =========================================================

document = """
Retrieval-Augmented Generation (RAG) is an AI framework
that retrieves relevant information from external documents
before generating a response using a language model.

RAG improves factual accuracy and reduces hallucinations.
FAISS is commonly used for vector similarity search.
"""

# =========================================================
# 3. CHUNKING
# =========================================================

def chunk_text(text, size=120, overlap=30):
    chunks = []

    start = 0

    while start < len(text):
        end = start + size
        chunks.append(text[start:end])

        start += size - overlap

    return chunks

chunks = chunk_text(document)

# =========================================================
# 4. CREATE EMBEDDINGS
# =========================================================

embeddings = embed_model.encode(
    chunks,
    convert_to_numpy=True
)

# Normalize for cosine similarity
faiss.normalize_L2(embeddings)

# =========================================================
# 5. CREATE FAISS INDEX
# =========================================================

dimension = embeddings.shape[1]

index = faiss.IndexFlatIP(dimension)

index.add(embeddings)

# =========================================================
# 6. RETRIEVAL FUNCTION
# =========================================================

def retrieve(query, k=2):

    query_embedding = embed_model.encode(
        [query],
        convert_to_numpy=True
    )

    faiss.normalize_L2(query_embedding)

    scores, indices = index.search(query_embedding, k)

    results = []

    for i in indices[0]:
        results.append(chunks[i])

    return results

# =========================================================
# 7. TEST RETRIEVAL
# =========================================================

query = "What does RAG do?"

results = retrieve(query)

print("\nRetrieved Chunks:\n")

for i, chunk in enumerate(results, 1):
    print(f"{i}. {chunk}\n")