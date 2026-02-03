import json
import uuid
import streamlit as st

from expense_manager.components.ai_chabot.engine import answer  # <- direct call

st.set_page_config(page_title="Expense Chatbot", page_icon="🧾", layout="wide")

# ---------- Sidebar ----------
st.sidebar.title("🧾 Expense Chatbot")
st.sidebar.caption("Streamlit + OpenAI + Neon (direct)")

if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []

show_debug = st.sidebar.toggle("Show debug", value=False)

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

    with st.chat_message("assistant"):
        with st.spinner("Querying database..."):
            try:
                data = answer(prompt, st.session_state.conversation_id)  # <- direct call
                reply = data.get("answer", "(no answer)")
            except Exception as e:
                reply = f"⚠️ Error: {e}"
                data = {"answer": reply}

        st.markdown(reply)

        if show_debug:
            with st.expander("Debug"):
                st.write("Result object:")
                st.code(json.dumps(data, indent=2, default=str))

    st.session_state.messages.append({"role": "assistant", "content": reply})
