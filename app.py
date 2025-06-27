import os
import re
import threading
import time
from flask import Flask, render_template, request, send_file, redirect, url_for, after_this_request
from werkzeug.utils import secure_filename
from PyPDF2 import PdfMerger, PdfReader, PdfWriter
from zipfile import ZipFile
import pikepdf
from PIL import Image
import img2pdf
from fpdf import FPDF

try:
    from docx2pdf import convert as docx2pdf_convert
    DOCX2PDF_AVAILABLE = True
except ImportError:
    DOCX2PDF_AVAILABLE = False

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
RESULT_FOLDER = 'results'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- Background temp file cleanup ---
def cleanup_temp_dirs():
    while True:
        now = time.time()
        for folder in [UPLOAD_FOLDER, RESULT_FOLDER]:
            for f in os.listdir(folder):
                fpath = os.path.join(folder, f)
                if os.path.isfile(fpath) and now - os.path.getmtime(fpath) > 600:  # 10 min
                    try:
                        os.remove(fpath)
                    except Exception:
                        pass
        time.sleep(600)  # Run every 10 minutes

threading.Thread(target=cleanup_temp_dirs, daemon=True).start()

# --- Landing Page ---
@app.route('/')
def home():
    return render_template('landing.html')

# --- Merge PDF ---
@app.route('/merge', methods=['GET', 'POST'])
def merge():
    if request.method == 'POST':
        files = request.files.getlist('files')
        uploaded_filepaths = []
        merger = PdfMerger()
        for f in files:
            if f and f.filename.endswith('.pdf'):
                filename = secure_filename(f.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                f.save(filepath)
                uploaded_filepaths.append(filepath)
                merger.append(filepath)
        output_path = os.path.join(RESULT_FOLDER, 'merged.pdf')
        merger.write(output_path)
        merger.close()

        @after_this_request
        def cleanup(response):
            try:
                os.remove(output_path)
                for f in uploaded_filepaths:
                    os.remove(f)
            except Exception:
                pass
            return response
        return send_file(output_path, as_attachment=True)
    return render_template('merge.html')

# --- Split PDF ---
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

        output_files = []
        if merge_ranges:
            writer = PdfWriter()
            for start, end in ranges:
                for i in range(start - 1, end):
                    writer.add_page(reader.pages[i])
            merged_path = os.path.join(RESULT_FOLDER, 'merged_pages.pdf')
            with open(merged_path, 'wb') as f:
                writer.write(f)
            output_files.append(merged_path)
            out_file = merged_path
            as_zip = False
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
                    output_files.append(part_path)
            out_file = zip_path
            as_zip = True

        @after_this_request
        def cleanup(response):
            try:
                os.remove(filepath)
                if as_zip:
                    os.remove(out_file)
                    for f in output_files:
                        if os.path.exists(f):
                            os.remove(f)
                else:
                    os.remove(out_file)
            except Exception:
                pass
            return response

        return send_file(out_file, as_attachment=True)
    return render_template('split.html')

# --- Compress PDF ---
@app.route('/compress', methods=['GET', 'POST'])
def compress():
    if request.method == 'POST':
        file = request.files['file']
        if file and file.filename.endswith('.pdf'):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

            compressed_path = os.path.join(RESULT_FOLDER, f'compressed_{filename}')
            pdf = pikepdf.open(filepath)
            pdf.save(compressed_path, optimize_streams=True)
            pdf.close()

            @after_this_request
            def cleanup(response):
                try:
                    os.remove(filepath)
                    os.remove(compressed_path)
                except Exception:
                    pass
                return response

            return send_file(compressed_path, as_attachment=True)
        return 'Invalid file format.'
    return render_template('compress.html')

# --- Convert to PDF ---
@app.route('/convert', methods=['GET', 'POST'])
def convert():
    if request.method == 'POST':
        file = request.files['file']
        if not file:
            return 'No file uploaded.'

        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        ext = filename.rsplit('.', 1)[-1].lower()
        output_path = os.path.join(RESULT_FOLDER, f'converted.pdf')

        # Word to PDF
        if ext == 'docx' and DOCX2PDF_AVAILABLE:
            try:
                docx2pdf_convert(filepath, output_path)
            except Exception as e:
                return f'Word to PDF conversion failed: {str(e)}'
        # Image to PDF (JPG, PNG, etc.)
        elif ext in ['jpg', 'jpeg', 'png', 'bmp', 'tiff']:
            try:
                im = Image.open(filepath)
                rgb_im = im.convert('RGB')
                rgb_im.save(output_path, 'PDF')
            except Exception as e:
                return f'Image to PDF conversion failed: {str(e)}'
        else:
            return 'Only DOCX or image files are supported for conversion.'

        @after_this_request
        def cleanup(response):
            try:
                os.remove(filepath)
                os.remove(output_path)
            except Exception:
                pass
            return response

        return send_file(output_path, as_attachment=True)
    return render_template('convert.html')

# --- TXT to PDF ---
@app.route('/txt2pdf', methods=['GET', 'POST'])
def txt2pdf():
    if request.method == 'POST':
        text = request.form.get('text')
        file = request.files.get('file')
        if not text and not file:
            return 'Provide a TXT file or paste text.'
        if file and file.filename.endswith('.txt'):
            text = file.read().decode('utf-8')
        pdf_path = os.path.join(RESULT_FOLDER, 'output.pdf')
        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.set_font("Arial", size=12)
        for line in text.splitlines():
            pdf.cell(0, 10, line, ln=True)
        pdf.output(pdf_path)

        @after_this_request
        def cleanup(response):
            try:
                os.remove(pdf_path)
            except Exception:
                pass
            return response

        return send_file(pdf_path, as_attachment=True)
    return render_template('txt2pdf.html')

# --- Edit Pages (Reorder, Rotate, Delete) ---
@app.route('/edit-pages', methods=['GET', 'POST'])
def edit_pages():
    if request.method == 'POST':
        file = request.files['file']
        if not (file and file.filename.endswith('.pdf')):
            return 'Invalid file format.'

        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        reader = PdfReader(filepath)
        total_pages = len(reader.pages)

        # Get user’s new order, rotations, and deletions
        new_order = request.form.getlist('page_order[]')
        rotations = request.form.getlist('rotation[]')
        keep_pages = request.form.getlist('keep_page[]')

        writer = PdfWriter()
        for idx, page_num_str in enumerate(new_order):
            page_idx = int(page_num_str) - 1
            if str(page_idx+1) in keep_pages and 0 <= page_idx < total_pages:
                page = reader.pages[page_idx]
                angle = int(rotations[idx])
                if angle in [90, 180, 270]:
                    page.rotate(angle)
                writer.add_page(page)
        out_path = os.path.join(RESULT_FOLDER, 'edited_pages.pdf')
        with open(out_path, 'wb') as f:
            writer.write(f)

        @after_this_request
        def cleanup(response):
            try:
                os.remove(filepath)
                os.remove(out_path)
            except Exception:
                pass
            return response

        return send_file(out_path, as_attachment=True)
    return render_template('edit_pages.html')

# --- Protect PDF ---
@app.route('/protect', methods=['GET', 'POST'])
def protect():
    if request.method == 'POST':
        file = request.files['file']
        password = request.form.get('password')
        allow_print = request.form.get('allow_print') == 'on'
        allow_copy = request.form.get('allow_copy') == 'on'
        if not (file and file.filename.endswith('.pdf')) or not password:
            return 'Provide a PDF and password.'
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        reader = PdfReader(filepath)
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        permissions = []
        if allow_print:
            permissions.append({"/Print": True})
        if allow_copy:
            permissions.append({"/Copy": True})
        writer.encrypt(password)
        out_path = os.path.join(RESULT_FOLDER, 'protected.pdf')
        with open(out_path, 'wb') as f:
            writer.write(f)

        @after_this_request
        def cleanup(response):
            try:
                os.remove(filepath)
                os.remove(out_path)
            except Exception:
                pass
            return response

        return send_file(out_path, as_attachment=True)
    return render_template('protect.html')

# --- Unlock PDF ---
@app.route('/unlock', methods=['GET', 'POST'])
def unlock():
    if request.method == 'POST':
        file = request.files['file']
        password = request.form.get('password')
        if not (file and file.filename.endswith('.pdf')) or not password:
            return 'Provide a password-protected PDF and password.'
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        reader = PdfReader(filepath)
        try:
            reader.decrypt(password)
        except Exception:
            return 'Wrong password or PDF cannot be unlocked.'
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        out_path = os.path.join(RESULT_FOLDER, 'unlocked.pdf')
        with open(out_path, 'wb') as f:
            writer.write(f)

        @after_this_request
        def cleanup(response):
            try:
                os.remove(filepath)
                os.remove(out_path)
            except Exception:
                pass
            return response

        return send_file(out_path, as_attachment=True)
    return render_template('unlock.html')

# --- Feedback Widget ---
@app.route('/feedback', methods=['POST'])
def feedback():
    feature = request.form.get('feature')
    email = request.form.get('email', '')
    with open('feedback.txt', 'a', encoding='utf-8') as f:
        f.write(f"Feature: {feature}\nEmail: {email}\n{'-'*40}\n")
    return render_template('thankyou.html')

if __name__ == '__main__':
    app.run(debug=True)
