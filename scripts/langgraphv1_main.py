from dotenv import load_dotenv
import os

from langchain_core.messages import HumanMessage
from langgraph.graph import MessagesState, StateGraph,END

from langgraphv1_nodes import run_agent_reasoning, tool_node

load_dotenv()

# LangSmith Configuration
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = "ReAct-LangGraph-Function-Calling"
# Make sure to set LANGCHAIN_API_KEY in your .env file

AGENT_REASON="agent_reason"
ACT= "act"
LAST = -1


def should_continue(state: MessagesState) -> str:
    """Decide whether to continue with tool execution or end the conversation."""
    last_message = state["messages"][LAST]
    
    # Check if the last message has tool calls
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        print(f"Tool calls found: {len(last_message.tool_calls)}")
        return ACT
    
    # Check if the message contains "FINAL ANSWER" to indicate completion
    if hasattr(last_message, 'content') and "FINAL ANSWER:" in str(last_message.content):
        print("Final answer detected, ending conversation")
        return END
    
    print("No tool calls found, ending conversation")
    return END

flow = StateGraph(MessagesState)

flow.add_node(AGENT_REASON, run_agent_reasoning)
flow.set_entry_point(AGENT_REASON)
flow.add_node(ACT, tool_node)

flow.add_conditional_edges(AGENT_REASON, should_continue, {
    END:END,
    ACT:ACT})

flow.add_edge(ACT, AGENT_REASON)

app = flow.compile()
app.get_graph().draw_mermaid_png(output_file_path="flow.png")

if __name__ == "__main__":
    print("Hello ReAct LangGraph with Function Calling")
    
    # Run with proper configuration to avoid recursion limit
    config = {"recursion_limit": 10}
    
    try:
        res = app.invoke(
            {"messages": [HumanMessage(content="What is the temperature(celsius) in Boston? List it and then triple it")]},
            config=config
        )
        print("Final result:")
        print(res["messages"][-1].content)
    except Exception as e:
        print(f"Error occurred: {e}")
        print("Check your .env file for proper API keys (OPENAI_API_KEY, TAVILY_API_KEY, LANGCHAIN_API_KEY)")

    res = app.invoke({"messages": [HumanMessage(content="What is the temperature(celcius) in Tokyo? List it and then triple it")]})
    print(res["messages"][LAST].content)