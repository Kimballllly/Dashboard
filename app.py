from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_bcrypt import Bcrypt
from math import ceil
from datetime import timedelta, datetime
import mysql.connector
import os
from flask import make_response

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Image, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from io import BytesIO
from flask import send_file
from reportlab.lib.colors import HexColor


# Initialize Flask app and Bcrypt for password hashing
app = Flask(__name__)
bcrypt = Bcrypt(app)


# Secret key for session management
app.secret_key = 'your_secret_key_here'
app.permanent_session_lifetime = timedelta(days=7)

connection = mysql.connector.connect(
            host="mydatabase.cziagw6u0a1u.ap-southeast-2.rds.amazonaws.com",
            user="admin",
            password="paperazzi",
            database="paperazzi"
        )




@app.route('/generate_report', methods=['GET'])
def generate_report():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    cursor = connection.cursor(dictionary=True)
    query = """
        SELECT pjd.file_name, pjd.color_mode, pjd.total_price, pj.created_at
        FROM print_jobs pj
        JOIN print_job_details pjd ON pj.job_id = pjd.job_id
        WHERE DATE(pj.created_at) BETWEEN %s AND %s AND pjd.status = 'complete'
        ORDER BY pj.created_at
    """
    cursor.execute(query, (start_date, end_date))
    report_data = cursor.fetchall()

    # Fetch summary metrics
    cursor.execute("""
        SELECT 
            COUNT(*) as total_jobs, 
            SUM(pjd.total_price) as total_revenue,
            SUM(CASE WHEN pjd.color_mode = 'colored' THEN pjd.total_price ELSE 0 END) as color_revenue,
            SUM(CASE WHEN pjd.color_mode = 'bw' THEN pjd.total_price ELSE 0 END) as bw_revenue
        FROM print_jobs pj
        JOIN print_job_details pjd ON pj.job_id = pjd.job_id
        WHERE DATE(pj.created_at) BETWEEN %s AND %s AND pjd.status = 'complete'
    """, (start_date, end_date))
    summary = cursor.fetchone()
    cursor.close()

    #pdf
    pdf_buffer = BytesIO()
    doc = SimpleDocTemplate(
        pdf_buffer,
        pagesize=letter,
        topMargin=20,  # Reduce top margin
        leftMargin=20,
        rightMargin=20,
        bottomMargin=20
    )
    elements = []

    styles = getSampleStyleSheet()
    normal_style = styles['Normal']

    # Header Section with Logo and Title
    logo_path = os.path.join(app.static_folder, "logo.jpg")
    header_table_data = []
    if os.path.exists(logo_path):
        logo = Image(logo_path, width=80, height=80)
        header_table_data.append([
            logo,
            Paragraph(
                "<strong>Paperazzi: Coin Operated Printing Machine Sales Report</strong><br/>Cavite State University - Imus Campus",
                normal_style
            )
        ])

    header_table = Table(header_table_data, colWidths=[100, 400])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (1, 0), (-1, -1), 'LEFT'),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 10))  # Reduce spacer size here


    # Summary Section
    summary_data = [
        ["Summary", ""],
        ["Total Completed Jobs", summary["total_jobs"]],
        ["Total Revenue (PHP)", f"{summary['total_revenue']:.2f}"],
        ["Color Revenue (PHP)", f"{summary['color_revenue']:.2f}"],
        ["Black & White Revenue (PHP)", f"{summary['bw_revenue']:.2f}"],
    ]
    summary_table = Table(summary_data, colWidths=[200, 200])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#ff294f')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 20))

    # Detailed Table
    table_data = [["Date", "File Name", "Color Mode", "Total Price (PHP)"]]
    for row in report_data:
        table_data.append([
            row["created_at"].strftime("%Y-%m-%d"),
            row["file_name"],
            row["color_mode"].capitalize(),
            f"{row['total_price']:.2f}"
        ])

    detail_table = Table(table_data, colWidths=[100, 250, 100, 100])
    detail_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#ff294f')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
    ]))
    elements.append(detail_table)

    # Build PDF
    doc.build(elements)
    pdf_buffer.seek(0)
    return send_file(pdf_buffer, as_attachment=True, download_name=f"Sales_Report_{start_date}_to_{end_date}.pdf")


# Signup Page
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

        cursor = connection.cursor()
        try:
            cursor.execute("""
                INSERT INTO admins (username, email, password_hash) 
                VALUES (%s, %s, %s)
            """, (username, email, hashed_password))
            connection.commit()
            flash('Account created successfully. Please log in.', 'success')
            return redirect(url_for('login'))
        except mysql.connector.Error as err:
            flash(f'Error: {err}', 'danger')
        finally:
            cursor.close()

    return render_template('signup.html')


# Login Page
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'admin_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM admins WHERE email = %s", (email,))
        admin = cursor.fetchone()
        cursor.close()

        if admin and bcrypt.check_password_hash(admin['password_hash'], password):
            session.permanent = True
            session['admin_id'] = admin['admin_id']
            session['username'] = admin['username']
            flash(f'Welcome back, {admin["username"]}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password. Please try again.', 'danger')

    return render_template('login.html')


# Logout
@app.route('/logout')
def logout():
    session.pop('admin_id', None)
    session.pop('username', None)
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

@app.route('/')
def dashboard():
    if 'admin_id' not in session:
        flash('Please log in to access the dashboard.', 'warning')
        return redirect(url_for('login'))

    admin_username = session.get('username')
    todays_page = int(request.args.get('todays_page', 1))  # Default to page 1
    jobs_per_page = 10

    try:
        cursor = connection.cursor(dictionary=True)

        # Fetch total print jobs
        cursor.execute("SELECT COUNT(*) as total_jobs FROM print_jobs")
        total_jobs = cursor.fetchone()['total_jobs']

        # Fetch remaining paper and last refilled time
        cursor.execute("""
            SELECT remaining_paper, updated_at 
            FROM printer_status 
            ORDER BY updated_at DESC 
            LIMIT 1
        """)
        printer_status = cursor.fetchone()

        # Handle case where no record exists in printer_status
        if printer_status:
            remaining_paper = printer_status['remaining_paper']
            last_refilled = printer_status['updated_at'].strftime('%B %d, %Y')
        else:
            remaining_paper = 0
            last_refilled = 'N/A'

        # Fetch today's completed jobs
        cursor.execute("""
            SELECT COUNT(*) as todays_completed_jobs 
            FROM print_job_details 
            WHERE status='complete' AND DATE(created_at) = CURDATE()
        """)
        todays_completed_jobs = cursor.fetchone()['todays_completed_jobs']

        # Fetch today's total sales (only for completed jobs)
        cursor.execute("""
            SELECT SUM(pjd.total_price) as todays_total_sales 
            FROM print_job_details pjd
            JOIN print_jobs pj ON pj.job_id = pjd.job_id
            WHERE pjd.status = 'complete' AND DATE(pj.created_at) = CURDATE()
        """)
        todays_total_sales = cursor.fetchone()['todays_total_sales'] or 0.0

        # Calculate total jobs for today
        cursor.execute("SELECT COUNT(*) as todays_jobs_count FROM print_jobs WHERE DATE(created_at) = CURDATE()")
        todays_jobs_count = cursor.fetchone()['todays_jobs_count']

        # Calculate pagination details
        todays_total_pages = (todays_jobs_count + jobs_per_page - 1) // jobs_per_page
        offset = (todays_page - 1) * jobs_per_page

        # Fetch today's print jobs with pagination
        cursor.execute(f"""
            SELECT pjd.job_id, pjd.file_name, pjd.pages_to_print, pjd.color_mode, 
                   pjd.total_price, pjd.inserted_amount, pjd.status 
            FROM print_jobs pj
            JOIN print_job_details pjd ON pj.job_id = pjd.job_id
            WHERE DATE(pj.created_at) = CURDATE()
            ORDER BY pj.created_at DESC
            LIMIT {jobs_per_page} OFFSET {offset}
        """)
        todays_jobs = cursor.fetchall()

        # Fetch printing prices
        cursor.execute("SELECT black_price, color_price FROM print_prices ORDER BY updated_at DESC LIMIT 1")
        prices = cursor.fetchone()
        if not prices:
            black_price, color_price = 3, 5  # Default prices
        else:
            black_price = prices['black_price']
            color_price = prices['color_price']

        # Render the dashboard template with all data
        return render_template(
            'dashboard.html',
            admin_username=admin_username,
            total_jobs=total_jobs,
            remaining_paper=remaining_paper,
            last_refilled=last_refilled,
            todays_completed_jobs=todays_completed_jobs,
            todays_total_sales=todays_total_sales,
            todays_jobs=todays_jobs,
            todays_page=todays_page,
            todays_total_pages=todays_total_pages,
            black_price=black_price,
            color_price=color_price
        )
    except mysql.connector.Error as err:
        return f"Error: {err}"



    
@app.route('/update_prices', methods=['POST'])
def update_prices():
    if 'admin_id' not in session:
        flash('Please log in to update prices.', 'warning')
        return redirect(url_for('login'))

    black_price = request.form.get('black_price', type=float)
    color_price = request.form.get('color_price', type=float)

    try:
        cursor = connection.cursor()
        cursor.execute("""
            INSERT INTO print_prices (black_price, color_price) 
            VALUES (%s, %s)
        """, (black_price, color_price))
        connection.commit()
        flash('Prices updated successfully.', 'success')
    except mysql.connector.Error as err:
        flash(f"Error updating prices: {err}", 'danger')
    return redirect(url_for('dashboard'))

@app.route('/jobs')
def jobs():
    try:
        cursor = connection.cursor(dictionary=True)

        # Get the month filter from query parameters
        selected_month = request.args.get('month')
        filter_clause = ""
        filter_params = []

        if selected_month:
            filter_clause = "WHERE DATE_FORMAT(pj.created_at, '%Y-%m') = %s"
            filter_params.append(selected_month)

        # Fetch total jobs (regardless of status)
        cursor.execute(f"""
            SELECT COUNT(*) as total_jobs 
            FROM print_job_details pjd
            {filter_clause}
        """, filter_params)
        total_jobs = cursor.fetchone()['total_jobs']

        # Fetch total sales (only for completed jobs in pjd)
        cursor.execute(f"""
            SELECT SUM(COALESCE(pjd.total_price, 0)) as total_sales 
            FROM print_job_details pjd
            JOIN print_jobs pj ON pj.job_id = pjd.job_id
            {filter_clause} AND pjd.status = 'complete'
        """, filter_params)
        total_sales = cursor.fetchone()['total_sales'] or 0.0

        # Fetch completed and pending jobs
        cursor.execute(f"""
            SELECT 
                SUM(CASE WHEN pjd.status = 'complete' THEN 1 ELSE 0 END) as completed_jobs,
                SUM(CASE WHEN pjd.status = 'cancelled' THEN 1 ELSE 0 END) as cancelled_jobs
            FROM print_jobs pj
            JOIN print_job_details pjd ON pj.job_id = pjd.job_id
            {filter_clause}
        """, filter_params)

        job_status_counts = cursor.fetchone()
        completed_jobs = job_status_counts['completed_jobs']
        cancelled_jobs = job_status_counts['cancelled_jobs']


        # Fetch revenue breakdown (Color vs. Black & White)
        cursor.execute(f"""
            SELECT 
                SUM(CASE WHEN pjd.color_mode = 'colored' THEN pjd.total_price ELSE 0 END) as color_revenue,
                SUM(CASE WHEN pjd.color_mode = 'bw' THEN pjd.total_price ELSE 0 END) as bw_revenue
            FROM print_job_details pjd
            JOIN print_jobs pj ON pj.job_id = pjd.job_id
            {filter_clause} AND pjd.status = 'complete'
        """, filter_params)
        revenue_breakdown = cursor.fetchone()
        color_revenue = revenue_breakdown['color_revenue'] or 0.0
        bw_revenue = revenue_breakdown['bw_revenue'] or 0.0

        # Calculate percentages
        total_revenue = color_revenue + bw_revenue
        color_percentage = (color_revenue / total_revenue * 100) if total_revenue > 0 else 0
        bw_percentage = (bw_revenue / total_revenue * 100) if total_revenue > 0 else 0
                
        
        # Fetch jobs for the table with pagination
        rows_per_page = 10
        page = int(request.args.get('page', 1))
        offset = (page - 1) * rows_per_page

        cursor.execute(f"""
            SELECT COUNT(*) as total_jobs 
            FROM print_jobs pj
            {filter_clause}
        """, filter_params)
        total_records = cursor.fetchone()['total_jobs']
        total_pages = ceil(total_records / rows_per_page)

        query_with_pagination = f"""
            SELECT pjd.id, pj.job_id, pjd.file_name, pjd.status, pj.created_at, 
                   pjd.pages_to_print, pjd.color_mode, pjd.total_price, 
                   pjd.inserted_amount, pjd.total_pages
            FROM print_jobs pj
            JOIN print_job_details pjd ON pj.job_id = pjd.job_id
            {filter_clause}
            ORDER BY pj.created_at DESC
            LIMIT %s OFFSET %s
        """
        cursor.execute(query_with_pagination, filter_params + [rows_per_page, offset])
        print_jobs = cursor.fetchall()

        # Fetch job trends (number of jobs by date)
        cursor.execute(f"""
            SELECT 
                DATE(pj.created_at) as job_date, 
                COUNT(*) as job_count 
            FROM print_jobs pj
            {filter_clause}
            GROUP BY DATE(pj.created_at)
            ORDER BY job_date
        """, filter_params)
        job_trends = cursor.fetchall()
        job_trend_dates = [trend['job_date'].strftime('%Y-%m-%d') for trend in job_trends]
        job_trend_counts = [trend['job_count'] for trend in job_trends]

        # Pagination range logic
        pagination_range = 5
        start_page = max(1, page - pagination_range // 2)
        end_page = min(total_pages, start_page + pagination_range - 1)
        if end_page - start_page < pagination_range:
            start_page = max(1, end_page - pagination_range + 1)

        return render_template(
        'jobs.html',
        total_jobs=total_jobs,
        total_sales=total_sales,
        completed_jobs=completed_jobs,
        cancelled_jobs=cancelled_jobs,
        color_revenue=color_revenue,
        bw_revenue=bw_revenue,
        color_percentage=color_percentage,
        bw_percentage=bw_percentage,
        print_jobs=print_jobs,
        page=page,
        total_pages=total_pages,
        start_page=start_page,
        end_page=end_page,
        selected_month=selected_month,
        job_trend_dates=job_trend_dates,
        job_trend_counts=job_trend_counts
    )

    except mysql.connector.Error as err:
        return f"Error: {err}"




@app.route('/update_remaining_paper', methods=['POST'])
def update_remaining_paper():
    try:
        # Get the new paper count from the form
        new_remaining_paper = int(request.form['new_remaining_paper'])

        # Update the database
        cursor = connection.cursor(dictionary=True)  # Use dictionary cursor
        cursor.execute("""
            INSERT INTO printer_status (remaining_paper, updated_at) 
            VALUES (%s, NOW())
        """, (new_remaining_paper,))
        connection.commit()

        cursor.execute("""
            SELECT updated_at 
            FROM printer_status 
            WHERE refill = TRUE 
            ORDER BY updated_at DESC 
            LIMIT 1
        """)

        last_refilled_row = cursor.fetchone()
        if last_refilled_row:
            last_refilled = last_refilled_row['updated_at'].strftime('%B %d, %Y')
        else:
            last_refilled = 'N/A'

        # Pass the last_refilled value to the dashboard
        flash(f"Paper count updated successfully. Last refilled: {last_refilled}", 'success')
        return redirect(url_for('dashboard'))
    except mysql.connector.Error as err:
        return f"Error: {err}"


@app.before_request
def require_login():
    allowed_routes = ['login', 'signup', 'logout', 'static']
    if request.endpoint not in allowed_routes and 'admin_id' not in session:
        flash('You must log in to access this page.', 'danger')
        return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)
