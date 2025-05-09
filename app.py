from flask import Flask, render_template, request, redirect
import pymysql
import os
import uuid
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB

# MySQL config (used in connection)
DB_HOST = os.getenv('DB_HOST')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_NAME = os.getenv('DB_NAME')
DB_PORT=os.getenv('DB_PORT')
# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Function to get DB connection
def get_db_connection():
    return pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        port=int(DB_PORT),
        cursorclass=pymysql.cursors.DictCursor
    )

@app.route('/', methods=['GET', 'POST'])
def index():
    connection = get_db_connection()
    cursor = connection.cursor()
    
    cursor.execute("SELECT id, name FROM technologies")
    technologies = cursor.fetchall()
    if request.method == 'POST':
        unique_id = str(uuid.uuid4())
        name = request.form['name']
        email = request.form['email']
        mobile = request.form['mobile']
        total_exp = request.form['total_exp']
        relevant_exp = request.form['relevant_exp']
        location = request.form['location']
        relocation = request.form['relocation']
        notice = request.form['notice']
        ctc = request.form['ctc']
        ectc = request.form['ectc']
        technology_id = request.form['technology']

        file = request.files['resume']
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            filename = f"{unique_id}_{filename}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
        else:
            filename = None

        cursor.execute("""
            INSERT INTO candidates 
            (id, name, email, mobile, total_exp, relevant_exp, location, relocation, notice, ctc, ectc, resume, technology_id, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, '1')
        """, (unique_id, name, email, mobile, total_exp, relevant_exp, location, relocation, notice, ctc, ectc, filename, technology_id))
        
        connection.commit()
        cursor.close()
        connection.close()

        return "Form submitted successfully!"

    cursor.close()
    connection.close()
    return render_template('form.html', technologies=technologies)

if __name__ == '__main__':
    app.run(debug=True)
