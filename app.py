import mysql.connector
from flask import Flask, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

# Dash
from dash_app import create_dash_app

# ------------------------ Flask App ------------------------
app = Flask(
    __name__,
    static_folder="static",
    template_folder="templates"
)

app.secret_key = "super_secret_key_change_it"

# ------------------------ DB Connection ------------------------


def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="dataia",
        port=3306
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

        if not nom or not email or not password:
            error = "❌ Tous les champs sont obligatoires"
            return render_template("signup.html", error=error)

        hashed_password = generate_password_hash(password)

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Vérifier si email existe
        cursor.execute(
            "SELECT id_utilisateur FROM utilisateurs WHERE email = %s",
            (email,)
        )
        if cursor.fetchone():
            error = "❌ Email déjà utilisé"
        else:
            cursor.execute(
                """
                INSERT INTO utilisateurs (nom_utilisateur, email, mot_de_passe)
                VALUES (%s, %s, %s)
                """,
                (nom, email, hashed_password)
            )
            conn.commit()
            cursor.close()
            conn.close()
            return redirect(url_for("login"))

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

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT * FROM utilisateurs WHERE email = %s",
            (email,)
        )
        user = cursor.fetchone()

        if user and check_password_hash(user["mot_de_passe"], password):
            session["logged_in"] = True
            session["user_id"] = user["id_utilisateur"]
            session["user_nom"] = user["nom_utilisateur"]
            session["user_email"] = user["email"]

            cursor.close()
            conn.close()
            return redirect("/dash/")

        error = "❌ Email ou mot de passe incorrect"
        cursor.close()
        conn.close()

    return render_template("login.html", error=error)

# ------------------------ Logout ------------------------


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ------------------------ Protect Dash ------------------------


@app.before_request
def protect_dash():
    if request.path.startswith("/dash"):
        if not session.get("logged_in"):
            return redirect(url_for("login"))


# ------------------------ Init Dash ------------------------
create_dash_app(app)

# ------------------------ Run ------------------------
if __name__ == "__main__":
    app.run(debug=True)
