from src.dbs.taxonomy_db import TaxonomyDB

def main():
    print("Hello from expense-manager!")

    taxonomy = TaxonomyDB()
    cats = taxonomy.get_row_by_id(1)
    print(cats)
    

if __name__ == "__main__":
    main()
