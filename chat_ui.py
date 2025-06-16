import streamlit as st
import asyncio
import httpx
from supabase import create_client, Client

# 🔐 API Keys & Configs
OPENROUTER_API_KEY = "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"
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "nvidia/llama-3.1-nemotron-ultra-253b-v1:free"

SUPABASE_URL = "https://vphtpzlbdcotorqpuonr.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZwaHRwemxiZGNvdG9ycXB1b25yIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDU1MDg0OTcsImV4cCI6MjA2MTA4NDQ5N30.XTP7clV__5ZVp9hZCJ2eGhL7HgEUeTcl2uINX0JC9WI"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# 🔢 Streamlit Config
st.set_page_config(page_title="Aiva Chatbot", layout="wide")
st.title("💬 Aiva Bidding Assistant")

# 🤖 Chat history
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# 📊 Fetch all bidding records
@st.cache_data
def fetch_all_bidding_records(batch_size=1000):
    all_data = []
    start = 0
    while True:
        response = supabase.table("BiddingDB").select("*").range(start, start + batch_size - 1).execute()
        data = response.data
        if not data:
            break
        all_data.extend(data)
        start += batch_size
    return all_data

# 🔍 LLM with Supabase context
async def get_openrouter_reply(user_message):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://aivadeus.onrender.com",
        "X-Title": "Aiva Chatbot"
    }

    # Contextual bidding data
    bids = fetch_all_bidding_records()
    summarized = [
        f"ReferenceNo: {r.get('ReferenceNo')}, Title: {r.get('Title')}, Entity: {r.get('Entity')}, Budget: {r.get('ApprovedBudget')}, Summary: {r.get('Summary')}"
        for r in bids if r.get("ReferenceNo") and r.get("Title")
    ][:20]  # limit to 20 to avoid token overflow

    # Build prompt context
    messages = [{"role": "system", "content": "You are Aiva, a smart bidding assistant."}]
    for msg in st.session_state.chat_history:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "system", "content": "Here are some current bidding opportunities:\n\n" + "\n".join(summarized)})
    messages.append({"role": "user", "content": user_message})

    payload = {
        "model": MODEL,
        "messages": messages
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(OPENROUTER_API_URL, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"]

# 💬 Chat input
user_input = st.chat_input("Ask about a bid, agency, category, or strategy...")
if user_input:
    st.session_state.chat_history.append({"role": "user", "content": user_input})
    with st.spinner("Aiva is thinking..."):
        try:
            answer = asyncio.run(get_openrouter_reply(user_input))
            st.session_state.chat_history.append({"role": "assistant", "content": answer})
        except Exception as e:
            st.session_state.chat_history.append({"role": "assistant", "content": f"❌ Error: {str(e)}"})

# 📋 Show history
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
