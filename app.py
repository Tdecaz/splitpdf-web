from flask import Flask, render_template, request, send_file
import os
from PyPDF2 import PdfMerger, PdfReader, PdfWriter
from werkzeug.utils import secure_filename
from zipfile import ZipFile

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
        total_pages = len(reader.pages)
        from_pages = request.form.getlist('from_page[]')
        to_pages = request.form.getlist('to_page[]')
        merge_ranges = 'merge_ranges' in request.form

        ranges = []
        for f, t in zip(from_pages, to_pages):
            start = max(1, int(f))
            end = min(total_pages, int(t))
            if start <= end:
                ranges.append((start, end))

        if not ranges:
            return 'No valid ranges specified.'

        if merge_ranges:
            writer = PdfWriter()
            for start, end in ranges:
                for i in range(start - 1, end):
                    writer.add_page(reader.pages[i])
            merged_path = os.path.join(RESULT_FOLDER, 'merged_ranges.pdf')
            with open(merged_path, 'wb') as f:
                writer.write(f)
            return send_file(merged_path, as_attachment=True)
        else:
            zip_path = os.path.join(RESULT_FOLDER, 'split_ranges.zip')
            with ZipFile(zip_path, 'w') as zipf:
                for idx, (start, end) in enumerate(ranges):
                    writer = PdfWriter()
                    for i in range(start - 1, end):
                        writer.add_page(reader.pages[i])
                    part_path = os.path.join(RESULT_FOLDER, f'range_{idx+1}.pdf')
                    with open(part_path, 'wb') as f:
                        writer.write(f)
                    zipf.write(part_path, arcname=f'range_{idx+1}.pdf')
            return send_file(zip_path, as_attachment=True)
    return 'Invalid file format.'

if __name__ == '__main__':
    app.run(debug=True)