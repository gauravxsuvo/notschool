import operator
from typing import Annotated, TypedDict, List, Any, Optional


class NotschoolState(TypedDict):
    """Unified state schema for the Notschool OS orchestrator."""
    # User Inputs
    goal: str
    mode: str  # currently always "learning" — kept for forward compatibility
    image_bytes: Optional[bytes]
    image_mime_type: Optional[str]
    user_access_token: Optional[str]
    user_id: Optional[str]

    # Agent Outputs
    curriculum_json: Optional[dict[str, Any]]
    youtube_urls: List[str]              
    web_trends: List[str]
    industry_opportunities: List[dict]
    calendar_event_id: Optional[str]    
    calendar_event_ids: Optional[List[str]]
    calendar_event_links: Optional[List[str]]   
    db_record_id: Optional[int]
    curriculum_id: Optional[int]        

    # Orchestration & Audit Logging
    messages: Annotated[List[dict[str, str]], operator.add]

    # Context
    user_timezone: str
    current_timestamp: str
    user_profile: Optional[dict[str, Any]]

    # Scheduling cadence — N units between consecutive modules.
    # unit ∈ {"min", "hour", "day", "week"}. Defaults to (1, "day").
    timeframe_amount: Optional[int]
    timeframe_unit: Optional[str]
