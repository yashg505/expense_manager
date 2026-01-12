import sys
from typing import Optional, List, Dict, Any

from expense_manager.dbs.taxonomy_db import TaxonomyDB
from expense_manager.dbs.corrections_db import CorrectionsDB
from expense_manager.dbs.main_db import MainDB
from expense_manager.utils.embed_texts import embed_texts
from expense_manager.models import ClassificationResult, ClassificationChoice
from expense_manager.logger import get_logger
from expense_manager.exception import CustomException

logger = get_logger(__name__)

CLASSIFIER_PROMPT = """
You are an expert at classifying receipt items into a specific taxonomy.
Given an item name, its generic type, and a list of potential categories from our taxonomy, select the most appropriate category ID.

Item: "{item_name}"
Type: "{item_type}"

Candidates:
{candidates_text}

Instructions:
1. Select the ID of the category that best fits the item.
2. If none of the categories are a good fit, return "NONE".
3. Only return the ID or "NONE", nothing else.
"""

class ClassifierAgent:
    """
    Orchestrates the multi-step classification waterfall:
    1. Corrections DB (Exact Shop + Item)
    2. Historical Items (Exact Shop + Item)
    3. Taxonomy RAG (Item Name Vector)
    4. Taxonomy RAG (Item Type Vector)
    5. Fallback (Uncategorized)
    """

    def __init__(self, llm_client=None):
        try:
            self.taxonomy_db = TaxonomyDB()
            self.corrections_db = CorrectionsDB()
            self.main_db = MainDB()
            self.llm_client = llm_client

            
            logger.info("ClassifierAgent initialized with enhanced waterfall logic.")
        except Exception as e:
            logger.error(f"Failed to initialize ClassifierAgent: {e}")
            raise CustomException(e, sys)

    def classify_item(self, item_name: str, shop_name: str = "Unknown", item_type: str = "Unknown") -> ClassificationResult:
        """
        Runs the full classification waterfall.
        """
        try:
            if not item_name or not item_name.strip():
                return self._uncategorized_result()

            # STEP 1: Corrections DB (Exact Shop + Item Match)
            correction_id = self.corrections_db.get_correction(shop_name, item_name)
            if correction_id:
                logger.info(f"Step 1 Hit (Correction): [{shop_name}] '{item_name}' -> {correction_id}")
                return self._build_result(correction_id, 1.0)

            logger.info(f"Step 1 Fail: No correction found for [{shop_name}] '{item_name}'")
            # STEP 2: Historical Items (Exact Shop + Item Match)
            history_id = self.main_db.get_historical_exact_match(shop_name, item_name)
            if history_id:
                logger.info(f"Step 2 Hit (History Exact): [{shop_name}] '{item_name}' -> {history_id}")
                return self._build_result(history_id, 1.0)

            logger.info(f"Step 2 Fail: No historical match found for [{shop_name}] '{item_name}'")
            # --- Vector Search Candidates ---
            candidates = []
            
            # STEP 3: Taxonomy Match (Item Name Vector)
            item_vector = embed_texts([item_name])
            item_candidates = self.taxonomy_db.search_vector(item_vector, k=3)
            candidates.extend(item_candidates)

            logger.info(f"Step 3: Found {len(item_candidates)} candidates from item name vector search.")
            
            # STEP 4: Taxonomy Match (Item Type Vector)
            if item_type and item_type.lower() != "unknown":
                type_vector = embed_texts([item_type])
                type_candidates = self.taxonomy_db.search_vector(type_vector, k=2)
                candidates.extend(type_candidates)

                logger.info(f"Step 4: Found {len(type_candidates)} candidates from item type vector search.")
            # Deduplicate candidates by row_id
            seen_ids = set()
            unique_candidates = []
            for c in candidates:
                if c["row_id"] not in seen_ids:
                    unique_candidates.append(c)
                    seen_ids.add(c["row_id"])

            if unique_candidates:
                # STEP 5: LLM Decision (if available)
                if self.llm_client:
                    chosen_id = self._llm_choose(item_name, item_type, unique_candidates)
                    if chosen_id and chosen_id != "NONE":
                        logger.info(f"Step 5 Hit (LLM Choice): '{item_name}' -> {chosen_id}")
                        return self._build_result(chosen_id, 0.9)
                else:
                    # No LLM? Just take the top vector match if score is good
                    top_match = unique_candidates[0]
                    if top_match["score"] < 1.0: 
                        logger.info(f"Step 3/4 Hit (Vector Match): '{item_name}' -> {top_match['row_id']}")
                        return self._build_result(top_match["row_id"], top_match["score"])

            # STEP 6: Fallback (Uncategorized)
            logger.warning(f"All classification steps failed for: '{item_name}'")
            return self._uncategorized_result()

        except Exception as e:
            logger.error(f"Classification failed for '{item_name}': {e}")
            return self._uncategorized_result()

    def _llm_choose(self, item_name: str, item_type: str, candidates: List[Dict[str, Any]]) -> Optional[str]:
        """Ask LLM to pick the best ID from candidates using structured output."""
        try:
            candidates_text = ""
            for c in candidates:
                row = self.taxonomy_db.get_row_by_id(c["row_id"])
                path = row.get("full_path", "Unknown") if row else "Unknown"
                candidates_text += f"- ID: {c['row_id']} | Path: {path}\n"

            prompt = CLASSIFIER_PROMPT.format(
                item_name=item_name,
                item_type=item_type,
                candidates_text=candidates_text
            )

            # Structured output using Pydantic model
            response = self.llm_client.generate(
                prompt=prompt,
                response_model=ClassificationChoice
            )
            
            choice = response.content
            if not isinstance(choice, ClassificationChoice):
                logger.warning(f"LLM did not return ClassificationChoice instance. Content type: {type(choice)}")
                return None

            chosen_id = choice.chosen_id.strip()
            reasoning = choice.reasoning
            
            logger.info(f"LLM Choice: {chosen_id} | Reasoning: {reasoning}")
            
            if chosen_id == "NONE":
                return "NONE"
            
            if self.taxonomy_db.validate_row_id(chosen_id):
                return chosen_id
            
            logger.warning(f"LLM returned invalid taxonomy ID: '{chosen_id}'")
            return None
        except Exception as e:
            logger.error(f"LLM classification choice failed: {e}")
            return None

    def _build_result(self, taxonomy_id: str, score: float) -> ClassificationResult:
        """Helper to build a ClassificationResult from a taxonomy ID."""
        row = self.taxonomy_db.get_row_by_id(taxonomy_id)
        if not row:
            return self._uncategorized_result()
            
        return ClassificationResult(
            category=row.get("category", "Unknown"),
            sub_category_i=row.get("sub_category_i"),
            sub_category_ii=row.get("sub_category_ii"),
            score=score,
            taxonomy_id=str(taxonomy_id)
        )

    def _uncategorized_result(self) -> ClassificationResult:
        """Returns a standard Uncategorized result."""
        return ClassificationResult(
            category="Uncategorized",
            sub_category_i=None,
            sub_category_ii=None,
            score=0.0,
            taxonomy_id="UNCATEGORIZED"
        )
