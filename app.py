import os
from flask import Flask, render_template, request, redirect
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import JSON

app = Flask(__name__)

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

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/index')
def index():
    db_records = DailyTracker.query.order_by(DailyTracker.id).all() 
    return render_template('index.html', records=db_records)

@app.route("/add", methods=["GET", "POST"])
def add_record():
    if request.method == "POST":
        bike_line = request.form.get("bike_line", "")
        total_parts = int(request.form.get("total_parts") or 1)
        
        linear_km = float(request.form.get("linear_km") or 0.0)
        estimation = float(request.form.get("estimation") or 0.0)
        employee_name = request.form.get("employee_name", "")
        start_date = request.form.get("start_date", "")
        end_date = request.form.get("end_date", "")
        completed_km = float(request.form.get("completed_km") or 0.0)
        time_taken = float(request.form.get("time_taken") or 0.0)
        count_val = int(request.form.get("count_val") or 0)
        progress_status = request.form.get("progress_status", "IP")
        
        # Calculate pending field safely
        pending_km = linear_km - completed_km
        if pending_km < 0:
            pending_km = 0.0

        # Handle dynamic extra fields from add page
        extra_keys = request.form.getlist("extra_metric_name[]")
        extra_vals = request.form.getlist("extra_metric_value[]")
        processed_extra = {}
        for key, val in zip(extra_keys, extra_vals):
            if key.strip():
                processed_extra[key.strip()] = val.strip()

        # Generate custom abbreviated prefix based on Selected Line
        line_prefix = bike_line[:3].upper() if bike_line else "NA"

        # Loop to add multiple parts dynamically
        for i in range(1, total_parts + 1):
            generated_part_no = f"P-{line_prefix}-{str(i).zfill(2)}"
            
            record = DailyTracker(
                bike_line=bike_line,
                part_no=generated_part_no, 
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
                extra_data=processed_extra
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
        
        # Calculate pending field safely on update
        pending_km = record.linear_km - record.completed_km
        record.pending_km = pending_km if pending_km >= 0 else 0.0
        
        # Capture dynamic section components
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

if __name__ == "__main__":
    with app.app_context():
        db.create_all()  
        print("Database connection active. Persistent tracking storage configured successfully.")
        
    app.run(debug=True)