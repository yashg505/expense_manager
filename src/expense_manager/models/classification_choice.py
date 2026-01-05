from pydantic import BaseModel, Field

class ClassificationChoice(BaseModel):
    """
    Model for structured LLM response during the classification step.
    """
    chosen_id: str = Field(..., description="The ID of the category that best fits the item. Use 'NONE' if no fit is found.")
    reasoning: str = Field(..., description="A brief explanation of why this category was selected.")
