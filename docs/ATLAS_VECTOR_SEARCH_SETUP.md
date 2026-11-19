# MongoDB Atlas Vector Search Index Configuration

OpsSage AI uses MongoDB Atlas Vector Search for semantic retrieval of historical incidents (RAG, Module 5).

## Prerequisites
- MongoDB Atlas cluster (M10+ or Atlas Serverless/Shared cluster with Search support).
- Database name: `opssage_ai` (or configured `MONGODB_DB_NAME`).
- Collection name: `knowledge_base`.

## Atlas Vector Search Index Definition

In the MongoDB Atlas UI:
1. Navigate to your Cluster -> **Atlas Search** tab (or **Vector Search**).
2. Click **Create Search Index**.
3. Select **JSON Editor** under **Atlas Vector Search**.
4. Select the Database: `opssage_ai` and Collection: `knowledge_base`.
5. Name the index: `vector_index_knowledge_base` (must match `ATLAS_VECTOR_INDEX_NAME` in `.env`).
6. Paste the following JSON definition:

```json
{
  "name": "vector_index_knowledge_base",
  "type": "vectorSearch",
  "fields": [
    {
      "type": "vector",
      "path": "embedding",
      "numDimensions": 384,
      "similarity": "cosine"
    },
    {
      "type": "filter",
      "path": "user_id"
    },
    {
      "type": "filter",
      "path": "service_name"
    },
    {
      "type": "filter",
      "path": "environment"
    }
  ]
}
```

7. Click **Create Vector Search Index** and wait for the status to show **Active**.

## Programmatic Verification

To check whether the index is active, run:
```powershell
.venv\Scripts\python.exe -m scripts.verify_vector_index
```
Or execute a test vector search query through the API.
