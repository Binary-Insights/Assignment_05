from dotenv import load_dotenv
from langgraph.graph import MessagesState
from langgraph.prebuilt import ToolNode
from langsmith import traceable

from langgraphv1_react import llm, tools

load_dotenv()

SYSYEM_MESSAGE="""
You are a helpful assistant that can use tools to answer questions.
When you get a final answer, make sure to say "FINAL ANSWER:" before providing the final result.
"""

@traceable
def run_agent_reasoning(state: MessagesState) -> MessagesState:
    """
    Run the agent reasoning node.
    """
    print(f"Agent reasoning with {len(state['messages'])} messages")
    response = llm.invoke([{"role": "system", "content": SYSYEM_MESSAGE}, *state["messages"]])
    print(f"Agent response: {response.content[:100]}...")
    return {"messages": [response]}

tool_node = ToolNode(tools)