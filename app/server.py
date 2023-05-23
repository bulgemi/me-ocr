# server.py
from flask import Flask, render_template


app = Flask(__name__, static_folder="static")
app.config['DEBUG'] = True
app.secret_key = 'secret_key-9ed4d409-98dd-422b-9c48-9382da44423a'


@app.route("/")
def index():
    return render_template("index.html")
