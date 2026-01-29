import json
import uuid
import requests
import streamlit as st

API_URL = "http://127.0.0.1:8000/chat"

st.set_page_config(page_title="Expense Chatbot", page_icon="🧾", layout="wide")

# ---------- Sidebar ----------
st.sidebar.title("🧾 Expense Chatbot")
st.sidebar.caption("FastAPI + OpenAI + Neon")

if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []  # list of {role, content}

show_debug = st.sidebar.toggle("Show debug", value=False)
api_timeout = st.sidebar.slider("API timeout (seconds)", min_value=10, max_value=120, value=60, step=5)

colA, colB = st.sidebar.columns(2)
if colA.button("🔄 New conversation"):
    st.session_state.conversation_id = str(uuid.uuid4())
    st.session_state.messages = []
    st.rerun()

if colB.button("🧹 Clear chat"):
    st.session_state.messages = []
    st.rerun()

st.sidebar.divider()
st.sidebar.write("Conversation ID:")
st.sidebar.code(st.session_state.conversation_id)

# ---------- Main UI ----------
st.title("Chat with your expenses 🧠➡️🗄️")
st.caption("Ask things like: “total spend for milk per month”, “most spent item and shop”, “expenses by category”")

# Render history
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# Input
prompt = st.chat_input("Ask about your receipts...")
if prompt:
    # Show user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Call backend
    payload = {"message": prompt, "conversation_id": st.session_state.conversation_id}

    with st.chat_message("assistant"):
        with st.spinner("Querying database..."):
            try:
                resp = requests.post(API_URL, json=payload, timeout=api_timeout)
                resp.raise_for_status()
                data = resp.json()
                answer = data.get("answer", "(no answer)")
            except Exception as e:
                answer = f"⚠️ API error: {e}"
                data = {"answer": answer}

        st.markdown(answer)

        if show_debug:
            with st.expander("Debug payload/response"):
                st.write("Request payload:")
                st.code(json.dumps(payload, indent=2))
                st.write("Raw response:")
                st.code(json.dumps(data, indent=2))

    st.session_state.messages.append({"role": "assistant", "content": answer})
