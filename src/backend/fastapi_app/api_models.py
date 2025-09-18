from enum import Enum
from typing import Any, Optional

from openai.types.responses import ResponseInputItemParam
from pydantic import BaseModel, Field


class AIChatRoles(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Message(BaseModel):
    content: str
    role: AIChatRoles = AIChatRoles.USER


class RetrievalMode(str, Enum):
    TEXT = "text"
    VECTORS = "vectors"
    HYBRID = "hybrid"


class ChatRequestOverrides(BaseModel):
    top: int = 3
    temperature: float = 0.3
    retrieval_mode: RetrievalMode = RetrievalMode.HYBRID
    use_advanced_flow: bool = True
    prompt_template: Optional[str] = None
    seed: Optional[int] = None


class ChatRequestContext(BaseModel):
    overrides: ChatRequestOverrides


class ChatRequest(BaseModel):
    messages: list[ResponseInputItemParam]
    context: ChatRequestContext
    sessionState: Optional[Any] = None


class ItemCreate(BaseModel):
    type: str
    brand: str
    name: str
    description: str
    price: float
    owner: str


class ItemUpdate(BaseModel):
    """Fields that can be updated for an Item. All optional for PATCH semantics."""

    type: Optional[str] = None
    brand: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    owner: Optional[str] = None


class ItemPublic(BaseModel):
    id: int
    type: str
    brand: str
    name: str
    description: str
    price: float
    owner: str

    def to_str_for_rag(self):
        return (
            f"Product Name: {self.name}\n"
            f"Description: {self.description}\n"
            f"Price: ${self.price}\n"
            f"Brand/Manufacturer: {self.brand}\n"
            f"Product Type: {self.type}\n"
            f"Current Owner: {self.owner}"
        )


class ItemWithDistance(ItemPublic):
    distance: float

    def __init__(self, **data):
        super().__init__(**data)
        self.distance = round(self.distance, 2)


class ThoughtStep(BaseModel):
    title: str
    description: Any
    props: dict = {}


class RAGContext(BaseModel):
    data_points: dict[int, ItemPublic]
    thoughts: list[ThoughtStep]
    followup_questions: Optional[list[str]] = None


class ErrorResponse(BaseModel):
    error: str


class RetrievalResponse(BaseModel):
    message: Message
    context: RAGContext
    sessionState: Optional[Any] = None


class RetrievalResponseDelta(BaseModel):
    delta: Optional[Message] = None
    context: Optional[RAGContext] = None
    sessionState: Optional[Any] = None


class ChatParams(ChatRequestOverrides):
    prompt_template: str
    response_token_limit: int = 1024
    enable_text_search: bool
    enable_vector_search: bool
    original_user_query: str
    past_messages: list[ResponseInputItemParam]


class Filter(BaseModel):
    column: str
    comparison_operator: str
    value: Any


class PriceFilter(Filter):
    column: str = Field(default="price", description="The column to filter on (always 'price' for this filter)")
    comparison_operator: str = Field(description="The operator for price comparison ('>', '<', '>=', '<=', '=')")
    value: float = Field(description="The price value to compare against (e.g., 30.00)")


class BrandFilter(Filter):
    column: str = Field(default="brand", description="The column to filter on (always 'brand' for this filter)")
    comparison_operator: str = Field(description="The operator for brand comparison ('=' or '!=')")
    value: str = Field(description="The brand name to compare against (e.g., 'AirStrider')")


class SearchResults(BaseModel):
    query: str
    """The original search query"""

    items: list[ItemPublic]
    """List of items that match the search query and filters"""

    filters: list[Filter]
    """List of filters applied to the search results"""
