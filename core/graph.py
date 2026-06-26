from langgraph.graph import StateGraph, END
from core.state import NotschoolState

from agents.architect_node import architect_node
from agents.librarian_node import librarian_node
from agents.scheduler_node import scheduler_node
from agents.db_node import db_node

def build_notschool_graph():
    """
    Compiles the LangGraph state machine.
    """
    workflow = StateGraph(NotschoolState)

    workflow.add_node("architect", architect_node)
    workflow.add_node("librarian", librarian_node)
    workflow.add_node("scheduler", scheduler_node)
    workflow.add_node("db_saver", db_node)

    workflow.set_entry_point("architect")
    
    workflow.add_edge("architect", "librarian")
    workflow.add_edge("librarian", "scheduler")
    workflow.add_edge("scheduler", "db_saver")
    workflow.add_edge("db_saver", END)

    return workflow.compile()

notschool_app = build_notschool_graph()
