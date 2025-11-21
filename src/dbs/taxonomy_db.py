'''
TaxonomyDB module to manage taxonomy database operations.

Loads and manages the controlled taxonomy from taxonomy.json
Build FAISS embeddings for category search and validates classifier outputs.

Classes:
    TaxonomyDB:
        - load_taxonomy() -> dict
        - get_all_categories() -> list[dict]
        - get_category_by_id(cat_id:str) -> dict|None
        - search_category(name:str) -> list[dict]
        - embed_categories()
        - validate(name:str) -> bool
'''