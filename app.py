from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.middleware.dispatcher import DispatcherMiddleware
import mysql.connector
from dash_app import dash_app  # ton Dash app

# ------------------------ Flask App ------------------------
app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = "change_this_secret_key"  # obligatoire pour session

# ------------------------ DB Connection ------------------------
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",     # si tu as mis un mot de passe pour root, mets-le ici
        database="dataia",
        port=3306        # par défaut WAMP
    )

# ------------------------ Landing ------------------------
@app.route("/")
def landing():
    return render_template("landing.html")

# ------------------------ Signup ------------------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    error = None
    if request.method == "POST":
        nom = request.form.get("nom_utilisateur")
        email = request.form.get("email")
        password = request.form.get("mot_de_passe")
        hashed_password = generate_password_hash(password)

        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)

            cursor.execute("SELECT id_utilisateur FROM utilisateurs WHERE email=%s", (email,))
            if cursor.fetchone():
                error = "❌ Email déjà utilisé"
            else:
                cursor.execute(
                    "INSERT INTO utilisateurs (nom_utilisateur, email, mot_de_passe) VALUES (%s,%s,%s)",
                    (nom, email, hashed_password)
                )
                conn.commit()
                print(f"Utilisateur créé: {nom} / {email} ✅")
                return redirect(url_for("login"))

        except Exception as e:
            error = f"Erreur DB: {str(e)}"
            print(error)
        finally:
            cursor.close()
            conn.close()

    return render_template("signup.html", error=error)

# ------------------------ Login ------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("mot_de_passe")

        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM utilisateurs WHERE email=%s", (email,))
            user = cursor.fetchone()

            if user and check_password_hash(user["mot_de_passe"], password):
                # créer session
                session["user_id"] = user["id_utilisateur"]
                session["user_nom"] = user["nom_utilisateur"]
                session["user_email"] = user["email"]
                session["logged_in"] = True
                print(f"Session créée pour: {user['nom_utilisateur']}")
                return redirect("/dash/")

            error = "❌ Email ou mot de passe incorrect"

        except Exception as e:
            error = f"Erreur DB: {str(e)}"
            print(error)
        finally:
            cursor.close()
            conn.close()

    return render_template("login.html", error=error)

# ------------------------ Logout ------------------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ------------------------ Link Dash ------------------------
# Dash sera accessible sous /dash
app.wsgi_app = DispatcherMiddleware(app.wsgi_app, {
    "/dash": dash_app.server
})

# ------------------------ Run ------------------------
if __name__ == "__main__":
    app.run(debug=False)  # debug=False pour WAMP session stable
