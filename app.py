from flask import Flask, render_template, request, send_file, redirect, url_for
import os
from PyPDF2 import PdfMerger, PdfReader, PdfWriter
from werkzeug.utils import secure_filename

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
RESULT_FOLDER = 'results'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/merge', methods=['POST'])
def merge():
    files = request.files.getlist('files')
    merger = PdfMerger()

    for f in files:
        if f and f.filename.endswith('.pdf'):
            filename = secure_filename(f.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            f.save(filepath)
            merger.append(filepath)

    output_path = os.path.join(RESULT_FOLDER, 'merged.pdf')
    merger.write(output_path)
    merger.close()

    return send_file(output_path, as_attachment=True)

@app.route('/split', methods=['POST'])
def split():
    file = request.files['file']
    if file and file.filename.endswith('.pdf'):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        reader = PdfReader(filepath)
        for i, page in enumerate(reader.pages):
            writer = PdfWriter()
            writer.add_page(page)
            output_path = os.path.join(RESULT_FOLDER, f'page_{i+1}.pdf')
            with open(output_path, 'wb') as f:
                writer.write(f)

        return redirect(url_for('index'))
    return 'Invalid file format.'

if __name__ == '__main__':
    app.run(debug=True)