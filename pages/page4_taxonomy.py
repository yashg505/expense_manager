
import streamlit as st
import pandas as pd
from expense_manager.dbs.taxonomy_db import TaxonomyDB
from expense_manager.sync.taxonomy_sync import TaxonomySync
from expense_manager.utils.embed_texts import embed_texts
from expense_manager.logger import get_logger

logger = get_logger(__name__)

st.set_page_config(page_title="Taxonomy Management", layout="wide")

st.title("🏷️ Taxonomy Management")
st.write("View and manage the expense classification taxonomy.")

db = TaxonomyDB()

# --- Sidebar Actions ---
st.sidebar.header("Actions")
if st.sidebar.button("🔄 Sync from Google Sheets", use_container_width=True):
    with st.spinner("Syncing taxonomy..."):
        try:
            syncer = TaxonomySync()
            success = syncer.sync()
            if success:
                st.sidebar.success("Taxonomy synced successfully!")
                st.cache_data.clear() # Clear any cached data
            else:
                st.sidebar.error("Sync failed. Check logs.")
        except Exception as e:
            st.sidebar.error(f"Error during sync: {e}")

# --- Search ---
st.header("Search Taxonomy")
search_query = st.text_input("Enter a keyword or description to search in taxonomy:")

if search_query:
    with st.spinner("Searching..."):
        try:
            # Generate embedding for search query
            query_embedding = embed_texts([search_query])[0]
            
            # Search in DB
            results = db.search_vector(query_embedding, k=10)
            
            if results:
                st.write(f"Top results for '{search_query}':")
                result_ids = [r["row_id"] for r in results]
                
                # Fetch full rows for these IDs
                all_rows = db.get_all_rows()
                matched_rows = [row for row in all_rows if row["id"] in result_ids]
                
                # Sort matched_rows by the order of result_ids to maintain distance ranking
                matched_rows.sort(key=lambda x: result_ids.index(x["id"]))
                
                # Add score to rows for display
                for i, row in enumerate(matched_rows):
                    row["match_score"] = round(1 - results[i]["score"], 4) # Simple 1-distance score
                
                df_results = pd.DataFrame(matched_rows)
                # Reorder columns to show score and path first
                cols = ["match_score", "full_path", "category", "sub_category_i", "sub_category_ii", "description"]
                st.dataframe(df_results[cols], use_container_width=True)
            else:
                st.warning("No matches found.")
        except Exception as e:
            st.error(f"Search failed: {e}")

# --- Full Taxonomy View ---
st.divider()
st.header("All Taxonomy Entries")

@st.cache_data
def get_taxonomy_data():
    return db.get_all_df()

df = get_taxonomy_data()

if not df.empty:
    st.write(f"Total entries: {len(df)}")
    
    # Filter by category
    categories = ["All"] + sorted(df["category"].unique().tolist())
    selected_cat = st.selectbox("Filter by Category:", categories)
    
    display_df = df.copy()
    if selected_cat != "All":
        display_df = display_df[display_df["category"] == selected_cat]
    
    # Drop embedding column for display
    if "embedding" in display_df.columns:
        display_df = display_df.drop(columns=["embedding"])
        
    st.dataframe(display_df, use_container_width=True)
else:
    st.info("No taxonomy data found in database. Please sync from Google Sheets.")

# --- Navigation ---
st.sidebar.divider()
if st.sidebar.button("⬅️ Back to Upload", use_container_width=True):
    st.switch_page("main.py")
