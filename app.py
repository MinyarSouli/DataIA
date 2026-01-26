# ================== 1. Imports ==================
import os
import pandas as pd
import mysql.connector
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# ================== 2. Config ==================
app = Flask(__name__)
app.config['SECRET_KEY'] = 'ma_cle_secrete_123'
app.config['UPLOAD_FOLDER'] = 'uploads'

# Thabbet el-dossier mta3 el-uploads mawjoud
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Connection function direct lel MySQL
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="", 
        database="dataia"
    )

# ================== 3. Login Manager & User Class ==================
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Class User makhdouma bech t-wafe9 Flask-Login m3a el-Base mta3ek
class User(UserMixin):
    def __init__(self, id_user, nom, email, password, role, bloque):
        self.id = id_user
        self.nom = nom
        self.email = email
        self.password = password
        self.role = role
        self.bloque = bloque

@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM utilisateurs WHERE id_utilisateur = %s", (user_id,))
    user_data = cursor.fetchone()
    cursor.close()
    conn.close()
    if user_data:
        return User(user_data['id_utilisateur'], user_data['nom_utilisateur'], 
                    user_data['email'], user_data['mot_de_passe'], 
                    user_data['role'], user_data['est_bloque'])
    return None

# ================== 4. Routes ==================

@app.route('/')
def landing():
    return render_template('landing.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        nom = request.form.get('nom_utilisateur')
        email = request.form.get('email')
        password = generate_password_hash(request.form.get('password'), method='pbkdf2:sha256')

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO utilisateurs (nom_utilisateur, email, mot_de_passe) VALUES (%s, %s, %s)", 
                           (nom, email, password))
            conn.commit()
            flash('Compte créé! Connectez-vous.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            flash(f"Erreur: {e}", "danger")
        finally:
            cursor.close()
            conn.close()
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM utilisateurs WHERE email = %s", (email,))
        user_data = cursor.fetchone()
        cursor.close()
        conn.close()

        if user_data and check_password_hash(user_data['mot_de_passe'], password):
            user = User(user_data['id_utilisateur'], user_data['nom_utilisateur'], 
                        user_data['email'], user_data['mot_de_passe'], 
                        user_data['role'], user_data['est_bloque'])
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Email ou mot de passe incorrect', 'danger')
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM fichiers WHERE id_utilisateur = %s", (current_user.id,))
    fichiers = cursor.fetchall()
    
    # Statistique sghira
    cursor.execute("SELECT COUNT(*) as count FROM questions WHERE id_utilisateur = %s", (current_user.id,))
    q_count = cursor.fetchone()['count']
    
    cursor.close()
    conn.close()
    return render_template('dashboard.html', fichiers=fichiers, questions_count=q_count)

@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    if 'file' not in request.files: return redirect(url_for('dashboard'))
    file = request.files['file']
    if file.filename == '': return redirect(url_for('dashboard'))
    
    if file:
        filename = secure_filename(file.filename)
        path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(path)
        
        file_type = 'Excel' if filename.endswith(('.xls', '.xlsx')) else 'CSV'
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO fichiers (id_utilisateur, nom_fichier, chemin_fichier, type_fichier) VALUES (%s, %s, %s, %s)",
                       (current_user.id, filename, path, file_type))
        conn.commit()
        cursor.close()
        conn.close()
        flash('Fichier uploadé!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)