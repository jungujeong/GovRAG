import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Ollama configuration
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.1"))

# Vector store configuration
VECTOR_DB_PATH = os.getenv("VECTOR_DB_PATH", "./data/vector_db")
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1000"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))

# Embedding models configuration
EMBEDDING_MODELS_STR = os.getenv("EMBEDDING_MODELS", "llama2,all-minilm,nomic-embed-text")
EMBEDDING_MODELS = [
    {"model": model, "name": model} for model in EMBEDDING_MODELS_STR.split(",")
]

# Document storage
DOCUMENTS_PATH = "./data/documents"

# HWP Server configuration
HWP_SERVER_URL = os.getenv("HWP_SERVER_URL", "http://192.168.0.2:8000")

# Logging configuration
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__) 