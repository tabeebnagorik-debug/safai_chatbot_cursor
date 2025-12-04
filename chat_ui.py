import streamlit as st
from langchain_core.messages import AIMessage
from safai_rag_langgraph import app
import uuid

# Page configuration
st.set_page_config(
    page_title="Safai AI Chat Agent",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
    <style>
    .stApp {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    }
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    .chat-message {
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
        display: flex;
        align-items: flex-start;
    }
    .user-message {
        background-color: #e3f2fd;
        margin-left: 20%;
    }
    .assistant-message {
        background-color: #f1f8e9;
        margin-right: 20%;
    }
    h1 {
        color: white;
        text-align: center;
    }
    </style>
    """, unsafe_allow_html=True)

# Initialize session state
if "session_id" not in st.session_state:
    st.session_state.session_id = f"streamlit_{uuid.uuid4().hex[:8]}"

if "messages" not in st.session_state:
    st.session_state.messages = []

# Sidebar for settings
with st.sidebar:
    st.header("⚙️ Settings")
    
    st.markdown("---")
    
    if st.button("🗑️ Clear Chat", use_container_width=True):
        st.session_state.messages = []
        st.session_state.session_id = f"streamlit_{uuid.uuid4().hex[:8]}"
        st.rerun()
    
    st.markdown("---")
    st.markdown("### 📝 Session Info")
    st.code(f"Session ID: {st.session_state.session_id}")
    st.markdown(f"**Messages:** {len(st.session_state.messages)}")
    
    st.markdown("---")
    st.markdown("### ℹ️ About")
    st.info(
        "This is Safai's AI Customer Support Assistant powered by LangGraph and RAG. "
        "Ask questions about Safai's cleaning services, pricing, policies, and booking procedures."
    )

# Main chat interface
st.title("🤖 Safai AI Customer Support Assistant")
st.markdown("---")

# Display chat history
chat_container = st.container()

with chat_container:
    if len(st.session_state.messages) == 0:
        with st.chat_message("assistant"):
            welcome_message = (
                "👋 **Welcome!** I'm Safai's AI Customer Support Assistant. "
                "I can help you with:\n\n"
                "- Service information and details\n"
                "- Pricing and minimum requirements\n"
                "- Booking procedures\n"
                "- Policies and terms\n\n"
                "How can I assist you today?"
            )
            st.markdown(welcome_message)
    else:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

# Chat input
placeholder_text = "Ask me anything about Safai's services..."
if user_query := st.chat_input(placeholder_text):
    # Add user message to chat
    st.session_state.messages.append({"role": "user", "content": user_query})
    
    with st.chat_message("user"):
        st.markdown(user_query)
    
    # Get response from LangGraph agent
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                # Prepare config for checkpointing
                config = {"configurable": {"thread_id": st.session_state.session_id}}
                
                # Get current state from checkpoint to preserve existing messages
                current_state = app.get_state(config)
                existing_messages = current_state.values.get("messages", []) if current_state.values else []
                
                # Create initial state with the new question and existing messages
                initial_state = {
                    "messages": existing_messages,
                    "question": user_query,
                    "context": ""
                }
                
                # Invoke the graph
                result = app.invoke(initial_state, config)
                
                # Extract AI response
                if result["messages"]:
                    ai_messages = [msg for msg in result["messages"] if isinstance(msg, AIMessage)]
                    if ai_messages:
                        ai_response = ai_messages[-1].content
                    else:
                        ai_response = result["messages"][-1].content
                else:
                    ai_response = "Sorry, I couldn't generate a response. Please try again."
                
                st.markdown(ai_response)
                
                # Add assistant response to chat history
                st.session_state.messages.append({"role": "assistant", "content": ai_response})
                
            except Exception as e:
                error_message = f"Error: {str(e)}"
                st.error(error_message)
                st.session_state.messages.append({"role": "assistant", "content": error_message})
