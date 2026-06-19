"""
Discovery pipeline: Scout searches SAM.gov and saves opportunities to the DB.
Simple START → scout → END for now.
When Greta (scoring agent) is added, extend to START → scout → greta → END.
"""
from langchain_core.messages import HumanMessage
from langgraph.graph import END, START, MessagesState, StateGraph

from apps.govcon.agents.scout import scout_agent


def scout_node(state: MessagesState) -> dict:
    result = scout_agent.invoke(state)
    return {"messages": result["messages"]}


builder = StateGraph(MessagesState)
builder.add_node("scout", scout_node)
builder.add_edge(START, "scout")
builder.add_edge("scout", END)

graph = builder.compile()
