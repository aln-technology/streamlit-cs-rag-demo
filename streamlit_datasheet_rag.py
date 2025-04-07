# streamlit_rag_chat.py

import os
import streamlit as st
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader
from llama_index.llms.openai import OpenAI

# Set OpenAI API key from Streamlit secrets
os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]


def index_documents(uploaded_files):
    """Index uploaded documents and return a query engine."""
    os.makedirs("uploaded_docs", exist_ok=True)
    for uploaded_file in uploaded_files:
        filepath = os.path.join("uploaded_docs", uploaded_file.name)
        with open(filepath, "wb") as f:
            f.write(uploaded_file.getbuffer())

    with st.spinner("Reading and indexing the documents..."):
        docs = SimpleDirectoryReader("uploaded_docs").load_data()
        llm = OpenAI(temperature=0.0)
        index = VectorStoreIndex.from_documents(docs, llm=llm)
        return index.as_query_engine()


st.set_page_config(page_title="Document Chat Assistant", layout="centered")
st.title("📄 Documentation Informed Customer Support - Demo")

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "query_engine" not in st.session_state:
    st.session_state.query_engine = None
if "question_count" not in st.session_state:
    st.session_state.question_count = 0

# File uploader
uploaded_files = st.file_uploader(
    "Upload documents", type=["pdf", "txt"], accept_multiple_files=True
)

if uploaded_files and st.session_state.query_engine is None:
    st.session_state.query_engine = index_documents(uploaded_files)
    st.success(
        f"Successfully indexed {len(uploaded_files)} document(s)! You can now ask questions about them."
    )

# Display chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat input
if prompt := st.chat_input("Ask a question about the document"):
    if st.session_state.question_count >= 15:
        with st.chat_message("assistant"):
            st.error(
                "You've reached the limit of 15 questions. Please refresh the page to start a new session."
            )
    else:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Get response from query engine if document is loaded
        if st.session_state.query_engine:
            response = st.session_state.query_engine.query(prompt)
            with st.chat_message("assistant"):
                st.markdown(response.response)
            st.session_state.messages.append(
                {"role": "assistant", "content": response.response}
            )
            st.session_state.question_count += 1
        else:
            with st.chat_message("assistant"):
                st.error("Please upload a document first to ask questions about it.")
