"""
phase3_embed.py
Converts every chunk into a vector embedding using a free local
sentence-transformers model and stores all vectors in Pinecone.

No API key needed for embeddings — runs entirely on your machine.

Usage:
    python phase3_embed.py
"""

import os
import psycopg2
from dotenv import load_dotenv
from pinecone import Pinecone, ServerlessSpec
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

load_dotenv()

DATABASE_URL     = os.getenv("DATABASE_URL")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
INDEX_NAME       = os.getenv("PINECONE_INDEX_NAME", "fund-docs")

# Free local embedding model — downloads once (~90MB), runs offline after
EMBEDDING_MODEL  = "all-MiniLM-L6-v2"
EMBEDDING_DIM    = 384   # dimension for all-MiniLM-L6-v2
BATCH_SIZE       = 50    # chunks per Pinecone upsert batch

def get_or_create_index(pc):
    """Create Pinecone index if it doesn't exist."""
    existing = [idx.name for idx in pc.list_indexes()]
    if INDEX_NAME not in existing:
        print(f"  Creating Pinecone index '{INDEX_NAME}'...")
        pc.create_index(
            name=INDEX_NAME,
            dimension=EMBEDDING_DIM,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1")
        )
        print(f"  Index created.")
    else:
        print(f"  Index '{INDEX_NAME}' already exists.")
    return pc.Index(INDEX_NAME)

def run_embedding():
    if not DATABASE_URL:
        raise EnvironmentError("DATABASE_URL not set in .env")
    if not PINECONE_API_KEY:
        raise EnvironmentError("PINECONE_API_KEY not set in .env")

    # ── LOAD EMBEDDING MODEL ──────────────────────────────────────────────
    print("\nLoading embedding model (downloads ~90MB on first run)...")
    model = SentenceTransformer(EMBEDDING_MODEL)
    print(f"  Model loaded: {EMBEDDING_MODEL} (dim={EMBEDDING_DIM})")

    # ── CONNECT TO PINECONE ───────────────────────────────────────────────
    print("\nConnecting to Pinecone...")
    pc    = Pinecone(api_key=PINECONE_API_KEY)
    index = get_or_create_index(pc)
    print(f"  Connected to index '{INDEX_NAME}'")

    # ── CONNECT TO DATABASE ───────────────────────────────────────────────
    print("\nConnecting to database...")
    conn = psycopg2.connect(DATABASE_URL)
    cur  = conn.cursor()

    # Load all chunks
    cur.execute("""
        SELECT chunk_id, document_id, filename, manager_name,
               asset_class, doc_type, doc_date::text, file_extension,
               chunk_index, page_number, text
        FROM chunks
        ORDER BY document_id, chunk_index
    """)
    chunks = cur.fetchall()
    cur.close()
    conn.close()

    if not chunks:
        print("No chunks found. Run phase2_chunk.py first.")
        return

    print(f"\nEmbedding {len(chunks)} chunks into Pinecone...\n")

    # ── EMBED AND UPSERT IN BATCHES ───────────────────────────────────────
    total_upserted = 0
    batch_texts    = []
    batch_meta     = []

    for chunk in tqdm(chunks, desc="Embedding", unit="chunk"):
        (chunk_id, doc_id, filename, manager, asset, dtype,
         doc_date, ext, chunk_idx, page_num, text) = chunk

        batch_texts.append(text)
        batch_meta.append({
            "chunk_id":      chunk_id,
            "document_id":   doc_id,
            "filename":      filename,
            "manager_name":  manager,
            "asset_class":   asset,
            "doc_type":      dtype,
            "doc_date":      str(doc_date),
            "file_extension": ext,
            "chunk_index":   chunk_idx,
            "page_number":   page_num if page_num else 1,
        })

        # When batch is full, embed and upsert
        if len(batch_texts) >= BATCH_SIZE:
            embeddings = model.encode(batch_texts, show_progress_bar=False)
            vectors = [
                (meta["chunk_id"], emb.tolist(), meta)
                for emb, meta in zip(embeddings, batch_meta)
            ]
            index.upsert(vectors=vectors)
            total_upserted += len(vectors)
            batch_texts = []
            batch_meta  = []

    # Upsert any remaining chunks
    if batch_texts:
        embeddings = model.encode(batch_texts, show_progress_bar=False)
        vectors = [
            (meta["chunk_id"], emb.tolist(), meta)
            for emb, meta in zip(embeddings, batch_meta)
        ]
        index.upsert(vectors=vectors)
        total_upserted += len(vectors)

    # ── VERIFY ────────────────────────────────────────────────────────────
    stats = index.describe_index_stats()
    total_in_index = stats.get("total_vector_count", 0)

    print(f"\n{'=' * 70}")
    print("EMBEDDING COMPLETE")
    print(f"{'=' * 70}")
    print(f"  Chunks embedded    : {total_upserted}")
    print(f"  Vectors in Pinecone: {total_in_index}")
    print(f"  Embedding model    : {EMBEDDING_MODEL}")
    print(f"  Vector dimensions  : {EMBEDDING_DIM}")

    if total_upserted == len(chunks):
        print(f"\n  ✅  All chunks embedded successfully.")
        print(f"      Run next: python phase4_query.py")
    else:
        print(f"\n  ⚠️  Expected {len(chunks)} but upserted {total_upserted} — re-run to retry.")
    print(f"{'=' * 70}\n")

if __name__ == "__main__":
    run_embedding()
