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
with open("system_prompt_2.txt", "r", encoding="utf-8") as f:
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
    temperature=0.2
)

# Define the state schema
class GraphState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    question: str
    context: str

def retrieve_node(state: GraphState) -> GraphState:
    """
    Retrieve relevant documents from the vector store based on the question.
    """
    question = state["question"]
    
    # Retrieve documents
    retrieved_docs = retriever.invoke(question)
    
    # Format context from retrieved documents
    context = "\n\n".join([doc.page_content for doc in retrieved_docs])
    
    # Update state with context
    return {
        **state,
        "context": context
    }

def generate_node(state: GraphState) -> GraphState:
    """
    Generate response using LLM with context and conversation history.
    """
    question = state["question"]
    context = state["context"]
    messages = state["messages"]
    
    # Format prompt with context and question
    formatted_prompt = prompt.format_messages(
        context=context,
        question=question,
        history=messages
    )
    
    # Get response from LLM
    response = llm.invoke(formatted_prompt)
    
    # Return new messages to be added to state (using add_messages reducer)
    return {
        "messages": [HumanMessage(content=question), AIMessage(content=response.content)]
    }

# Build the graph
workflow = StateGraph(GraphState)

# Add nodes
workflow.add_node("retrieve", retrieve_node)
workflow.add_node("generate", generate_node)

# Add edges
workflow.set_entry_point("retrieve")
workflow.add_edge("retrieve", "generate")
workflow.add_edge("generate", END)

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
            "context": ""
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

