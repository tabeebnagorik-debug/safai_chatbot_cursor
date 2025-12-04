from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_openai.chat_models import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres import PostgresSaver
import psycopg
from langgraph.graph.message import add_messages
import os
import json
from dotenv import load_dotenv
from urllib.parse import quote_plus

load_dotenv(dotenv_path=".env", override=True)

# Initializing the embedder
embedding_tool = OpenAIEmbeddings(
    api_key=os.getenv("OPENAI_API_KEY"),
    model="text-embedding-3-small"
)

# Loading Knowledge Base
vector_store = Chroma(
    persist_directory="safai_KB",
    embedding_function=embedding_tool
)

# Retrieving Knowledge
retriever = vector_store.as_retriever(
    search_type="similarity",
    search_kwargs={"k": 10}
)

# Reading system prompt
with open("system_prompt.txt", "r", encoding="utf-8") as f:
    system_template = f.read().strip()

# Creating Prompt Template
prompt_format = """{system}
"context": {{context}}
"question": {{question}}""".format(system=system_template)

prompt = ChatPromptTemplate.from_messages([
    ("system", prompt_format),
    MessagesPlaceholder(variable_name="history"),
    ("human", "{question}")
])

# Initializing the LLM brain
llm = ChatOpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    model="gpt-4.1-mini",
    temperature=0
)

# Define the state schema
class GraphState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    question: str
    context: str
    validation_feedback: str  # Feedback from validation agent for regeneration
    retry_count: int  # Track number of regeneration attempts
    is_irrelevant: bool  # Flag to indicate if query is irrelevant to the service

def retrieve_node(state: GraphState) -> GraphState:
    """
    Retrieve relevant documents from the vector store based on the question.
    """
    question = state["question"]
    
    # Retrieve documents
    retrieved_docs = retriever.invoke(question)
    
    # Format context from retrieved documents
    context = "\n\n".join([doc.page_content for doc in retrieved_docs])
    
    # Update state with context and initialize validation fields
    return {
        **state,
        "context": context,
        "validation_feedback": "",  # Initialize feedback
        "retry_count": 0,  # Initialize retry count
        "is_irrelevant": False  # Initialize relevance flag
    }

def generate_node(state: GraphState) -> GraphState:
    """
    Generate response using LLM with context and conversation history.
    If validation_feedback exists, regenerate the response with feedback to correct mistakes.
    For irrelevant queries, handles them directly without calling validation tool.
    """
    question = state["question"]
    context = state["context"]
    messages = state["messages"]
    validation_feedback = state.get("validation_feedback", "")
    retry_count = state.get("retry_count", 0)
    
    # Check if query is irrelevant (only on first attempt, not regenerations)
    if not validation_feedback:
        # Check relevance of the query to the service domain
        relevance_check_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a relevance checker. Your task is to determine if a user's query is relevant to Safai's cleaning services.

Safai provides cleaning services including:
- Home cleaning
- Office cleaning
- Kitchen cleaning
- Bathroom cleaning
- Carpet cleaning
- Sofa cleaning
- Chair cleaning
- Window and roof cleaning
- General cleaning services

A query is RELEVANT if it:
- Asks about cleaning services, prices, booking, scheduling
- Asks about specific cleaning types (kitchen, bathroom, etc.)
- Asks about service details, policies, or procedures
- Is related to Safai's cleaning business in any way

A query is IRRELEVANT if it:
- Is about completely unrelated topics (weather, sports, general knowledge, etc.)
- Is a greeting or casual conversation with no service-related intent
- Is spam, gibberish, or nonsensical
- Is about services Safai doesn't provide

Respond with ONLY a JSON object:
{{
    "is_relevant": true/false,
    "reason": "brief explanation"
}}"""),
            ("human", "User Query: {question}\n\nIs this query relevant to Safai's cleaning services?")
        ])
        
        formatted_relevance_prompt = relevance_check_prompt.format_messages(question=question)
        relevance_result = llm.invoke(formatted_relevance_prompt)
        relevance_text = relevance_result.content.strip()
        
        # Parse relevance check result
        is_relevant = True  # Default to relevant
        try:
            start_idx = relevance_text.find("{")
            end_idx = relevance_text.rfind("}") + 1
            if start_idx != -1 and end_idx > start_idx:
                json_str = relevance_text[start_idx:end_idx]
                relevance_data = json.loads(json_str)
                is_relevant = relevance_data.get("is_relevant", True)
        except (json.JSONDecodeError, KeyError):
            # If parsing fails, default to relevant (safer to validate than skip)
            is_relevant = True
        
        # If query is irrelevant, handle it directly without validation
        if not is_relevant:
            # Generate a polite response for irrelevant queries
            irrelevant_response_prompt = ChatPromptTemplate.from_messages([
                ("system", """You are a helpful customer service assistant for Safai cleaning services. 
When a user asks something irrelevant to cleaning services, politely redirect them to ask about Safai's cleaning services.

Keep the response:
- Polite and friendly
- Brief
- Redirect them to ask about cleaning services
- Match the language of the user's query (English or Bangla)"""),
                ("human", "User Query: {question}\n\nGenerate a polite response redirecting them to ask about Safai's cleaning services.")
            ])
            
            formatted_irrelevant_prompt = irrelevant_response_prompt.format_messages(question=question)
            irrelevant_response = llm.invoke(formatted_irrelevant_prompt)
            
            return {
                "messages": [HumanMessage(content=question), AIMessage(content=irrelevant_response.content)],
                "retry_count": 0,
                "validation_feedback": "",
                "is_irrelevant": True  # Mark as irrelevant to skip validation
            }
    
    # If there's validation feedback, we need to regenerate with that feedback
    if validation_feedback:
        # Create a prompt that includes the feedback to help the model correct its mistake
        feedback_system_template = """{system}
"context": {{context}}
"question": {{question}}

IMPORTANT FEEDBACK FROM VALIDATION AGENT:
The previous response was found to be incorrect or not aligned with the retrieved context. Please regenerate your response.

Validation Feedback: {{feedback}}

Please carefully review the retrieved context and provide a corrected response that properly addresses the question and aligns with the retrieved data."""
        
        feedback_system = feedback_system_template.format(system=system_template)
        
        feedback_prompt = ChatPromptTemplate.from_messages([
            ("system", feedback_system),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{question}")
        ])
        
        # Format prompt with feedback
        formatted_prompt = feedback_prompt.format_messages(
            context=context,
            question=question,
            history=messages,
            feedback=validation_feedback
        )
    else:
        # First attempt - use normal prompt
        formatted_prompt = prompt.format_messages(
            context=context,
            question=question,
            history=messages
        )
    
    # Get response from LLM
    response = llm.invoke(formatted_prompt)
    
    # Increment retry count if this is a regeneration
    new_retry_count = retry_count + 1 if validation_feedback else 0
    
    # Return new messages to be added to state (using add_messages reducer)
    # Only add HumanMessage on first attempt, not on regenerations
    if not validation_feedback:
        return {
            "messages": [HumanMessage(content=question), AIMessage(content=response.content)],
            "retry_count": new_retry_count,
            "validation_feedback": "",  # Clear feedback
            "is_irrelevant": False  # Mark as relevant for validation
        }
    else:
        # On regeneration, only add the new AI message (user message already exists)
        return {
            "messages": [AIMessage(content=response.content)],
            "retry_count": new_retry_count,
            "validation_feedback": "",  # Clear feedback
            "is_irrelevant": False  # Keep as relevant
        }

def validation_tool_agent(state: GraphState) -> GraphState:
    """
    Validation tool agent that analyzes whether the response from generate_node is correct
    based on the retrieved data. If incorrect, provides feedback for regeneration.
    
    This agent receives:
    - Retrieved context data
    - User's question
    - AI's response from generate_node
    
    Based on this, it decides if the response is correct and provides feedback.
    """
    question = state["question"]
    context = state["context"]
    messages = state["messages"]
    retry_count = state.get("retry_count", 0)
    max_retries = 3  # Maximum number of regeneration attempts
    
    # Extract the last AI message (the response from generate_node)
    ai_response = None
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            ai_response = msg.content
            break
    
    if not ai_response:
        # If no AI message found, consider it invalid
        return {
            "validation_feedback": "No AI response found. Please generate a response.",
            "retry_count": retry_count
        }
    
    # Create validation prompt for the tool agent
    validation_prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a validation tool agent. Your task is to analyze whether an AI assistant's response is correct and accurate based on the retrieved context data.

Your analysis should check:
1. Factual Accuracy: Does the response accurately reflect the information in the retrieved context?
2. Consistency: Are there any contradictions between the response and the retrieved context?
3. Language Consistency: Is the response language consistent with the User Question? That is the response should be english if the user question is in english, and response should be bangla if the user question is in bangla/banglish.

You must respond in JSON format with the following structure:
{{
    "is_correct": true/false,
    "feedback": "Detailed feedback explaining what is wrong (if incorrect) or confirmation (if correct)"
}}

If the response is incorrect or inaccurate:
- Set "is_correct" to false
- Provide specific, actionable feedback about what is wrong
- Point out which parts of the retrieved context contradict or are missing from the response
- Be constructive so the AI can understand and correct its mistake
- Focus on factual errors, missing information, or contradictions
- Explain what the correct information should be based on the retrieved context

If the response is correct:
- Set "is_correct" to true
- Provide brief confirmation

Important: Be strict but fair. Only mark as incorrect if there are genuine factual errors, missing critical information, or contradictions with the retrieved context. The feedback should help the generate_node understand its mistake and correct it."""),
        ("human", """Retrieved Context Data:
{context}

User Question:
{question}

AI Response to Validate:
{ai_response}

Analyze the AI response against the retrieved context data and provide your validation in JSON format. Check if the response is factually accurate, consistent with the context, complete, and relevant.""")
    ])
    
    # Format and invoke validation
    formatted_validation_prompt = validation_prompt.format_messages(
        question=question,
        context=context,
        ai_response=ai_response
    )
    
    # Get validation result from LLM
    validation_result = llm.invoke(formatted_validation_prompt)
    validation_text = validation_result.content.strip()
    
    # Parse the JSON response
    import json
    try:
        # Try to extract JSON from the response (handle cases where LLM adds extra text)
        # Look for JSON object in the response
        start_idx = validation_text.find("{")
        end_idx = validation_text.rfind("}") + 1
        if start_idx != -1 and end_idx > start_idx:
            json_str = validation_text[start_idx:end_idx]
            validation_data = json.loads(json_str)
            is_correct = validation_data.get("is_correct", False)
            feedback = validation_data.get("feedback", "No feedback provided")
        else:
            # Fallback: if JSON parsing fails, check if response indicates correctness
            is_correct = "is_correct" in validation_text.lower() and "true" in validation_text.lower()
            feedback = validation_text
    except json.JSONDecodeError:
        # If JSON parsing fails, try to infer from text
        is_correct = "correct" in validation_text.lower() and "incorrect" not in validation_text.lower()
        feedback = validation_text
    
    # Check retry limit
    if not is_correct and retry_count >= max_retries:
        # Max retries reached, accept the response anyway
        return {
            "validation_feedback": "",
            "retry_count": retry_count
        }
    
    # Return validation result
    if is_correct:
        # Response is correct, clear feedback
        return {
            "validation_feedback": "",
            "retry_count": retry_count
        }
    else:
        # Response is incorrect, provide feedback for regeneration
        return {
            "validation_feedback": feedback,
            "retry_count": retry_count
        }

def should_validate(state: GraphState) -> str:
    """
    Conditional function to decide whether to validate the response or skip validation.
    Returns "validate" if query is relevant, "end" if irrelevant.
    """
    is_irrelevant = state.get("is_irrelevant", False)
    
    # If query is irrelevant, skip validation and end
    if is_irrelevant:
        return "end"
    else:
        # Query is relevant, proceed to validation
        return "validate"

def should_regenerate(state: GraphState) -> str:
    """
    Conditional function to decide whether to regenerate or proceed to end.
    Returns "regenerate" if validation feedback exists, otherwise "end".
    """
    validation_feedback = state.get("validation_feedback", "")
    retry_count = state.get("retry_count", 0)
    max_retries = 3
    
    # If there's feedback and we haven't exceeded max retries, regenerate
    if validation_feedback and retry_count < max_retries:
        return "regenerate"
    else:
        return "end"  # Response is correct or max retries reached, proceed to end

# Build the graph
workflow = StateGraph(GraphState)

# Add nodes
workflow.add_node("retrieve", retrieve_node)
workflow.add_node("generate", generate_node)
workflow.add_node("validation_tool_agent", validation_tool_agent)

# Add edges
workflow.set_entry_point("retrieve")
workflow.add_edge("retrieve", "generate")
# Conditional edge from generate: if irrelevant, end; if relevant, validate
workflow.add_conditional_edges(
    "generate",
    should_validate,
    {
        "validate": "validation_tool_agent",  # Route to validation if relevant
        "end": END  # End if irrelevant query
    }
)
# Conditional edge: if validation feedback exists, regenerate; otherwise end
workflow.add_conditional_edges(
    "validation_tool_agent",
    should_regenerate,
    {
        "regenerate": "generate",  # Route back to generate_node if incorrect
        "end": END  # End if correct or max retries reached
    }
)

# PostgreSQL configuration for chat history storage
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "safai_chat_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

# Build connection string
# Format: postgresql://user:password@host:port/database
# If password is empty, use: postgresql://user@host:port/database
if DB_PASSWORD:
    conn_string = f"postgresql://{DB_USER}:{quote_plus(DB_PASSWORD)}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
else:
    conn_string = f"postgresql://{DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Initialize PostgreSQL checkpointer for persistent chat history
checkpointer = None
try:
    # Create database if it doesn't exist
    if DB_NAME != 'postgres':
        # Use same password logic for admin connection
        if DB_PASSWORD:
            admin_conn_string = f"postgresql://{DB_USER}:{quote_plus(DB_PASSWORD)}@{DB_HOST}:{DB_PORT}/postgres"
        else:
            admin_conn_string = f"postgresql://{DB_USER}@{DB_HOST}:{DB_PORT}/postgres"
        try:
            with psycopg.connect(admin_conn_string) as conn:
                conn.autocommit = True
                with conn.cursor() as cur:
                    # Check if database exists
                    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DB_NAME,))
                    if not cur.fetchone():
                        # Create database
                        cur.execute(f'CREATE DATABASE "{DB_NAME}"')
                        print(f"✓ Created database: {DB_NAME}")
                    else:
                        print(f"✓ Database {DB_NAME} already exists")
        except Exception as db_create_error:
            print(f"⚠ Note: Could not create database (might already exist): {db_create_error}")
    
    # Initialize PostgresSaver with connection string
    # PostgresSaver.from_conn_string returns a context manager
    # We need to enter it and keep it alive for the application lifetime
    checkpointer_ctx = PostgresSaver.from_conn_string(conn_string)
    checkpointer = checkpointer_ctx.__enter__()
    
    # Setup database schema (creates necessary tables for checkpointing)
    checkpointer.setup()
    
    print(f"✓ Connected to PostgreSQL database: {DB_NAME}")
    print("✓ Database schema initialized")
    print("✓ Chat history will be stored persistently in PostgreSQL")
    
    # Store context manager reference for cleanup (if needed)
    # Note: We keep the checkpointer alive for the app lifetime
    
except Exception as e:
    print(f"⚠ Warning: Failed to connect to PostgreSQL: {e}")
    print("⚠ Falling back to in-memory storage (data will be lost on restart)")
    from langgraph.checkpoint.memory import MemorySaver
    checkpointer = MemorySaver()

# Compile graph with PostgreSQL checkpointer for persistent storage
app = workflow.compile(checkpointer=checkpointer)

# Interactive chat loop
if __name__ == "__main__":
    user_input = ""
    session_id = "langgraph_session_1"
    config = {"configurable": {"thread_id": session_id}}
    
    print("LangGraph RAG Chat Agent - Type 'quit' to exit")
    print("=" * 50)
    
    while user_input.lower() != "quit":
        user_input = input("\nMe: ")
        
        if user_input.lower() == "quit":
            break
        
        # Get current state from checkpoint to preserve existing messages
        current_state = app.get_state(config)
        existing_messages = current_state.values.get("messages", []) if current_state.values else []
        
        # Create initial state with the new question and existing messages
        initial_state = {
            "messages": existing_messages,
            "question": user_input,
            "context": "",
            "validation_feedback": "",
            "retry_count": 0,
            "is_irrelevant": False
        }
        
        # Invoke the graph - checkpointing will persist the updated state
        result = app.invoke(initial_state, config)
        
        # Extract and print the AI response (last message should be the AI response)
        if result["messages"]:
            # Find the last AI message
            ai_messages = [msg for msg in result["messages"] if isinstance(msg, AIMessage)]
            if ai_messages:
                ai_response = ai_messages[-1].content
                print(f"\nAI: {ai_response}")
            else:
                # Fallback: get last message content
                ai_response = result["messages"][-1].content
                print(f"\nAI: {ai_response}")
            print("-" * 50)

