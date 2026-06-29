import os
import re
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import JSON

# Third-party data parsing integrations
import pandas as pd
import pdfplumber

app = Flask(__name__)

# Secret key required for Flask flash messages to work securely
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-session-fallback-key-99128')

# Reads the cloud connection string from Vercel env, or defaults to your Neon DB string
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL', 
    'postgresql://neondb_owner:npg_etJ17mdqjRgT@ep-ancient-star-athmk64o-pooler.c-9.us-east-1.aws.neon.tech/neondb?sslmode=require'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class DailyTracker(db.Model):
    __tablename__ = "daily_tracker"

    id = db.Column(db.Integer, primary_key=True)
    bike_line = db.Column(db.String(50))         
    part_no = db.Column(db.String(50))           
    linear_km = db.Column(db.Float)              
    estimation = db.Column(db.Float)             
    employee_name = db.Column(db.String(100))    
    start_date = db.Column(db.String(20))        
    end_date = db.Column(db.String(20))          
    completed_km = db.Column(db.Float)           
    pending_km = db.Column(db.Float)             
    time_taken = db.Column(db.Float)             
    count_val = db.Column(db.Integer)            
    progress_status = db.Column(db.String(20))    
    extra_data = db.Column(JSON, default=dict)
    
    # New columns structural properties
    new_column_text = db.Column(db.String(200), default="")
    new_column_numeric = db.Column(db.Float, default=0.0)

    # Added QC tracking metrics
    qc_person = db.Column(db.String(100), default="")
    qc_start_date = db.Column(db.String(20), default="")
    qc_end_date = db.Column(db.String(20), default="")
    qc_completed_km = db.Column(db.Float, default=0.0)
    qc_pending_km = db.Column(db.Float, default=0.0)
    qc_time_taken = db.Column(db.Float, default=0.0)
    qc_extra_count = db.Column(db.Integer, default=0)
    qc_status = db.Column(db.String(20), default="IP")


# --- INTERNAL HELPER DATA PARSING UTILITIES ---

def parse_excel_file(file_path):
    """Parses Excel workbook rows and collects clean metadata dictionaries."""
    df = pd.read_excel(file_path)
    df.columns = [str(col).strip().lower() for col in df.columns]
    
    records = []
    for _, row in df.iterrows():
        # Fuzzy keyword matching across sheet header variants
        part_no = next((str(row[c]).strip() for c in df.columns if 'part' in c or 'pn' in c or 'id' in c), None)
        linear_km = next((float(row[c]) for c in df.columns if 'linear' in c or 'lin' in c), 0.0)
        estimation = next((float(row[c]) for c in df.columns if 'estim' in c), 0.0)
        
        if part_no and part_no != 'nan':
            records.append({'part_no': part_no, 'linear_km': linear_km, 'estimation': estimation})
    return records


def parse_pdf_file(file_path):
    """Extracts unstructured row tables out of uploaded PDF matrices safely."""
    records = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            table = page.extract_table()
            if not table:
                continue
                
            headers = [str(cell).strip().lower() if cell else "" for cell in table[0]]
            
            part_idx = next((i for i, h in enumerate(headers) if 'part' in h or 'pn' in h or 'id' in h), None)
            linear_idx = next((i for i, h in enumerate(headers) if 'linear' in h or 'lin' in h), None)
            estim_idx = next((i for i, h in enumerate(headers) if 'estim' in h), None)
            
            if part_idx is None:
                continue 
                
            for row in table[1:]:
                if not row or len(row) <= part_idx or not row[part_idx]:
                    continue
                
                part_no = str(row[part_idx]).strip()
                
                def extract_clean_float(val):
                    if not val: return 0.0
                    matches = re.findall(r"[-+]?\d*\.\d+|\d+", str(val))
                    return float(matches[0]) if matches else 0.0

                linear_km = extract_clean_float(row[linear_idx]) if linear_idx is not None else 0.0
                estimation = extract_clean_float(row[estim_idx]) if estim_idx is not None else 0.0
                
                if part_no:
                    records.append({'part_no': part_no, 'linear_km': linear_km, 'estimation': estimation})
    return records


# --- FLASK APPLICATION ROUTE MANIFESTS ---

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/index')
def index():
    db_records = DailyTracker.query.order_by(DailyTracker.id).all() 
    seen_parts = set()
    primary_records = []
    
    for record in db_records:
        if record.part_no not in seen_parts:
            primary_records.append(record)
            seen_parts.add(record.part_no)
            
    return render_template('index.html', records=primary_records)

@app.route('/upload_report', methods=['POST'])
def upload_report():
    """Endpoint responsible for processing uploaded data documents and updating properties."""
    if 'file' not in request.files:
        return redirect(url_for('index'))
        
    file = request.files['file']
    if file.filename == '':
        return redirect(url_for('index'))
        
    if file:
        filename = file.filename
        ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
        
        # Uses platform-agnostic safe temp fallbacks
        temp_dir = '/tmp' if os.name != 'nt' else 'C:\\Windows\\Temp'
        temp_path = os.path.join(temp_dir, filename)
        file.save(temp_path)
        
        try:
            if ext in ['xls', 'xlsx']:
                extracted_data = parse_excel_file(temp_path)
            elif ext == 'pdf':
                extracted_data = parse_pdf_file(temp_path)
            else:
                return redirect(url_for('index'))
                
            updated_count = 0
            for item in extracted_data:
                # Queries all database rows that match this incoming part number identifier
                matching_records = DailyTracker.query.filter_by(part_no=item['part_no']).all()
                
                for record in matching_records:
                    record.linear_km = item['linear_km']
                    record.estimation = item['estimation']
                    
                    # Keep pending_km fields accurate relative to new data metrics
                    current_comp = record.completed_km or 0.0
                    calc_pending = item['linear_km'] - current_comp
                    record.pending_km = calc_pending if calc_pending >= 0 else 0.0
                    
                    updated_count += 1
            
            db.session.commit()
            
        except Exception as e:
            db.session.rollback()
            print(f"Exception encountered during extraction workflow execution: {str(e)}")
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
    return redirect(url_for('index'))

@app.route("/joint_records")
def joint_records():
    db_records = DailyTracker.query.order_by(DailyTracker.id).all()
    
    first_worker_map = {}
    for record in db_records:
        if record.part_no not in first_worker_map:
            first_worker_map[record.part_no] = record.employee_name or 'Unassigned'
            
    seen_parts = set()
    joint_records_list = []
    
    for record in db_records:
        if record.part_no in seen_parts:
            record.original_worker_name = first_worker_map.get(record.part_no, 'Unassigned')
            joint_records_list.append(record)
        else:
            seen_parts.add(record.part_no)
            
    return render_template("joint_records.html", records=joint_records_list)

@app.route("/add", methods=["GET", "POST"])
def add_record():
    if request.method == "POST":
        # Pull form fields as lists to handle the dynamically generated multi-row inputs
        bike_lines = request.form.getlist("bike_line[]")
        part_numbers = request.form.getlist("part_no[]")
        linear_kms = request.form.getlist("linear_km[]")
        estimations = request.form.getlist("estimation[]")
        employee_names = request.form.getlist("employee_name[]")
        start_dates = request.form.getlist("start_date[]")
        end_dates = request.form.getlist("end_date[]")
        completed_kms = request.form.getlist("completed_km[]")
        time_takens = request.form.getlist("time_taken[]")
        count_vals = request.form.getlist("count_val[]")
        progress_statuses = request.form.getlist("progress_status[]")
        
        new_col_txts = request.form.getlist("new_column_text[]")
        new_col_nums = request.form.getlist("new_column_numeric[]")
        
        # Read the general extra metric keys/values
        extra_keys = request.form.getlist("extra_metric_name[]")
        extra_vals = request.form.getlist("extra_metric_value[]")
        processed_extra = {}
        for key, val in zip(extra_keys, extra_vals):
            if key.strip():
                processed_extra[key.strip()] = val.strip()

        # Handle QC fields (pull standard forms, fall back safely if arrays aren't used for QC)
        qc_person = request.form.get("qc_person", "")
        qc_start_date = request.form.get("qc_start_date", "")
        qc_end_date = request.form.get("qc_end_date", "")
        qc_completed_km = float(request.form.get("qc_completed_km") or 0.0)
        qc_pending_km = float(request.form.get("qc_pending_km") or 0.0)
        qc_time_taken = float(request.form.get("qc_time_taken") or 0.0)
        qc_extra_count = int(request.form.get("qc_extra_count") or 0)
        qc_status = request.form.get("qc_status", "IP")

        # Determine total items generated by the Excel script sheet frontend
        total_records = len(part_numbers) if part_numbers else 1

        for i in range(total_records):
            # Access each positional element in the arrays safely
            bike_line = bike_lines[i] if i < len(bike_lines) else request.form.get("bike_line", "")
            part_no = part_numbers[i] if i < len(part_numbers) else ""
            linear_km = float(linear_kms[i]) if (i < len(linear_kms) and linear_kms[i]) else 0.0
            estimation = float(estimations[i]) if (i < len(estimations) and estimations[i]) else 0.0
            employee_name = employee_names[i] if i < len(employee_names) else ""
            start_date = start_dates[i] if i < len(start_dates) else ""
            end_date = end_dates[i] if i < len(end_dates) else ""
            completed_km = float(completed_kms[i]) if (i < len(completed_kms) and completed_kms[i]) else 0.0
            time_taken = float(time_takens[i]) if (i < len(time_takens) and time_takens[i]) else 0.0
            count_val = int(count_vals[i]) if (i < len(count_vals) and count_vals[i]) else 0
            progress_status = progress_statuses[i] if i < len(progress_statuses) else "IP"
            
            new_col_txt = new_col_txts[i] if i < len(new_col_txts) else ""
            new_col_num = float(new_col_nums[i]) if (i < len(new_col_nums) and new_col_nums[i]) else 0.0

            # Compute pending balance per block safely
            pending_km = linear_km - completed_km
            if pending_km < 0:
                pending_km = 0.0

            # Fallback logic if a record is added manually via interface buttons without an uploaded document
            if not part_no:
                line_prefix = bike_line[:3].upper() if bike_line else "NA"
                part_no = f"P-{line_prefix}-{str(i + 1).zfill(2)}"

            record = DailyTracker(
                bike_line=bike_line,
                part_no=part_no, 
                linear_km=linear_km,
                estimation=estimation,
                employee_name=employee_name,
                start_date=start_date,
                end_date=end_date,
                completed_km=completed_km,
                pending_km=pending_km,
                time_taken=time_taken,
                count_val=count_val,
                progress_status=progress_status,
                extra_data=processed_extra,
                new_column_text=new_col_txt,
                new_column_numeric=new_col_num,
                qc_person=qc_person,
                qc_start_date=qc_start_date,
                qc_end_date=qc_end_date,
                qc_completed_km=qc_completed_km,
                qc_pending_km=qc_pending_km,
                qc_time_taken=qc_time_taken,
                qc_extra_count=qc_extra_count,
                qc_status=qc_status
            )
            db.session.add(record)
            
        db.session.commit()
        return redirect("/index")
        
    return render_template("add_record.html")

@app.route("/edit/<int:id>", methods=["GET", "POST"])
def edit_record(id):
    record = DailyTracker.query.get_or_404(id)
    
    if request.method == "POST":
        record.bike_line = request.form.get("bike_line", "")
        record.linear_km = float(request.form.get("linear_km") or 0.0)
        record.estimation = float(request.form.get("estimation") or 0.0)
        record.employee_name = request.form.get("employee_name", "")
        record.start_date = request.form.get("start_date", "")
        record.end_date = request.form.get("end_date", "")
        record.completed_km = float(request.form.get("completed_km") or 0.0)
        record.time_taken = float(request.form.get("time_taken") or 0.0)
        record.count_val = int(request.form.get("count_val") or 0)
        record.progress_status = request.form.get("progress_status", "IP")
        
        record.new_column_text = request.form.get("new_column_text", "")
        record.new_column_numeric = float(request.form.get("new_column_numeric") or 0.0)
        
        record.qc_person = request.form.get("qc_person", "")
        record.qc_start_date = request.form.get("qc_start_date", "")
        record.qc_end_date = request.form.get("qc_end_date", "")
        record.qc_completed_km = float(request.form.get("qc_completed_km") or 0.0)
        record.qc_pending_km = float(request.form.get("qc_pending_km") or 0.0)
        record.qc_time_taken = float(request.form.get("qc_time_taken") or 0.0)
        record.qc_extra_count = int(request.form.get("qc_extra_count") or 0)
        record.qc_status = request.form.get("qc_status", "IP")
        
        pending_km = record.linear_km - record.completed_km
        record.pending_km = pending_km if pending_km >= 0 else 0.0
        
        extra_keys = request.form.getlist("extra_metric_name[]")
        extra_vals = request.form.getlist("extra_metric_value[]")
        
        processed_extra = {}
        for key, val in zip(extra_keys, extra_vals):
            if key.strip(): 
                processed_extra[key.strip()] = val.strip()
                
        record.extra_data = processed_extra
        
        db.session.commit()
        return redirect("/index")
        
    return render_template("edit_record.html", record=record)

@app.route("/employee_report")
def employee_report():
    all_records = DailyTracker.query.order_by(DailyTracker.start_date.desc()).all()
    organized_data = {}
    
    for record in all_records:
        date = record.start_date if record.start_date else "No Date Specified"
        emp = record.employee_name.strip() if record.employee_name else "Unassigned"
        
        if date not in organized_data:
            organized_data[date] = {}
            
        if emp not in organized_data[date]:
            organized_data[date][emp] = {
                'records': [],
                'total_linear': 0.0,
                'total_completed': 0.0,
                'total_pending': 0.0,
                'total_time': 0.0,
                'total_count': 0
            }
            
        organized_data[date][emp]['records'].append(record)
        organized_data[date][emp]['total_linear'] += float(record.linear_km or 0.0)
        organized_data[date][emp]['total_completed'] += float(record.completed_km or 0.0)
        organized_data[date][emp]['total_pending'] += float(record.pending_km or 0.0)
        organized_data[date][emp]['total_time'] += float(record.time_taken or 0.0)
        organized_data[date][emp]['total_count'] += int(record.count_val or 0)

    return render_template("individual_report.html", report_data=organized_data)

@app.route("/delete/<int:id>")
def delete_record(id):
    record = DailyTracker.query.get_or_404(id)
    db.session.delete(record)
    db.session.commit()
    return redirect("/index")

@app.route("/delete_all")
def delete_all():
    DailyTracker.query.delete()
    db.session.commit()
    return redirect("/index")

@app.route("/join/<int:id>", methods=["GET", "POST"])
def join_worker(id):
    base_record = DailyTracker.query.get_or_404(id)
    
    if request.method == "POST":
        new_worker = request.form.get("employee_name", "").strip()
        completed_km = float(request.form.get("completed_km") or 0.0)
        time_taken = float(request.form.get("time_taken") or 0.0)
        count_val = int(request.form.get("count_val") or 0)
        progress_status = request.form.get("progress_status", "IP")
        new_col_txt = request.form.get("new_column_text", "")
        new_col_num = float(request.form.get("new_column_numeric") or 0.0)
        
        pending_km = base_record.linear_km - completed_km
        if pending_km < 0:
            pending_km = 0.0
            
        joint_record = DailyTracker(
            bike_line=base_record.bike_line,
            part_no=base_record.part_no, 
            linear_km=base_record.linear_km,
            estimation=base_record.estimation,
            employee_name=new_worker,
            start_date=base_record.start_date, 
            end_date=base_record.end_date,
            completed_km=completed_km,
            pending_km=pending_km,
            time_taken=time_taken,
            count_val=count_val,
            progress_status=progress_status,
            extra_data=base_record.extra_data, 
            new_column_text=new_col_txt,
            new_column_numeric=new_col_num,
            qc_person=base_record.qc_person,
            qc_start_date=base_record.qc_start_date,
            qc_end_date=base_record.qc_end_date,
            qc_completed_km=base_record.qc_completed_km,
            qc_pending_km=base_record.qc_pending_km,
            qc_time_taken=base_record.qc_time_taken,
            qc_extra_count=base_record.qc_extra_count,
            qc_status=base_record.qc_status
        )
        
        db.session.add(joint_record)
        db.session.commit()
        return redirect("/index")
        
    return render_template("join_worker.html", base_record=base_record)

@app.route('/calculate_metrics')
def calculate_metrics():
    """Aggregates and calculates production efficiencies across all records."""
    records = DailyTracker.query.all()
    
    total_linear = sum(r.linear_km or 0.0 for r in records)
    total_completed = sum(r.completed_km or 0.0 for r in records)
    total_pending = sum(r.pending_km or 0.0 for r in records)
    total_time = sum(r.time_taken or 0.0 for r in records)
    
    # Calculate global efficiency (KM per hour)
    efficiency = total_completed / total_time if total_time > 0 else 0.0
    
    # Calculate completeness percentage
    completion_rate = (total_completed / total_linear * 100) if total_linear > 0 else 0.0

    metrics = {
        'total_linear': round(total_linear, 2),
        'total_completed': round(total_completed, 2),
        'total_pending': round(total_pending, 2),
        'total_time': round(total_time, 2),
        'efficiency': round(efficiency, 2),
        'completion_rate': round(completion_rate, 1)
    }
    
    return render_template('metrics_summary.html', metrics=metrics)

@app.route('/data_calculator', methods=['GET', 'POST'])
def data_calculator():
    """Applies user-selected arithmetic operations across tracker data columns dynamically."""
    records = DailyTracker.query.all()
    calculated_results = []
    
    # Defaults
    left_col = request.form.get('left_col', 'linear_km')
    operator = request.form.get('operator', '+')
    right_col = request.form.get('right_col', 'completed_km')
    
    for r in records:
        # Extract attribute values safely matching user choice
        val1 = float(getattr(r, left_col) or 0.0)
        val2 = float(getattr(r, right_col) or 0.0)
        
        # Execute selected mathematical evaluation matrix
        if operator == '+':
            res = val1 + val2
        elif operator == '-':
            res = val1 - val2
        elif operator == '*':
            res = val1 * val2
        elif operator == '/':
            res = val1 / val2 if val2 != 0 else 0.0  # Avoid ZeroDivisionError
        else:
            res = 0.0
            
        calculated_results.append({
            'id': r.id,
            'part_no': r.part_no,
            'val1': val1,
            'val2': val2,
            'result': round(res, 2)
        })
        
    return render_template(
        'data_calculator.html', 
        results=calculated_results, 
        left_col=left_col, 
        operator=operator, 
        right_col=right_col
    )

if __name__ == "__main__":
    with app.app_context():
        db.create_all()  
    app.run(debug=True)