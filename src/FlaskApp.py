from simulation import MyApp
from flask import Flask, render_template

flaskApp = Flask(__name__)

@flaskApp.route('/')
def home():
    app = MyApp()
    return render_template('home.html', app=app)


if __name__ == '__main__':
    flaskApp.run(debug=True)
