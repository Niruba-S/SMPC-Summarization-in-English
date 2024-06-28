import streamlit as st
import PyPDF2
from deep_translator import GoogleTranslator
import time
import google.generativeai as genai
import os
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph
from io import BytesIO
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get API key from environment variable
api_key = os.getenv('GEMINI_API_KEY')

# Function to extract text from PDF
def extract_text_from_pdf(file):
    reader = PyPDF2.PdfReader(file)
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    return text

# Function to translate large text
def translate_large_text(text, chunk_size=4500):
    translator = GoogleTranslator(source='es', target='en')
    chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
    translated_text = ""
    
    for chunk in chunks:
        translated_chunk = translator.translate(chunk)
        translated_text += translated_chunk
        time.sleep(1)  # To avoid hitting rate limits
    
    return translated_text

# Function to extract product information and summary using Gemini Pro
def extract_info_and_summarize(text, api_key):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-pro')

    prompt = f"""
    Analyze the following text and provide:
    1. Product Name
    2. Brief Description (2-3 sentences)
    3. Composition
    4. Excipients with known effects
    5. Dosage form
    6. Posology
    7. Warnings
    8. Any other essential information
    9. An overall summary of the text
    10. Detailed Summary including:
       a. Composition
       b. Excipients with known effects
       c. Dosage form
       d. Posology
       e. Warnings

    Provide a structured output with these details, clearly separating each item. Use markdown formatting for better readability.

    Text: {text}
    """

    response = model.generate_content(prompt)
    return response.text

# Modified chatbot function
def get_chat_response(query, context, api_key):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-pro')
    
    prompt = f"""
    Context: {context}

    Human: {query}

    Assistant: Based on the context provided, I'll answer the question. If the answer isn't explicitly in the context, I'll say so and provide the most relevant information I can.
    """

    response = model.generate_content(prompt)
    return response.text

def create_pdf(content):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    flowables = []

    for line in content.split('\n'):
        p = Paragraph(line, styles['Normal'])
        flowables.append(p)

    doc.build(flowables)
    buffer.seek(0)
    return buffer

# Streamlit app
st.title("SMPC summarization in English ")

# File uploader
uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")

# API Key input


if 'english_text' not in st.session_state:
    st.session_state.english_text = ""
if 'info_and_summary' not in st.session_state:
    st.session_state.info_and_summary = ""
if 'context' not in st.session_state:
    st.session_state.context = ""
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

if uploaded_file is not None and api_key:
    if st.button("Process PDF"):
        try:
            with st.spinner("Processing PDF..."):
                spanish_text = extract_text_from_pdf(uploaded_file)
                st.session_state.english_text = translate_large_text(spanish_text)
                st.session_state.info_and_summary = extract_info_and_summarize(st.session_state.english_text, api_key)
                
                # Set context for chat
                st.session_state.context = st.session_state.english_text + "\n\n" + st.session_state.info_and_summary
            st.success("PDF processed successfully!")
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")

if st.session_state.info_and_summary:
    # Display results
    st.subheader("Product Information and Summary")
    st.markdown(st.session_state.info_and_summary)

    # Option to download English text
    st.download_button(
        label="Download Extracted English Text",
        data=st.session_state.english_text,
        file_name="extracted_english_text.txt",
        mime="text/plain",
        key="download_english"
    )

    # Option to download summary as PDF
    pdf_buffer = create_pdf(st.session_state.info_and_summary)
    st.download_button(
        label="Download Product Information and Summary (PDF)",
        data=pdf_buffer,
        file_name="product_info_and_summary.pdf",
        mime="application/pdf",
        key="download_summary_pdf"
    )

    # Chatbot interface
    st.subheader("Chat with the Document")
    user_question = st.text_input("Ask a question about the document:")
    if st.button("Ask"):
        if st.session_state.context:
            try:
                response = get_chat_response(user_question, st.session_state.context, api_key)
                st.session_state.chat_history.append(("You", user_question))
                st.session_state.chat_history.append(("Bot", response))
            except Exception as e:
                st.error(f"I don't have knowledge about the query: {str(e)}")
        else:
            st.warning("Please process a PDF first before asking questions.")

    # Display chat history
    for role, message in st.session_state.chat_history:
        if role == "You":
            st.write(f"**You:** {message}")
        else:
            st.write(f"**Bot:** {message}")

