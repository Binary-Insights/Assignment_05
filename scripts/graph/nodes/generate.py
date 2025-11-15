from typing import Any, Dict

from graph.chains.generation import generation_chain
from graph.state import GraphState


def generate(state: GraphState) -> Dict[str, Any]:
    print("---GENERATE---")
    question = state["question"]
    documents = state["documents"]

    print('questions: ')
    print(question)
    
    # Convert documents to string format for the generation chain
    context_str = "\n\n".join([doc.page_content for doc in documents])
    
    generation = generation_chain.invoke({"context": context_str, "question": question})
    return {"documents": documents, "question": question, "generation": generation}
