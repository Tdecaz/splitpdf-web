from flask import Flask, render_template, request, send_file, redirect, url_for
import os
from PyPDF2 import PdfMerger, PdfReader, PdfWriter
from werkzeug.utils import secure_filename
from zipfile import ZipFile
import re

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
RESULT_FOLDER = 'results'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/')
def home():
    return render_template('landing.html')

@app.route('/merge', methods=['GET', 'POST'])
def merge():
    if request.method == 'POST':
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
    return render_template('merge.html')

@app.route('/split', methods=['GET', 'POST'])
def split():
    if request.method == 'POST':
        file = request.files['file']
        if not (file and file.filename.endswith('.pdf')):
            return 'Invalid file format.'
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        reader = PdfReader(filepath)
        total_pages = len(reader.pages)
        merge_ranges = 'merge_ranges' in request.form
        split_mode = request.form.get('split_mode', 'range')

        ranges = []
        if split_mode == 'range':
            from_pages = request.form.getlist('from_page[]')
            to_pages = request.form.getlist('to_page[]')
            for f, t in zip(from_pages, to_pages):
                start = max(1, int(f))
                end = min(total_pages, int(t))
                if start <= end:
                    ranges.append((start, end))
        elif split_mode == 'pages':
            page_list = request.form.get('page_list', '')
            tokens = [x.strip() for x in page_list.split(',') if x.strip()]
            for token in tokens:
                m = re.match(r"^(\d+)-(\d+)$", token)
                if m:
                    start, end = int(m.group(1)), int(m.group(2))
                    if 1 <= start <= end <= total_pages:
                        ranges.append((start, end))
                else:
                    try:
                        page = int(token)
                        if 1 <= page <= total_pages:
                            ranges.append((page, page))
                    except ValueError:
                        pass

        if not ranges:
            return 'No valid pages or ranges specified.'

        if merge_ranges:
            writer = PdfWriter()
            for start, end in ranges:
                for i in range(start - 1, end):
                    writer.add_page(reader.pages[i])
            merged_path = os.path.join(RESULT_FOLDER, 'merged_pages.pdf')
            with open(merged_path, 'wb') as f:
                writer.write(f)
            return send_file(merged_path, as_attachment=True)
        else:
            zip_path = os.path.join(RESULT_FOLDER, 'split_pages.zip')
            with ZipFile(zip_path, 'w') as zipf:
                for idx, (start, end) in enumerate(ranges):
                    writer = PdfWriter()
                    for i in range(start - 1, end):
                        writer.add_page(reader.pages[i])
                    part_path = os.path.join(RESULT_FOLDER, f'pages_{start}_to_{end}.pdf')
                    with open(part_path, 'wb') as f:
                        writer.write(f)
                    zipf.write(part_path, arcname=f'pages_{start}_to_{end}.pdf')
            return send_file(zip_path, as_attachment=True)
    return render_template('split.html')

if __name__ == '__main__':
    app.run(debug=True)