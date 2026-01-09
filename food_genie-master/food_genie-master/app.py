from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import os
import json
import sqlite3
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from utils.db import init_db, get_db_connection
from utils.auth import register_user, authenticate_user
from utils.gemini import analyze_image, generate_full_recipe_details, chat_with_chef

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev_secret_key_change_me")

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

try:
    init_db()
except Exception as e:
    print(f"Error initializing DB: {e}")

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- Routes ---

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html', user_name=session.get('user_name'))

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if 'file' not in request.files:
        flash('No file part', 'danger')
        return redirect(request.url)
    file = request.files['file']
    if file.filename == '' or not allowed_file(file.filename):
        flash('Invalid file', 'danger')
        return redirect(request.url)
    
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    
    vision_data = analyze_image(filepath)
    if not vision_data or 'dish_name' not in vision_data:
        flash('Could not identify food.', 'danger')
        return redirect(url_for('dashboard'))
        
    dish_name = vision_data.get('dish_name')
    cuisine = vision_data.get('cuisine')
    category = vision_data.get('category')
    
    recipe_data = generate_full_recipe_details(dish_name, cuisine)
    if not recipe_data:
        flash('Error generating recipe.', 'danger')
        return redirect(url_for('dashboard'))
    
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        INSERT INTO recipes (
            user_id, image_path, dish_name, cuisine_type, category,
            ingredients_en, instructions_en, 
            ingredients_ta, instructions_ta,
            cooking_time, difficulty, content_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        session['user_id'], f"uploads/{filename}", dish_name, cuisine, category,
        json.dumps(recipe_data['english']['ingredients']),
        json.dumps(recipe_data['english']['instructions']),
        json.dumps(recipe_data['tamil']['ingredients']),
        json.dumps(recipe_data['tamil']['instructions']),
        recipe_data['english']['cooking_time'],
        recipe_data['english']['difficulty'],
        json.dumps(recipe_data)
    ))
    recipe_id = c.lastrowid
    
    nutri = recipe_data['nutrition']
    c.execute('''
        INSERT INTO nutrition_data (recipe_id, calories, protein, carbs, fats, fiber, raw_json) 
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (recipe_id, nutri.get('calories'), nutri.get('protein'), nutri.get('carbs'), nutri.get('fats'), nutri.get('fiber'), json.dumps(nutri)))
    
    conn.commit()
    conn.close()
    return redirect(url_for('view_recipe', id=recipe_id))

@app.route('/recipe/<int:id>')
def view_recipe(id):
    conn = get_db_connection()
    recipe = conn.execute('SELECT * FROM recipes WHERE id = ?', (id,)).fetchone()
    
    if recipe is None:
        conn.close()
        return "Recipe not found", 404
        
    nutrition = conn.execute('SELECT * FROM nutrition_data WHERE recipe_id = ?', (id,)).fetchone()
    
    # Check favorite
    is_favorite = False
    if 'user_id' in session:
        fav = conn.execute('SELECT * FROM favorites WHERE user_id = ? AND recipe_id = ?', 
                          (session['user_id'], id)).fetchone()
        is_favorite = True if fav else False
    
    conn.close()
    
    # Parse JSON fields for template use
    r_dict = dict(recipe)
    try:
        r_dict['ingredients_en'] = json.loads(r_dict['ingredients_en'])
        r_dict['instructions_en'] = json.loads(r_dict['instructions_en'])
        
        # Parse content_json safely
        if r_dict['content_json']:
            additional_data = json.loads(r_dict['content_json'])
            r_dict['image_prompts'] = additional_data.get('image_prompts', [])
            r_dict['video_script'] = additional_data.get('video_script', {})
            r_dict['estimated_cost'] = additional_data.get('estimated_cost', 'N/A')
        else:
            r_dict['estimated_cost'] = 'N/A'
            
    except Exception as e:
        print(f"Error parsing recipe JSON: {e}")

    return render_template('recipe.html', recipe=r_dict, nutrition=nutrition, is_favorite=is_favorite)

@app.route('/history')
def history():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    recipes = conn.execute('SELECT * FROM recipes WHERE user_id = ? ORDER BY created_at DESC', (session['user_id'],)).fetchall()
    conn.close()
    return render_template('history.html', recipes=recipes)

@app.route('/favorites')
def favorites():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    recipes = conn.execute('''
        SELECT r.* FROM recipes r
        JOIN favorites f ON r.id = f.recipe_id
        WHERE f.user_id = ?
        ORDER BY r.created_at DESC
    ''', (session['user_id'],)).fetchall()
    conn.close()
    return render_template('favorites.html', recipes=recipes)

@app.route('/api/favorite/<int:recipe_id>', methods=['POST'])
def toggle_favorite(recipe_id):
    if 'user_id' not in session: return jsonify({'error': '401'}), 401
    conn = get_db_connection()
    uid = session['user_id']
    existing = conn.execute('SELECT * FROM favorites WHERE user_id=? AND recipe_id=?', (uid, recipe_id)).fetchone()
    if existing:
        conn.execute('DELETE FROM favorites WHERE user_id=? AND recipe_id=?', (uid, recipe_id))
        status = 'removed'
    else:
        conn.execute('INSERT INTO favorites (user_id, recipe_id) VALUES (?, ?)', (uid, recipe_id))
        status = 'added'
    conn.commit()
    conn.close()
    return jsonify({'status': status})

# --- New Features ---

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    message = data.get('message')
    recipe_context = data.get('context')
    
    if not message:
        return jsonify({'response': "I didn't catch that."})
        
    response = chat_with_chef(message, recipe_context)
    return jsonify({'response': response})

@app.route('/shopping-list')
def shopping_list():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    items = conn.execute('SELECT * FROM shopping_list WHERE user_id = ? ORDER BY id DESC', (session['user_id'],)).fetchall()
    conn.close()
    return render_template('shopping_list.html', items=items)

@app.route('/api/shopping-list/add', methods=['POST'])
def add_shopping_item():
    if 'user_id' not in session: return jsonify({'error': '401'}), 401
    item = request.json.get('item')
    if item:
        conn = get_db_connection()
        conn.execute('INSERT INTO shopping_list (user_id, item) VALUES (?, ?)', (session['user_id'], item))
        conn.commit()
        conn.close()
        return jsonify({'status': 'added'})
    return jsonify({'status': 'error'})

@app.route('/api/shopping-list/toggle/<int:item_id>', methods=['POST'])
def toggle_shopping_item(item_id):
    if 'user_id' not in session: return jsonify({'error': '401'}), 401
    conn = get_db_connection()
    # Check current status
    curr = conn.execute('SELECT is_checked FROM shopping_list WHERE id = ?', (item_id,)).fetchone()
    if curr:
        new_val = 0 if curr['is_checked'] else 1
        conn.execute('UPDATE shopping_list SET is_checked = ? WHERE id = ?', (new_val, item_id))
        conn.commit()
    conn.close()
    return jsonify({'status': 'toggled'})

@app.route('/api/shopping-list/delete/<int:item_id>', methods=['POST'])
def delete_shopping_item(item_id):
    if 'user_id' not in session: return jsonify({'error': '401'}), 401
    conn = get_db_connection()
    conn.execute('DELETE FROM shopping_list WHERE id = ?', (item_id,))
    conn.commit()
    conn.close()
    return jsonify({'status': 'deleted'})


# Auth
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        if register_user(name, email, password):
            flash('Registered!', 'success')
            return redirect(url_for('login'))
        else:
            flash('Email taken.', 'danger')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = authenticate_user(email, password)
        if user:
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# --- V2.1 Professional Features ---

@app.route('/recipe/add', methods=['GET', 'POST'])
def add_recipe():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    if request.method == 'POST':
        # Handle manual creation
        dish_name = request.form['dish_name']
        cuisine = request.form['cuisine_type']
        category = request.form['category']
        cooking_time = request.form['cooking_time']
        difficulty = request.form['difficulty']
        
        ingredients = request.form.getlist('ingredients[]')
        instructions = request.form.getlist('instructions[]')
        
        # Image
        image_path = "img/default_food.jpg" # Fallback
        if 'image' in request.files:
            file = request.files['image']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                image_path = f"uploads/{filename}"

        # Save
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('''
            INSERT INTO recipes (
                user_id, image_path, dish_name, cuisine_type, category,
                ingredients_en, instructions_en, 
                cooking_time, difficulty, content_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            session['user_id'], image_path, dish_name, cuisine, category,
            json.dumps(ingredients), json.dumps(instructions),
            cooking_time, difficulty,
            json.dumps({'manual': True}) # Marker
        ))
        recipe_id = c.lastrowid
        
        # Placeholder Nutrition
        c.execute('INSERT INTO nutrition_data (recipe_id, calories) VALUES (?, ?)', (recipe_id, "N/A"))
        
        conn.commit()
        conn.close()
        return redirect(url_for('view_recipe', id=recipe_id))
        
    return render_template('recipe_form.html', recipe=None)

@app.route('/recipe/edit/<int:id>', methods=['GET', 'POST'])
def edit_recipe(id):
    if 'user_id' not in session: return redirect(url_for('login'))
    
    conn = get_db_connection()
    recipe = conn.execute('SELECT * FROM recipes WHERE id = ? AND user_id = ?', (id, session['user_id'])).fetchone()
    
    if not recipe:
        flash('Recipe not found or access denied.', 'danger')
        conn.close()
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        dish_name = request.form['dish_name']
        ingredients = request.form.getlist('ingredients[]')
        instructions = request.form.getlist('instructions[]')
        
        c = conn.cursor()
        c.execute('''
            UPDATE recipes SET 
            dish_name = ?, cuisine_type = ?, category = ?, 
            cooking_time = ?, difficulty = ?,
            ingredients_en = ?, instructions_en = ?
            WHERE id = ?
        ''', (
            dish_name, request.form['cuisine_type'], request.form['category'],
            request.form['cooking_time'], request.form['difficulty'],
            json.dumps(ingredients), json.dumps(instructions),
            id
        ))
        conn.commit()
        conn.close()
        flash('Recipe updated successfully!', 'success')
        return redirect(url_for('view_recipe', id=id))

    # Prep data for form
    r_dict = dict(recipe)
    try:
        r_dict['ingredients_en'] = json.loads(r_dict['ingredients_en'])
        r_dict['instructions_en'] = json.loads(r_dict['instructions_en'])
    except:
        pass
        
    conn.close()
    return render_template('recipe_form.html', recipe=r_dict)

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    conn = get_db_connection()
    
    if request.method == 'POST':
        name = request.form['name']
        conn.execute('UPDATE users SET name = ? WHERE id = ?', (name, session['user_id']))
        conn.commit()
        session['user_name'] = name # Update session
        flash('Profile updated!', 'success')
    
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    recipes_count = conn.execute('SELECT COUNT(*) FROM recipes WHERE user_id = ?', (session['user_id'],)).fetchone()[0]
    favorites_count = conn.execute('SELECT COUNT(*) FROM favorites WHERE user_id = ?', (session['user_id'],)).fetchone()[0]
    
    conn.close()
    return render_template('profile.html', user=user, recipes_count=recipes_count, favorites_count=favorites_count)

if __name__ == '__main__':
    app.run(debug=True)
