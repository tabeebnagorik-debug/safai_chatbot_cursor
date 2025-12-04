from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
import os
from dotenv import load_dotenv

load_dotenv(dotenv_path = ".env")

# Loading all files from knowledge_base folder
script_dir = os.path.dirname(os.path.abspath(__file__))
knowledge_base_dir = os.path.join(script_dir, "knowledge_base")

all_documents = []

# Get all files in the knowledge_base directory
for filename in os.listdir(knowledge_base_dir):
    file_path = os.path.join(knowledge_base_dir, filename)
    
    # Skip directories and hidden files
    if os.path.isdir(file_path) or filename.startswith('.'):
        continue
    
    try:
        # Load PDF files
        if filename.lower().endswith('.pdf'):
            print(f"Loading PDF: {filename}")
            try:
                loader = PyPDFLoader(file_path=file_path)
                documents = loader.load()
                if documents:
                    all_documents.extend(documents)
                    print(f"  ✓ Successfully loaded {len(documents)} pages")
                else:
                    print(f"  ⚠ Warning: No content extracted from {filename}")
            except Exception as pdf_error:
                print(f"  ✗ Error loading PDF {filename}: {str(pdf_error)}")
                # Check if it's a pypdf missing error
                if "pypdf" in str(pdf_error).lower() or "pypdf" in str(pdf_error):
                    print(f"  💡 Tip: Install pypdf with: pip install pypdf")
                continue
        
        # Load text files
        elif filename.lower().endswith(('.txt', '.md', '.csv')):
            print(f"Loading text file: {filename}")
            loader = TextLoader(file_path=file_path, encoding='utf-8')
            documents = loader.load()
            all_documents.extend(documents)
        
        else:
            print(f"Skipping unsupported file type: {filename}")
    
    except Exception as e:
        print(f"Error loading {filename}: {str(e)}")
        continue

print(f"Total documents loaded: {len(all_documents)}")

# Check if any documents were loaded
if len(all_documents) == 0:
    print("⚠ Warning: No documents were loaded. Please check:")
    print("  1. PDF files exist in knowledge_base folder")
    print("  2. pypdf is installed: pip install pypdf")
    print("  3. File names don't contain problematic characters")
    exit(1)

# Chunking all documents
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size = 1000,
    chunk_overlap = 100
)

chunks = text_splitter.split_documents(all_documents)
print(f"Total chunks created: {len(chunks)}")

# Check if chunks were created
if len(chunks) == 0:
    print("⚠ Warning: No chunks were created from documents.")
    exit(1)

#Intializing Embedder
embedding_tool = OpenAIEmbeddings(
    api_key = os.getenv("OPENAI_API_KEY"),
    model = "text-embedding-3-small"
)

#Creating Vector DB
vector_store = Chroma.from_documents(
    documents = chunks,
    embedding = embedding_tool,
    persist_directory = "safai_KB"
)

print("Vector database created and persisted successfully!")


