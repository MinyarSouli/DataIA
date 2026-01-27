# ================== 1. Imports ==================
import os
import re

import mysql.connector
import pandas as pd
import requests  # pour Mistral API
from flask import (Flask, flash, jsonify, redirect, render_template, request,
                   url_for)
from flask_login import (LoginManager, UserMixin, current_user, login_required,
                         login_user, logout_user)
from fpdf import FPDF
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

# ================== 2. Config ==================
app = Flask(__name__)
app.config['SECRET_KEY'] = 'ma_cle_secrete_123'
app.config['UPLOAD_FOLDER'] = 'uploads'

# --- Configuration Mistral ---
MISTRAL_API_KEY = "rTC8zh0eyNB0GOV3OA8MySZL2KBCCaUn"


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

    # نجيبوا كان آخر 5 ملفات باستعمال LIMIT 5
    cursor.execute("""
        SELECT * FROM fichiers 
        WHERE id_utilisateur = %s 
        ORDER BY id_fichier DESC 
        LIMIT 5
    """, (current_user.id,))
    fichiers = cursor.fetchall()

    # إحصائيات سريعة
    cursor.execute("SELECT COUNT(*) as count FROM questions WHERE id_utilisateur = %s", (current_user.id,))
    q_count = cursor.fetchone()['count']

    cursor.close()
    conn.close()
    return render_template('dashboard.html', fichiers=fichiers, questions_count=q_count)


# --- الـ Route الجديدة لجميع الملفات ---
@app.route('/mes_fichiers')
@login_required
def mes_fichiers():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # نجيبوا الملفات الكل من غير LIMIT
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
        flash('Fichier uploadé!', 'success')
    return redirect(url_for('dashboard'))


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/chat/<int:file_id>')
@login_required
def chat(file_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # 1. Njibou el-fichier
    cursor.execute("SELECT * FROM fichiers WHERE id_fichier = %s AND id_utilisateur = %s", (file_id, current_user.id))
    fichier = cursor.fetchone()

    # 2. Njibou el-historique mta3 el-chat l-hadha el-fichier bed-dabt
    cursor.execute("""
        SELECT question_texte, reponse_texte 
        FROM questions 
        WHERE id_fichier = %s AND id_utilisateur = %s 
        ORDER BY date_question ASC
    """, (file_id, current_user.id))
    historique = cursor.fetchall()

    cursor.close()
    conn.close()

    if not fichier:
        return redirect(url_for('dashboard'))

    # Nab3thou el-historique lel-HTML
    return render_template('chat.html', fichier=fichier, historique=historique)


@app.route('/ask_ia', methods=['POST'])
@login_required
def ask_ia():
    try:
        data = request.get_json()
        file_id = data.get('file_id')
        user_question = data.get('question')

        if not user_question:
            return jsonify({"status": "error", "message": "Question vide"}), 400

        # 1. Njibou el-fichier mel Base de données
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM fichiers WHERE id_fichier = %s", (file_id,))
        fichier = cursor.fetchone()

        if not fichier:
            cursor.close()
            conn.close()
            return jsonify({"status": "error", "message": "Fichier introuvable"}), 404

        # 2. Na9raw el-data (CSV wala Excel)
        path = fichier['chemin_fichier']
        try:
            df = pd.read_csv(path) if path.endswith('.csv') else pd.read_excel(path)
            context = df.head(15).to_string()  # Nékhdou awel 15 lignes k-contexte
        except Exception as e:
            return jsonify({"status": "error", "message": f"Erreur lecture fichier: {str(e)}"}), 500

        # 3. Kallam Mistral API
        url = "https://api.mistral.ai/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {MISTRAL_API_KEY}"
        }

        payload = {
            "model": "open-mistral-7b",
            "messages": [
                {
                    "role": "system",
                    "content": """Tu es un expert en Business Intelligence.
                    Réponds directement aux questions sur les données.
                    1. Pas de code Python/SQL.
                    2. Pas de blabla technique.
                    3. Si graphique demandé, réponds UNIQUEMENT avec ce JSON : {"type_graph": "bar", "data": {"x": [], "y": []}, "title": "..."}"""
                },
                {
                    "role": "user",
                    "content": f"Données du fichier {fichier['nom_fichier']} :\n{context}\n\nQuestion: {user_question}"
                }
            ],
            "temperature": 0.2
        }

        response = requests.post(url, json=payload, headers=headers)
        result = response.json()

        if response.status_code == 200:
            answer = result['choices'][0]['message']['content']

            # 4. Tasjil fil-base (Table questions)
            # Thabbet m3aya f-asme el-colonnes: question_texte, reponse_texte, date_question
            query = """INSERT INTO questions 
                       (id_utilisateur, id_fichier, question_texte, reponse_texte, date_question) 
                       VALUES (%s, %s, %s, %s, NOW())"""

            cursor.execute(query, (current_user.id, file_id, user_question, answer))
            conn.commit()

            cursor.close()
            conn.close()

            return jsonify({"status": "success", "answer": answer})

        else:
            cursor.close()
            conn.close()
            return jsonify({"status": "error", "message": "Erreur API Mistral"}), 500

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/export_pdf', methods=['POST'])
@login_required
def export_pdf():
    try:
        data = request.get_json()
        chat_content = data.get('content', '')

        # 1. Nettoyage : Na7iw el-Emojis w el-caractères elli ya3mlou machakel
        # fpdf2 fil-base ma t-7ebbech el-non-latin
        clean_text = re.sub(r'[^\x00-\x7F]+', ' ', chat_content)

        pdf = FPDF()
        pdf.add_page()

        # 2. Police standard
        pdf.set_font("helvetica", "B", 16)
        pdf.cell(0, 10, "Rapport d'Analyse IA", new_x="LMARGIN", new_y="NEXT", align='C')
        pdf.ln(10)

        # 3. Contenu
        pdf.set_font("helvetica", "", 12)
        pdf.multi_cell(0, 10, txt=clean_text)

        # 4. Response correcte pour Flask
        pdf_bytes = pdf.output()  # fpdf2 output() ya3ti bytes direct

        response = make_response(pdf_bytes)
        response.headers.set('Content-Disposition', 'attachment', filename='rapport.pdf')
        response.headers.set('Content-Type', 'application/pdf')
        return response

    except Exception as e:
        print(f"Erreur PDF détaillée: {str(e)}")  # Chof el-terminal hna!
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/delete_file/<int:file_id>')
@login_required
def delete_file(file_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # 1. نجيبوا مسار الملف قبل ما نفسخوه باش نحيوه مالـ Dossier
    cursor.execute("SELECT chemin_fichier FROM fichiers WHERE id_fichier = %s AND id_utilisateur = %s",
                   (file_id, current_user.id))
    fichier = cursor.fetchone()

    if fichier:
        # فسخ الملف من الـ Dossier uploads
        if os.path.exists(fichier['chemin_fichier']):
            os.remove(fichier['chemin_fichier'])

        # 2. فسخ التسجيل من الـ Database
        cursor.execute("DELETE FROM fichiers WHERE id_fichier = %s", (file_id,))
        conn.commit()
        flash("Fichier supprimé avec succès", "success")

    cursor.close()
    conn.close()
    return redirect(url_for('dashboard'))


if __name__ == '__main__':
    app.run(debug=True)
