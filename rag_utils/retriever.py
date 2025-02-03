def retrieve_documents(client, collection_name, query_embedding, top_k = 1):
    search_result = client.search(
        collection_name=collection_name,
        query_vector=query_embedding,
        limit=top_k
    )
    return search_result