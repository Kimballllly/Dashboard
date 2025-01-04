from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_bcrypt import Bcrypt
from math import ceil
from datetime import timedelta, datetime
import mysql.connector

# Initialize Flask app and Bcrypt for password hashing
app = Flask(__name__)
bcrypt = Bcrypt(app)

# Secret key for session management
app.secret_key = 'your_secret_key_here'
app.permanent_session_lifetime = timedelta(days=7)

# Database connection
connection = mysql.connector.connect(
    host="paperazzi.cre40o0wmfru.ap-southeast-2.rds.amazonaws.com",
    user="admin",
    password="paperazzi",
    database="paperazzi"
)

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
            FROM print_jobs pj
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
                SUM(CASE WHEN pj.status = 'Complete' THEN 1 ELSE 0 END) as completed_jobs,
                SUM(CASE WHEN pj.status != 'Complete' THEN 1 ELSE 0 END) as pending_jobs
            FROM print_jobs pj
            {filter_clause}
        """, filter_params)
        job_status_counts = cursor.fetchone()
        completed_jobs = job_status_counts['completed_jobs']
        pending_jobs = job_status_counts['pending_jobs']

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
            SELECT pjd.id,pj.job_id,pjd.file_name, pj.status, pj.created_at, pjd.pages_to_print, 
                   pjd.color_mode, pjd.total_price, pjd.inserted_amount,pjd.total_pages
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
            pending_jobs=pending_jobs,
            color_revenue=color_revenue,
            bw_revenue=bw_revenue,
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

        # Fetch the last updated_at value
        cursor.execute("""
            SELECT updated_at 
            FROM printer_status 
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
    app.run(debug=True)
