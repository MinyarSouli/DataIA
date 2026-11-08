# ================== 1. Imports ==================
import os
import re
from functools import wraps
from io import BytesIO

import mysql.connector
import pandas as pd
import requests
from flask import (Flask, flash, jsonify, make_response, redirect,
                   render_template, request, send_file, url_for)
from flask_login import (LoginManager, UserMixin, current_user, login_required,
                         login_user, logout_user)
from fpdf import FPDF
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from config_ia import MISTRAL_CONFIG, SYSTEM_PROMPT

# ================== 2. Config ==================
app = Flask(__name__)
app.config['SECRET_KEY'] = 'ma_cle_secrete_123'
app.config['UPLOAD_FOLDER'] = 'uploads'

MISTRAL_API_KEY = "rTC8zh0eyNB0GOV3OA8MySZL2KBCCaUn"

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")


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
        password = generate_password_hash(request.form.get('password'))
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

            
            if user_data.get('est_bloque') == 1:
                flash('Votre compte est bloqué par l\'administrateur.', 'danger')
                return render_template('login.html')

            
            user = User(user_data['id_utilisateur'], user_data['nom_utilisateur'],
                        user_data['email'], user_data['mot_de_passe'],
                        user_data['role'], user_data['est_bloque'])

            login_user(user)

           
            if user_data['role'] == 'administrateur':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('dashboard'))

        flash('Email ou mot de passe incorrect', 'danger')

    return render_template('login.html')


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        
        if not current_user.is_authenticated or current_user.role != 'administrateur':
            return "Accès interdit : Vous n'êtes pas administrateur", 403
        return f(*args, **kwargs)
    return decorated_function


@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM fichiers WHERE id_utilisateur = %s ORDER BY id_fichier DESC LIMIT 5", (current_user.id,))
    fichiers = cursor.fetchall()
    cursor.execute("SELECT COUNT(*) as count FROM questions WHERE id_utilisateur = %s", (current_user.id,))
    q_count = cursor.fetchone()['count']
    cursor.close()
    conn.close()
    return render_template('dashboard.html', fichiers=fichiers, questions_count=q_count)


@app.route('/chat/<int:file_id>')
@login_required
def chat(file_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM fichiers WHERE id_fichier = %s AND id_utilisateur = %s", (file_id, current_user.id))
    fichier = cursor.fetchone()
    cursor.execute(
        "SELECT question_texte, reponse_texte FROM questions WHERE id_fichier = %s ORDER BY date_question ASC", (file_id,))
    historique = cursor.fetchall()
    cursor.close()
    conn.close()
    if not fichier:
        return redirect(url_for('dashboard'))
    return render_template('chat.html', fichier=fichier, historique=historique)

# ================== Route ask_ia ==================


@app.route('/ask_ia', methods=['POST'])
@login_required
def ask_ia():
    try:
        data = request.get_json()
        file_id = data.get('file_id')
        user_question = data.get('question')

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM fichiers WHERE id_fichier = %s", (file_id,))
        fichier = cursor.fetchone()

        if not fichier:
            conn.close()
            return jsonify({"status": "error", "message": "Fichier introuvable"}), 404

        path = fichier['chemin_fichier']
        df = pd.read_csv(path) if path.endswith('.csv') else pd.read_excel(path)

        cols = df.columns.tolist()
        summary_stats = df.describe(include='all').to_string()
        head_data = df.head(5).to_string()

        texts = df.astype(str).apply(lambda x: " | ".join(f"{col}: {val}" for col, val in x.items()), axis=1).tolist()

        vector_store = FAISS.from_texts(texts, embeddings)
        relevant_docs = vector_store.similarity_search(user_question, k=100)
        context = "\n".join([doc.page_content for doc in relevant_docs])

        
        prompt_final = f"""
STRUCTURE DES COLONNES : {cols}
STATISTIQUES GLOBALES : {summary_stats}
EXEMPLE DE DONNÉES : {head_data}
CONTEXTE DÉTAILLÉ (RAG) :
{context}

QUESTION UTILISATEUR : {user_question}
"""

        url = "https://api.mistral.ai/v1/chat/completions"
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {MISTRAL_API_KEY}"}

       
        payload = {
            "model": MISTRAL_CONFIG["model"],
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt_final}
            ],
            "temperature": MISTRAL_CONFIG["temperature"],
            "top_p": MISTRAL_CONFIG["top_p"],
            "max_tokens": MISTRAL_CONFIG["max_tokens"],
            "n": MISTRAL_CONFIG["n"],
            "safe_prompt": MISTRAL_CONFIG["safe_prompt"]
        }

        response = requests.post(url, json=payload, headers=headers)

        if response.status_code == 200:
            answer = response.json()['choices'][0]['message']['content']
            cursor.execute("INSERT INTO questions (id_utilisateur, id_fichier, question_texte, reponse_texte, date_question) VALUES (%s, %s, %s, %s, NOW())",
                           (current_user.id, file_id, user_question, answer))
            conn.commit()
            cursor.close()
            conn.close()
            return jsonify({"status": "success", "answer": answer})

        return jsonify({"status": "error", "message": "Erreur lors de la communication avec l'IA"}), 500

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ================== Route export_pdf ==================


@app.route('/export_pdf', methods=['POST'])
@login_required
def export_pdf():
    try:
        
        data = request.get_json()
        history = data.get('history', '')
        conseil = data.get('conseil', 'Aucun conseil généré.')

       
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        
        cursor.execute(
            "SELECT id_question FROM questions WHERE id_utilisateur = %s ORDER BY id_question DESC LIMIT 1", (current_user.id,))
        result = cursor.fetchone()
        question_id = result['id_question'] if result else None

        
        
        pdf = FPDF()
        pdf.add_page()

       
        pdf.set_font("helvetica", "B", 18)
        pdf.cell(0, 15, "Rapport d'Analyse Automatique", ln=True, align='C')
        pdf.ln(5)

       
        def clean_text(t):
            return str(t).encode('latin-1', 'ignore').decode('latin-1')

       
        pdf.set_font("helvetica", "B", 12)
        pdf.cell(0, 10, "Historique des echanges :", ln=True)
        pdf.set_font("helvetica", size=10)
        pdf.multi_cell(0, 8, txt=clean_text(history))

        pdf.ln(10)

        
        pdf.set_fill_color(230, 240, 250)
        pdf.set_font("helvetica", "B", 12)
        pdf.cell(0, 10, "Conseil Strategique :", ln=True, fill=True)
        pdf.set_font("helvetica", "I", 11)
        pdf.multi_cell(0, 10, txt=clean_text(conseil), border=1)

        # 2. Gestion du stockage physique sur le serveur
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Rapport_U{current_user.id}_{timestamp}.pdf"

        # Vérification et création du dossier de destination si inexistant
        report_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'rapports')
        if not os.path.exists(report_folder):
            os.makedirs(report_folder)

        # Chemin complet pour sauvegarder le fichier PDF
        report_path = os.path.join(report_folder, filename)
        pdf.output(report_path)

        # 3. Enregistrement des métadonnées dans la table 'rapports' (selon ton image)
        # Colonnes cibles : id_question, rapport_texte, chemin_resume, date_generation
        query = """
            INSERT INTO rapports 
            (id_question, rapport_texte, chemin_resume, date_generation) 
            VALUES (%s, %s, %s, NOW())
        """
        # On insère un extrait du texte et le chemin physique du fichier
        cursor.execute(query, (question_id, clean_text(history[:500]), report_path))

        conn.commit()
        cursor.close()
        conn.close()

        # 4. Envoi du fichier généré au navigateur pour téléchargement
        return send_file(report_path, as_attachment=True, download_name="Rapport_DataIA.pdf")

    except Exception as e:
        # En cas d'erreur, on affiche le log dans la console et on renvoie un JSON d'erreur
        print(f"DEBUG EXPORT PDF: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ================== Mes Fichiers & Upload & Delete ==================


@app.route('/mes_fichiers')
@login_required
def mes_fichiers():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM fichiers WHERE id_utilisateur = %s ORDER BY id_fichier DESC", (current_user.id,))
    tous_les_fichiers = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('mes_fichiers.html', fichiers=tous_les_fichiers)


@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    if 'file' not in request.files:
        return redirect(url_for('dashboard'))
    file = request.files['file']
    if file.filename == '':
        return redirect(url_for('dashboard'))
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
        flash('Fichier uploadé avec succès!', 'success')
    return redirect(url_for('dashboard'))


@app.route('/delete_file/<int:file_id>')
@login_required
def delete_file(file_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT chemin_fichier FROM fichiers WHERE id_fichier = %s AND id_utilisateur = %s",
                   (file_id, current_user.id))
    fichier = cursor.fetchone()
    if fichier:
        if os.path.exists(fichier['chemin_fichier']):
            os.remove(fichier['chemin_fichier'])
        cursor.execute("DELETE FROM fichiers WHERE id_fichier = %s", (file_id,))
        conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('dashboard'))


@app.route('/admin/dashboard')
@login_required
@admin_required
def admin_dashboard():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        
        cursor.execute("SELECT COUNT(*) as total FROM utilisateurs")
        users_count = cursor.fetchone()['total']
        cursor.execute("SELECT COUNT(*) as total FROM rapports")
        reports_count = cursor.fetchone()['total']

    
        cursor.execute("""
            SELECT u.*, 
                   COUNT(q.id_question) as nb_questions,
                   (SELECT COUNT(*) FROM rapports r 
                    JOIN questions q2 ON r.id_question = q2.id_question 
                    WHERE q2.id_utilisateur = u.id_utilisateur) as nb_rapports
            FROM utilisateurs u 
            LEFT JOIN questions q ON u.id_utilisateur = q.id_utilisateur 
            GROUP BY u.id_utilisateur
        """)
        all_users = cursor.fetchall()

        # 3
        query = """
            SELECT r.id_rapport, q.question_texte, u.nom_utilisateur as user_name, 
                   r.date_generation, r.chemin_resume 
            FROM rapports r
            JOIN questions q ON r.id_question = q.id_question
            JOIN utilisateurs u ON q.id_utilisateur = u.id_utilisateur
            ORDER BY r.date_generation DESC
        """
        cursor.execute(query)
        reports_list = cursor.fetchall()

        cursor.close()
        conn.close()

        return render_template('admin_dashboard.html',
                               users=users_count,
                               reports=reports_count,
                               list=reports_list,
                               all_users=all_users)
    except Exception as e:
        return f"Erreur Admin: {str(e)}"


@app.route('/view_report/<path:filename>')
@login_required
def view_report(filename):
    try:
        return send_file(filename)
    except Exception as e:
        return f"Fichier introuvable: {str(e)}"

# 1. Route pour supprimer un utilisateur


@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    if current_user.role != 'administrateur':
        return "Accès refusé", 403
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "DELETE FROM rapports WHERE id_question IN (SELECT id_question FROM questions WHERE id_utilisateur = %s)", (user_id,))
        cursor.execute("DELETE FROM questions WHERE id_utilisateur = %s", (user_id,))
        cursor.execute("DELETE FROM fichiers WHERE id_utilisateur = %s", (user_id,))
        cursor.execute("DELETE FROM utilisateurs WHERE id_utilisateur = %s", (user_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return redirect(url_for('admin_dashboard'))
    except Exception as e:
        return str(e)

# 2. Route pour bloquer/débloquer


@app.route('/admin/toggle_user/<int:user_id>', methods=['POST'])
@login_required
def toggle_user(user_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT est_bloque FROM utilisateurs WHERE id_utilisateur = %s", (user_id,))
        user = cursor.fetchone()

        nouvel_etat = 1 if user['est_bloque'] == 0 else 0

        cursor.execute("UPDATE utilisateurs SET est_bloque = %s WHERE id_utilisateur = %s", (nouvel_etat, user_id))
        conn.commit()
        cursor.close()
        conn.close()
        return redirect(url_for('admin_dashboard'))
    except Exception as e:
        return f"Erreur: {str(e)}"


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(debug=True)
