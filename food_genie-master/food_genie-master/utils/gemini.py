from google import genai
from google.genai import types
import os
import json
from dotenv import load_dotenv
import PIL.Image

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
client = None

if API_KEY:
    client = genai.Client(api_key=API_KEY)

# Models
VISION_MODEL = 'gemini-1.5-flash'
TEXT_MODEL = 'gemini-1.5-flash'

def analyze_image(image_path):
    """
    Analyzes the food image to identify the dish using the new SDK.
    """
    if not client:
        print("No API_KEY, skipping analysis.")
        return None
        
    try:
        print(f"DEBUG: Analyzing image with model {VISION_MODEL}...")
        # Load image with PIL
        image = PIL.Image.open(image_path)
        
        prompt = """
        Analyze this food image. Identify the dish name, cuisine type, and whether it is Vegetarian or Non-Vegetarian.
        Return strictly Valid JSON in this format:
        {
            "dish_name": "Name of dish",
            "cuisine": "Cuisine type (e.g., Indian, Italian)",
            "category": "Veg or Non-Veg"
        }
        """
        
        response = client.models.generate_content(
            model=VISION_MODEL,
            contents=[image, prompt]
        )
        
        print(f"DEBUG: AI Response: {response.text}")
        
        text = response.text
        # Clean markdown if present
        if '```json' in text:
            text = text.split('```json')[1].split('```')[0]
        elif '```' in text:
            text = text.split('```')[0]
            
        data = json.loads(text.strip())
        return data
        
    except Exception as e:
        print(f"Error in analyze_image (new SDK): {e}")
        # Consider inspecting e.response for detailed API handling errors if available in new SDK
        return None

def generate_full_recipe_details(dish_name, cuisine):
    """
    Generates recipe, nutrition, translation, etc using the new SDK.
    """
    if not client:
        return None
        
    try:
        prompt = f"""
        Generate a complete cooking guide for "{dish_name}" ({cuisine}).
        
        I need the output in strictly VALID JSON format with the following structure:
        
        {{
            "english": {{
                "ingredients": ["Item 1", "Item 2"],
                "instructions": ["Step 1", "Step 2"],
                "cooking_time": "Time",
                "difficulty": "Easy/Medium/Hard"
            }},
            "tamil": {{
                "ingredients": ["Tamil Item 1", "Tamil Item 2"],
                "instructions": ["Tamil Step 1", "Tamil Step 2"],
                "cooking_time": "Tamil Time", 
                "difficulty": "Tamil Difficulty"
            }},
            "nutrition": {{
                "calories": "Value",
                "protein": "Value",
                "carbs": "Value",
                "fats": "Value",
                "fiber": "Value"
            }},
            "estimated_cost": "Approximate cost (e.g., $10-$15 or ₹X-₹Y)",
            "image_prompts": [
                 "Prompt 1", "Prompt 2"
            ],
            "video_script": {{
                "scene_description": "Description",
                "camera_angle": "Angle",
                "text_overlay": "Text"
            }}
        }}
        """
        
        response = client.models.generate_content(
            model=TEXT_MODEL,
            contents=prompt
        )
        
        text = response.text
        if '```json' in text:
            text = text.split('```json')[1].split('```')[0]
        elif '```' in text:
            text = text.split('```')[0]
            
        data = json.loads(text.strip())
        return data
        
    except Exception as e:
        print(f"Error in generate_full_recipe_details (new SDK): {e}")
        return None

def chat_with_chef(user_message, recipe_context):
    """
    Chat with the AI Chef.
    """
    if not client:
        return "I'm offline right now!"
        
    try:
        prompt = f"""
        You are a friendly and expert AI Chef. 
        The user is currently looking at this recipe:
        {json.dumps(recipe_context) if isinstance(recipe_context, dict) else recipe_context}
        
        User Query: "{user_message}"
        
        Answer helpful, briefly, and encouragingly. Focus on the query.
        """
        
        response = client.models.generate_content(
            model=TEXT_MODEL,
            contents=prompt
        )
        return response.text.strip()
    except Exception as e:
        print(f"Chat Error (new SDK): {e}")
        return "I'm having trouble hearing you in the kitchen! Can you repeat that?"
