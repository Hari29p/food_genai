# Food Genie - Setup Guide

## Prerequisites
- Python 3.8+
- Google Gemini API Key

## Setup Steps
1. Navigate to the project directory:
   ```bash
   cd food_genie
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure Environment Variables:
   - Rename `.env.example` to `.env`:
     ```bash
     mv .env.example .env  # or copy
     ```
   - Open `.env` and add your **Gemini API Key** and a **Secret Key**.

4. Run the Application:
   ```bash
   python app.py
   ```
   *The database will be initialized automatically on the first run.*

5. Open Browser:
   - Go to `http://127.0.0.1:5000`
   - Register a new account.
   - Upload a food image to test!

## Features
- **AI Vision**: Identifies dish from image.
- **AI Chef**: Generates recipes in English & Tamil.
- **Nutrition**: Detailed breakdown cards.
- **Voice**: "Listen" button reads instructions.
- **Share**: WhatsApp button creates a formatted message.
