from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
import qrcode
import uuid
import os

app = Flask(__name__)

# Secret key is required for flash messages
app.secret_key = "eventsphere_secret_key"

# Database file
DATABASE = "eventsphere.db"


# --------------------------------------------------
# DATABASE CONNECTION
# --------------------------------------------------

def get_db_connection():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


# --------------------------------------------------
# CREATE DATABASE TABLES
# --------------------------------------------------

def init_db():

    connection = get_db_connection()

    # -----------------------------------------
    # EVENTS TABLE
    # -----------------------------------------

    connection.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            venue TEXT,
            organizer TEXT,
            max_participants INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # -----------------------------------------
    # PARTICIPANTS TABLE
    # -----------------------------------------

    connection.execute("""
        CREATE TABLE IF NOT EXISTS participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT,
            ticket_id TEXT UNIQUE,
            qr_code TEXT,
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (event_id)
            REFERENCES events(id)
        )
    """)

    # -----------------------------------------
    # VENUES TABLE
    # -----------------------------------------

    connection.execute("""
        CREATE TABLE IF NOT EXISTS venues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            location TEXT,
            capacity INTEGER
        )
    """)

    # -----------------------------------------
    # VENDORS TABLE
    # -----------------------------------------

    connection.execute("""
        CREATE TABLE IF NOT EXISTS vendors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            service TEXT,
            phone TEXT,
            email TEXT
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS resources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            available_quantity INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'Available'
        )
    """)  

    connection.execute("""
        CREATE TABLE IF NOT EXISTS resource_allocations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            resource_id INTEGER NOT NULL,
            event_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            allocated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (resource_id) REFERENCES resources(id),
            FOREIGN KEY (event_id) REFERENCES events(id)
        )
    """)

# EXPENSES TABLE
    connection.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            amount REAL NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (event_id) REFERENCES events(id)
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER,
            notification_type TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (event_id) REFERENCES events(id)
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS automation_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER,
            automation_type TEXT NOT NULL,
            message TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Completed',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (event_id) REFERENCES events(id)
        )
    """) 
   

    # -----------------------------------------
    # ADD NEW COLUMNS TO OLD DATABASE
    # -----------------------------------------

    columns = connection.execute(
        "PRAGMA table_info(events)"
    ).fetchall()

    column_names = [column["name"] for column in columns]

    if "organizer" not in column_names:

        connection.execute("""
            ALTER TABLE events
            ADD COLUMN organizer TEXT
        """)

    if "max_participants" not in column_names:

        connection.execute("""
            ALTER TABLE events
            ADD COLUMN max_participants INTEGER
        """)

    connection.commit()

    connection.close()

    


# --------------------------------------------------
# HOME PAGE
# --------------------------------------------------

@app.route("/")
def index():
    return redirect(url_for("dashboard"))


# --------------------------------------------------
# DASHBOARD
# --------------------------------------------------

@app.route("/dashboard")
def dashboard():

    connection = get_db_connection()

    # Count total events
    event_count = connection.execute(
        "SELECT COUNT(*) FROM events"
    ).fetchone()[0]

    # Count total participants
    participant_count = connection.execute(
        "SELECT COUNT(*) FROM participants"
    ).fetchone()[0]

    # Count total venues
    venue_count = connection.execute(
        "SELECT COUNT(*) FROM venues"
    ).fetchone()[0]

    # Count total vendors
    vendor_count = connection.execute(
        "SELECT COUNT(*) FROM vendors"
    ).fetchone()[0]

    # Count total resources
    resource_count = connection.execute(
        "SELECT COUNT(*) FROM resources"
    ).fetchone()[0]

    # Calculate total budget
    total_budget = connection.execute("""
        SELECT COALESCE(SUM(budget), 0)
        FROM events
    """).fetchone()[0]

    # Calculate total expenses
    total_expenses = connection.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM expenses
    """).fetchone()[0]

     # Calculate remaining budget
    remaining_budget = total_budget - total_expenses

    # Calculate budget utilization
    if total_budget > 0:
        budget_utilization = round(
            (total_expenses / total_budget) * 100,
            1
        )
    else:
        budget_utilization = 0

    # Get latest 5 events
    recent_events = connection.execute("""
        SELECT *
        FROM events
        ORDER BY id DESC
        LIMIT 5
    """).fetchall()

    connection.close()

    return render_template(
        "dashboard.html",
        event_count=event_count,
        participant_count=participant_count,
        venue_count=venue_count,
        vendor_count=vendor_count,
         resource_count=resource_count,
        total_budget=total_budget,
        total_expenses=total_expenses,
        remaining_budget=remaining_budget,
        budget_utilization=budget_utilization,
        recent_events=recent_events
    )


# --------------------------------------------------
# CREATE EVENT
# --------------------------------------------------

@app.route("/create-event", methods=["GET", "POST"])
def create_event():

    if request.method == "POST":

        # -----------------------------------------
        # GET FORM DATA
        # -----------------------------------------

        name = request.form.get("name", "").strip()

        description = request.form.get(
            "description", ""
        ).strip()

        date = request.form.get(
            "date", ""
        ).strip()

        start_time = request.form.get(
            "start_time", ""
        ).strip()

        end_time = request.form.get(
            "end_time", ""
        ).strip()

        venue = request.form.get(
            "venue", ""
        ).strip()

        organizer = request.form.get(
            "organizer", ""
        ).strip()

        max_participants = request.form.get(
            "max_participants", ""
        ).strip()

        budget = request.form.get(
            "budget", ""
        ).strip()


        # -----------------------------------------
        # VALIDATE EVENT NAME
        # -----------------------------------------

        if not name:

            flash(
                "Event name is required.",
                "error"
            )

            return redirect(
                url_for("create_event")
            )


        # -----------------------------------------
        # VALIDATE DATE
        # -----------------------------------------

        if not date:

            flash(
                "Event date is required.",
                "error"
            )

            return redirect(
                url_for("create_event")
            )


        # -----------------------------------------
        # VALIDATE TIME
        # -----------------------------------------

        if not start_time or not end_time:

            flash(
                "Start time and end time are required.",
                "error"
            )

            return redirect(
                url_for("create_event")
            )


        if start_time >= end_time:

            flash(
                "End time must be later than start time.",
                "error"
            )

            return redirect(
                url_for("create_event")
            )


        # -----------------------------------------
        # VALIDATE ORGANIZER
        # -----------------------------------------

        if not organizer:

            flash(
                "Organizer name is required.",
                "error"
            )

            return redirect(
                url_for("create_event")
            )


        # -----------------------------------------
        # VALIDATE MAX PARTICIPANTS
        # -----------------------------------------

        if max_participants:

            try:

                max_participants = int(
                    max_participants
                )

                if max_participants <= 0:

                    flash(
                        "Maximum participants must be greater than 0.",
                        "error"
                    )

                    return redirect(
                        url_for("create_event")
                    )

            except ValueError:

                flash(
                    "Maximum participants must be a number.",
                    "error"
                )

                return redirect(
                    url_for("create_event")
                )

        else:

            max_participants = None


        # -----------------------------------------
        # SAVE EVENT
        # -----------------------------------------

        connection = get_db_connection()

        connection.execute("""
            INSERT INTO events
            (
                name,
                description,
                date,
                start_time,
                end_time,
                venue,
                organizer,
                max_participants,
                budget
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            name,
            description,
            date,
            start_time,
            end_time,
            venue,
            organizer,
            max_participants,
            budget
        ))

        connection.commit()

        connection.close()


        # -----------------------------------------
        # SUCCESS MESSAGE
        # -----------------------------------------

        flash(
            "Event created successfully!",
            "success"
        )


        return redirect(
            url_for("events")
        )


    connection = get_db_connection()

    venues_list = connection.execute("""
        SELECT *
        FROM venues
        ORDER BY name ASC
    """).fetchall()

    connection.close()

    return render_template(
        "create_event.html",
        venues=venues_list
    )


# --------------------------------------------------
# VIEW EVENTS
# --------------------------------------------------

@app.route("/events")
def events():

    connection = get_db_connection()

    events_list = connection.execute("""
        SELECT * FROM events
        ORDER BY date ASC
    """).fetchall()

    connection.close()

    return render_template(
        "events.html",
        events=events_list
    )

# --------------------------------------------------
# EDIT EVENT
# --------------------------------------------------

@app.route("/edit-event/<int:event_id>", methods=["GET", "POST"])
def edit_event(event_id):

    connection = get_db_connection()

    # Get the event
    event = connection.execute("""
        SELECT *
        FROM events
        WHERE id = ?
    """, (event_id,)).fetchone()

    if event is None:
        connection.close()

        flash(
            "Event not found.",
            "error"
        )

        return redirect(url_for("events"))

    # -----------------------------------------
    # UPDATE EVENT
    # -----------------------------------------

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        date = request.form.get("date", "").strip()
        start_time = request.form.get("start_time", "").strip()
        end_time = request.form.get("end_time", "").strip()
        venue = request.form.get("venue", "").strip()
        organizer = request.form.get("organizer", "").strip()
        max_participants = request.form.get(
            "max_participants", ""
        ).strip()
        budget = request.form.get("budget", ""
        ).strip()

        # Validate name
        if not name:
            connection.close()
            flash("Event name is required.", "error")
            return redirect(
                url_for("edit_event", event_id=event_id)
            )

        # Validate date
        if not date:
            connection.close()
            flash("Event date is required.", "error")
            return redirect(
                url_for("edit_event", event_id=event_id)
            )

        # Validate time
        if not start_time or not end_time:
            connection.close()
            flash(
                "Start time and end time are required.",
                "error"
            )
            return redirect(
                url_for("edit_event", event_id=event_id)
            )

        if start_time >= end_time:
            connection.close()
            flash(
                "End time must be later than start time.",
                "error"
            )
            return redirect(
                url_for("edit_event", event_id=event_id)
            )

        # Validate organizer
        if not organizer:
            connection.close()
            flash(
                "Organizer name is required.",
                "error"
            )
            return redirect(
                url_for("edit_event", event_id=event_id)
            )

        # Validate maximum participants
        if max_participants:

            try:
                max_participants = int(max_participants)

                if max_participants <= 0:
                    connection.close()
                    flash(
                        "Maximum participants must be greater than 0.",
                        "error"
                    )
                    return redirect(
                        url_for("edit_event", event_id=event_id)
                    )

            except ValueError:
                connection.close()
                flash(
                    "Maximum participants must be a number.",
                    "error"
                )
                return redirect(
                    url_for("edit_event", event_id=event_id)
                )

        else:
            max_participants = None

        # -----------------------------------------
        # CHECK VENUE CONFLICT
        # -----------------------------------------

        if venue:

            conflict = connection.execute("""
                SELECT *
                FROM events
                WHERE venue = ?
                AND date = ?
                AND start_time < ?
                AND end_time > ?
                AND id != ?
            """, (
                venue,
                date,
                end_time,
                start_time,
                event_id
            )).fetchone()

            if conflict:

                connection.close()

                flash(
                    f"Venue conflict! {venue} is already "
                    f"booked from {conflict['start_time']} "
                    f"to {conflict['end_time']}.",
                    "error"
                )

                return redirect(
                    url_for(
                        "edit_event",
                        event_id=event_id
                    )
                )

        # -----------------------------------------
        # UPDATE DATABASE
        # -----------------------------------------

        connection.execute("""
            UPDATE events
            SET
                name = ?,
                description = ?,
                date = ?,
                start_time = ?,
                end_time = ?,
                venue = ?,
                organizer = ?,
                max_participants = ?,
                budget = ?
            WHERE id = ?
        """, (
            name,
            description,
            date,
            start_time,
            end_time,
            venue,
            organizer,
            max_participants,
            event_id,
            budget
        ))

        connection.commit()
        connection.close()

        flash(
            "Event updated successfully!",
            "success"
        )

        return redirect(
            url_for("events")
        )

    # -----------------------------------------
    # GET VENUES
    # -----------------------------------------

    venues_list = connection.execute("""
        SELECT *
        FROM venues
        ORDER BY name ASC
    """).fetchall()

    connection.close()

    return render_template(
        "edit_event.html",
        event=event,
        venues=venues_list
    )

# --------------------------------------------------
# VENDOR REGISTRATION + EVENT ASSIGNMENT
# --------------------------------------------------

@app.route("/add-vendor", methods=["GET", "POST"])
def add_vendor():

    connection = get_db_connection()

    if request.method == "POST":

        name = request.form["name"]
        service = request.form["service"]
        phone = request.form["phone"]
        email = request.form["email"]
        event_id = request.form["event_id"]

        connection.execute("""
            INSERT INTO vendors
            (name, service, phone, email, event_id)
            VALUES (?, ?, ?, ?, ?)
        """, (
            name,
            service,
            phone,
            email,
            event_id
        ))

        connection.commit()
        connection.close()

        flash(
            "Vendor registered and assigned successfully!",
            "success"
        )

        return redirect(
            url_for("vendors")
        )


    events_list = connection.execute("""
        SELECT *
        FROM events
        ORDER BY date ASC
    """).fetchall()

    connection.close()

    return render_template(
        "add_vendor.html",
        events=events_list
    )


# --------------------------------------------------
# VIEW VENDORS
# --------------------------------------------------

@app.route("/vendors")
def vendors():

    connection = get_db_connection()

    vendors_list = connection.execute("""
        SELECT
            vendors.*,
            events.name AS event_name
        FROM vendors

        LEFT JOIN events
        ON vendors.event_id = events.id

        ORDER BY vendors.id DESC
    """).fetchall()

    connection.close()

    return render_template(
        "vendors.html",
        vendors=vendors_list
    )

@app.route("/resources")
def resources():
    connection = get_db_connection()

    resources = connection.execute("""
        SELECT *
        FROM resources
        ORDER BY id DESC
    """).fetchall()

    connection.close()

    return render_template(
        "resources.html",
        resources=resources
    )

@app.route("/add-resource", methods=["GET", "POST"])
def add_resource():

    if request.method == "POST":

        name = request.form["name"].strip()

        try:
            quantity = int(request.form["quantity"])
        except ValueError:
            flash("Quantity must be a valid number.", "error")
            return redirect(url_for("add_resource"))

        if not name:
            flash("Resource name is required.", "error")
            return redirect(url_for("add_resource"))

        if quantity <= 0:
            flash("Quantity must be greater than zero.", "error")
            return redirect(url_for("add_resource"))

        connection = get_db_connection()

        connection.execute("""
            INSERT INTO resources
            (name, quantity, available_quantity, status)
            VALUES (?, ?, ?, ?)
        """, (
            name,
            quantity,
            quantity,
            "Available"
        ))

        connection.commit()
        connection.close()

        flash("Resource added successfully!", "success")

        return redirect(url_for("resources"))

    return render_template("add_resource.html")


@app.route("/allocate-resource/<int:resource_id>", methods=["GET", "POST"])
def allocate_resource(resource_id):

    connection = get_db_connection()

    resource = connection.execute("""
        SELECT *
        FROM resources
        WHERE id = ?
    """, (resource_id,)).fetchone()

    if resource is None:
        connection.close()
        flash("Resource not found.", "error")
        return redirect(url_for("resources"))

    events = connection.execute("""
        SELECT *
        FROM events
        ORDER BY date ASC, start_time ASC
    """).fetchall()

    if request.method == "POST":

        event_id = request.form.get("event_id")

        try:
            quantity = int(request.form.get("quantity"))
        except (ValueError, TypeError):
            connection.close()
            flash("Quantity must be a valid number.", "error")
            return redirect(
                url_for("allocate_resource", resource_id=resource_id)
            )

        if not event_id:
            connection.close()
            flash("Please select an event.", "error")
            return redirect(
                url_for("allocate_resource", resource_id=resource_id)
            )

        if quantity <= 0:
            connection.close()
            flash("Quantity must be greater than zero.", "error")
            return redirect(
                url_for("allocate_resource", resource_id=resource_id)
            )

        if quantity > resource["quantity"]:
            connection.close()
            flash(
                "Requested quantity is greater than available resource quantity.",
                "error"
            )
            return redirect(
                url_for("allocate_resource", resource_id=resource_id)
            )

        event = connection.execute("""
            SELECT *
            FROM events
            WHERE id = ?
        """, (event_id,)).fetchone()

        if event is None:
            connection.close()
            flash("Event not found.", "error")
            return redirect(
                url_for("allocate_resource", resource_id=resource_id)
            )

        # Check resource usage during overlapping events
        overlapping = connection.execute("""
            SELECT COALESCE(SUM(ra.quantity), 0) AS allocated_quantity
            FROM resource_allocations ra
            JOIN events e
                ON ra.event_id = e.id
            WHERE ra.resource_id = ?
              AND e.date = ?
              AND e.start_time < ?
              AND e.end_time > ?
        """, (
            resource_id,
            event["date"],
            event["end_time"],
            event["start_time"]
        )).fetchone()

        already_allocated = overlapping["allocated_quantity"]

        if already_allocated + quantity > resource["quantity"]:
            connection.close()

            flash(
                "Resource is not available in the requested quantity "
                "for this event time.",
                "error"
            )

            return redirect(
                url_for("allocate_resource", resource_id=resource_id)
            )

        connection.execute("""
            INSERT INTO resource_allocations
            (resource_id, event_id, quantity)
            VALUES (?, ?, ?)
        """, (
            resource_id,
            event_id,
            quantity
        ))

        # Update available quantity
        new_available_quantity = resource["available_quantity"] - quantity

        if new_available_quantity <= 0:
            new_status = "Unavailable"
        else:
            new_status = "Available"

        connection.execute("""
            UPDATE resources
            SET available_quantity = ?,
                status = ?
            WHERE id = ?
        """, (
            new_available_quantity,
            new_status,
            resource_id
        ))

        connection.commit()
        connection.close()

        flash(
            "Resource allocated to the event successfully!",
            "success"
        )

        return redirect(url_for("resources"))

    connection.close()

    return render_template(
        "allocate_resource.html",
        resource=resource,
        events=events
    )


# --------------------------------------------------
# ADD EXPENSE
# --------------------------------------------------

@app.route("/add-expense", methods=["GET", "POST"])
def add_expense():

    connection = get_db_connection()

    if request.method == "POST":

        event_id = request.form.get(
            "event_id", ""
        ).strip()

        category = request.form.get(
            "category", ""
        ).strip()

        description = request.form.get(
            "description", ""
        ).strip()

        amount = request.form.get(
            "amount", ""
        ).strip()

        # Validate event
        if not event_id:
            connection.close()
            flash(
                "Please select an event.",
                "error"
            )
            return redirect(url_for("add_expense"))

        # Validate category
        if not category:
            connection.close()
            flash(
                "Please select an expense category.",
                "error"
            )
            return redirect(url_for("add_expense"))

        # Validate amount
        try:
            amount = float(amount)
        except (ValueError, TypeError):
            connection.close()
            flash(
                "Expense amount must be a valid number.",
                "error"
            )
            return redirect(url_for("add_expense"))

        if amount <= 0:
            connection.close()
            flash(
                "Expense amount must be greater than zero.",
                "error"
            )
            return redirect(url_for("add_expense"))

        # Check event exists
        event = connection.execute("""
            SELECT *
            FROM events
            WHERE id = ?
        """, (event_id,)).fetchone()

        if event is None:
            connection.close()
            flash(
                "Event not found.",
                "error"
            )
            return redirect(url_for("add_expense"))

        # Insert expense
        connection.execute("""
            INSERT INTO expenses
            (
                event_id,
                category,
                description,
                amount
            )
            VALUES (?, ?, ?, ?)
        """, (
            event_id,
            category,
            description,
            amount
        ))

        connection.commit()
        connection.close()

        flash(
            "Expense added successfully!",
            "success"
        )

        return redirect(url_for("budget"))

    # Get events for dropdown
    events = connection.execute("""
        SELECT *
        FROM events
        ORDER BY date ASC, start_time ASC
    """).fetchall()

    connection.close()

    return render_template(
        "add_expense.html",
        events=events
    )

@app.route("/expenses")
def expenses():

    connection = get_db_connection()

    expenses_list = connection.execute("""
        SELECT
            expenses.*,
            events.name AS event_name
        FROM expenses
        LEFT JOIN events
            ON expenses.event_id = events.id
        ORDER BY expenses.id DESC
    """).fetchall()

    connection.close()

    return render_template(
        "expenses.html",
        expenses=expenses_list
    )
    


# --------------------------------------------------
# PARTICIPANT CHECK-IN
# --------------------------------------------------

@app.route("/checkin", methods=["GET", "POST"])
def checkin():

    if request.method == "POST":

        ticket_id = request.form["ticket_id"].strip()

        connection = get_db_connection()

        participant = connection.execute("""
            SELECT
                participants.*,
                events.name AS event_name,
                events.date AS event_date,
                events.start_time,
                events.end_time,
                events.venue
            FROM participants

            JOIN events
            ON participants.event_id = events.id

            WHERE participants.ticket_id = ?
        """, (ticket_id,)).fetchone()

        if participant is None:

            connection.close()

            flash(
                "Invalid ticket ID. Participant not found.",
                "error"
            )

            return redirect(url_for("checkin"))

        if participant["checked_in"] == 1:

            connection.close()

            flash(
                "This participant has already checked in.",
                "error"
            )

            return redirect(url_for("checkin"))

        from datetime import datetime

        check_in_time = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        connection.execute("""
            UPDATE participants
            SET
                checked_in = 1,
                check_in_time = ?
            WHERE ticket_id = ?
        """, (
            check_in_time,
            ticket_id
        ))

        connection.commit()
        connection.close()

        flash(
            "Participant checked in successfully!",
            "success"
        )

        return redirect(url_for("checkin"))

    return render_template("checkin.html")


# --------------------------------------------------
# DIRECT PARTICIPANT CHECK-IN
# --------------------------------------------------

@app.route("/checkin-participant/<int:participant_id>", methods=["POST"])
def checkin_participant(participant_id):

    connection = get_db_connection()

    participant = connection.execute("""
        SELECT *
        FROM participants
        WHERE id = ?
    """, (participant_id,)).fetchone()

    if participant is None:

        connection.close()

        flash(
            "Participant not found.",
            "error"
        )

        return redirect(url_for("registrations"))

    # Check if already checked in

    if participant["checked_in"] == 1:

        connection.close()

        flash(
            "This participant has already checked in.",
            "error"
        )

        return redirect(url_for("registrations"))

    # Get current time

    from datetime import datetime

    check_in_time = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    # Update participant

    connection.execute("""
        UPDATE participants
        SET
            checked_in = 1,
            check_in_time = ?
        WHERE id = ?
    """, (
        check_in_time,
        participant_id
    ))

    connection.commit()
    connection.close()

    flash(
        "Participant checked in successfully!",
        "success"
    )

    return redirect(url_for("registrations"))

# --------------------------------------------------
# ATTENDANCE
# --------------------------------------------------

@app.route("/attendance")
def attendance():

    connection = get_db_connection()

    participants = connection.execute("""
        SELECT
            participants.*,
            events.name AS event_name
        FROM participants
        LEFT JOIN events
        ON participants.event_id = events.id
        ORDER BY participants.id DESC
    """).fetchall()


    total_participants = connection.execute("""
        SELECT COUNT(*)
        FROM participants
    """).fetchone()[0]


    checked_in_count = connection.execute("""
        SELECT COUNT(*)
        FROM participants
        WHERE checked_in = 1
    """).fetchone()[0]


    not_checked_in_count = connection.execute("""
        SELECT COUNT(*)
        FROM participants
        WHERE checked_in = 0
    """).fetchone()[0]


    connection.close()


    return render_template(
        "attendance.html",
        participants=participants,
        total_participants=total_participants,
        checked_in_count=checked_in_count,
        not_checked_in_count=not_checked_in_count
    )


# --------------------------------------------------
# REPORTS
# --------------------------------------------------

@app.route("/reports")
def reports():

    connection = get_db_connection()


    # Total events

    total_events = connection.execute("""
        SELECT COUNT(*)
        FROM events
    """).fetchone()[0]


    # Total participants

    total_participants = connection.execute("""
        SELECT COUNT(*)
        FROM participants
    """).fetchone()[0]


    # Total checked-in participants

    checked_in_count = connection.execute("""
        SELECT COUNT(*)
        FROM participants
        WHERE checked_in = 1
    """).fetchone()[0]


    # Overall attendance percentage

    if total_participants > 0:

        attendance_percentage = round(
            (checked_in_count / total_participants) * 100,
            1
        )

    else:

        attendance_percentage = 0

    # -----------------------------------------------
    # VENUE UTILIZATION
    # -----------------------------------------------

    venue_usage = connection.execute("""
        SELECT
            venues.name AS venue_name,
            venues.capacity,
            COUNT(events.id) AS event_count
        FROM venues
        LEFT JOIN events
        ON venues.name = events.venue
        GROUP BY venues.id
        ORDER BY event_count DESC
    """).fetchall()


    # -----------------------------------------------
    # RESOURCE USAGE
    # -----------------------------------------------

    resource_usage = connection.execute("""
        SELECT
            resources.name AS resource_name,
            resources.quantity AS total_quantity,
            COALESCE(
                SUM(resource_allocations.quantity),
                0
            ) AS allocated_quantity
        FROM resources
        LEFT JOIN resource_allocations
        ON resources.id = resource_allocations.resource_id
        GROUP BY resources.id
        ORDER BY allocated_quantity DESC
    """).fetchall()


    # Event-wise report

    event_reports = connection.execute("""
        SELECT
            events.id,
            events.name,
            events.date,

            COUNT(participants.id)
                AS participant_count,

            SUM(
                CASE
                    WHEN participants.checked_in = 1
                    THEN 1
                    ELSE 0
                END
            ) AS checked_in_count

        FROM events

        LEFT JOIN participants
        ON events.id = participants.event_id

        GROUP BY
            events.id

        ORDER BY
            events.date ASC
    """).fetchall()


    connection.close()


    return render_template(
        "reports.html",
        total_events=total_events,
        total_participants=total_participants,
        checked_in_count=checked_in_count,
        attendance_percentage=attendance_percentage,
        event_reports=event_reports,
        venue_usage=venue_usage,
        resource_usage=resource_usage

    )

# --------------------------------------------------
# BUDGET MANAGEMENT
# --------------------------------------------------

@app.route("/budget")
def budget():

    connection = get_db_connection()

    # Total budget of all events
    total_budget = connection.execute("""
        SELECT COALESCE(SUM(budget), 0)
        FROM events
    """).fetchone()[0]

    # Total expenses
    total_expenses = connection.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM expenses
    """).fetchone()[0]

    # Remaining budget
    remaining_budget = total_budget - total_expenses

    # Budget utilization
    if total_budget > 0:
        budget_utilization = round(
            (total_expenses / total_budget) * 100,
            1
        )
    else:
        budget_utilization = 0

    # Event-wise budget report
    budget_reports = connection.execute("""
        SELECT
            events.id,
            events.name,
            events.budget,
            COALESCE(SUM(expenses.amount), 0) AS expenses
        FROM events
        LEFT JOIN expenses
        ON events.id = expenses.event_id
        GROUP BY events.id
        ORDER BY events.date ASC
    """).fetchall()

    connection.close()

    # Calculate remaining budget for each event
    budget_reports = [
        dict(event) | {
            "remaining": (event["budget"] or 0)
                         - (event["expenses"] or 0)
        }
        for event in budget_reports
    ]

    return render_template(
        "budget.html",
        total_budget=total_budget,
        total_expenses=total_expenses,
        remaining_budget=remaining_budget,
        budget_utilization=budget_utilization,
        budget_reports=budget_reports
    )

@app.route("/add-notification", methods=["GET", "POST"])
def add_notification():

    connection = get_db_connection()

    if request.method == "POST":

        event_id = request.form.get(
            "event_id", ""
        ).strip()

        notification_type = request.form.get(
            "notification_type", ""
        ).strip()

        message = request.form.get(
            "message", ""
        ).strip()

        if not event_id:
            connection.close()
            flash("Please select an event.", "error")
            return redirect(url_for("add_notification"))

        if not notification_type:
            connection.close()
            flash("Please select a notification type.", "error")
            return redirect(url_for("add_notification"))

        if not message:
            connection.close()
            flash("Please enter a notification message.", "error")
            return redirect(url_for("add_notification"))

        event = connection.execute("""
            SELECT *
            FROM events
            WHERE id = ?
        """, (event_id,)).fetchone()

        if event is None:
            connection.close()
            flash("Event not found.", "error")
            return redirect(url_for("add_notification"))

        connection.execute("""
            INSERT INTO notifications
            (
                event_id,
                notification_type,
                message
            )
            VALUES (?, ?, ?)
        """, (
            event_id,
            notification_type,
            message
        ))

        connection.commit()
        connection.close()

        flash(
            "Notification added successfully!",
            "success"
        )

        return redirect(url_for("notifications"))

    events = connection.execute("""
        SELECT *
        FROM events
        ORDER BY date ASC, start_time ASC
    """).fetchall()

    connection.close()

    return render_template(
        "add_notification.html",
        events=events
    )


@app.route("/notifications")
def notifications():

    connection = get_db_connection()

    notifications_list = connection.execute("""
        SELECT
            notifications.*,
            events.name AS event_name
        FROM notifications
        LEFT JOIN events
            ON notifications.event_id = events.id
        ORDER BY notifications.id DESC
    """).fetchall()

    connection.close()

    return render_template(
        "notifications.html",
        notifications=notifications_list
    )
# --------------------------------------------------
# VENUE MANAGEMENT
# --------------------------------------------------

@app.route("/venues")
def venues():

    connection = get_db_connection()

    venues_list = connection.execute("""
        SELECT *
        FROM venues
        ORDER BY name ASC
    """).fetchall()

    connection.close()

    return render_template(
        "venues.html",
        venues=venues_list
    )


# --------------------------------------------------
# ADD VENUE
# --------------------------------------------------

@app.route("/add-venue", methods=["GET", "POST"])
def add_venue():

    if request.method == "POST":

        name = request.form.get(
            "name", ""
        ).strip()

        location = request.form.get(
            "location", ""
        ).strip()

        capacity = request.form.get(
            "capacity", ""
        ).strip()


        # Validate venue name

        if not name:

            flash(
                "Venue name is required.",
                "error"
            )

            return redirect(
                url_for("add_venue")
            )


        # Validate capacity

        if capacity:

            try:

                capacity = int(capacity)

                if capacity <= 0:

                    flash(
                        "Capacity must be greater than 0.",
                        "error"
                    )

                    return redirect(
                        url_for("add_venue")
                    )

            except ValueError:

                flash(
                    "Capacity must be a number.",
                    "error"
                )

                return redirect(
                    url_for("add_venue")
                )

        else:

            capacity = None

        # -----------------------------------------
        # CHECK VENUE CONFLICT
        # -----------------------------------------

        if venue:

            connection = get_db_connection()

            conflict = connection.execute("""
                SELECT *
                FROM events
                WHERE venue = ?
                AND date = ?
                AND start_time < ?
                AND end_time > ?
            """, (
                venue,
                date,
                end_time,
                start_time
            )).fetchone()

            connection.close()


            if conflict:

                flash(
                    f"Venue conflict! {venue} is already "
                    f"booked from {conflict['start_time']} "
                    f"to {conflict['end_time']}.",
                    "error"
                )

                return redirect(
                    url_for("create_event")
                )


        # Save venue

        connection = get_db_connection()

        connection.execute("""
            INSERT INTO venues
            (name, location, capacity)
            VALUES (?, ?, ?)
        """, (
            name,
            location,
            capacity
        ))

        connection.commit()

        connection.close()


        flash(
            "Venue added successfully!",
            "success"
        )

        return redirect(
            url_for("venues")
        )


    return render_template(
        "add_venue.html"
    )


# --------------------------------------------------
# DELETE VENUE
# --------------------------------------------------

@app.route("/delete-venue/<int:venue_id>")
def delete_venue(venue_id):

    connection = get_db_connection()

    # Get venue

    venue = connection.execute("""
        SELECT *
        FROM venues
        WHERE id = ?
    """, (venue_id,)).fetchone()


    if venue is None:

        connection.close()

        flash(
            "Venue not found.",
            "error"
        )

        return redirect(
            url_for("venues")
        )


    # Check whether venue is being used

    events_using_venue = connection.execute("""
        SELECT COUNT(*)
        FROM events
        WHERE venue = ?
    """, (venue["name"],)).fetchone()[0]


    if events_using_venue > 0:

        connection.close()

        flash(
            "Cannot delete this venue because it is assigned to an event.",
            "error"
        )

        return redirect(
            url_for("venues")
        )


    connection.execute("""
        DELETE FROM venues
        WHERE id = ?
    """, (venue_id,))


    connection.commit()

    connection.close()


    flash(
        "Venue deleted successfully!",
        "success"
    )

    return redirect(
        url_for("venues")
    )

# --------------------------------------------------
# VIEW ALL REGISTRATIONS
# --------------------------------------------------

@app.route("/registrations")
def registrations():

    connection = get_db_connection()

    participants = connection.execute("""
        SELECT
            participants.*,
            events.name AS event_name
        FROM participants

        LEFT JOIN events
        ON participants.event_id = events.id

        ORDER BY participants.id DESC
    """).fetchall()

    connection.close()

    return render_template(
        "registrations.html",
        participants=participants
    )

# --------------------------------------------------
# PARTICIPANT REGISTRATION
# --------------------------------------------------

@app.route("/register", methods=["GET", "POST"])
def register():

    connection = get_db_connection()

    # Get all events
    events_list = connection.execute("""
        SELECT *
        FROM events
        ORDER BY date ASC
    """).fetchall()

    connection.close()


    # -----------------------------------------
    # DISPLAY REGISTRATION FORM
    # -----------------------------------------

    if request.method == "GET":

        return render_template(
            "register.html",
            events=events_list
        )


    # -----------------------------------------
    # GET FORM DATA
    # -----------------------------------------

    event_id = request.form.get(
        "event_id", ""
    ).strip()

    name = request.form.get(
        "name", ""
    ).strip()

    email = request.form.get(
        "email", ""
    ).strip()

    phone = request.form.get(
        "phone", ""
    ).strip()


    # -----------------------------------------
    # VALIDATE EVENT
    # -----------------------------------------

    if not event_id:

        flash(
            "Please select an event.",
            "error"
        )

        return redirect(
            url_for("register")
        )


    # -----------------------------------------
    # VALIDATE NAME
    # -----------------------------------------

    if not name:

        flash(
            "Participant name is required.",
            "error"
        )

        return redirect(
            url_for("register")
        )


    # -----------------------------------------
    # VALIDATE EMAIL
    # -----------------------------------------

    if not email:

        flash(
            "Email address is required.",
            "error"
        )

        return redirect(
            url_for("register")
        )


    # -----------------------------------------
    # CHECK EVENT
    # -----------------------------------------

    connection = get_db_connection()

    event = connection.execute("""
        SELECT *
        FROM events
        WHERE id = ?
    """, (event_id,)).fetchone()


    if event is None:

        connection.close()

        flash(
            "Selected event does not exist.",
            "error"
        )

        return redirect(
            url_for("register")
        )


    # -----------------------------------------
    # CHECK CURRENT PARTICIPANTS
    # -----------------------------------------

    participant_count = connection.execute("""
        SELECT COUNT(*)
        FROM participants
        WHERE event_id = ?
    """, (event_id,)).fetchone()[0]


    # -----------------------------------------
    # CHECK MAXIMUM CAPACITY
    # -----------------------------------------

    if (
        event["max_participants"] is not None
        and
        participant_count >= event["max_participants"]
    ):

        connection.close()

        flash(
            "Registration is full for this event.",
            "error"
        )

        return redirect(
            url_for("register")
        )


    # -----------------------------------------
    # CHECK DUPLICATE EMAIL
    # -----------------------------------------

    existing_participant = connection.execute("""
        SELECT *
        FROM participants
        WHERE event_id = ?
        AND email = ?
    """, (
        event_id,
        email
    )).fetchone()


    if existing_participant:

        connection.close()

        flash(
            "This email is already registered for this event.",
            "error"
        )

        return redirect(
            url_for("register")
        )

    # -----------------------------------------
    # GENERATE TICKET ID
    # -----------------------------------------

    ticket_id = "ES-" + uuid.uuid4().hex[:8].upper()


    # -----------------------------------------
    # GENERATE QR CODE
    # -----------------------------------------

    qr_data = f"EventSphere Ticket: {ticket_id}"

    qr = qrcode.make(qr_data)


    qr_folder = os.path.join(
        app.static_folder,
        "qrcodes"
    )

    os.makedirs(
        qr_folder,
        exist_ok=True
    )


    qr_filename = f"{ticket_id}.png"

    qr_path = os.path.join(
        qr_folder,
        qr_filename
    )

    qr.save(qr_path)


    # Check for duplicate registration
    existing_participant = connection.execute("""
        SELECT id
        FROM participants
        WHERE event_id = ?
            AND (
                LOWER(email) = LOWER(?)
                OR phone = ?
            )
    """, (
        event_id,
        email,
        phone
    )).fetchone()

    if existing_participant:
        connection.close()

        flash(
            "This participant is already registered for this event.",
            "error"
        )

        return redirect(
            url_for("register")
        )


    # -----------------------------------------
    # SAVE PARTICIPANT + TICKET
    # -----------------------------------------

    connection.execute("""
        INSERT INTO participants
        (
            event_id,
            name,
            email,
            phone,
            ticket_id,
            qr_code
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        event_id,
        name,
        email,
        phone,
        ticket_id,
        qr_filename
    ))

    # Automatic registration notification
    notification_message = (
        f"Registration successful for {event['name']}. "
        f"Your ticket ID is {ticket_id}."
    )

    connection.execute("""
        INSERT INTO notifications
        (
            event_id,
            notification_type,
            message
        )
        VALUES (?, ?, ?)
    """, (
        event_id,
        "Registration Confirmation",
        notification_message
    ))

    # Record automation activity
    connection.execute("""
        INSERT INTO automation_logs
        (
            event_id,
            automation_type,
            message,
            status
        )
        VALUES (?, ?, ?, ?)
    """, (
        event_id,
        "Registration Confirmation",
        notification_message,
        "Completed"
    ))


    connection.commit()

    connection.close()


    flash(
        "Participant registered successfully!",
        "success"
    )


    return redirect(
        url_for(
            "ticket",
            ticket_id=ticket_id
        )
    )


    connection.commit()

    connection.close()


    # --------------------------------------------------
# DIGITAL TICKET
# --------------------------------------------------

@app.route("/ticket/<ticket_id>")
def ticket(ticket_id):

    connection = get_db_connection()

    participant = connection.execute("""
        SELECT
            participants.*,
            events.name AS event_name,
            events.description AS event_description,
            events.date AS event_date,
            events.start_time,
            events.end_time,
            events.venue
        FROM participants

        JOIN events
        ON participants.event_id = events.id

        WHERE participants.ticket_id = ?
    """, (ticket_id,)).fetchone()

    connection.close()


    if participant is None:

        flash(
            "Ticket not found.",
            "error"
        )

        return redirect(
            url_for("register")
        )


    return render_template(
        "ticket.html",
        participant=participant
    )


    # -----------------------------------------
    # SUCCESS
    # -----------------------------------------

    flash(
        "Participant registered successfully!",
        "success"
    )


    return redirect(
        url_for(
            "registration_success"
        )
    )

# --------------------------------------------------
# REGISTRATION SUCCESS
# --------------------------------------------------

@app.route("/registration-success")
def registration_success():

    return render_template(
        "registration_success.html"
    )

# --------------------------------------------------
# FIND DIGITAL TICKET
# --------------------------------------------------

@app.route("/find-ticket", methods=["GET", "POST"])
def find_ticket():

    if request.method == "POST":

        email = request.form["email"]

        connection = get_db_connection()

        participant = connection.execute("""
            SELECT *
            FROM participants
            WHERE email = ?
            ORDER BY id DESC
            LIMIT 1
        """, (email,)).fetchone()

        connection.close()

        if participant:

            return render_template(
                "ticket.html",
                participant=participant
            )

        flash(
            "No ticket found for this email.",
            "error"
        )

    return render_template("find_ticket.html")

@app.route("/generate-reminders")
def generate_reminders():

    from datetime import datetime, timedelta

    connection = get_db_connection()

    today = datetime.now().date()
    reminder_date = today + timedelta(days=1)

    events = connection.execute("""
        SELECT *
        FROM events
        WHERE date = ?
    """, (reminder_date.strftime("%Y-%m-%d"),)).fetchall()

    reminder_count = 0

    for event in events:

        message = (
            f"Reminder: {event['name']} is scheduled for tomorrow "
            f"at {event['start_time']} at {event['venue']}."
        )

        # Prevent duplicate reminders
        existing = connection.execute("""
            SELECT id
            FROM notifications
            WHERE event_id = ?
              AND notification_type = ?
              AND message = ?
        """, (
            event["id"],
            "Event Reminder",
            message
        )).fetchone()

        if existing:
            continue

        # Create notification
        connection.execute("""
            INSERT INTO notifications
            (
                event_id,
                notification_type,
                message
            )
            VALUES (?, ?, ?)
        """, (
            event["id"],
            "Event Reminder",
            message
        ))

        # Record automation
        connection.execute("""
            INSERT INTO automation_logs
            (
                event_id,
                automation_type,
                message,
                status
            )
            VALUES (?, ?, ?, ?)
        """, (
            event["id"],
            "Event Reminder",
            message,
            "Completed"
        ))

        reminder_count += 1

    connection.commit()
    connection.close()

    flash(
        f"{reminder_count} event reminder(s) generated.",
        "success"
    )

    return redirect(url_for("notifications"))

# --------------------------------------------------
# UPDATE DATABASE
# --------------------------------------------------

def update_database():

    connection = get_db_connection()

    columns = connection.execute("""
        PRAGMA table_info(participants)
    """).fetchall()

    column_names = [
        column["name"]
        for column in columns
    ]

    if "ticket_id" not in column_names:
        connection.execute("""
            ALTER TABLE participants
            ADD COLUMN ticket_id TEXT
        """)

    if "qr_code" not in column_names:
        connection.execute("""
            ALTER TABLE participants
            ADD COLUMN qr_code TEXT
        """)

        # --------------------------------------------------
    # ATTENDANCE COLUMNS
    # --------------------------------------------------

    participant_columns = connection.execute("""
        PRAGMA table_info(participants)
    """).fetchall()

    participant_column_names = [
        column["name"]
        for column in participant_columns
    ]

    if "checked_in" not in participant_column_names:

        connection.execute("""
            ALTER TABLE participants
            ADD COLUMN checked_in INTEGER DEFAULT 0
        """)

    if "check_in_time" not in participant_column_names:

        connection.execute("""
            ALTER TABLE participants
            ADD COLUMN check_in_time TEXT
        """)

    # VENDORS TABLE
    vendor_columns = connection.execute("""
        PRAGMA table_info(vendors)
    """).fetchall()

    vendor_column_names = [
        column["name"]
        for column in vendor_columns
    ]

    if "event_id" not in vendor_column_names:

        connection.execute("""
            ALTER TABLE vendors
            ADD COLUMN event_id INTEGER
        """)

        # Add budget column to events table if it does not exist
    try:
        connection.execute("""
            ALTER TABLE events
            ADD COLUMN budget REAL DEFAULT 0
        """)
    except sqlite3.OperationalError:
        pass

    connection.commit()
    connection.close()


# --------------------------------------------------
# APPLICATION START
# --------------------------------------------------

if __name__ == "__main__":

    # Create database and tables
    init_db()

    print("======================================")
    print("       EventSphere is starting...")
    print("======================================")
    update_database()

    app.run(debug=True)