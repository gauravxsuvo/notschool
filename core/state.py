import operator
from typing import Annotated, TypedDict, List, Any, Optional


class NotschoolState(TypedDict):
    """Unified state schema for the Notschool OS orchestrator."""
    goal: str
    mode: str  
    image_bytes: Optional[bytes]
    image_mime_type: Optional[str]
    user_access_token: Optional[str]
    user_id: Optional[str]

    curriculum_json: Optional[dict[str, Any]]
    youtube_urls: List[str]              
    web_trends: List[str]
    industry_opportunities: List[dict]
    calendar_event_id: Optional[str]    
    calendar_event_ids: Optional[List[str]]
    calendar_event_links: Optional[List[str]]   
    db_record_id: Optional[int]
    curriculum_id: Optional[int]        

    messages: Annotated[List[dict[str, str]], operator.add]

    user_timezone: str
    current_timestamp: str
    user_profile: Optional[dict[str, Any]]

    timeframe_amount: Optional[int]
    timeframe_unit: Optional[str]
